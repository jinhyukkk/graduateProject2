"""DIN-SQL Lightweight Wrapper (Section 5).

Pourreza & Rafiei (2023) "DIN-SQL: Decomposed In-Context Learning of Text-to-SQL
with Self-Correction" (NeurIPS 2023).

핵심 4-모듈 파이프라인 (논문 §3):
  1. Schema Linking         — 자연어 질의에서 관련 테이블·컬럼·값 추출
  2. Difficulty Classifier  — 질의를 EASY / NON-NESTED / NESTED 3-tier로 분류
  3. SQL Generator          — 난이도별 *전용* 프롬프트로 SQL 생성
                                 EASY: 직접 생성
                                 NON-NESTED: sub-question 분해 후 단일 쿼리 통합
                                 NESTED: sub-SQL 작성 후 결합
  4. Self-Correction        — 생성된 SQL을 LLM에 다시 검토 요청 (gentle/aggressive 2-mode)

구현 방침:
  - 공식 repo 래핑 대신 핵심 4단계를 경량 재구현 (MAC-SQL 래퍼와 동일 방침)
  - 각 단계 프롬프트는 DIN-SQL 논문 §3 + Appendix B 기반
  - GPT-4o 백본 통일 (DAIL/MAC과 동일 환경 비교)
  - max correction rounds = 1 (논문 기본값, gentle 1회)
"""
from __future__ import annotations

import re
import sqlite3
import time
import logging

from src.baselines.base import BaselineModel, extract_sql

logger = logging.getLogger(__name__)


SCHEMA_LINKING_PROMPT = """You are an expert SQL schema linker. Given a question and a database schema, identify the *minimal* set of tables and columns needed to answer the question.

## Database Schema
{schema}

## Question
{question}

## Output (one item per line)
Tables: <comma-separated table names>
Columns: <comma-separated table.column references>
Predicates: <comma-separated value/literal hints, if any>
"""


CLASSIFIER_PROMPT = """You are a SQL difficulty classifier. Given a question and a schema, classify into one of:
- EASY: single table, simple WHERE/aggregation. No JOIN.
- NON-NESTED: multi-table JOIN with WHERE/GROUP BY/HAVING/ORDER BY but no subquery.
- NESTED: requires nested subqueries (IN/EXISTS/subquery in FROM/SELECT).

## Database Schema
{schema}

## Question
{question}

## Output (single line)
Class: <EASY|NON-NESTED|NESTED>
Reasoning: <one short sentence>
"""


EASY_PROMPT = """You are an expert SQL generator for EASY queries (single table, no JOIN).

## Database Schema
{schema}

## Question
{question}
{evidence}
## Output
Write the SQL inside a fenced code block:
```sql
SELECT ...
```
"""


NON_NESTED_PROMPT = """You are an expert SQL generator for NON-NESTED multi-table queries (with JOIN, no subquery).

## Database Schema
{schema}

## Question
{question}
{evidence}
## Reasoning steps
1. Identify the *sub-questions* this complex question decomposes into.
2. For each sub-question, identify which tables and join conditions are needed.
3. Combine the sub-question logic into a single SQL with JOINs (no subquery).

## Output
Write the final SQL inside a fenced code block:
```sql
SELECT ...
```
"""


NESTED_PROMPT = """You are an expert SQL generator for NESTED queries (requiring subqueries).

## Database Schema
{schema}

## Question
{question}
{evidence}
## Reasoning steps
1. Identify the inner sub-question that must be answered first (this becomes the subquery).
2. Identify the outer query that consumes the subquery's result.
3. Choose the right correlation: IN, EXISTS, scalar subquery, or subquery-in-FROM.

## Output
Write the final SQL inside a fenced code block:
```sql
SELECT ...
```
"""


CORRECTION_PROMPT = """You are an expert SQL reviewer. The following SQL was generated for the question. Review it and produce a corrected version if needed. If it looks correct, return it unchanged.

## Database Schema
{schema}

## Question
{question}

## Original SQL
```sql
{sql}
```

## Execution feedback
{feedback}

## Output (corrected SQL only)
```sql
SELECT ...
```
"""


class DINSQLBaseline(BaselineModel):
    """DIN-SQL 4-module 경량 래퍼.

    파이프라인: Schema Linking → Classifier → SQL Generator (난이도별) → Self-Correction.
    각 모듈은 별도 LLM 호출이며, GPT-4o-2024-11-20을 통일적으로 사용한다.
    """

    def __init__(self, config: dict):
        super().__init__(config)
        din_config = config.get("baselines", {}).get("din_sql", {}) or {}
        self.max_correction_rounds = din_config.get("max_correction_rounds", 1)
        self.sqlite_timeout = din_config.get("sqlite_timeout", 5.0)

    # ------------------------------------------------------------------ Module 1
    def _schema_linking(self, question: str, schema_text: str) -> str:
        """Module 1: 관련 테이블/컬럼/값 후보를 추출하여 schema_text에 prepend할 hint 생성."""
        try:
            content = self._call_llm(
                SCHEMA_LINKING_PROMPT.format(schema=schema_text, question=question)
            )
            # 결과를 그대로 hint 블록으로 사용
            return f"## Schema Linking Hints\n{content.strip()}\n"
        except Exception as e:
            logger.warning("schema_linking failed: %s", e)
            return ""

    # ------------------------------------------------------------------ Module 2
    def _classify(self, question: str, schema_text: str) -> str:
        """Module 2: 난이도 클래스 반환 (EASY / NON-NESTED / NESTED)."""
        try:
            content = self._call_llm(
                CLASSIFIER_PROMPT.format(schema=schema_text, question=question)
            )
            m = re.search(r"Class:\s*([A-Z\-]+)", content)
            if m:
                cls = m.group(1).strip().upper()
                if cls in ("EASY", "NON-NESTED", "NESTED"):
                    return cls
            # 폴백: 패턴 매칭
            if "NESTED" in content.upper():
                return "NESTED"
            if "NON" in content.upper():
                return "NON-NESTED"
            return "EASY"
        except Exception as e:
            logger.warning("classify failed: %s", e)
            return "NON-NESTED"

    # ------------------------------------------------------------------ Module 3
    def _generate_by_class(
        self, question: str, schema_text: str, evidence: str, cls: str
    ) -> str:
        ev_block = (
            f"\n## External Knowledge / Hint\n{evidence.strip()}\n"
            if evidence and evidence.strip() else ""
        )
        if cls == "EASY":
            template = EASY_PROMPT
        elif cls == "NESTED":
            template = NESTED_PROMPT
        else:
            template = NON_NESTED_PROMPT
        try:
            content = self._call_llm(
                template.format(schema=schema_text, question=question, evidence=ev_block)
            )
            return extract_sql(content)
        except Exception as e:
            logger.warning("generate failed: %s", e)
            return ""

    # ------------------------------------------------------------------ Module 4
    def _correct(
        self, question: str, schema_text: str, sql: str, feedback: str
    ) -> str:
        try:
            content = self._call_llm(
                CORRECTION_PROMPT.format(
                    schema=schema_text, question=question, sql=sql, feedback=feedback
                )
            )
            return extract_sql(content) or sql
        except Exception as e:
            logger.warning("correction failed: %s", e)
            return sql

    # ------------------------------------------------------------------ orchestrator
    def predict(self, question: str, schema: dict, db_path: str, evidence: str = "") -> dict:
        """DIN-SQL 4-module 파이프라인으로 SQL 생성."""
        t_start = time.time()
        schema_text = schema.get("schema_text", "")

        # 1. Schema Linking (hint 생성)
        link_hint = self._schema_linking(question, schema_text)
        enriched_schema = link_hint + schema_text if link_hint else schema_text

        # 2. Classifier
        cls = self._classify(question, enriched_schema)

        # 3. SQL Generator (난이도별)
        sql = self._generate_by_class(question, enriched_schema, evidence, cls)
        if not sql:
            return {
                "sql": "",
                "metadata": {"din_class": cls, "rounds": 0, "latency": time.time() - t_start},
            }

        # 4. Self-Correction (실행 피드백 기반)
        rounds = 0
        for _ in range(self.max_correction_rounds):
            ok, feedback = self._execute_check(sql, db_path)
            if ok:
                break
            sql = self._correct(question, enriched_schema, sql, feedback)
            rounds += 1

        return {
            "sql": sql,
            "metadata": {
                "din_class": cls,
                "rounds": rounds,
                "latency": time.time() - t_start,
            },
        }

    # ------------------------------------------------------------------ helpers
    def _execute_check(self, sql: str, db_path: str) -> tuple[bool, str]:
        if not sql:
            return False, "empty SQL"
        try:
            conn = sqlite3.connect(db_path, timeout=self.sqlite_timeout)
            c = conn.cursor()
            c.execute(sql)
            rows = c.fetchall()
            conn.close()
            if not rows:
                return False, "Empty result set — check filters and JOINs."
            return True, "ok"
        except Exception as e:
            return False, f"Execution error: {e!s}"

    def _call_llm(self, prompt: str) -> str:
        """OpenAI chat completion. base.BaselineModel.client 활용."""
        resp = self.client.chat.completions.create(
            model=self.config["llm"]["model"],
            temperature=self.config["llm"].get("temperature", 0.0),
            max_completion_tokens=self.config["llm"].get("max_tokens", 1024),
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content or ""
