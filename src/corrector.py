"""
Corrector (Section 4.4.3)
오류 정보 기반 SQL 교정. RQ2: 오류 유형별 전용 교정 지시문 라우팅.
"""

import os
from openai import OpenAI
from src.execution_validator import ValidationResult
from src.semantic_verifier import VerificationResult
from src.openai_retry import chat_completion


# RQ2: 오류 유형별 전용 교정 지시문.
# E1~E8은 ExecutionValidator의 분류 체계와 1:1 대응한다.
# SEMANTIC_MISMATCH는 실행은 성공했으나 NLI 의미 검증이 불일치를 진단한 경우.
TYPED_CORRECTION_GUIDANCE = {
    "E1_SYNTAX": (
        "이 SQL은 문법 오류로 실행되지 못했습니다. "
        "키워드 철자, 괄호·콤마·따옴표 균형, FROM/WHERE/GROUP BY/ORDER BY 절 순서를 점검하세요. "
        "스키마나 의미는 그대로 유지하고 문법 토큰만 최소 수정하세요."
    ),
    "E2_NO_SUCH_TABLE": (
        "참조한 테이블이 스키마에 존재하지 않습니다. "
        "제공된 스키마에서 가장 의미가 가까운 테이블명을 찾아 교체하세요. "
        "대소문자, 단·복수, 약어 차이를 특히 주의하세요. 스키마에 없는 테이블을 새로 만들지 마세요."
    ),
    "E3_NO_SUCH_COLUMN": (
        "참조한 컬럼이 해당 테이블에 존재하지 않습니다. "
        "스키마의 PRAGMA table_info를 떠올려, 각 컬럼이 어느 테이블에 속하는지 다시 확인하고 "
        "필요하다면 올바른 테이블을 JOIN하거나, 컬럼명을 스키마에 존재하는 것으로 교정하세요. "
        "유사 의미 컬럼명(예: name vs full_name)을 우선 후보로 검토하세요."
    ),
    "E4_AMBIGUOUS_COLUMN": (
        "여러 테이블에 같은 이름의 컬럼이 있어 모호합니다. "
        "모든 컬럼 참조를 `테이블별칭.컬럼` 형태로 명시적으로 한정하고, "
        "FROM/JOIN 절의 모든 테이블에 짧은 별칭(alias)을 부여하세요."
    ),
    "E5_TYPE_MISMATCH": (
        "비교·연산하는 두 값의 자료형이 호환되지 않습니다. "
        "리터럴의 따옴표 유무를 확인하고, 필요하면 CAST(... AS INTEGER/REAL/TEXT)로 명시 변환하세요. "
        "날짜는 strftime/date 함수로, 숫자 비교에는 따옴표 없이 사용하세요."
    ),
    "E6_AGGREGATE_ERROR": (
        "집계 함수 사용이 잘못되었습니다. "
        "SELECT 절에 집계 함수와 일반 컬럼이 함께 등장한다면 GROUP BY를 추가하고, "
        "집계 결과로 필터링하려면 WHERE 대신 HAVING을 사용하세요. "
        "GROUP BY 키에는 집계되지 않은 모든 일반 컬럼이 포함되어야 합니다."
    ),
    "E7_EMPTY_RESULT": (
        "SQL은 정상 실행되었으나 결과가 0행입니다. 논리 오류일 가능성이 높습니다. "
        "다음을 차례로 점검하세요: "
        "(1) WHERE 조건이 너무 엄격하지 않은가 (대소문자·공백·LIKE 와일드카드), "
        "(2) JOIN 조건이 잘못되어 매칭이 사라지지 않았는가 (INNER vs LEFT), "
        "(3) NULL 처리(IS NULL / COALESCE)가 필요한가, "
        "(4) 비교 값이 실제 데이터와 일치하는 형태(대소문자·약어)인가. "
        "조건을 한 단계 완화하거나 JOIN 종류를 바꿔 결과가 나오는 형태로 교정하세요."
    ),
    "E8_EXCESSIVE_RESULT": (
        "결과 행 수가 비정상적으로 많습니다(>1000행). 질의 의도에 비해 필터/조인이 부족합니다. "
        "다음을 점검하세요: "
        "(1) JOIN 조건이 누락되어 카테시안 곱이 발생하지 않았는가, "
        "(2) 자연어 질의가 암시하는 WHERE 조건(특정 연도·범주·상위 N)이 빠지지 않았는가, "
        "(3) DISTINCT나 GROUP BY가 필요하지 않은가, "
        "(4) LIMIT 절이 필요한 'top-N' 질의가 아닌가. "
        "누락된 제약을 추가해 의도한 행 수에 맞도록 교정하세요."
    ),
    "SEMANTIC_MISMATCH": (
        "SQL은 정상 실행되었으나, 결과를 자연어로 역번역해 보면 원 질문의 의도와 어긋납니다. "
        "원 질문을 한 줄씩 다시 읽고, 다음을 점검하세요: "
        "(1) SELECT 컬럼이 질문이 묻는 대상과 정확히 일치하는가, "
        "(2) 집계 단위(개수·평균·합계·최대/최소)가 질문과 일치하는가, "
        "(3) 필터 조건이 질문의 모든 한정어를 포함하는가, "
        "(4) 정렬·상위 N 요건이 반영되었는가. "
        "의미 진단(`mismatch_diagnosis`)이 있다면 그 지적을 우선적으로 반영하세요."
    ),
}

# 분류되지 않은 오류에 대한 일반 지시문 (안전망).
GENERIC_CORRECTION_GUIDANCE = (
    "오류 메시지와 의미 진단을 종합해 최소한의 변경으로 SQL을 교정하세요. "
    "스키마와 원 질문의 의도를 우선 따르고, 불필요한 구조 변경은 피하세요."
)


class Corrector:
    """
    Section 4.4.3: 구체적 오류 정보를 포함한 교정 프롬프트로 SQL을 교정한다.

    교정 프롬프트 구조 (Section 4.4.3):
      원래 질의 + 생성된 SQL + 실행 결과 + 감지된 오류 + 의미 일관성 진단
      + (RQ2) 오류 유형별 전용 교정 지시문

    Args:
        config: configs/config.yaml에서 로드된 설정.
        use_typed_prompt: True면 RQ2의 타입별 지시문을, False면 단일 공용 지시문을 사용.
            어블레이션(typed vs generic) 비교 시 False로 설정.
    """

    def __init__(self, config: dict, use_typed_prompt: bool = True):
        self.config = config
        self.client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        self.llm_model = config["llm"]["model"]
        self.use_typed_prompt = use_typed_prompt

    def correct(
        self,
        query: str,
        sql: str,
        validation_result: ValidationResult,
        verification_result: VerificationResult | None,
        schema_context: dict | None = None,
        correction_history: list[dict] | None = None,
        evidence: str = "",
    ) -> str:
        """
        Section 4.4.3: 오류 정보를 기반으로 SQL을 교정한다.

        Args:
            query: 원래 자연어 질의
            sql: 교정 대상 SQL
            validation_result: ExecutionValidator.validate() 결과
            verification_result: SemanticVerifier.verify() 결과 (없을 수 있음)
            schema_context: SchemaLinker.link() 결과 — 스키마 텍스트 포함 시
                            E3_NO_SUCH_COLUMN 교정 품질이 대폭 향상된다.
            correction_history: 이번 질의에서 이전 교정 라운드 기록.
                각 항목: {"round": int, "error_type": str, "original_sql": str,
                          "corrected_sql": str, "semantic_score": float}
                이전 시도와 동일한 실수를 반복하지 않도록 프롬프트에 포함한다.

        Returns:
            교정된 SQL 문자열
        """
        # Section 4.4.3: 교정 프롬프트 구성
        error_info = self._format_error_info(validation_result)
        semantic_info = self._format_semantic_info(verification_result)
        execution_info = self._format_execution_result(validation_result)

        # RQ2: 진단된 오류 유형에 맞는 전용 교정 지시문을 선택한다.
        routed_error_type = self._route_error_type(validation_result, verification_result)
        guidance = self._select_guidance(routed_error_type)

        # 스키마 블록: schema_context가 있으면 프롬프트에 포함 (E3/E2 교정 품질 향상)
        schema_block = ""
        if schema_context:
            schema_text = schema_context.get("schema_text", "")
            if schema_text:
                schema_block = f"\n## Database Schema\n{schema_text}\n"

        # 이전 교정 이력 블록: 반복 실수 방지
        history_block = self._format_correction_history(correction_history or [])

        # Evidence(외부 도메인 지식) 블록 — BIRD 등에서만 제공
        evidence_block = ""
        if evidence and evidence.strip():
            evidence_block = f"\n## External Knowledge / Hint\n{evidence.strip()}\n"

        # Section 4.4.3 + RQ2: 오류 유형별 지시문이 포함된 Corrector 프롬프트
        prompt = f"""You are an expert SQL debugger. Fix the following SQL query based on the error information provided.
{schema_block}{evidence_block}
원래 질의: {query}
생성된 SQL: {sql}
실행 결과: {execution_info}
감지된 오류: {error_info}
의미 일관성 진단: {semantic_info}
{history_block}
[교정 지시 — 오류 유형: {routed_error_type}]
{guidance}

위의 지시에 따라 SQL을 교정하세요. 수정한 부분과 이유를 간략히 설명하세요.

Return the corrected SQL query wrapped in ```sql``` code blocks, followed by a brief explanation."""

        response = chat_completion(
            self.client,
            model=self.llm_model,
            temperature=self.config["llm"]["temperature"],
            max_completion_tokens=self.config["llm"]["max_tokens"],
            messages=[{"role": "user", "content": prompt}],
        )

        result_text = response.choices[0].message.content.strip()

        # SQL 추출
        if "```sql" in result_text:
            corrected_sql = result_text.split("```sql")[1].split("```")[0].strip()
        elif "```" in result_text:
            corrected_sql = result_text.split("```")[1].split("```")[0].strip()
        else:
            # 코드 블록이 없으면 전체 텍스트에서 SQL 추출 시도
            lines = result_text.strip().split("\n")
            sql_lines = []
            for line in lines:
                stripped = line.strip().upper()
                if stripped.startswith(("SELECT", "WITH", "INSERT", "UPDATE", "DELETE",
                                        "CREATE", "DROP", "ALTER", "FROM", "WHERE",
                                        "JOIN", "LEFT", "RIGHT", "INNER", "GROUP",
                                        "ORDER", "HAVING", "LIMIT", "UNION", "EXCEPT",
                                        "INTERSECT", "(")) or sql_lines:
                    sql_lines.append(line)
            corrected_sql = "\n".join(sql_lines).strip() if sql_lines else result_text

        return corrected_sql

    def _route_error_type(
        self,
        validation_result: ValidationResult,
        verification_result: VerificationResult | None,
    ) -> str:
        """
        RQ2: 교정 라우팅 규칙.

        실행 오류(E1~E6)가 있으면 최우선으로 해당 타입을 사용한다.
        실행은 성공했지만 빈/과대 결과면 E7/E8.
        실행과 결과가 모두 정상이지만 의미 검증이 불일치면 SEMANTIC_MISMATCH.
        그 외(분류 실패)는 UNKNOWN으로 폴백한다.
        """
        if validation_result.error_type is not None:
            return validation_result.error_type
        if verification_result is not None and not verification_result.is_consistent:
            return "SEMANTIC_MISMATCH"
        return "UNKNOWN"

    def _select_guidance(self, error_type: str) -> str:
        """RQ2: 오류 유형에 맞는 교정 지시문을 반환한다.

        어블레이션 모드(use_typed_prompt=False)에서는 항상 공용 지시문을 반환한다.
        """
        if not self.use_typed_prompt:
            return GENERIC_CORRECTION_GUIDANCE
        return TYPED_CORRECTION_GUIDANCE.get(error_type, GENERIC_CORRECTION_GUIDANCE)

    def _format_error_info(self, validation_result: ValidationResult) -> str:
        """오류 정보를 포맷한다."""
        if validation_result.error_type is None:
            return "오류 없음"

        parts = [validation_result.error_type]
        if validation_result.error_message:
            parts.append(f"- {validation_result.error_message}")
        if validation_result.is_empty:
            parts.append("- 결과가 비어있음 (논리 오류 가능성)")
        if validation_result.is_excessive:
            parts.append(
                f"- 결과가 과대함 ({validation_result.row_count}행, 필터/조인 누락 가능성)"
            )
        return " ".join(parts)

    def _format_semantic_info(self, verification_result: VerificationResult | None) -> str:
        """의미 일관성 진단 정보를 포맷한다."""
        if verification_result is None:
            return "의미 검증 미수행"
        if verification_result.is_consistent:
            return f"일치 (score={verification_result.similarity_score:.3f})"
        parts = [
            f"불일치 (score={verification_result.similarity_score:.3f}, threshold={self.config['correction']['semantic_threshold']})"
        ]
        if verification_result.mismatch_diagnosis:
            parts.append(f"진단: {verification_result.mismatch_diagnosis}")
        return "\n".join(parts)

    def _format_correction_history(self, history: list[dict]) -> str:
        """
        이전 교정 라운드 기록을 프롬프트 블록으로 변환한다.

        Fix 3 (Phase 1 분석 반영):
          - 직전 1라운드만 노출 (이전 시도 전부 보여주면 LLM이 가까운 정답도 회피)
          - "완전히 다른 접근법" → "동일한 실수 반복 금지"로 문구 순화
          - 실행 오류 유형(E1~E6)은 이미 어떤 오류인지 알려주므로 상세 재서술 대신 간결 요약
        """
        if not history:
            return ""

        # 직전 라운드만 사용 (너무 많은 이력은 오히려 과도한 제약이 됨)
        entry = history[-1]
        round_num = entry.get("round", "?")
        error_type = entry.get("error_type", "UNKNOWN")
        prev_sql = entry.get("original_sql", "")
        score = entry.get("semantic_score", None)
        score_str = f", semantic_score={score:.3f}" if score is not None else ""

        lines = [
            "\n## 이전 시도 (참고용)",
            f"직전 라운드 {round_num}에서 시도한 SQL은 '{error_type}' 문제를 보였습니다{score_str}:",
            f"```sql\n{prev_sql}\n```",
            "이 SQL의 **동일한 실수를 반복하지 마세요**. 단, 올바른 부분은 유지해도 됩니다.",
        ]
        return "\n".join(lines) + "\n"

    def _format_execution_result(self, validation_result: ValidationResult) -> str:
        """실행 결과를 포맷한다."""
        if not validation_result.success:
            return f"실행 실패: {validation_result.error_message}"
        if validation_result.is_empty:
            return "실행 성공, 결과 없음 (0행)"
        # 결과 샘플 표시 (최대 5행)
        sample_rows = validation_result.results[:5]
        header = ", ".join(validation_result.column_names) if validation_result.column_names else ""
        rows_str = "\n".join(str(row) for row in sample_rows)
        suffix = f"\n... (총 {validation_result.row_count}행)" if validation_result.row_count > 5 else ""
        return f"실행 성공 ({validation_result.row_count}행)\n컬럼: {header}\n{rows_str}{suffix}"
