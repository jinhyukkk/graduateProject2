"""
SQL Generator (Section 4.3)
Few-shot 예시 선택 + GPT-4o SQL 생성.
Phase 2: Logprob 기반 Confidence Scoring + Cross-encoder Reranking 추가.
"""

import math
import os
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
    ) -> dict:
        """
        Section 4.3 + Phase 2 + Phase 3: SQL을 생성하고 신뢰도 점수를 함께 반환한다.

        Args:
            query: 자연어 질의
            schema_context: SchemaLinker.link()의 반환값 (schema_text 포함)
            conversation_history: 이전 대화 이력 (Phase 3 멀티턴).
            evidence: 외부 도메인 지식(BIRD evidence). 비어있으면 무시.

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

        prompt = f"""You are an expert SQL query generator. Given a database schema and a natural language question, generate the correct SQL query.

## Database Schema
{schema_text}
{evidence_block}
## Guidelines
1. Use only the tables and columns provided in the schema above.
2. Use proper JOIN conditions based on foreign key relationships shown in FOREIGN KEY definitions.
3. Be careful with aggregate functions (COUNT, SUM, AVG, etc.) and GROUP BY clauses.
4. Use appropriate WHERE clauses for filtering. Match the exact case and format of values shown in column comments (-- e.g.: ...).
5. When filtering on a column that may contain NULLs, explicitly add IS NOT NULL unless the question asks for NULL values.
6. Always alias every table (e.g. T1, T2) and qualify all column references with the alias (e.g. T1.column_name) to avoid ambiguity.
7. Do NOT use subqueries unless necessary.
8. If an "External Knowledge / Hint" section is provided, treat it as authoritative domain knowledge and reflect it in the SQL.
9. Return ONLY the SQL query, no explanations.

{few_shot_block}{history_block}
## Question
{query}

## SQL
"""

        response = chat_completion(
            self.client,
            model=self.llm_model,
            temperature=self.config["llm"]["temperature"],
            max_completion_tokens=self.config["llm"]["max_tokens"],
            messages=[{"role": "user", "content": prompt}],
            logprobs=True,  # Phase 2: Confidence Scoring
        )

        raw = response.choices[0].message.content.strip()

        # SQL 코드 블록 추출
        if "```sql" in raw:
            sql = raw.split("```sql")[1].split("```")[0].strip()
        elif "```" in raw:
            sql = raw.split("```")[1].split("```")[0].strip()
        else:
            sql = raw

        # Phase 2: Logprob 기반 신뢰도 계산
        # 각 토큰의 log probability 평균 → exp → [0, 1] 범위의 기하평균 확률
        confidence = self._compute_confidence(response)

        return {"sql": sql, "confidence": confidence}

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
