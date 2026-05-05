"""
Guardrails (Phase 3 — Section 5)
입력 검증 + 출력 검증으로 파이프라인 안전성을 보장한다.

InputGuardrails:
  - 빈 쿼리 / 너무 짧은 쿼리 거부
  - 쿼리 최대 길이 제한 (500자)
  - 위험 SQL 키워드 주입 시도 감지

OutputGuardrails:
  - 결과 행 수 상한선 적용 (MAX_ROWS)
  - NLI threshold 미달 + 교정 루프 소진 시 경고 플래그

GuardrailsError:
  - InputGuardrails.validate() 실패 시 raise
"""

import re
from dataclasses import dataclass


# ── 예외 ─────────────────────────────────────────────────────────────────────

class GuardrailsError(Exception):
    """입력 Guardrails 위반 시 발생."""
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


# ── 입력 Guardrails ───────────────────────────────────────────────────────────

class InputGuardrails:
    """
    자연어 질의가 파이프라인에 진입하기 전에 유효성을 검사한다.

    검사 항목:
      1. 빈 쿼리 / 너무 짧은 쿼리 (< MIN_LENGTH)
      2. 최대 길이 초과 (> MAX_LENGTH)
      3. SQL 주입 패턴 감지 (; + DML/DDL 키워드)
      4. 반복 문자 / 의미 없는 입력
    """

    MIN_LENGTH = 3
    MAX_LENGTH = 500

    # 세미콜론 + DML/DDL (SQL injection 시도)
    _SQL_INJECTION_PATTERN = re.compile(
        r";\s*(drop|delete|insert|update|create|alter|truncate|exec|execute)\b",
        re.IGNORECASE,
    )

    # 단일 문자 반복 (예: "aaaaaaaa")
    _REPEATED_CHAR_PATTERN = re.compile(r"(.)\1{9,}")

    def validate(self, query: str) -> str:
        """
        질의 문자열을 검사하고 정제된 질의를 반환한다.

        Args:
            query: 사용자가 입력한 자연어 질의

        Returns:
            공백 정제 후 질의 문자열

        Raises:
            GuardrailsError: 검사 실패 시
        """
        if not isinstance(query, str):
            raise GuardrailsError("질의는 문자열이어야 합니다.")

        cleaned = query.strip()

        if len(cleaned) < self.MIN_LENGTH:
            raise GuardrailsError(
                f"질의가 너무 짧습니다 (최소 {self.MIN_LENGTH}자 이상)."
            )

        if len(cleaned) > self.MAX_LENGTH:
            raise GuardrailsError(
                f"질의가 너무 깁니다 (최대 {self.MAX_LENGTH}자). "
                f"현재 길이: {len(cleaned)}자."
            )

        if self._SQL_INJECTION_PATTERN.search(cleaned):
            raise GuardrailsError(
                "SQL 명령어가 포함된 입력은 허용되지 않습니다."
            )

        if self._REPEATED_CHAR_PATTERN.search(cleaned):
            raise GuardrailsError(
                "의미 있는 질의를 입력해 주세요."
            )

        return cleaned


# ── 출력 Guardrails ───────────────────────────────────────────────────────────

@dataclass
class OutputGuardrailsResult:
    """출력 Guardrails 검사 결과.

    §6.2 표 10 운영 가이드라인의 6 케이스 + §6.2.1 표 11 페르소나 시나리오의
    *세분화된 권장 액션* 을 시연 시스템에 직접 반영한다.
    """
    rows_truncated: bool = False      # MAX_ROWS 초과로 잘림
    original_row_count: int = 0       # 잘리기 전 행 수
    # 후방 호환: 기존 단일 경고 플래그 유지
    low_confidence_warning: bool = False  # NLI 신뢰도 낮음 경고
    warning_message: str = ""         # 사용자에게 보여줄 경고 메시지

    # §6.2 운영 가이드라인 — 권장 액션 명시
    # action ∈ {auto_execute, auto_with_note, user_warning, hitl_triage,
    #            retry_auto, empty_result_info, clarification_request}
    action: str = "auto_execute"
    action_severity: str = "info"   # 'info' | 'success' | 'warning' | 'error'
    action_title: str = ""           # 사용자에게 보여줄 짧은 라벨
    action_detail: str = ""          # 권장 행동 자세한 설명
    case_id: str = ""                # 표 10 케이스 ID (예: "C2", "C3")
    persona_scenario: str = ""       # 표 11 페르소나 시나리오 ID (예: "S2")


class OutputGuardrails:
    """
    파이프라인 결과가 사용자에게 반환되기 전에 후처리한다.

    §6.2 표 10 운영 가이드라인 — 6 케이스 분기를 직접 구현한다.

    | # | 실행 결과 | NLI | SQL 신뢰도 | 권장 액션 | UI 표현 |
    |---|---|---|---|---|---|
    | C1 | 정상 | 일치 (≥θ) | 높음 (≥0.7) | auto_execute       | "확신도 높음" 배지 (success) |
    | C2 | 정상 | 불일치 (<θ) | 높음 (≥0.7) | hitl_triage        | "의도 풀이 확인" 경고 + 백번역 동시 표시 |
    | C3 | 정상 | 불일치 (<θ) | 낮음 (<0.7) | retry_auto         | "교정 진행됨" 안내 (loop가 이미 시도) |
    | C4 | 빈 결과 | 불일치 | (무관) | retry_auto         | "조건 완화 시도" |
    | C5 | 빈 결과 | 일치 | (무관) | empty_result_info  | "조건에 맞는 데이터 없음" 안내 |
    | C6 | 실행 실패 | (무관) | (무관) | retry_auto         | "재생성 진행됨" 안내 |

    추가로 신뢰도 보통(0.65~0.7) + NLI 통과 → user_warning ("확신도 보통")
    질의 자체가 매우 모호 (NLI<0.3 AND conf<0.5) → clarification_request
    """

    MAX_ROWS = 1000
    CONF_THRESHOLD_HIGH = 0.70
    CONF_THRESHOLD_LOW = 0.50
    NLI_VERY_LOW = 0.30  # 사용자 재질문 트리거

    def __init__(self, semantic_threshold: float = 0.75):
        self.semantic_threshold = semantic_threshold

    def apply(
        self,
        results: list[tuple],
        sql_confidence: float,
        nli_score: float,
        correction_rounds: int,
        max_rounds: int,
        exec_success: bool = True,
    ) -> tuple[list[tuple], OutputGuardrailsResult]:
        """결과에 Guardrails 적용 + 운영 가이드라인 표 10의 권장 액션 결정.

        Args:
            results:           SQL 실행 결과 행 리스트
            sql_confidence:    SQL 생성 신뢰도 (0~1)
            nli_score:         NLI ICS (0~1)
            correction_rounds: 실제 교정 횟수
            max_rounds:        최대 교정 횟수 (K)
            exec_success:      마지막 실행이 정상 통과했는가
        """
        gr = OutputGuardrailsResult(original_row_count=len(results))

        # 1. 행 수 제한
        if len(results) > self.MAX_ROWS:
            results = results[: self.MAX_ROWS]
            gr.rows_truncated = True

        # 2. §6.2 표 10 케이스 분기
        is_empty = len(results) == 0
        nli_pass = nli_score >= self.semantic_threshold
        conf_high = sql_confidence >= self.CONF_THRESHOLD_HIGH

        loop_exhausted = (correction_rounds >= max_rounds) and (max_rounds > 0)

        # C6: 실행 실패 (모든 라운드 소진했음에도)
        if not exec_success:
            gr.case_id = "C6"
            gr.action = "retry_auto"
            gr.action_severity = "error"
            gr.action_title = "재생성 시도 실패"
            exhausted_note = " (최대 교정 횟수 소진)" if loop_exhausted else ""
            gr.action_detail = (
                f"교정 루프 {correction_rounds}/{max_rounds}회 시도 후에도 실행 실패{exhausted_note}. "
                "질의를 다시 확인하시거나 더 명확하게 입력해 주세요."
            )
        # C5: 빈 결과 + NLI 통과 → 진짜 없음
        elif is_empty and nli_pass:
            gr.case_id = "C5"
            gr.action = "empty_result_info"
            gr.action_severity = "info"
            gr.action_title = "조건에 맞는 데이터가 없습니다"
            gr.action_detail = (
                "질의의 의도는 정확하게 해석되었지만, 데이터베이스에 해당 "
                "조건을 만족하는 행이 존재하지 않습니다."
            )
        # C4: 빈 결과 + NLI 불일치
        elif is_empty and not nli_pass:
            gr.case_id = "C4"
            gr.action = "retry_auto"
            gr.action_severity = "warning"
            gr.action_title = "조건이 너무 좁을 수 있습니다"
            gr.action_detail = (
                "결과가 0건이고 의미 검증도 일치하지 않습니다. 필터 조건을 "
                "완화하거나 질의를 다시 작성해 보세요."
            )
        # 매우 모호한 질의 — clarification_request
        elif nli_score < self.NLI_VERY_LOW and sql_confidence < self.CONF_THRESHOLD_LOW:
            gr.case_id = "Cq"
            gr.action = "clarification_request"
            gr.action_severity = "warning"
            gr.action_title = "질의를 더 명확하게 해주세요"
            gr.action_detail = (
                "어떤 항목·기간·범위의 데이터인지 구체적으로 입력해 주세요. "
                "예시: '이번 달 본인 급여', '부서별 평균 급여', '재직 중인 직원 수' 등."
            )
        # C2: 정상 + NLI 불일치 + 신뢰도 높음 → HITL 트리아지
        elif nli_pass is False and conf_high:
            gr.case_id = "C2"
            gr.action = "hitl_triage"
            gr.action_severity = "warning"
            gr.action_title = "의도 풀이 확인이 권장됩니다"
            gr.action_detail = (
                f"실행은 통과했지만 의미 검증 점수(ICS={nli_score:.2f})가 임계값"
                f"({self.semantic_threshold})에 미치지 못합니다. "
                "역번역된 의도 풀이가 원래 질문과 같은지 확인해 주세요. "
                "EIED 분석에 따르면 이 시나리오의 약 2/3가 실제 오답입니다."
            )
        # C3: 정상 + NLI 불일치 + 신뢰도 낮음
        elif nli_pass is False and not conf_high:
            gr.case_id = "C3"
            gr.action = "retry_auto"
            gr.action_severity = "warning"
            gr.action_title = "재생성 시도됨"
            gr.action_detail = (
                f"의미 검증·SQL 신뢰도 모두 낮아 자동 교정({correction_rounds}회) "
                "을 시도했습니다. 결과를 신중히 검토해 주세요."
            )
        # 신뢰도 보통(0.5~0.7) + NLI 통과 → 경고
        elif nli_pass and not conf_high:
            gr.case_id = "C1m"
            gr.action = "user_warning"
            gr.action_severity = "warning"
            gr.action_title = "확신도 보통"
            gr.action_detail = (
                f"의미 검증은 통과했지만 SQL 신뢰도(={sql_confidence:.2f})가 보통 수준입니다. "
                "결과를 한 번 검토하시기 바랍니다."
            )
        # C1: 정상 + NLI 통과 + 신뢰도 높음 → 자동 실행
        else:
            gr.case_id = "C1"
            gr.action = "auto_execute"
            gr.action_severity = "success"
            gr.action_title = "확신도 높음"
            gr.action_detail = (
                f"의미 검증과 SQL 신뢰도 모두 양호합니다 "
                f"(ICS={nli_score:.2f}, conf={sql_confidence:.2f})."
            )

        # 후방 호환: 케이스 C2/C3/C4/Cq 시 low_confidence_warning 플래그 세팅
        if gr.action in ("hitl_triage", "retry_auto", "user_warning", "clarification_request"):
            gr.low_confidence_warning = True
            gr.warning_message = gr.action_detail

        return results, gr
