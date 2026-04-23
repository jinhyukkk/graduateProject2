"""
Semantic Consistency Verifier (Section 4.4.2)
SQL 역번역 + NLI 일치 검증.
"""

import logging
import os
from dataclasses import dataclass

import numpy as np
from openai import OpenAI
from sentence_transformers import CrossEncoder

from src.openai_retry import chat_completion

logger = logging.getLogger(__name__)


@dataclass
class VerificationResult:
    """의미 일관성 검증 결과."""
    back_translation: str          # SQL의 자연어 역번역 (한국어, 표시용)
    similarity_score: float        # NLI entailment score ∈ [0, 1]
    is_consistent: bool            # sim >= θ 여부
    mismatch_diagnosis: str | None = None  # 불일치 시 GPT-4o 진단 결과


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
        """
        if not self._contains_korean(text):
            return text

        response = chat_completion(
            self.client,
            model=self.llm_model,
            temperature=0.0,
            max_completion_tokens=256,
            messages=[{
                "role": "user",
                "content": (
                    "Translate the following Korean database query to English.\n"
                    "Preserve the exact intent and phrasing style of the question.\n"
                    "Return ONLY the English translation, nothing else.\n\n"
                    f"Korean: {text}"
                ),
            }],
        )
        translated = response.choices[0].message.content.strip()
        logger.debug("한→영 번역: '%s' → '%s'", text, translated)
        return translated

    def _back_translate(self, sql: str) -> tuple[str, str]:
        """
        Section 4.4.2, Step 1: SQL을 자연어 질문으로 역번역한다.

        Returns:
            (korean_text, english_text)
            - korean_text: UI 표시용 한국어 역번역
            - english_text: NLI 입력용 영어 역번역 (구어체 질문 형태)
        """
        prompt = (
            "You are given a SQL query. Rewrite it as a natural language question "
            "a user would ask when querying a database.\n\n"
            "Rules:\n"
            "- Write in plain, conversational English (e.g. 'Which employees joined this year?')\n"
            "- Do NOT use SQL keywords or technical terms\n"
            "- Include all filtering conditions, aggregations, and groupings implied by the SQL\n"
            "- Return ONLY the question, nothing else\n\n"
            f"SQL: {sql}"
        )

        response = chat_completion(
            self.client,
            model=self.llm_model,
            temperature=0.0,
            max_completion_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        english_text = response.choices[0].message.content.strip()
        logger.debug("역번역(영어): %s", english_text)

        # UI 표시용 한국어 번역
        kr_response = chat_completion(
            self.client,
            model=self.llm_model,
            temperature=0.0,
            max_completion_tokens=256,
            messages=[{
                "role": "user",
                "content": (
                    "Translate the following English question to Korean.\n"
                    "Return ONLY the Korean translation, nothing else.\n\n"
                    f"English: {english_text}"
                ),
            }],
        )
        korean_text = kr_response.choices[0].message.content.strip()
        logger.debug("역번역(한국어): %s", korean_text)

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

    def _diagnose_mismatch(self, original_query: str, sql: str, back_translation: str) -> str:
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

        response = chat_completion(
            self.client,
            model=self.llm_model,
            temperature=0.0,
            max_completion_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content.strip()

    def verify(self, original_query: str, sql: str) -> VerificationResult:
        """
        Section 4.4.2: 의미론적 일관성을 검증한다.

        Args:
            original_query: 원래 자연어 질의 (한국어 또는 영어)
            sql: 검증할 SQL 문자열

        Returns:
            VerificationResult: 검증 결과 (유사도 점수, 일치 여부, 진단 결과)
        """
        # Step 1: 역번역 (표시용 한국어 + NLI용 영어)
        back_translation_kr, back_translation_en = self._back_translate(sql)

        # Step 2: 원래 질의를 영어로 정규화 (NLI 모델은 영어 전용)
        query_en = self._translate_to_english(original_query)

        # Step 3: NLI 점수 계산 (영어 ↔ 영어)
        nli_score, nli_is_confident = self._compute_nli_score(query_en, back_translation_en)

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

        # Step 5: θ=0.75 기준으로 일관성 판단
        is_consistent = similarity_score >= self.threshold

        mismatch_diagnosis = None
        if not is_consistent:
            mismatch_diagnosis = self._diagnose_mismatch(
                original_query, sql, back_translation_kr
            )

        logger.info(
            "의미 검증 완료: nli=%.4f final=%.4f consistent=%s",
            nli_score, similarity_score, is_consistent,
        )

        return VerificationResult(
            back_translation=back_translation_kr,   # UI 표시는 한국어
            similarity_score=similarity_score,
            is_consistent=is_consistent,
            mismatch_diagnosis=mismatch_diagnosis,
        )
