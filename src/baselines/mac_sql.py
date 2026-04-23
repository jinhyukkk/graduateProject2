"""
MAC-SQL Lightweight Wrapper (Section 5).
Wang et al. (2024) "MAC-SQL: A Multi-Agent Collaborative Framework for Text-to-SQL"
EMNLP 2024 Findings.

핵심 아이디어: 3에이전트 파이프라인 (논문 순서 준수)
  1. Selector   — 스키마 토큰이 임계값 초과 시에만 활성화 (조건부)
                  전체 스키마에서 관련 테이블/컬럼만 선택 (스키마 축소)
  2. Decomposer — 축소(또는 전체) 스키마로 복잡 질의 분해 + 각 하위 SQL 생성 + 최종 SQL 조립
  3. Refiner    — 실행 오류 또는 빈 결과(소프트 실패) 시 최대 max_refine_rounds회 교정
                  오류 메시지 + exception class 모두 전달

구현 방침:
  - 공식 repo 래핑 대신 핵심 3단계를 직접 경량 재구현
  - 각 단계의 프롬프트는 MAC-SQL 논문 기반
  - max_refine_rounds=3 (논문 Appendix A.3 기본값)
  - Selector 임계값: 논문 기준 len(tokens) > 0.8 * max_context_length
    경량 구현에서는 schema_text 길이(글자 수) > selector_char_threshold로 근사
  - 모든 LLM 호출은 동일 GPT 백엔드, temperature=0
"""

import sqlite3
import time
import logging

from src.baselines.base import BaselineModel, extract_sql

logger = logging.getLogger(__name__)


class MACSQLBaseline(BaselineModel):
    """
    Section 5: MAC-SQL 경량 래퍼.

    논문 정확한 파이프라인: Selector(조건부) → Decomposer → Refiner

    하이퍼파라미터 (configs/config.yaml):
      - baselines.mac_sql.max_refine_rounds: Refiner 최대 교정 횟수 (기본 3)
      - baselines.mac_sql.sqlite_timeout: SQL 실행 타임아웃 (기본 5.0초)
      - baselines.mac_sql.selector_char_threshold: Selector 활성화 임계값 (기본 6000자)
        논문: len(tokens) > 0.8 * max_seq_len (GPT-4-32k 기준 >25k 토큰)
        경량 근사: schema_text 글자 수 > 6000 (≈ 1500토큰)
    """

    def __init__(self, config: dict):
        super().__init__(config)
        mac_config = config.get("baselines", {}).get("mac_sql", {})
        self.max_refine_rounds = mac_config.get("max_refine_rounds", 3)
        self.sqlite_timeout = mac_config.get("sqlite_timeout", 5.0)
        # Selector는 스키마가 클 때만 활성화 (논문 Appendix A.1)
        self.selector_char_threshold = mac_config.get("selector_char_threshold", 6000)

    def predict(self, question: str, schema: dict, db_path: str, evidence: str = "") -> dict:
        """
        MAC-SQL 3에이전트 파이프라인으로 SQL을 생성한다.
        논문 기준 순서: Selector → Decomposer → Refiner

        Args:
            question: 자연어 질의
            schema: 스키마 정보 (schema_text, tables, columns, foreign_keys)
            db_path: SQLite DB 파일 경로
            evidence: 외부 도메인 지식(BIRD evidence). 비어있으면 무시.

        Returns:
            표준 결과 딕셔너리
        """
        start_time = time.time()
        full_schema_text = schema.get("schema_text", "")
        total_prompt_tokens = 0
        total_completion_tokens = 0
        all_raw_outputs = []

        try:
            # Agent 1: Selector — 스키마가 임계값 초과 시에만 활성화 (논문 Appendix A.1)
            if len(full_schema_text) > self.selector_char_threshold:
                pruned_schema, cost1 = self._select_schema(question, full_schema_text)
                total_prompt_tokens += cost1["prompt_tokens"]
                total_completion_tokens += cost1["completion_tokens"]
                all_raw_outputs.append(f"[Selector]\n{pruned_schema}")
            else:
                # 스키마가 충분히 작으면 원본 그대로 사용
                pruned_schema = full_schema_text
                all_raw_outputs.append("[Selector] skipped (schema within threshold)")

            # Agent 2: Decomposer — 축소(또는 전체) 스키마로 질의 분해 + SQL 생성
            sql, decomposition, cost2 = self._decompose_and_generate(
                question, pruned_schema, evidence
            )
            total_prompt_tokens += cost2["prompt_tokens"]
            total_completion_tokens += cost2["completion_tokens"]
            all_raw_outputs.append(f"[Decomposer]\n{decomposition}")

            # Agent 3: Refiner — 실행 오류 또는 빈 결과 시 교정 (최대 max_refine_rounds회)
            for refine_round in range(1, self.max_refine_rounds + 1):
                exec_result = self._execute_sql(sql, db_path)

                feedback = self._get_refinement_feedback(exec_result)
                if feedback is None:
                    # 실행 성공 + 결과 있음 → 교정 불필요
                    break

                refined_sql, cost_ref = self._refine(
                    question, sql, feedback, pruned_schema, evidence
                )
                total_prompt_tokens += cost_ref["prompt_tokens"]
                total_completion_tokens += cost_ref["completion_tokens"]
                all_raw_outputs.append(
                    f"[Refiner round {refine_round}]\n"
                    f"Error: {feedback['error']}\n"
                    f"Exception: {feedback['exception_class']}\n"
                    f"Refined: {refined_sql}"
                )
                sql = refined_sql

            latency = time.time() - start_time
            raw_output = "\n\n".join(all_raw_outputs)

            return self._make_result(
                sql=sql,
                raw_output=raw_output,
                prompt_tokens=total_prompt_tokens,
                completion_tokens=total_completion_tokens,
                latency=latency,
            )

        except Exception as e:
            latency = time.time() - start_time
            logger.error("MACSQLBaseline.predict failed: %s", e)
            raw_output = "\n\n".join(all_raw_outputs) if all_raw_outputs else ""
            return self._make_result(
                sql="",
                raw_output=raw_output,
                prompt_tokens=total_prompt_tokens,
                completion_tokens=total_completion_tokens,
                latency=latency,
                error=str(e),
            )

    # ------------------------------------------------------------------ #
    #  Agent 1: Selector                                                   #
    # ------------------------------------------------------------------ #

    def _select_schema(
        self, question: str, full_schema_text: str
    ) -> tuple[str, dict]:
        """
        MAC-SQL Selector: 전체 스키마에서 질의에 필요한 테이블/컬럼만 선택한다.
        선택된 축소 스키마는 Decomposer에 전달된다.

        Args:
            question: 자연어 질의
            full_schema_text: 전체 DB 스키마 (DDL)

        Returns:
            (축소된 스키마 텍스트, {"prompt_tokens": int, "completion_tokens": int})
        """
        prompt = f"""You are a database schema selector for a Text-to-SQL system. Given a natural language question and the full database schema, select ONLY the tables and columns necessary to answer the question.

## Full Database Schema
{full_schema_text}

## Question
{question}

## Instructions
1. Identify all tables directly needed to answer the question.
2. Include tables required for JOIN operations (even if not in the final SELECT).
3. Select only the relevant columns from those tables.
4. Include all foreign key relationships between selected tables.
5. Present the selected schema as CREATE TABLE statements.
6. If all tables are needed, return the full schema.

## Selected Schema
"""
        response = self._call_llm([{"role": "user", "content": prompt}])
        cost = {
            "prompt_tokens": response["prompt_tokens"],
            "completion_tokens": response["completion_tokens"],
        }
        return response["content"], cost

    # ------------------------------------------------------------------ #
    #  Agent 2: Decomposer (분해 + SQL 생성 통합)                          #
    # ------------------------------------------------------------------ #

    def _decompose_and_generate(
        self, question: str, pruned_schema: str, evidence: str = ""
    ) -> tuple[str, str, dict]:
        """
        MAC-SQL Decomposer: 복잡한 질의를 하위 질의로 분해하고,
        각 하위 질의에 대한 SQL을 생성한 후 최종 SQL을 조립한다.
        단순 질의는 분해 없이 직접 SQL을 생성한다.

        논문 기준:
          - Simple question: 직접 SQL 생성
          - Complex question: 하위 질의 분해 → 각 SQL 생성 → 최종 SQL 조립

        Args:
            question: 자연어 질의
            pruned_schema: Selector가 축소한 스키마 (DDL)

        Returns:
            (최종 SQL, 전체 추론 과정 텍스트, {"prompt_tokens": int, "completion_tokens": int})
        """
        evidence_block = (
            f"\n## External Knowledge / Hint\n{evidence.strip()}\n"
            if evidence and evidence.strip() else ""
        )
        prompt = f"""You are an expert SQL query generator. Use a divide-and-conquer approach to answer the question.

## Database Schema (Relevant Tables Only)
{pruned_schema}
{evidence_block}
## Question
{question}

## Instructions
Step 1 - Classify the question:
  - SIMPLE: Can be answered with a single straightforward SQL query.
  - COMPLEX: Requires multiple steps, sub-queries, or aggregating results from intermediate queries.

Step 2 - If SIMPLE: Generate the final SQL query directly.

Step 2 - If COMPLEX:
  a) Decompose into numbered sub-questions.
  b) For each sub-question, write the intermediate SQL.
  c) Explain how intermediate results combine.
  d) Write the final SQL incorporating all sub-queries.

## Examples

### Example 1 (SIMPLE)
Question: How many employees work in the 'Sales' department?
Classification: SIMPLE
Final SQL:
SELECT COUNT(*) FROM employees WHERE department = 'Sales'

### Example 2 (COMPLEX)
Question: Which employees earn more than the average salary of their own department?
Classification: COMPLEX
Sub-question 1: What is the average salary for each department?
  SQL 1: SELECT department_id, AVG(salary) AS avg_sal FROM employees GROUP BY department_id
Sub-question 2: Which employees have salary above their department's average?
  SQL 2: SELECT e.* FROM employees e
         JOIN (SELECT department_id, AVG(salary) AS avg_sal FROM employees GROUP BY department_id) d
           ON e.department_id = d.department_id
         WHERE e.salary > d.avg_sal
Final SQL:
SELECT e.* FROM employees e
JOIN (SELECT department_id, AVG(salary) AS avg_sal FROM employees GROUP BY department_id) d
  ON e.department_id = d.department_id
WHERE e.salary > d.avg_sal

## Your Response
Classification: [SIMPLE or COMPLEX]
[decomposition steps if COMPLEX]
Final SQL:
"""
        response = self._call_llm([{"role": "user", "content": prompt}])
        full_output = response["content"]
        sql = extract_sql(full_output)
        cost = {
            "prompt_tokens": response["prompt_tokens"],
            "completion_tokens": response["completion_tokens"],
        }
        return sql, full_output, cost

    # ------------------------------------------------------------------ #
    #  Agent 3: Refiner                                                    #
    # ------------------------------------------------------------------ #

    def _execute_sql(self, sql: str, db_path: str) -> dict:
        """
        SQL을 SQLite 샌드박스에서 실행하여 결과를 반환한다.

        Returns:
            {
                "success": bool,
                "results": list[tuple],
                "row_count": int,
                "error": str | None,
            }
        """
        conn = None
        try:
            conn = sqlite3.connect(
                f"file:{db_path}?mode=ro",
                uri=True,
                timeout=self.sqlite_timeout,
            )
            conn.execute("PRAGMA query_only = ON;")
            cursor = conn.cursor()
            cursor.execute(sql)
            rows = cursor.fetchall()

            return {
                "success": True,
                "results": rows,
                "row_count": len(rows),
                "error": None,
            }

        except Exception as e:
            return {
                "success": False,
                "results": [],
                "row_count": 0,
                "error": str(e),
                "exception_class": type(e).__name__,
            }
        finally:
            if conn:
                conn.close()

    def _get_refinement_feedback(self, exec_result: dict) -> dict | None:
        """
        실행 결과를 분석하여 Refiner에 전달할 피드백을 결정한다.

        논문 기준 (Appendix A.3):
          - SQL syntax errors
          - Schema illusions (non-existent table/column names)
          - Empty query results
          - 논문 명시 한계: 비어있지 않은 결과이나 의미상 틀린 경우는 미교정

        Returns:
            None                  — 교정 불필요 (실행 성공 + 결과 있음)
            {"error": str,        — 교정 필요
             "exception_class": str,
             "is_empty": bool}
        """
        if not exec_result["success"]:
            return {
                "error": exec_result["error"],
                "exception_class": exec_result.get("exception_class", "Exception"),
                "is_empty": False,
            }

        if exec_result["row_count"] == 0:
            return {
                "error": (
                    "Query executed successfully but returned 0 rows. "
                    "Check filter conditions, WHERE clauses, and JOIN conditions."
                ),
                "exception_class": "EmptyResultError",
                "is_empty": True,
            }

        return None

    def _refine(
        self,
        question: str,
        sql: str,
        feedback: dict,
        pruned_schema: str,
        evidence: str = "",
    ) -> tuple[str, dict]:
        """
        MAC-SQL Refiner: 실행 피드백을 기반으로 SQL을 교정한다.

        논문 기준 (Appendix A.3, B.3):
          - 최대 max_refine_rounds=3회
          - 하드 실패(실행 오류)와 소프트 실패(빈 결과) 모두 처리
          - [SQLite error] + [Exception class] 두 항목을 모두 전달
          - 축소 스키마(pruned_schema)를 사용 (전체 스키마 아님)

        Args:
            feedback: {"error": str, "exception_class": str, "is_empty": bool}

        Returns:
            (교정된 SQL 문자열, {"prompt_tokens": int, "completion_tokens": int})
        """
        error_msg = feedback["error"]
        exc_class = feedback["exception_class"]
        evidence_block = (
            f"\n[External knowledge / hint]\n{evidence.strip()}\n"
            if evidence and evidence.strip() else ""
        )

        prompt = f"""[Instruction]
When executing SQL below, some errors occurred, please fix up SQL based on query and database info. Solve the task step by step if you need to. Using SQL format in the code block, and indicate script type in the code block. When you find an answer, verify the answer carefully.{evidence_block}

[Constraints]
- In 'SELECT <column>', just select needed columns in the question without any unnecessary column or value
- In 'FROM <table>' or 'JOIN <table>', do not include unnecessary table
- If use max or min func, 'JOIN <table>' FIRST, THEN use 'SELECT MAX(<column>)' or 'SELECT MIN(<column>)'
- If use 'ORDER BY <column> ASC|DESC', add 'GROUP BY <column>' before to select distinct values

[Query]
{question}

[Database info]
{pruned_schema}

[old SQL]
```sql
{sql}
```

[SQLite error]
{error_msg}

[Exception class]
{exc_class}

Now please fixup old SQL and generate new SQL again.
[correct SQL]
"""
        response = self._call_llm([{"role": "user", "content": prompt}])
        refined_sql = extract_sql(response["content"])
        cost = {
            "prompt_tokens": response["prompt_tokens"],
            "completion_tokens": response["completion_tokens"],
        }
        return refined_sql, cost
