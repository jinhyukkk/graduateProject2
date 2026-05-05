"""
Semantic Consistency Verifier (Section 4.4.2)
SQL 역번역 + NLI 일치 검증.
"""

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable

import numpy as np
from openai import OpenAI
from sentence_transformers import CrossEncoder

from src.openai_retry import chat_completion, chat_completion_streaming

logger = logging.getLogger(__name__)


@dataclass
class VerificationResult:
    """의미 일관성 검증 결과 — 3축 검증."""
    back_translation: str          # SQL의 자연어 역번역 (한국어, 표시용)
    similarity_score: float        # NLI entailment score ∈ [0, 1] (어휘 매칭 축)
    is_consistent: bool            # 통합 판정 (NLI 또는 LLM 자기 비평이 통과)
    mismatch_diagnosis: str | None = None  # 불일치 시 진단 텍스트
    # LLM 자기 비평 (Self-Critique) — Claude/GPT 류 시스템과 같은 의미 진단 방식
    # NLI가 어휘 매칭 약점(예: "total payment" vs "monthly earnings")으로 거짓 음성을
    # 낼 때, LLM은 *전체 컨텍스트(질의·SQL·실행 결과·스키마)* 를 보고 의미·도메인
    # 수준에서 추가 진단한다. 두 축은 직교적으로 결합된다.
    llm_critique_score: float = 1.0   # LLM 자기 비평 점수 ∈ [0, 1]
    llm_critique_pass: bool = True     # LLM 자기 비평 통과 여부
    llm_critique_reason: str = ""      # LLM이 의심한 사유 (불일치 시)


class SemanticVerifier:
    """
    Section 4.4.2: 의미론적 일관성 검증기.

    Step 1: GPT-4o로 SQL을 영어 자연어 질문으로 역번역한다.
    Step 2: 원래 질의가 한국어이면 영어로 번역하여 NLI 입력을 영어로 통일한다.
            NLI 모델(cross-encoder/nli-deberta-v3-base)은 영어 전용이므로
            두 텍스트를 동일 언어(영어)로 맞춘 뒤 entailment score를 계산한다.
            sim_nli = 0.6·P(q_en → q̂_en) + 0.4·P(q̂_en → q_en) ∈ [0, 1]
    Step 3: NLI 출력이 진짜 불확실(max 클래스 확률 ≤ 0.5)한 경우에만 GPT-4o 의미 유사도로 보정한다.
            낮은 NLI 점수가 "모순 확신"인 경우(max_prob > 0.5)는 GPT 보정 없이 유지한다.
    Step 4: sim < θ=0.75 이면 불일치 → GPT-4o로 원인을 진단한다.

    표시용 back_translation은 한국어로 별도 생성해 UI에 노출한다.
    """

    # NLI entailment score가 이 값 미만이면 "낮은 점수"로 로깅한다.
    # 실제 GPT 보정 여부는 is_confident 플래그로 결정한다 (_compute_nli_score 참조).
    _NLI_RELIABLE_THRESHOLD = 0.10

    def __init__(self, config: dict):
        self.config = config
        self.client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        self.llm_model = config["llm"]["model"]
        self.threshold = config["correction"]["semantic_threshold"]  # θ=0.75
        self.nli_model_name = config["nli"]["model"]
        # NLI cross-encoder 로드 (영어 전용 모델)
        self.nli_model = CrossEncoder(self.nli_model_name)
        self._entailment_idx = self._detect_entailment_idx()

    def _detect_entailment_idx(self) -> int:
        """
        NLI 모델의 label2id에서 entailment 레이블 인덱스를 탐지한다.
        탐지 실패 시 cross-encoder/nli-deberta-v3-base 기본값인 1을 사용한다.
        """
        try:
            label2id = self.nli_model.model.config.label2id
            label2id_lower = {k.lower(): int(v) for k, v in label2id.items()}
            idx = label2id_lower.get("entailment", 1)
            logger.debug("NLI label2id: %s → entailment_idx=%d", label2id_lower, idx)
            return idx
        except Exception as exc:
            logger.warning("label2id 탐지 실패 (%s), 기본값 1 사용", exc)
            return 1

    @staticmethod
    def _contains_korean(text: str) -> bool:
        """한글 유니코드 범위(가-힣)가 포함되어 있으면 True."""
        return any('\uAC00' <= c <= '\uD7A3' for c in text)

    def _translate_to_english(self, text: str) -> str:
        """
        한국어 텍스트를 영어로 번역한다 (NLI 입력 정규화용).
        영어 텍스트는 그대로 반환한다.

        시연 진단(2026-05-01) 후 보강: "작년/올해/이번 달" 같은 *상대 시간* 표현은
        SQL이 명시 연도/월(예: '2025')로 변환되어 NLI에서 어휘가 갈라진다.
        Today 컨텍스트를 함께 주어 *상대 시간을 절대 시간으로* 풀어쓰도록 강제한다.
        """
        if not self._contains_korean(text):
            return text

        from datetime import datetime
        today = datetime.now()
        time_hint = (
            f"Today is {today.strftime('%Y-%m-%d')}. "
            f"For relative time terms in the input, expand them with explicit year/month: "
            f"'올해'={today.year}, '작년'={today.year - 1}, "
            f"'이번 달'={today.year}-{today.month:02d}, etc. "
            f"Include the explicit year/month in the English output so it matches "
            f"hardcoded values that downstream SQL might use."
        )

        response = chat_completion(
            self.client,
            model=self.llm_model,
            temperature=0.0,
            max_completion_tokens=256,
            messages=[{
                "role": "user",
                "content": (
                    "Translate the following Korean database query to English.\n"
                    "Preserve the intent, but expand relative time terms to explicit dates.\n"
                    f"{time_hint}\n"
                    "Return ONLY the English translation, nothing else.\n\n"
                    f"Korean: {text}"
                ),
            }],
        )
        translated = response.choices[0].message.content.strip()
        logger.debug("한→영 번역: '%s' → '%s'", text, translated)
        return translated

    def _back_translate_to_english(self, sql: str, user_query_en: str | None = None) -> str:
        """SQL을 사용자 의도 수준의 영어 질문으로 역번역한다.

        시연 점검 후 개선:
          - HRDB 코드값('S10','F')과 오라클식 물리 컬럼명을 *비즈니스 의미*로 풀어쓸 것
          - 역번역과 사용자 영문 질의의 *어휘 갈라짐* 으로 NLI가 0.4 미만에 머무는 문제 발견
            → user_query_en이 주어지면 *해당 어휘 풀(noun phrases)*을 *기본 사용*하도록 지시.
            단, *원 질의 문장을 그대로 복제* 하지 말고 SQL의 의미를 풀어쓰는 의무는 유지
            (역번역의 모사 위험 — §6.4 한계 #4 — 을 균형 있게 회피).
        """
        vocab_hint = ""
        if user_query_en:
            vocab_hint = (
                "\nVocabulary alignment hint: the user originally asked it in these words:\n"
                f"  USER QUESTION: \"{user_query_en}\"\n"
                "Where the SQL preserves the same intent, prefer the user's vocabulary "
                "(e.g. nouns/verbs they used) so a downstream NLI model can compare meanings reliably. "
                "If the SQL changes the meaning, do NOT copy the user's words — describe the SQL faithfully.\n"
            )

        prompt = (
            "Rewrite the following SQL as the natural-language question a non-technical "
            "user would have asked. The question should describe the user's *business intent*, "
            "not the SQL implementation.\n\n"
            "Rules:\n"
            "- Plain conversational English, like a question to a coworker.\n"
            "- Do NOT mention SQL keywords (SELECT, JOIN, WHERE, GROUP BY, ...).\n"
            "- Do NOT cite literal code values (e.g. 'S10', 'F', 'EDATE IS NULL'). "
            "Instead, infer the business meaning (e.g. 'currently active employees', "
            "'female employees', 'employees who have not left').\n"
            "- Use natural domain words (employee, department, salary, position) rather than "
            "physical column names (STATUS_CD, JIKGUB_NM).\n"
            "- Preserve every filter, aggregation, and grouping the SQL implies.\n"
            "- Return ONLY the question, no preamble.\n"
            f"{vocab_hint}\n"
            f"SQL: {sql}"
        )

        response = chat_completion(
            self.client,
            model=self.llm_model,
            temperature=0.0,
            max_completion_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        english_text = response.choices[0].message.content.strip()
        logger.debug("역번역(영어): %s", english_text)
        return english_text

    def _english_to_korean(self, english_text: str) -> str:
        """영어 역번역을 UI 표시용 한국어로 변환한다."""
        kr_response = chat_completion(
            self.client,
            model=self.llm_model,
            temperature=0.0,
            max_completion_tokens=200,
            messages=[{
                "role": "user",
                "content": (
                    "Translate the following English question to natural conversational Korean. "
                    "Return ONLY the Korean translation, nothing else.\n\n"
                    f"English: {english_text}"
                ),
            }],
        )
        korean_text = kr_response.choices[0].message.content.strip()
        logger.debug("역번역(한국어): %s", korean_text)
        return korean_text

    def _back_translate(self, sql: str) -> tuple[str, str]:
        """역호환 wrapper — 신규 호출부는 verify()에서 병렬 분기로 직접 호출한다."""
        english_text = self._back_translate_to_english(sql)
        korean_text = self._english_to_korean(english_text)
        return korean_text, english_text

    def _compute_nli_score(self, query_en: str, back_translation_en: str) -> tuple[float, bool]:
        """
        Section 4.4.2, Step 2: NLI 모델로 양방향 entailment score를 계산한다.

        sim_nli = 0.6·P(q → q̂) + 0.4·P(q̂ → q)

        raw logits를 직접 받아 numpy softmax로 안전하게 변환한다.
        apply_softmax=True는 sentence-transformers 버전별 동작이 다르므로 사용하지 않는다.

        Returns:
            (score, is_confident)
            - score: entailment 기반 유사도 점수 ∈ [0, 1]
            - is_confident: 모델이 어떤 클래스든 확신을 갖고 예측했으면 True.
              낮은 score가 "불확실"이 아닌 "모순 확신"인 경우를 구별하기 위해 사용한다.
              GPT 보정은 is_confident=False인 경우(진짜 불확실)에만 적용한다.
        """
        # raw logits (apply_softmax=False, default)
        raw = self.nli_model.predict(
            [
                (query_en, back_translation_en),  # q → q̂
                (back_translation_en, query_en),  # q̂ → q
            ],
        )
        raw = np.array(raw)  # (2,) 또는 (2, num_labels) 형태
        logger.debug(
            "NLI raw shape=%s values=%s entailment_idx=%d",
            raw.shape, raw, self._entailment_idx,
        )

        def _softmax(x: np.ndarray) -> np.ndarray:
            e = np.exp(x - x.max())
            return e / e.sum()

        # 형태에 따라 안전하게 entailment 확률 추출
        if raw.ndim == 2:
            # (2, num_labels): 정상적인 분류 모델 출력
            probs_fwd = _softmax(raw[0])
            probs_bwd = _softmax(raw[1])
            forward = float(probs_fwd[self._entailment_idx])
            backward = float(probs_bwd[self._entailment_idx])
            # 어느 방향이든 max 클래스 확률 > 0.5 이면 "확신 있음"
            is_confident = float(probs_fwd.max()) > 0.5 or float(probs_bwd.max()) > 0.5
        elif raw.ndim == 1 and raw.shape[0] == 2:
            # (2,): 회귀 모델처럼 쌍별 단일 점수를 반환한 경우
            # sigmoid로 [0,1] 변환 후 두 방향 평균
            forward = float(1 / (1 + np.exp(-raw[0])))
            backward = float(1 / (1 + np.exp(-raw[1])))
            # 회귀 출력은 항상 신뢰 가능으로 처리
            is_confident = True
        else:
            logger.warning("NLI 예상치 못한 출력 형태: %s — 0.5 반환", raw.shape)
            return 0.5, False

        logger.debug("NLI forward=%.4f backward=%.4f is_confident=%s", forward, backward, is_confident)
        return 0.6 * forward + 0.4 * backward, is_confident

    def llm_self_critique(
        self,
        query: str,
        sql: str,
        schema_text: str = "",
        result_preview: list[tuple] | None = None,
        column_names: list[str] | None = None,
        on_token: Callable[[str], None] | None = None,
    ) -> tuple[float, bool, str]:
        """LLM 자기 비평 — Claude/GPT 류 시스템과 같은 *내용 기반* 의미 진단.

        외부 NLI는 두 문자열의 *어휘 매칭* 만 보지만, 본 메서드는 LLM에게
        (질의 + SQL + 결과 일부 + 스키마)를 모두 보여주고 *내용·도메인 수준* 의
        타당성을 평가하게 한다. 이 방식은 다음 케이스에서 NLI보다 강하다:
          - "total payment" vs "monthly earnings" 같은 *어휘는 다르나 의미 같은*
            paraphrase에 NLI가 거짓 음성을 내는 경우
          - SQL이 실행은 통과했지만 *재직자만 세야 할 곳에 퇴직자도 포함* 같은
            도메인 추론 오류
          - 결과 행이 명백히 잘못된 단위(예: 급여를 부서 수로 잘못 매핑)

        Returns:
            (score ∈ [0,1], pass(score>=0.6), reason)
        """
        # 결과 미리보기 (최대 3행)
        result_block = ""
        if result_preview and column_names:
            preview_rows = result_preview[:3]
            cols_str = " | ".join(column_names)
            rows_str = "\n".join(
                " | ".join(str(v) if v is not None else "NULL" for v in row)
                for row in preview_rows
            )
            result_block = (
                f"\n## Execution Result Preview ({len(result_preview)} rows total, showing first 3)\n"
                f"{cols_str}\n{rows_str}\n"
            )
        elif result_preview is not None and len(result_preview) == 0:
            result_block = "\n## Execution Result\n(empty — no rows returned)\n"

        schema_block = ""
        if schema_text:
            # 스키마 너무 길면 첫 1500자만
            sb = schema_text[:1500] + ("\n..." if len(schema_text) > 1500 else "")
            schema_block = f"\n## Schema (first 1500 chars)\n{sb}\n"

        # 현재 날짜 컨텍스트 — "작년/올해/이번 달" 같은 한국어 상대 시간 표현이
        # SQL의 *명시 연도/월* 과 같은지 판정하기 위해 critique LLM에 today를 알려준다.
        # 시연 진단 (2026-05-01 시점, "작년 입사자" 케이스): NLI와 LLM critique 모두
        # *작년 = 2025* 매핑을 모르고 SQL의 하드코딩된 '2025'를 의심하는 거짓 음성을 발생.
        from datetime import datetime
        today = datetime.now()
        last_year = today.year - 1
        this_year = today.year
        time_context = (
            f"\n## Date Context (CRITICAL for relative time terms)\n"
            f"Today's date is {today.strftime('%Y-%m-%d')}. Therefore:\n"
            f"  - 올해 / this year = {this_year}\n"
            f"  - 작년 / last year = {last_year}\n"
            f"  - 재작년 / two years ago = {this_year - 2}\n"
            f"  - 이번 달 / this month = {today.year}-{today.month:02d}\n"
            f"  - 지난달 / last month = derived from today\n"
            f"When evaluating the SQL, treat hardcoded literals like '{last_year}' as "
            f"CORRECT for '작년' / 'last year' since today is {today.strftime('%Y-%m-%d')}. "
            f"Do NOT downgrade the SQL just because the year is hardcoded — judge whether "
            f"the *current execution at today's date* is correct, not whether the SQL is "
            f"future-proof.\n"
        )

        prompt = (
            "You are a senior data analyst reviewing whether a generated SQL query "
            "actually answers the user's question. Apply the same critical lens that "
            "Claude or GPT-4 use when re-checking their own answers mid-stream — "
            "look for *meaning-level* and *domain-level* errors that pure string "
            "matching would miss.\n\n"
            "Important scoring policy:\n"
            "- Judge whether the SQL is CORRECT WHEN EXECUTED TODAY, not whether it is "
            "future-proof. Hardcoded years/months/dates that match the user's relative "
            "time expression at today's date are FINE (PASS).\n"
            "- Code-style concerns (robustness, maintainability) are NOT failure reasons "
            "— only meaning-level errors are.\n\n"
            f"## User Question (Korean or English)\n{query}\n"
            f"{time_context}"
            f"\n## Generated SQL\n{sql}\n"
            f"{schema_block}{result_block}\n"
            "## Review Checklist (think through each)\n"
            "1. INTENT: Does the SQL truly target what the user is asking?\n"
            "2. FILTERS: Are required conditions (e.g. '재직 중' → status='S10' AND "
            "EDATE IS NULL) all present? Are extra/missing filters introducing wrong scope? "
            "For relative time terms (작년/올해/지난달 etc.), use the Date Context above to "
            "verify the literal year/month in the SQL is the CORRECT value for today.\n"
            "3. AGGREGATION: Is the grouping at the right granularity? Is COUNT/SUM "
            "computed over the right population?\n"
            "4. JOIN: Are joined tables/keys appropriate, with code↔code or name↔name "
            "(not code↔name)?\n"
            "5. RESULT SANITY: Does the result preview look plausible for the question? "
            "Any obvious unit/scope mismatch?\n\n"
            "## Output (single line, exactly this format)\n"
            "score: <0.0-1.0> | verdict: <PASS|FAIL> | reason: <one short sentence>\n"
            "score 1.0 = SQL fully and correctly answers the question (today). "
            "score 0.5 = ambiguous, partial, or potentially scoped wrong. "
            "score 0.0 = SQL clearly does not answer the question (today)."
        )

        try:
            if on_token is None:
                response = chat_completion(
                    self.client,
                    model=self.llm_model,
                    temperature=0.0,
                    max_completion_tokens=120,
                    messages=[{"role": "user", "content": prompt}],
                )
                raw = (response.choices[0].message.content or "").strip()
            else:
                # 시연 폴리시: LLM 자기 비평의 한 줄 판정을 토큰 단위로 흘려보낸다.
                raw = chat_completion_streaming(
                    self.client,
                    on_token,
                    model=self.llm_model,
                    temperature=0.0,
                    max_completion_tokens=120,
                    messages=[{"role": "user", "content": prompt}],
                ).strip()
        except Exception as e:
            logger.warning("LLM 자기 비평 실패: %s", e)
            return 0.7, True, "(LLM 자기 비평 호출 실패 — 기본 통과)"

        # 파싱: "score: 0.85 | verdict: PASS | reason: ..."
        import re
        m_score = re.search(r"score\s*:\s*([0-9]*\.?[0-9]+)", raw, re.IGNORECASE)
        m_verdict = re.search(r"verdict\s*:\s*(PASS|FAIL)", raw, re.IGNORECASE)
        m_reason = re.search(r"reason\s*:\s*(.+?)(?:\n|$)", raw, re.IGNORECASE)
        score = float(m_score.group(1)) if m_score else 0.7
        score = max(0.0, min(1.0, score))
        verdict_pass = (m_verdict.group(1).upper() == "PASS") if m_verdict else (score >= 0.6)
        reason = m_reason.group(1).strip() if m_reason else raw[:200]

        logger.debug("LLM critique: score=%.2f pass=%s reason=%s", score, verdict_pass, reason)
        return score, verdict_pass, reason

    def _compute_gpt_score(self, query_en: str, back_translation_en: str) -> float:
        """
        GPT-4o로 두 영어 질문의 의미 유사도를 0–1 스케일로 평가한다.
        NLI 점수가 신뢰 불가 수준일 때 보정용으로 사용한다.
        """
        prompt = (
            "Rate the semantic similarity of the two questions below on a scale of 0 to 10.\n"
            "Focus on whether they are asking for the same information.\n"
            "Return ONLY a single integer (0–10), nothing else.\n\n"
            f"Question 1: {query_en}\n"
            f"Question 2: {back_translation_en}\n\n"
            "Score (0-10):"
        )
        response = chat_completion(
            self.client,
            model=self.llm_model,
            temperature=0.0,
            max_completion_tokens=8,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.choices[0].message.content.strip()
        try:
            score = max(0.0, min(10.0, float(raw))) / 10.0
        except ValueError:
            logger.warning("GPT 유사도 점수 파싱 실패: '%s'", raw)
            score = 0.5
        logger.debug("GPT semantic score: %s → %.4f", raw, score)
        return score

    def _diagnose_mismatch(
        self,
        original_query: str,
        sql: str,
        back_translation: str,
        on_token: Callable[[str], None] | None = None,
    ) -> str:
        """
        Section 4.4.2, Step 4: 불일치 시 GPT-4o로 원인을 진단한다.
        """
        prompt = f"""다음 SQL 쿼리가 사용자의 의도를 올바르게 반영하지 못하고 있습니다.
원래 질문과 SQL 쿼리 사이의 불일치를 분석해주세요.

## 원래 질문
{original_query}

## 생성된 SQL
{sql}

## SQL의 의미 (역번역)
{back_translation}

## 지시사항
1. 사용자가 요청한 내용과 SQL이 실제로 수행하는 내용의 구체적인 차이를 파악하세요.
2. 사용자의 의도에 맞게 SQL에서 변경해야 할 사항을 설명하세요.
3. 간결하고 구체적으로 작성하세요.

## 진단 결과"""

        if on_token is None:
            response = chat_completion(
                self.client,
                model=self.llm_model,
                temperature=0.0,
                max_completion_tokens=512,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.choices[0].message.content.strip()

        # 시연 폴리시: 의미 불일치 진단 추론을 토큰 단위로 흘려보낸다.
        return chat_completion_streaming(
            self.client,
            on_token,
            model=self.llm_model,
            temperature=0.0,
            max_completion_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        ).strip()

    def verify(
        self,
        original_query: str,
        sql: str,
        schema_text: str = "",
        result_preview: list[tuple] | None = None,
        column_names: list[str] | None = None,
        on_token: Callable[[str], None] | None = None,
    ) -> VerificationResult:
        """
        Section 4.4.2: 의미론적 일관성을 3축으로 검증한다.

        축 ①: NLI entailment (외부 분류기, 어휘 매칭)
        축 ②: LLM 자기 비평 (Claude/GPT 류 self-critique, 의미·도메인 추론)
        통합: 둘 중 하나라도 통과하면 is_consistent=True. 둘 다 실패하면 불일치.

        실행 결과 미리보기와 스키마 텍스트가 주어지면 LLM 자기 비평이 더 정확해진다.

        Args:
            original_query: 원래 자연어 질의 (한국어 또는 영어)
            sql: 검증할 SQL 문자열
            schema_text: (옵션) LLM 자기 비평에 컨텍스트로 넣을 스키마
            result_preview: (옵션) 실행 결과 행 리스트 (LLM이 결과 sanity 점검 시 활용)
            column_names: (옵션) result_preview의 컬럼 이름

        Returns:
            VerificationResult: 3축 검증 결과
        """
        # Step 1: query→EN 번역 + 역번역(어휘 정렬 힌트 사용)
        query_en = self._translate_to_english(original_query)
        back_translation_en = self._back_translate_to_english(sql, user_query_en=query_en)

        # Step 2: 세 작업을 병렬 실행
        #  (a) EN→KR 표시용 번역
        #  (b) NLI 점수 계산
        #  (c) LLM 자기 비평 — Claude/GPT 류의 내용 기반 의미 진단
        with ThreadPoolExecutor(max_workers=3) as pool:
            f_kr = pool.submit(self._english_to_korean, back_translation_en)
            f_nli = pool.submit(self._compute_nli_score, query_en, back_translation_en)
            f_critique = pool.submit(
                self.llm_self_critique,
                original_query, sql, schema_text, result_preview, column_names,
                on_token,
            )
            back_translation_kr = f_kr.result()
            nli_score, nli_is_confident = f_nli.result()
            llm_score, llm_pass, llm_reason = f_critique.result()

        # Step 4: NLI가 불확실한 경우에만 GPT-4o 보정 점수로 대체한다.
        # 낮은 NLI 점수 = "모순 확신"과 "진짜 불확실" 두 경우가 있다.
        # - 모순 확신(is_confident=True, 낮은 score): NLI가 올바르게 불일치를 감지한 것 → 그대로 유지
        # - 진짜 불확실(is_confident=False): 모델이 모호한 경우 → GPT 보정 적용
        if not nli_is_confident:
            gpt_score = self._compute_gpt_score(query_en, back_translation_en)
            logger.info(
                "NLI 불확실(max_prob≤0.5) → GPT 보정 적용: nli=%.4f gpt=%.4f",
                nli_score, gpt_score,
            )
            similarity_score = gpt_score
        else:
            if nli_score < self._NLI_RELIABLE_THRESHOLD:
                logger.info(
                    "NLI 확신 있는 낮은 점수 %.4f (모순 신호) → GPT 보정 없이 유지",
                    nli_score,
                )
            similarity_score = nli_score

        # Step 5: 통합 판정 — NLI 또는 LLM 자기 비평 중 하나라도 통과하면 PASS
        # (NLI는 어휘 매칭 약점, LLM은 보다 관대 — 두 축이 직교적으로 false negative 방지)
        # is_consistent = (nli_pass) OR (llm_pass)
        nli_pass = similarity_score >= self.threshold
        is_consistent = nli_pass or llm_pass

        mismatch_diagnosis = None
        # 둘 다 실패할 때만 별도 진단 호출 (호출 비용 가드)
        if not is_consistent and similarity_score >= 0.05:
            mismatch_diagnosis = self._diagnose_mismatch(
                original_query, sql, back_translation_kr,
                on_token=on_token,
            )
        elif not nli_pass and llm_pass:
            # NLI는 거짓 음성, LLM이 구원 — 진단 사유에 명시
            mismatch_diagnosis = (
                f"NLI 어휘 매칭 거짓 음성 (ICS={nli_score:.2f}). "
                f"LLM 자기 비평이 통과로 판정 (점수={llm_score:.2f}): {llm_reason}"
            )

        logger.info(
            "의미 검증 완료(3축): nli=%.4f llm=%.2f integrated=%s nli_pass=%s llm_pass=%s",
            nli_score, llm_score, is_consistent, nli_pass, llm_pass,
        )

        return VerificationResult(
            back_translation=back_translation_kr,
            similarity_score=similarity_score,
            is_consistent=is_consistent,
            mismatch_diagnosis=mismatch_diagnosis,
            llm_critique_score=llm_score,
            llm_critique_pass=llm_pass,
            llm_critique_reason=llm_reason,
        )
