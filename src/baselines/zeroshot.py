"""
Zero-shot GPT-4o Baseline (Section 5).
가장 단순한 베이스라인 (하한선): 역할 지시 + 스키마(DDL) + 질의 -> SQL 생성.
Few-shot 예시 없음, 자기교정 없음.
"""

import time
import logging

from src.baselines.base import BaselineModel, extract_sql

logger = logging.getLogger(__name__)


class ZeroShotBaseline(BaselineModel):
    """
    Section 5: Zero-shot GPT-4o 베이스라인.

    프롬프트 구성:
      - 시스템 역할: SQL 전문가
      - 스키마: CREATE TABLE DDL
      - 질의: 자연어 질문
      - 지시: SQL만 반환

    하이퍼파라미터: configs/config.yaml에서 로드
      - llm.model, llm.temperature, llm.max_tokens
    """

    def predict(self, question: str, schema: dict, db_path: str, evidence: str = "") -> dict:
        """
        Zero-shot으로 SQL을 생성한다.

        Args:
            question: 자연어 질의
            schema: 스키마 정보 (schema_text 키 필수)
            db_path: SQLite DB 파일 경로 (이 베이스라인에서는 미사용)
            evidence: 외부 도메인 지식(BIRD evidence). 비어있으면 무시.

        Returns:
            표준 결과 딕셔너리
        """
        start_time = time.time()
        schema_text = schema.get("schema_text", "")

        prompt = self._build_prompt(question, schema_text, evidence)
        messages = [
            {"role": "system", "content": "You are an expert SQL query generator for SQLite databases. Return ONLY the SQL query, no explanations."},
            {"role": "user", "content": prompt},
        ]

        try:
            response = self._call_llm(messages)
            raw_output = response["content"]
            sql = extract_sql(raw_output)
            latency = time.time() - start_time

            return self._make_result(
                sql=sql,
                raw_output=raw_output,
                prompt_tokens=response["prompt_tokens"],
                completion_tokens=response["completion_tokens"],
                latency=latency,
            )

        except Exception as e:
            latency = time.time() - start_time
            logger.error("ZeroShotBaseline.predict failed: %s", e)
            return self._make_result(
                sql="",
                raw_output="",
                prompt_tokens=0,
                completion_tokens=0,
                latency=latency,
                error=str(e),
            )

    def _build_prompt(self, question: str, schema_text: str, evidence: str = "") -> str:
        """Zero-shot 프롬프트를 구성한다."""
        evidence_block = (
            f"\n## External Knowledge / Hint\n{evidence.strip()}\n"
            if evidence and evidence.strip() else ""
        )
        return f"""You are an expert SQL query generator. Given a database schema and a natural language question, generate the correct SQLite SQL query.

## Database Schema
{schema_text}
{evidence_block}
## Guidelines
1. Use only the tables and columns provided in the schema above.
2. Use proper JOIN conditions based on foreign key relationships.
3. Be careful with aggregate functions (COUNT, SUM, AVG, etc.) and GROUP BY clauses.
4. Use appropriate WHERE clauses for filtering.
5. Handle NULL values appropriately.
6. If an "External Knowledge / Hint" section is provided, treat it as authoritative domain knowledge.
7. Return ONLY the SQL query, no explanations.

## Question
{question}

## SQL
"""
