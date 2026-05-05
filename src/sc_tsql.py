"""
SC-TSQL 메인 파이프라인 (Section 4 전체)
Schema Linker → SQL Generator → Self-Correction Loop → Result Explainer

Phase 2 추가:
- 단계별 latency 추적 (stage_latency)
- SQL 생성 신뢰도 기록 (sql_confidence)
- Cross-encoder Reranking: SemanticVerifier의 NLI 모델을 SQLGenerator에 공유

Phase 3 추가:
- OutputGuardrails: 결과 행 수 제한 + 저신뢰 경고
- conversation_history: 멀티턴 대화 히스토리 SQL 생성 프롬프트 반영
"""

import sqlite3
import time
from dataclasses import dataclass, field
from typing import Callable

from src.schema_linker import SchemaLinker
from src.sql_generator import SQLGenerator
from src.execution_validator import ExecutionValidator, ValidationResult
from src.semantic_verifier import SemanticVerifier, VerificationResult
from src.corrector import Corrector
from src.result_explainer import ResultExplainer
from src.guardrails import OutputGuardrails, OutputGuardrailsResult
from src.value_retriever import ValueRetriever


@dataclass
class AblationFlags:
    """어블레이션 실험용 구성요소 비활성화 플래그."""
    disable_schema_linker: bool = False
    disable_execution_validator: bool = False
    disable_semantic_verifier: bool = False
    disable_correction_loop: bool = False
    # RQ2 어블레이션: True면 오류 유형별 지시문 대신 단일 공용 지시문을 사용한다.
    use_generic_correction_prompt: bool = False
    # Phase 2 어블레이션: True면 few-shot cross-encoder reranking을 비활성화한다.
    disable_reranking: bool = False
    # Improvement #3 어블레이션: True면 Corrector 프롬프트에 이전 라운드 교정 이력을 포함하지 않는다.
    disable_correction_history: bool = False
    # Value retrieval 어블레이션: True면 DB content 기반 값 매칭을 건너뛴다.
    disable_value_retrieval: bool = False
    # Self-consistency 어블레이션: True면 k=1로 강제(단일 생성)
    disable_self_consistency: bool = False
    # RQ1 순수 어블레이션: True면 NLI 검증 자체는 수행(지표 보고용)하되,
    # 교정 트리거에서는 NLI 불일치를 사용하지 않는다. reranker/지표 계산은 유지.
    # → "NLI의 교정 기여도"만 분리 측정. disable_semantic_verifier와의 차이:
    #   disable_semantic_verifier=True는 NLI 모델 자체를 건드리지 않고 결과를 항상 '일치'로 둠
    #   (reranker=None으로 설정되어 SQL 생성도 달라짐 → 순수 NLI 기여 측정 불가).
    disable_nli_correction_trigger: bool = False


@dataclass
class SCTSQLResult:
    """SC-TSQL 파이프라인 실행 결과."""
    query: str
    final_sql: str
    results: list[tuple] = field(default_factory=list)
    column_names: list[str] = field(default_factory=list)
    correction_history: list[dict] = field(default_factory=list)
    explanation: str = ""
    latency: float = 0.0                  # 총 소요 시간 (초)
    total_correction_rounds: int = 0      # 실제 교정 횟수
    final_validation: ValidationResult | None = None
    final_verification: VerificationResult | None = None
    # Phase 2: 단계별 latency 및 신뢰도
    stage_latency: dict = field(default_factory=dict)
    sql_confidence: float = 0.5           # SQL 생성 신뢰도 (logprob 기반, 0~1)
    # Phase 3: Guardrails 결과
    guardrails: OutputGuardrailsResult | None = None
    # 스키마 링커가 선택한 테이블/컬럼 (UI schema_context용)
    schema_context: dict = field(default_factory=dict)


class SCTSQL:
    """
    SC-TSQL 메인 파이프라인 (Section 4).

    전체 흐름:
      1. SchemaLinker.link()       — Section 4.2
      2. SQLGenerator.generate()   — Section 4.3
      3. Self-correction loop      — Section 4.4 (최대 K=3회)
         a. ExecutionValidator.validate()    — Section 4.4.1
         b. SemanticVerifier.verify()        — Section 4.4.2
         c. Corrector.correct()              — Section 4.4.3 (오류/불일치 시)
      4. ResultExplainer.explain()  — Section 4.5

    Phase 2 변경:
      - SemanticVerifier를 SQLGenerator보다 먼저 초기화하여 NLI 모델을
        few-shot reranker로 공유한다 (추가 모델 로딩 없이 reranking 구현).
      - SCTSQLResult에 stage_latency, sql_confidence 필드 추가.

    Phase 3 변경:
      - OutputGuardrails: run() 결과에 행 수 제한 + 저신뢰 경고 적용.
      - run()에 conversation_history 파라미터 추가 (멀티턴 컨텍스트).
    """

    def __init__(
        self,
        db_path: str,
        config: dict,
        few_shot_examples: list[dict] | None = None,
        ablation: AblationFlags | None = None,
    ):
        """
        Args:
            db_path: SQLite 데이터베이스 파일 경로
            config: configs/config.yaml에서 로드된 설정
            few_shot_examples: SQL Generator용 few-shot 후보 리스트
            ablation: 어블레이션 플래그 (None이면 모든 구성요소 활성화)
        """
        self.db_path = db_path
        self.config = config
        self.ablation = ablation or AblationFlags()
        self.max_rounds = config["correction"]["max_rounds"]  # K=3, Section 4.4

        # 교정 루프 비활성화 시 max_rounds=0으로 강제
        if self.ablation.disable_correction_loop:
            self.max_rounds = 0

        # Phase 2: SemanticVerifier를 먼저 초기화하여 NLI 모델을 reranker로 공유
        self.execution_validator = ExecutionValidator()
        self.semantic_verifier = SemanticVerifier(config)

        # Phase 2: disable_reranking 플래그 또는 disable_semantic_verifier 시 reranker=None
        reranker = None
        if (
            not self.ablation.disable_reranking
            and not self.ablation.disable_semantic_verifier
        ):
            reranker = self.semantic_verifier.nli_model

        if not self.ablation.disable_schema_linker:
            self.schema_linker = SchemaLinker(db_path, config)
        else:
            self.schema_linker = None

        self.sql_generator = SQLGenerator(config, few_shot_examples, reranker=reranker)
        self.corrector = Corrector(
            config,
            use_typed_prompt=not self.ablation.use_generic_correction_prompt,
        )
        self.result_explainer = ResultExplainer(config)

        # Phase 3: OutputGuardrails
        semantic_threshold = config["correction"].get("semantic_threshold", 0.75)
        self.output_guardrails = OutputGuardrails(semantic_threshold=semantic_threshold)

        # Value Retriever (DB content 기반 값 매칭)
        if not self.ablation.disable_value_retrieval:
            self.value_retriever = ValueRetriever(db_path)
        else:
            self.value_retriever = None

    def _self_consistency_select(
        self, candidates: list[dict]
    ) -> tuple[dict, dict]:
        """k개 SQL 후보 중 결과 핑거프린트 다수결로 1개를 선택한다.

        선택 절차:
          1) 빈/syntax-fail 후보는 즉시 제외.
          2) 각 후보를 ExecutionValidator로 안전 실행 → 결과 행 정렬 후 hash로 핑거프린트 산출.
          3) 핑거프린트 빈도가 가장 높은 그룹의 첫 후보를 선택.
          4) 모두 실패하면 confidence가 가장 높은 원 후보를 fallback.

        Wang et al. (2022) Self-Consistency 방식의 SQL 변형:
          텍스트 동률 비교가 아니라 *실행 결과 동치성*으로 의미 다수결.

        Returns:
            (chosen_candidate, summary_dict). summary는 _emit("self_consistency", ...)
            이벤트 페이로드로 사용된다.
        """
        import hashlib

        if not candidates:
            return {"sql": "", "confidence": 0.0}, {"k": 0, "valid": 0, "groups": []}

        valid: list[tuple[dict, ValidationResult, str]] = []
        for c in candidates:
            sql = (c.get("sql") or "").strip()
            if not sql:
                continue
            try:
                vr = self.execution_validator.validate(sql, self.db_path)
            except Exception:
                continue
            if not vr.success:
                continue
            # 결과 핑거프린트: 행을 정렬 후 직렬화하여 hash. 컬럼 순서·이름 무시 위해
            # 각 행을 정렬된 튜플로, 그 뒤 전체 행을 정렬해 안정화.
            try:
                rows = vr.results or []
                # 각 row의 element를 str로 정규화 후 정렬(순서 무관 비교).
                norm = sorted(tuple(sorted(map(str, r))) for r in rows)
                fp = hashlib.sha256(repr(norm).encode("utf-8")).hexdigest()[:16]
            except Exception:
                fp = "exec_ok_unhashable"
            valid.append((c, vr, fp))

        if not valid:
            # fallback: confidence 최댓값
            best = max(candidates, key=lambda x: x.get("confidence", 0.0))
            return best, {
                "k": len(candidates), "valid": 0,
                "groups": [], "selector": "fallback_confidence",
            }

        # 핑거프린트 그룹화
        groups: dict[str, list[tuple[dict, ValidationResult]]] = {}
        for c, vr, fp in valid:
            groups.setdefault(fp, []).append((c, vr))
        # 빈도 내림차순, 동률시 평균 confidence 높은 쪽
        ranked = sorted(
            groups.items(),
            key=lambda kv: (
                len(kv[1]),
                sum(c.get("confidence", 0.0) for c, _ in kv[1]) / len(kv[1]),
            ),
            reverse=True,
        )
        winner_fp, winner_members = ranked[0]
        chosen = winner_members[0][0]
        summary = {
            "k": len(candidates),
            "valid": len(valid),
            "winner_votes": len(winner_members),
            "groups": [{"fp": fp, "votes": len(m)} for fp, m in ranked[:3]],
            "selector": "majority_vote_by_result",
        }
        return chosen, summary

    def _fallback_schema_context(self) -> dict:
        """스키마 링커 비활성화 시 전체 스키마를 직접 읽어 반환한다."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
        )
        tables = [row[0] for row in cursor.fetchall()]

        all_columns = {}
        fk_list = []
        schema_lines = []
        for table in tables:
            cursor.execute(f"PRAGMA table_info(`{table}`);")
            cols = [col[1] for col in cursor.fetchall()]
            all_columns[table] = cols

            col_defs = ", ".join(f"{c} TEXT" for c in cols)
            schema_lines.append(f"CREATE TABLE {table} ({col_defs});")

            cursor.execute(f"PRAGMA foreign_key_list(`{table}`);")
            for fk in cursor.fetchall():
                fk_list.append({
                    "from": f"{table}.{fk[3]}",
                    "to": f"{fk[2]}.{fk[4]}",
                })

        conn.close()
        return {
            "tables": tables,
            "columns": all_columns,
            "foreign_keys": fk_list,
            "schema_text": "\n\n".join(schema_lines),
        }

    def run(
        self,
        query: str,
        conversation_history: list[dict] | None = None,
        on_event: Callable[[str, dict], None] | None = None,
        evidence: str = "",
    ) -> SCTSQLResult:
        """
        Section 4: 전체 파이프라인을 실행한다.

        Args:
            query: 자연어 질의
            conversation_history: 이전 대화 이력 (Phase 3 멀티턴).
                각 항목: {"question": str, "sql": str, "explanation": str}

        Returns:
            SCTSQLResult: SQL, 결과, 교정 이력, 설명, 지연시간 포함
        """
        total_start = time.time()
        stage_latency = {}
        correction_history = []

        def _emit(event: str, data: dict) -> None:
            if on_event is not None:
                on_event(event, data)

        # 추론 토큰을 흘려보내는 단일 채널. sc_tsql은 단계 헤더(예: "[교정 라운드 1]")를
        # 토큰처럼 직접 emit해 시연 화면에서 단계가 자연스럽게 구분되도록 한다.
        def _emit_reasoning(text: str) -> None:
            if on_event is not None and text:
                on_event("reasoning_chunk", {"text": text})

        on_token: Callable[[str], None] | None = _emit_reasoning if on_event is not None else None

        # Step 1: Schema Linking (Section 4.2)
        _emit("step", {"stage": "schema_link"})
        t0 = time.time()
        if self.schema_linker is not None:
            schema_context = self.schema_linker.link(query)
        else:
            schema_context = self._fallback_schema_context()
        stage_latency["schema_linking"] = round(time.time() - t0, 3)

        # Step 1.5: Value Retrieval — 쿼리 내 값 후보를 DB 실제 값과 매칭
        value_hints = ""
        if self.value_retriever is not None:
            t0 = time.time()
            try:
                vr_result = self.value_retriever.retrieve(query, schema_context)
                value_hints = vr_result.get("prompt_block", "")
                stage_latency["value_retrieval"] = round(time.time() - t0, 3)
                _emit("value_hints", {
                    "candidates": vr_result.get("candidates_extracted", []),
                    "n_matches": len(vr_result.get("matches", {})),
                })
            except Exception as e:
                stage_latency["value_retrieval"] = round(time.time() - t0, 3)
                # 값 검색 실패는 파이프라인 차단 사유 아님
                import logging
                logging.getLogger(__name__).warning("value retrieval failed: %s", e)

        # Step 2: SQL Generation (Section 4.3)
        _emit("step", {"stage": "sql_generating"})
        t0 = time.time()

        # Self-consistency 설정: k>=2이고 streaming 시연이 아니면 다중 후보 생성
        # → 결과 핑거프린트 다수결로 단일 SQL을 선택한다 (Wang et al. 2022 SC).
        sc_cfg = self.config.get("self_consistency", {}) or {}
        sc_k = int(sc_cfg.get("k", 1))
        if self.ablation.disable_self_consistency:
            sc_k = 1
        # 시연 폴리시: on_event가 연결돼 있으면 SQL 생성 LLM 호출을 streaming으로
        # 돌려 CoT(추론 과정) 토큰을 'reasoning_chunk' 이벤트로 실시간 전송한다.
        # ChatGPT 스타일의 점진적 표시를 위해 사용. SC(k>=2)에서는 후보 다수결로
        # 단일 SQL을 정하므로 토큰 스트리밍이 의미 없어 끄고 단계 헤더만 표시한다.
        gen_streaming_token = on_token if sc_k <= 1 else None
        if on_token is not None:
            _emit_reasoning("\n**[1단계] SQL 초안 작성 — 의도 풀이 → 스키마 선택 → SQL 작성**\n\n")

        if sc_k >= 2:
            # Self-consistency 경로: k개 후보 생성 → 실행 → 결과 핑거프린트 다수결
            candidates = self.sql_generator.generate_candidates(
                query, schema_context,
                k=sc_k,
                conversation_history=conversation_history or [],
                evidence=evidence,
                value_hints=value_hints,
            )
            chosen, sc_summary = self._self_consistency_select(candidates)
            current_sql = chosen["sql"]
            sql_confidence = chosen["confidence"]
            _emit("self_consistency", sc_summary)
        else:
            gen_result = self.sql_generator.generate(
                query, schema_context,
                conversation_history=conversation_history or [],
                evidence=evidence,
                value_hints=value_hints,
                on_token=gen_streaming_token,
            )
            current_sql = gen_result["sql"]
            sql_confidence = gen_result["confidence"]
        stage_latency["sql_generation"] = round(time.time() - t0, 3)
        _emit("sql_generated", {"sql": current_sql, "confidence": round(sql_confidence, 4)})

        # Step 3: Self-Correction Loop (Section 4.4, 최대 K회)
        validation_result = None
        verification_result = None
        prev_error_type = None  # 연속 동일 오류 감지용

        for round_num in range(1, self.max_rounds + 1):
            t0 = time.time()

            # 실행 검증(Section 4.4.1) + 의미 검증(Section 4.4.2)을 병렬로 실행한다.
            # 두 단계는 입력만 공유(쿼리, SQL)하고 서로 의존하지 않으므로 안전하게 병렬화 가능.
            # NLI inference(보통 0.5-2s) + LLM 백번역(0.3-1s)이 직렬 누적되던 것을 단축한다.
            _emit("step", {"stage": "validating", "round": round_num})
            _emit("step", {"stage": "verifying", "round": round_num})

            def _run_validation() -> ValidationResult:
                if self.ablation.disable_execution_validator:
                    return ValidationResult(
                        success=True, results=[], column_names=[],
                        error_type=None, error_message=None,
                        is_empty=False, is_excessive=False, row_count=0,
                    )
                return self.execution_validator.validate(current_sql, self.db_path)

            # 검증·의미 검증의 데이터 의존성 처리:
            # LLM 자기 비평이 *실행 결과 미리보기* 를 컨텍스트로 받으면 더 정확하므로
            # 실행 검증을 먼저 끝낸 뒤 의미 검증에 결과를 전달한다. 단, 응답 시간 영향을
            # 최소화하기 위해 실행 검증은 병렬로 백번역과 함께 진행 가능하지만 본 구현은
            # 단순화를 위해 실행 → 의미 순으로 직렬화한다 (비용: NLI 단독 대비 +2~3s).
            if self.ablation.disable_execution_validator:
                validation_result = ValidationResult(
                    success=True, results=[], column_names=[],
                    error_type=None, error_message=None,
                    is_empty=False, is_excessive=False, row_count=0,
                )
            else:
                validation_result = self.execution_validator.validate(current_sql, self.db_path)

            if self.ablation.disable_semantic_verifier:
                verification_result = VerificationResult(
                    back_translation="",
                    similarity_score=1.0,
                    is_consistent=True,
                    mismatch_diagnosis=None,
                )
            else:
                if on_token is not None:
                    _emit_reasoning(
                        f"\n\n**[2단계 · 라운드 {round_num}] 의미 검증 — 실행 결과·스키마로 의도 일치 자기비평**\n\n"
                    )
                verification_result = self.semantic_verifier.verify(
                    query,
                    current_sql,
                    schema_text=schema_context.get("schema_text", "") if isinstance(schema_context, dict) else "",
                    result_preview=validation_result.results,
                    column_names=validation_result.column_names,
                    on_token=on_token,
                )

            _emit("validated", {
                "success": validation_result.success,
                "error_type": validation_result.error_type,
            })
            _emit("verified", {
                "score": round(verification_result.similarity_score, 4),
                "is_consistent": verification_result.is_consistent,
                "back_translation": verification_result.back_translation,
            })

            # 교정 필요 여부 판단 (Fix 1·2: sql_confidence + NLI 트리거 비활성 옵션 반영)
            needs_correction = self._needs_correction(
                validation_result, verification_result,
                sql_confidence=sql_confidence,
            )

            if not needs_correction:
                stage_latency[f"correction_round_{round_num}"] = round(time.time() - t0, 3)
                break

            # Section 4.4.3: 교정
            error_type = validation_result.error_type or "SEMANTIC_MISMATCH"

            # 연속 동일 오류(E3/E2)가 반복되면 교정 불가로 판단하고 조기 종료
            # (같은 지시문으로 재시도해도 개선 불가 — 실험 데이터에서 11회 패턴 확인)
            if (
                error_type == prev_error_type
                and error_type in ("E3_NO_SUCH_COLUMN", "E2_NO_SUCH_TABLE")
            ):
                stage_latency[f"correction_round_{round_num}"] = round(time.time() - t0, 3)
                break

            prev_error_type = error_type
            _emit("step", {"stage": "correcting", "round": round_num})
            correction_entry = {
                "round": round_num,
                "error_type": error_type,
                "original_sql": current_sql,
                "validation_success": validation_result.success,
                "semantic_score": verification_result.similarity_score,
            }

            if on_token is not None:
                _emit_reasoning(
                    f"\n\n**[3단계 · 라운드 {round_num}] 교정 — 오류 유형 `{error_type}` 전용 지시문으로 SQL 재생성**\n\n"
                )
            corrected_sql = self.corrector.correct(
                query, current_sql, validation_result, verification_result,
                schema_context=schema_context,
                correction_history=(
                    [] if self.ablation.disable_correction_history else correction_history
                ),
                evidence=evidence,
                value_hints=value_hints,
                on_token=on_token,
            )

            # Fix A: Rollback — 교정이 원본보다 열화되면 원본 유지.
            # Phase 2 분석에서 교정 기여 0%, 교정 시도 4건 전부 최종 실패 확인.
            # → 교정을 시도하되, 결과가 나쁘면 되돌려 "함부로 망가뜨리지 않음"을 보장.
            accepted_sql, rollback_info = self._validate_correction(
                original_sql=current_sql,
                corrected_sql=corrected_sql,
                original_validation=validation_result,
                original_verification=verification_result,
                query=query,
            )

            correction_entry["corrected_sql"] = corrected_sql
            correction_entry["accepted_sql"] = accepted_sql
            correction_entry["rolled_back"] = rollback_info["rolled_back"]
            correction_entry["rollback_reason"] = rollback_info.get("reason", "")
            correction_history.append(correction_entry)
            _emit("corrected", {
                "round": round_num,
                "error_type": error_type,
                "original_sql": correction_entry["original_sql"],
                "corrected_sql": corrected_sql,
                "accepted_sql": accepted_sql,
                "rolled_back": rollback_info["rolled_back"],
                "semantic_score": round(verification_result.similarity_score, 4),
                "validation_success": False,
            })

            # 롤백 시엔 동일한 원본으로 다음 라운드 재시도해도 의미 없으므로 루프 종료
            if rollback_info["rolled_back"]:
                stage_latency[f"correction_round_{round_num}"] = round(time.time() - t0, 3)
                current_sql = accepted_sql
                break

            current_sql = accepted_sql
            stage_latency[f"correction_round_{round_num}"] = round(time.time() - t0, 3)

        # 최종 실행 (교정 후 결과 갱신)
        if validation_result is None or correction_history:
            validation_result = self.execution_validator.validate(current_sql, self.db_path)

        # Step 4: Result Explanation (Section 4.5)
        results = validation_result.results if validation_result.success else []
        column_names = validation_result.column_names if validation_result.success else []

        _emit("step", {"stage": "explaining"})
        t0 = time.time()
        if on_token is not None:
            _emit_reasoning("\n\n**[4단계] 결과 설명 — 비전문가용 자연어 답변 정리**\n\n")
        explanation = self.result_explainer.explain(
            query, current_sql, results, correction_history,
            on_token=on_token,
        )
        stage_latency["explanation"] = round(time.time() - t0, 3)
        _emit("explanation", {"text": explanation})

        latency = time.time() - total_start

        # Phase 3: Output Guardrails 적용
        nli_score = (
            verification_result.similarity_score
            if verification_result is not None
            else 1.0
        )
        # 마지막 실행 성공 여부 (validation_result는 마지막 라운드의 검증 결과)
        last_exec_success = bool(validation_result.success) if validation_result is not None else True
        results, guardrails_result = self.output_guardrails.apply(
            results=results,
            sql_confidence=sql_confidence,
            nli_score=nli_score,
            correction_rounds=len(correction_history),
            max_rounds=self.max_rounds,
            exec_success=last_exec_success,
        )

        return SCTSQLResult(
            query=query,
            final_sql=current_sql,
            results=results,
            column_names=column_names,
            correction_history=correction_history,
            explanation=explanation,
            latency=latency,
            total_correction_rounds=len(correction_history),
            final_validation=validation_result,
            final_verification=verification_result,
            stage_latency=stage_latency,
            sql_confidence=sql_confidence,
            guardrails=guardrails_result,
            schema_context=schema_context,
        )

    # Fix 2 (조정, Phase 2 분석 반영): logprob confidence 게이팅.
    # 이전 0.9는 gpt-4o의 거의 모든 SQL(conf≈0.99)을 차단해 교정 트리거 0건.
    # → 0.7로 완화해 교정 기회를 열되, Fix A(_validate_correction) 롤백으로 안전망 제공.
    # 0.7 = "모델이 대충 확신" 수준. 그 이상은 NLI 불일치 시에도 원본 신뢰.
    HIGH_CONF_SQL_THRESHOLD = 0.70

    def _needs_correction(
        self,
        validation_result: ValidationResult,
        verification_result: VerificationResult,
        sql_confidence: float = 0.5,
    ) -> bool:
        """
        Section 4.4: 교정이 필요한지 판단한다.

        교정 조건:
        1. 실행 실패 (E1~E6) — 항상 교정
        2. 결과 비어있음(E7)/과대(E8) + NLI 불일치 — 교정
           (단독 empty/large는 valid gold일 수 있어 NLI 확인 필요)
        3. 실행 정상 + NLI 불일치 — 조건부 교정
           - score < 0.05: NLI 오탐으로 간주, 스킵
           - sql_confidence ≥ HIGH_CONF (Fix 2): 모델이 확신하는 SQL은
             NLI만으로 교정하지 않음 → 과잉 교정 방지
           - 그 외: 교정

        Ablation:
          disable_nli_correction_trigger=True면 NLI 불일치로 인한 교정 트리거를 모두 비활성화
          (실행 오류/empty/excessive는 여전히 교정됨).
        """
        if not validation_result.success:
            return True

        # NLI 트리거가 어블레이션으로 꺼져 있으면 empty/excessive도 NLI와 독립
        if self.ablation.disable_nli_correction_trigger:
            # empty/excessive만으로는 교정하지 않음 (원래도 NLI 병용 조건이었음)
            return False

        if validation_result.is_empty or validation_result.is_excessive:
            if not verification_result.is_consistent:
                return True
            return False

        if not verification_result.is_consistent:
            # 오탐 필터: score가 0에 가까우면 NLI 자체가 불안정하다고 보고 스킵
            if verification_result.similarity_score < 0.05:
                return False
            # Fix 2: 고신뢰 SQL은 NLI만으로 교정 금지
            if sql_confidence >= self.HIGH_CONF_SQL_THRESHOLD:
                return False
            return True

        return False

    def _validate_correction(
        self,
        original_sql: str,
        corrected_sql: str,
        original_validation: ValidationResult,
        original_verification: VerificationResult,
        query: str,
    ) -> tuple[str, dict]:
        """
        Fix A + Fix C (D1 분석 반영): 교정 결과를 재검증하고, 원본보다 열화되면 롤백한다.

        Fix C 개정: rollback 판단에 NLI를 사용하지 않는다. D1에서 관찰된 현상:
          - NLI 기반 rollback이 너무 엄격해 좋은 교정까지 되돌림
          - no_nli 어블레이션에서 CSR=50%인데 main에서 CSR=0%로 튐 → NLI rollback이 원인
          - 따라서 rollback은 **실행 기반 dominance만** 사용

        Dominance 원칙 (실행 기반):
          - 원본이 실행 성공 + 결과 있음:
              · 교정이 실행 실패 → 롤백
              · 교정이 empty (원본은 non-empty) → 롤백
              · 그 외 → 수용 (NLI 차이와 무관)
          - 원본이 실행 실패:
              · 무조건 교정 수용 (다음 라운드 기회)
          - SQL 동일 → 롤백 플래그는 False

        의미 기반 판단은 `semantic_verifier`가 다음 라운드의 교정 트리거로 담당.
        """
        info = {"rolled_back": False, "reason": ""}

        if not corrected_sql or corrected_sql.strip() == original_sql.strip():
            return original_sql, info

        # 원본이 실행 실패였으면 교정은 기회 → 무조건 수용
        if not original_validation.success:
            return corrected_sql, info

        # 원본이 실행 성공 — 실행 기반 dominance만 체크
        corrected_valid = self.execution_validator.validate(corrected_sql, self.db_path)

        if not corrected_valid.success:
            info["rolled_back"] = True
            info["reason"] = f"corrected exec failed: {corrected_valid.error_type}"
            return original_sql, info

        # 원본은 결과 있었는데 교정은 empty → 롤백
        if corrected_valid.is_empty and not original_validation.is_empty:
            info["rolled_back"] = True
            info["reason"] = "corrected is empty while original had rows"
            return original_sql, info

        # Fix C: NLI regression 체크는 제거 — 의미 기반 판단은 다음 라운드 교정 트리거가 담당
        return corrected_sql, info
