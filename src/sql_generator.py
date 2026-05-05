"""
SQL Generator (Section 4.3)
Few-shot 예시 선택 + GPT-4o SQL 생성.
Phase 2: Logprob 기반 Confidence Scoring + Cross-encoder Reranking 추가.
"""

import math
import os
from datetime import datetime
from typing import Callable

import numpy as np
from openai import OpenAI

from src.openai_retry import chat_completion, embeddings as embeddings_call


class SQLGenerator:
    """
    Section 4.3: Few-shot 기반 SQL 생성기.

    DAIL-SQL 방식 참고: 구조적 유사도(0.5) + 의미적 유사도(0.5) 가중합으로
    가장 유사한 예시 K개를 선택하여 few-shot 프롬프트를 구성한다.

    Phase 2 추가:
    - Cross-encoder Reranking: 초기 embedding 후보 2K개를 cross-encoder로 재정렬
    - Confidence Scoring: logprob 기반 생성 신뢰도 계산
    """

    def __init__(
        self,
        config: dict,
        few_shot_examples: list[dict] | None = None,
        reranker=None,
    ):
        """
        Args:
            config: configs/config.yaml에서 로드된 설정
            few_shot_examples: few-shot 후보 리스트. 각 항목은
                {"query": str, "sql": str, "schema": str, "db_id": str} 형태.
            reranker: (Phase 2) CrossEncoder 인스턴스. 제공 시 few-shot 재정렬에 사용.
                      None이면 embedding+structural 점수만 사용.
        """
        self.config = config
        self.client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        self.llm_model = config["llm"]["model"]
        self.embedding_model = config["embedding"]["model"]
        self.few_shot_k = config["sql_generator"]["few_shot_k"]
        self.few_shot_examples = few_shot_examples or []
        self.reranker = reranker  # Phase 2: CrossEncoder for reranking
        self._example_embeddings = None

    def _get_embedding(self, texts: list[str]) -> np.ndarray:
        """OpenAI 임베딩 API로 텍스트 리스트를 임베딩한다. 2048개씩 배치 처리."""
        batch_size = 2048
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            response = embeddings_call(
                self.client,
                model=self.embedding_model,
                input=batch,
            )
            all_embeddings.extend([item.embedding for item in response.data])
        return np.array(all_embeddings, dtype=np.float32)

    def _compute_example_embeddings(self):
        """few-shot 예시들의 임베딩을 미리 계산한다."""
        if not self.few_shot_examples or self._example_embeddings is not None:
            return
        texts = [ex["query"] for ex in self.few_shot_examples]
        self._example_embeddings = self._get_embedding(texts)

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> np.ndarray:
        """코사인 유사도를 계산한다."""
        a_norm = a / (np.linalg.norm(a, axis=-1, keepdims=True) + 1e-9)
        b_norm = b / (np.linalg.norm(b, axis=-1, keepdims=True) + 1e-9)
        return np.dot(a_norm, b_norm.T)

    def _structural_similarity(self, query_schema: str, example_schema: str) -> float:
        """
        Section 4.3: 구조적 유사도 계산.
        스키마 토큰 Jaccard 유사도 (DAIL-SQL 기본 설정)
        """
        query_tokens = set(query_schema.lower().split())
        example_tokens = set(example_schema.lower().split())
        if not query_tokens or not example_tokens:
            return 0.0
        intersection = query_tokens & example_tokens
        union = query_tokens | example_tokens
        return len(intersection) / len(union)

    def _select_few_shot(self, query: str, schema_text: str) -> list[dict]:
        """
        Section 4.3 + Phase 2: 구조적 유사도(0.5) + 의미적 유사도(0.5) 가중합으로
        상위 후보를 추출하고, reranker가 있으면 cross-encoder로 재정렬한다.

        Phase 2 Reranking:
          1단계: embedding + Jaccard 가중합으로 2K개 후보 추출 (K = few_shot_k)
          2단계: cross-encoder(query, example_query)의 entailment score로 재정렬
                 → 상위 K개 최종 선택
        """
        if not self.few_shot_examples:
            return []

        self._compute_example_embeddings()

        # 의미적 유사도: 질의 임베딩 vs 예시 질의 임베딩
        query_emb = self._get_embedding([query])
        semantic_scores = self._cosine_similarity(query_emb, self._example_embeddings)[0]

        # 구조적 유사도: 스키마 토큰 Jaccard
        structural_scores = np.array([
            self._structural_similarity(schema_text, ex.get("schema", ""))
            for ex in self.few_shot_examples
        ])

        # 가중합: 0.5 * structural + 0.5 * semantic
        combined_scores = 0.5 * structural_scores + 0.5 * semantic_scores

        # Phase 2 Reranking: cross-encoder가 있으면 2K 후보를 먼저 뽑은 뒤 재정렬
        if self.reranker is not None:
            pre_k = min(self.few_shot_k * 2, len(self.few_shot_examples))
            pre_indices = np.argsort(combined_scores)[::-1][:pre_k]
            pre_candidates = [self.few_shot_examples[i] for i in pre_indices]

            # cross-encoder: (query, example_query) 쌍의 entailment score
            # cross-encoder/nli-deberta-v3-base: [contradiction, entailment, neutral]
            pairs = [(query, ex["query"]) for ex in pre_candidates]
            try:
                ce_scores = self.reranker.predict(pairs, apply_softmax=True)
                # entailment score (index 1) 사용
                entailment_scores = [float(s[1]) for s in ce_scores]
                # entailment score 기준으로 재정렬
                ranked = sorted(
                    zip(pre_candidates, entailment_scores),
                    key=lambda x: x[1],
                    reverse=True,
                )
                return [c for c, _ in ranked[:self.few_shot_k]]
            except Exception:
                # reranker 실패 시 fallback: 기존 combined_scores 사용
                return [pre_candidates[i] for i in range(self.few_shot_k)]

        # Reranker 없음: 기존 방식
        top_indices = np.argsort(combined_scores)[::-1][:self.few_shot_k]
        return [self.few_shot_examples[i] for i in top_indices]

    def generate(
        self,
        query: str,
        schema_context: dict,
        conversation_history: list[dict] | None = None,
        evidence: str = "",
        value_hints: str = "",
        on_token: Callable[[str], None] | None = None,
    ) -> dict:
        """
        Section 4.3 + Phase 2 + Phase 3: SQL을 생성하고 신뢰도 점수를 함께 반환한다.

        Args:
            query: 자연어 질의
            schema_context: SchemaLinker.link()의 반환값 (schema_text 포함)
            conversation_history: 이전 대화 이력 (Phase 3 멀티턴).
            evidence: 외부 도메인 지식(BIRD evidence). 비어있으면 무시.
            on_token: (옵션) LLM이 생성한 토큰을 실시간으로 받는 콜백.
                제공되면 OpenAI streaming API를 사용해 CoT 추론 과정을 토큰
                단위로 흘려보낸다. 시연에서 ChatGPT 같은 점진적 표시에 사용.

        Returns:
            {
                "sql": str,         # 생성된 SQL 문자열
                "confidence": float # logprob 기반 생성 신뢰도 (0~1)
            }
        """
        schema_text = schema_context.get("schema_text", "")
        selected_examples = self._select_few_shot(query, schema_text)

        few_shot_block = self._format_few_shot(selected_examples)
        history_block = self._format_conversation_history(conversation_history or [])
        evidence_block = f"\n## External Knowledge / Hint\n{evidence.strip()}\n" if evidence and evidence.strip() else ""
        value_block = f"\n{value_hints.strip()}\n" if value_hints and value_hints.strip() else ""

        # Today 힌트 — "올해/작년/최근" 같은 상대 시간 표현을 LLM이 학습 cutoff
        # 시점(예: 2023)으로 잘못 매핑하는 문제를 방지한다 (시연 점검에서 확인됨).
        today = datetime.now().strftime("%Y-%m-%d")
        today_block = (
            f"\n## Today\nCURRENT_DATE = {today}.  "
            f"Resolve relative time words (올해/작년/이번 달/최근) using this date.\n"
        )

        prompt = self._build_generation_prompt(
            schema_text=schema_text,
            few_shot_block=few_shot_block,
            history_block=history_block,
            evidence_block=evidence_block,
            value_block=value_block,
            today_block=today_block,
            query=query,
        )

        if on_token is None:
            response = chat_completion(
                self.client,
                model=self.llm_model,
                temperature=self.config["llm"]["temperature"],
                max_completion_tokens=self.config["llm"]["max_tokens"],
                messages=[{"role": "user", "content": prompt}],
                logprobs=True,  # Phase 2: Confidence Scoring
            )
            raw = response.choices[0].message.content.strip()
            confidence = self._compute_confidence(response)
        else:
            raw, confidence = self._generate_streaming(prompt, on_token)

        sql = self._extract_sql(raw)
        return {"sql": sql, "confidence": confidence}

    def generate_candidates(
        self,
        query: str,
        schema_context: dict,
        k: int,
        conversation_history: list[dict] | None = None,
        evidence: str = "",
        value_hints: str = "",
        temperature: float | None = None,
    ) -> list[dict]:
        """Self-consistency용: 동일 프롬프트로 k개의 SQL 후보를 샘플링 생성.

        temperature > 0 (기본 0.7)으로 다양화하며, 첫 후보는 결정론적(0.0)으로
        둬서 단일 생성 베이스라인과 동일한 SQL을 항상 포함한다 (탐색 + 활용).

        Args:
            k: 생성할 후보 수 (>=1).
            temperature: 샘플링 온도. None이면 config의 self_consistency.temperature
                또는 기본값 0.7을 사용한다.

        Returns:
            [{"sql": str, "confidence": float}, ...] 리스트. 빈 SQL은 제외.
        """
        if k < 1:
            raise ValueError("k must be >= 1")

        sample_temp = temperature
        if sample_temp is None:
            sample_temp = self.config.get("self_consistency", {}).get("temperature", 0.7)

        schema_text = schema_context.get("schema_text", "")
        selected_examples = self._select_few_shot(query, schema_text)
        few_shot_block = self._format_few_shot(selected_examples)
        history_block = self._format_conversation_history(conversation_history or [])
        evidence_block = (
            f"\n## External Knowledge / Hint\n{evidence.strip()}\n"
            if evidence and evidence.strip() else ""
        )
        value_block = f"\n{value_hints.strip()}\n" if value_hints and value_hints.strip() else ""
        today = datetime.now().strftime("%Y-%m-%d")
        today_block = (
            f"\n## Today\nCURRENT_DATE = {today}.  "
            f"Resolve relative time words (올해/작년/이번 달/최근) using this date.\n"
        )

        prompt = self._build_generation_prompt(
            schema_text=schema_text,
            few_shot_block=few_shot_block,
            history_block=history_block,
            evidence_block=evidence_block,
            value_block=value_block,
            today_block=today_block,
            query=query,
        )

        candidates: list[dict] = []
        # 첫 후보: temperature=0 (결정론적, 단일 생성과 동일)
        # 나머지 k-1: temperature=sample_temp (다양화)
        from concurrent.futures import ThreadPoolExecutor

        def _one_call(temp: float) -> dict:
            try:
                response = chat_completion(
                    self.client,
                    model=self.llm_model,
                    temperature=temp,
                    max_completion_tokens=self.config["llm"]["max_tokens"],
                    messages=[{"role": "user", "content": prompt}],
                    logprobs=True,
                )
                raw = response.choices[0].message.content.strip()
                conf = self._compute_confidence(response)
                sql = self._extract_sql(raw)
                return {"sql": sql, "confidence": conf}
            except Exception:
                return {"sql": "", "confidence": 0.0}

        temps = [0.0] + [sample_temp] * (k - 1)
        # 병렬 호출로 응답 시간 단축 (k=5 ≈ 단일 호출 + few seconds)
        with ThreadPoolExecutor(max_workers=min(k, 5)) as pool:
            results = list(pool.map(_one_call, temps))

        for r in results:
            if r["sql"]:
                candidates.append(r)
        return candidates

    def _build_generation_prompt(
        self,
        schema_text: str,
        few_shot_block: str,
        history_block: str,
        evidence_block: str,
        value_block: str,
        today_block: str,
        query: str,
    ) -> str:
        """generate()와 generate_candidates()가 공유하는 프롬프트 빌더."""
        return f"""You are an expert SQL query generator. Given a database schema and a natural language question, generate the correct SQL query.

## Database Schema
{schema_text}
{today_block}{evidence_block}{value_block}
## Guidelines
1. Use only the tables and columns provided in the schema above.
2. Use proper JOIN conditions based on foreign key relationships shown in FOREIGN KEY definitions.
3. **JOIN value-domain safety (critical)**: Only join columns that share the same value domain. For paired columns where one stores a *code* (e.g. `JIKGUB_CD` with values like 'J01','J02') and the other stores a *human-readable name* (e.g. `JIKGUB_NM` with values like '사원','과장'), NEVER write `T1.X_CD = T2.Y_NM`. Always join code-to-code or name-to-name. Inspect the column comments (-- e.g.: ...) to confirm both sides share the same value style before writing the JOIN.
4. **Group-by display rule**: When grouping or aggregating by a `_CD` (code) column whose paired `_NM` (name) column is available in the schema, **also SELECT the `_NM` column** alongside the aggregate so the result is human-readable. Do not return rows keyed only by an opaque code.
5. **Time expressions**: When the question contains relative time words ("올해" = this year, "작년" = last year, "이번 달" = this month, "최근" = recent), use the **CURRENT_DATE** value provided in the "Today" hint (if present) — never assume a past year from training data. Express filters with explicit year/month derived from the CURRENT_DATE.
6. **Output column discipline**: SELECT only the columns the user asked for, plus the `_NM` companion of any aggregated `_CD` (rule 4). Do not add status/audit columns unless the question references them.
7. Be careful with aggregate functions (COUNT, SUM, AVG, etc.) and GROUP BY clauses.
8. Use appropriate WHERE clauses for filtering. Match the exact case and format of values shown in column comments (-- e.g.: ...).
9. When filtering on a column that may contain NULLs, explicitly add IS NOT NULL unless the question asks for NULL values.
10. Always alias every table (e.g. T1, T2) and qualify all column references with the alias (e.g. T1.column_name) to avoid ambiguity.
11. Do NOT use subqueries unless necessary.
12. If an "External Knowledge / Hint" section is provided, treat it as authoritative domain knowledge and reflect it in the SQL.
13. If a "Value Hints" section is provided, match string literal values exactly to the DB's actual values listed there (case, spacing).

## Pre-finalization checklist (think through these before writing SQL)
Briefly answer each line as a single short sentence, THEN write the SQL.
- **Intent**: What single question is the user asking? (one short sentence in Korean)
- **Tables/joins**: Which tables and join keys? Do all join keys share the same value domain?
- **Filters**: Which WHERE conditions? If "재직", did you include EDATE IS NULL? If "올해/작년/최근", did you use Today's CURRENT_DATE?
- **Aggregation/grouping**: Are GROUP BY columns the right granularity? If grouping by `_CD`, did you SELECT the paired `_NM`?
- **Output columns**: Do SELECT columns match what the user asked, with no extras?

## Output format
After the checklist, write the final SQL inside a fenced code block:

```sql
SELECT ...
```

Do not add commentary after the code block.

{few_shot_block}{history_block}
## Question
{query}

## SQL
"""

    def _generate_streaming(
        self,
        prompt: str,
        on_token: Callable[[str], None],
    ) -> tuple[str, float]:
        """OpenAI streaming chat completion으로 토큰을 실시간 흘려보낸다.

        시연에서 CoT 추론 과정을 ChatGPT처럼 한 글자씩 보여주기 위한 경로.
        SQL fenced block(```sql ... ```)은 코드 블록으로 인식되어 on_token에
        전달되지 않으므로 추론 패널에 SQL이 직접 새지 않는다. 펜스 이전·이후의
        프로즈 토큰은 모두 흘려보낸다.

        Returns:
            (raw_full_text, confidence_estimate)
        """
        from src.openai_retry import chat_completion_streaming

        raw = chat_completion_streaming(
            self.client,
            on_token,
            model=self.llm_model,
            temperature=self.config["llm"]["temperature"],
            max_completion_tokens=self.config["llm"]["max_tokens"],
            messages=[{"role": "user", "content": prompt}],
        )
        # streaming은 logprobs를 안정적으로 받기 어려우므로 confidence는 0.85 고정.
        # (downstream의 high-conf gating(0.70) 통과 — NLI 트리거가 의미가 있도록)
        return raw.strip(), 0.85

    @staticmethod
    def _extract_sql(raw: str) -> str:
        """LLM 응답에서 SQL을 안전하게 추출한다.

        프롬프트가 CoT(self-check checklist) + ```sql 블록 형태로 응답을 요구하므로
        다음 우선순위로 추출한다:
          1) ```sql ... ``` fenced block (가장 안전)
          2) ``` ... ``` 임의 fenced block
          3) raw text에서 마지막 SELECT/WITH/INSERT/UPDATE/DELETE 토큰부터 끝까지

        (3)을 사용하는 이유: CoT가 raw text 앞부분을 차지할 때 fence를 깜빡한 경우.
        """
        import re

        if "```sql" in raw:
            return raw.split("```sql", 1)[1].split("```", 1)[0].strip()
        if "```" in raw:
            inner = raw.split("```", 2)
            if len(inner) >= 3:
                return inner[1].strip()
            return inner[1].strip() if len(inner) >= 2 else raw.strip()

        # Fallback: SQL 키워드 시작점 탐지 (case-insensitive, 마지막 매치)
        match = list(re.finditer(
            r"(?im)^\s*(?:SELECT|WITH|INSERT|UPDATE|DELETE)\b",
            raw,
        ))
        if match:
            return raw[match[-1].start():].strip()
        return raw.strip()

    def _compute_confidence(self, response) -> float:
        """
        Phase 2: Logprob 기반 생성 신뢰도를 계산한다.

        토큰별 log probability의 산술평균을 exp한 값 (기하평균 확률).
        값이 높을수록 모델이 확신을 갖고 생성한 SQL임을 의미한다.

        Returns:
            float in [0, 1]. logprobs 미지원 시 0.5 반환.
        """
        try:
            logprobs_content = response.choices[0].logprobs
            if logprobs_content is None or not logprobs_content.content:
                return 0.5
            lps = [
                t.logprob for t in logprobs_content.content
                if t.logprob is not None
            ]
            if not lps:
                return 0.5
            return float(math.exp(sum(lps) / len(lps)))
        except Exception:
            return 0.5

    def _format_few_shot(self, examples: list[dict]) -> str:
        """선택된 few-shot 예시를 프롬프트 포맷으로 변환한다."""
        if not examples:
            return ""

        lines = ["## Examples"]
        for i, ex in enumerate(examples, 1):
            lines.append(f"\n### Example {i}")
            lines.append(f"Question: {ex['query']}")
            lines.append(f"SQL: {ex['sql']}")

        return "\n".join(lines)

    def _format_conversation_history(self, history: list[dict]) -> str:
        """
        Phase 3: 이전 대화 이력을 프롬프트 블록으로 변환한다.

        최대 최근 3턴만 포함 (프롬프트 길이 관리).
        각 항목: {"question": str, "sql": str, "explanation": str (optional)}
        """
        if not history:
            return ""

        # 최근 3턴만 사용
        recent = history[-3:]
        lines = ["\n## Conversation History (recent turns)"]
        for i, turn in enumerate(recent, 1):
            q = turn.get("question", "")
            sql = turn.get("sql", "")
            if q and sql:
                lines.append(f"\n### Turn {i}")
                lines.append(f"Question: {q}")
                lines.append(f"SQL: {sql}")

        return "\n".join(lines) + "\n"
