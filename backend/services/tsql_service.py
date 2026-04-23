"""
Service layer that wraps src/ modules for the FastAPI backend.
Does NOT modify any src/ code -- only imports and calls.
"""

import json
import os
import sqlite3
import sys
import time
import asyncio
from collections import Counter
from dataclasses import dataclass, field as dc_field
from datetime import datetime, timezone
from typing import Any, AsyncGenerator

import yaml

# ── Add project root to sys.path so src/ modules can be imported ──
# __file__ = backend/services/tsql_service.py -> dirname x3 = project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ── Import src modules (guarded) ──
try:
    from src.sc_tsql import SCTSQL, SCTSQLResult
    from src.execution_validator import ExecutionValidator, ValidationResult
    from src.semantic_verifier import VerificationResult
    from src.langgraph_orchestrator import LangGraphSCTSQL
    SRC_AVAILABLE = True
except ImportError as e:
    # If src/ modules cannot be imported (e.g. missing deps), mark as unavailable.
    # The service will use mock implementations where needed.
    SRC_AVAILABLE = False
    _import_error = str(e)

try:
    from src.metrics import execution_accuracy, correction_success_rate, average_latency
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False

try:
    from evaluate import (
        load_hrdb_dev,
        load_bird_dev,
        get_db_path,
        execute_gold_sql,
        load_few_shot_examples,
    )
    EVALUATE_AVAILABLE = True
except ImportError:
    EVALUATE_AVAILABLE = False


# ────────────────────────────────────────────────────────────
# Configuration helpers
# ────────────────────────────────────────────────────────────

def load_config() -> dict:
    """Load configs/config.yaml from the project root."""
    config_path = os.path.join(PROJECT_ROOT, "configs", "config.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


CONFIG = load_config()


# ────────────────────────────────────────────────────────────
# Database scanning
# ────────────────────────────────────────────────────────────

def scan_databases() -> list[dict]:
    """Scan data/raw/{hrdb,bird} for SQLite database files."""
    databases = []
    data_root = os.path.join(PROJECT_ROOT, "data", "raw")

    # HR-DB: data/raw/hrdb/hrdb.sqlite (단일 DB)
    hrdb_file = os.path.join(data_root, "hrdb", "hrdb.sqlite")
    if os.path.isfile(hrdb_file):
        table_count = _count_tables(hrdb_file)
        rel_path = os.path.relpath(hrdb_file, PROJECT_ROOT)
        databases.append({
            "id": "hrdb",
            "dataset": "hrdb",
            "table_count": table_count,
            "path": rel_path,
        })

    # BIRD: data/raw/bird/dev_databases/{db_id}/{db_id}.sqlite
    bird_db_root = os.path.join(data_root, "bird", "dev_databases")
    if os.path.isdir(bird_db_root):
        for db_id in sorted(os.listdir(bird_db_root)):
            db_dir = os.path.join(bird_db_root, db_id)
            db_file = os.path.join(db_dir, f"{db_id}.sqlite")
            if os.path.isfile(db_file):
                table_count = _count_tables(db_file)
                rel_path = os.path.relpath(db_file, PROJECT_ROOT)
                databases.append({
                    "id": db_id,
                    "dataset": "bird",
                    "table_count": table_count,
                    "path": rel_path,
                })

    return databases


def _count_tables(db_path: str) -> int:
    """Count user tables in a SQLite database."""
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=2.0)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
        )
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except Exception:
        return 0


def resolve_db_path(dataset: str, db_id: str) -> str:
    """Resolve absolute path to a SQLite database file."""
    data_root = os.path.join(PROJECT_ROOT, "data", "raw")

    if dataset == "hrdb":
        path = os.path.join(data_root, "hrdb", "hrdb.sqlite")
        if os.path.isfile(path):
            return path
    elif dataset == "bird":
        path = os.path.join(data_root, "bird", "dev_databases", db_id, f"{db_id}.sqlite")
        if os.path.isfile(path):
            return path
        # Fallback via evaluate.py helper
        if EVALUATE_AVAILABLE:
            try:
                path = get_db_path(dataset, db_id, CONFIG)
                if os.path.isfile(path):
                    return path
            except Exception:
                pass

    raise FileNotFoundError(f"Database not found: {dataset}/{db_id}")


def get_schema_info(db_path: str) -> dict:
    """Read schema metadata (tables, columns, foreign keys) from a SQLite DB."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=2.0)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
    )
    table_names = [row[0] for row in cursor.fetchall()]

    tables = []
    all_fks = []
    for table_name in table_names:
        cursor.execute(f"PRAGMA table_info(`{table_name}`);")
        columns = []
        for col_info in cursor.fetchall():
            columns.append({
                "name": col_info[1],
                "type": col_info[2] or "TEXT",
                "is_primary_key": bool(col_info[5]),
            })
        tables.append({"name": table_name, "columns": columns})

        cursor.execute(f"PRAGMA foreign_key_list(`{table_name}`);")
        for fk in cursor.fetchall():
            all_fks.append({
                "from_table": table_name,
                "from_column": fk[3],
                "to_table": fk[2],
                "to_column": fk[4],
            })

    conn.close()
    return {"tables": tables, "foreign_keys": all_fks}


def schema_context_to_ui(schema_context: dict, db_path: str) -> dict:
    """
    SCTSQLResult.schema_context (링커 형식) → UI schema_context 형식으로 변환한다.

    링커 형식: {"tables": ["t1","t2"], "columns": {"t1": ["c1",...]}, "foreign_keys": [...]}
    UI 형식:   {"tables": [{"name": "t1", "columns": [{"name","type","is_primary_key"}]}], "foreign_keys": [...]}

    링커가 columns에 type/PK 정보를 갖고 있지 않으므로 DB에서 보완한다.
    schema_context가 비어있으면 get_schema_info()로 fallback한다.
    """
    selected_tables = schema_context.get("tables", [])
    if not selected_tables:
        return get_schema_info(db_path)

    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=2.0)
        cursor = conn.cursor()

        tables = []
        all_fks = []
        for table_name in selected_tables:
            cursor.execute(f"PRAGMA table_info(`{table_name}`);")
            columns = []
            for col_info in cursor.fetchall():
                columns.append({
                    "name": col_info[1],
                    "type": col_info[2] or "TEXT",
                    "is_primary_key": bool(col_info[5]),
                })
            tables.append({"name": table_name, "columns": columns})

            cursor.execute(f"PRAGMA foreign_key_list(`{table_name}`);")
            for fk in cursor.fetchall():
                all_fks.append({
                    "from_table": table_name,
                    "from_column": fk[3],
                    "to_table": fk[2],
                    "to_column": fk[4],
                })

        conn.close()
        return {"tables": tables, "foreign_keys": all_fks}
    except Exception:
        return get_schema_info(db_path)


# ────────────────────────────────────────────────────────────
# Single query execution
# ────────────────────────────────────────────────────────────

def run_query(
    query: str,
    db_id: str,
    dataset: str = "hrdb",
    conversation_history: list[dict] | None = None,
) -> dict:
    """
    Execute the SC-TSQL pipeline for a single natural language query.
    Returns a dict matching the QueryResponse schema shape.

    Args:
        query: 자연어 질의
        db_id: 데이터베이스 식별자
        dataset: "hrdb" | "bird"
        conversation_history: 이전 대화 이력 (Phase 3 멀티턴).
            각 항목: {"question": str, "sql": str, "explanation": str}
    """
    db_path = resolve_db_path(dataset, db_id)

    if not SRC_AVAILABLE:
        raise RuntimeError(
            f"src/ modules not available (import error: {_import_error}). "
            "Ensure all dependencies are installed."
        )

    config = load_config()
    # Phase 3: config.use_langgraph=true 시 LangGraph 오케스트레이터 사용
    if config.get("use_langgraph", False):
        pipeline = LangGraphSCTSQL(db_path, config)
    else:
        pipeline = SCTSQL(db_path, config)
    result: SCTSQLResult = pipeline.run(
        query,
        conversation_history=conversation_history or [],
    )

    # Build response
    query_id = f"q_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{id(result) % 0xFFFFFF:06x}"

    # Schema context: 링커가 선택한 테이블만 포함
    schema_info = schema_context_to_ui(result.schema_context, db_path)

    # Correction steps
    correction_steps = []
    for entry in result.correction_history:
        correction_steps.append({
            "round": entry["round"],
            "error_type": entry.get("error_type", "UNKNOWN"),
            "original_sql": entry.get("original_sql", ""),
            "corrected_sql": entry.get("corrected_sql", ""),
            "validation_success": entry.get("validation_success", False),
            "semantic_score": entry.get("semantic_score", 0.0),
        })

    # Original SQL = first correction's original_sql, or final_sql if no corrections
    original_sql = correction_steps[0]["original_sql"] if correction_steps else result.final_sql

    # Result rows as list[dict]
    rows = []
    for row_tuple in result.results:
        row_dict = {}
        for i, col_name in enumerate(result.column_names):
            row_dict[col_name] = row_tuple[i] if i < len(row_tuple) else None
        rows.append(row_dict)

    # Validation info
    validation = {"success": True, "error_type": None, "error_message": None,
                  "is_empty": False, "is_excessive": False, "row_count": 0}
    if result.final_validation is not None:
        validation = {
            "success": result.final_validation.success,
            "error_type": result.final_validation.error_type,
            "error_message": result.final_validation.error_message,
            "is_empty": result.final_validation.is_empty,
            "is_excessive": result.final_validation.is_excessive,
            "row_count": result.final_validation.row_count,
        }

    # Verification info
    verification = {"back_translation": "", "similarity_score": 0.0,
                    "is_consistent": True, "mismatch_diagnosis": None}
    if result.final_verification is not None:
        verification = {
            "back_translation": result.final_verification.back_translation,
            "similarity_score": result.final_verification.similarity_score,
            "is_consistent": result.final_verification.is_consistent,
            "mismatch_diagnosis": result.final_verification.mismatch_diagnosis,
        }

    # Guardrails info (Phase 3)
    guardrails_info = {
        "rows_truncated": False,
        "original_row_count": 0,
        "low_confidence_warning": False,
        "warning_message": "",
    }
    if result.guardrails is not None:
        guardrails_info = {
            "rows_truncated": result.guardrails.rows_truncated,
            "original_row_count": result.guardrails.original_row_count,
            "low_confidence_warning": result.guardrails.low_confidence_warning,
            "warning_message": result.guardrails.warning_message,
        }

    return {
        "id": query_id,
        "query": result.query,
        "db_id": db_id,
        "original_sql": original_sql,
        "final_sql": result.final_sql,
        "was_corrected": len(result.correction_history) > 0,
        "correction_steps": correction_steps,
        "schema_context": schema_info,
        "result": {
            "columns": result.column_names,
            "rows": rows,
        },
        "explanation": result.explanation,
        "latency": round(result.latency, 2),
        "validation": validation,
        "verification": verification,
        "sql_confidence": round(result.sql_confidence, 4),
        "guardrails": guardrails_info,
    }


# ────────────────────────────────────────────────────────────
# Streaming query execution (SSE)
# ────────────────────────────────────────────────────────────

async def run_query_stream(
    query: str,
    db_id: str,
    dataset: str = "hrdb",
    conversation_history: list[dict] | None = None,
) -> AsyncGenerator[str, None]:
    """
    SC-TSQL 파이프라인을 실행하면서 SSE 이벤트를 실시간으로 yield한다.
    각 파이프라인 단계가 완료될 때마다 클라이언트로 이벤트를 전송한다.
    """
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def emit(event_type: str, data: dict) -> None:
        """스레드에서 asyncio 큐에 안전하게 이벤트를 삽입한다."""
        loop.call_soon_threadsafe(queue.put_nowait, (event_type, data))

    def run_pipeline() -> None:
        try:
            db_path = resolve_db_path(dataset, db_id)

            if not SRC_AVAILABLE:
                raise RuntimeError(
                    f"src/ modules not available (import error: {_import_error}). "
                    "Ensure all dependencies are installed."
                )

            config = load_config()
            if config.get("use_langgraph", False):
                # LangGraph 오케스트레이터는 on_event 미지원 — 일반 파이프라인으로 fallback
                pipeline = SCTSQL(db_path, config)
            else:
                pipeline = SCTSQL(db_path, config)

            result: SCTSQLResult = pipeline.run(
                query,
                conversation_history=conversation_history or [],
                on_event=emit,
            )

            # 최종 결과 직렬화 (링커가 선택한 테이블만 포함)
            schema_info = schema_context_to_ui(result.schema_context, db_path)
            query_id = (
                f"q_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
                f"_{id(result) % 0xFFFFFF:06x}"
            )

            correction_steps = []
            for entry in result.correction_history:
                correction_steps.append({
                    "round": entry["round"],
                    "error_type": entry.get("error_type", "UNKNOWN"),
                    "original_sql": entry.get("original_sql", ""),
                    "corrected_sql": entry.get("corrected_sql", ""),
                    "validation_success": entry.get("validation_success", False),
                    "semantic_score": entry.get("semantic_score", 0.0),
                })

            original_sql = (
                correction_steps[0]["original_sql"]
                if correction_steps
                else result.final_sql
            )

            rows = []
            for row_tuple in result.results:
                row_dict = {}
                for i, col_name in enumerate(result.column_names):
                    row_dict[col_name] = row_tuple[i] if i < len(row_tuple) else None
                rows.append(row_dict)

            validation = {
                "success": True, "error_type": None, "error_message": None,
                "is_empty": False, "is_excessive": False, "row_count": 0,
            }
            if result.final_validation is not None:
                validation = {
                    "success": result.final_validation.success,
                    "error_type": result.final_validation.error_type,
                    "error_message": result.final_validation.error_message,
                    "is_empty": result.final_validation.is_empty,
                    "is_excessive": result.final_validation.is_excessive,
                    "row_count": result.final_validation.row_count,
                }

            verification = {
                "back_translation": "", "similarity_score": 0.0,
                "is_consistent": True, "mismatch_diagnosis": None,
            }
            if result.final_verification is not None:
                verification = {
                    "back_translation": result.final_verification.back_translation,
                    "similarity_score": result.final_verification.similarity_score,
                    "is_consistent": result.final_verification.is_consistent,
                    "mismatch_diagnosis": result.final_verification.mismatch_diagnosis,
                }

            guardrails_info = {
                "rows_truncated": False, "original_row_count": 0,
                "low_confidence_warning": False, "warning_message": "",
            }
            if result.guardrails is not None:
                guardrails_info = {
                    "rows_truncated": result.guardrails.rows_truncated,
                    "original_row_count": result.guardrails.original_row_count,
                    "low_confidence_warning": result.guardrails.low_confidence_warning,
                    "warning_message": result.guardrails.warning_message,
                }

            emit("result", {
                "id": query_id,
                "query": result.query,
                "db_id": db_id,
                "original_sql": original_sql,
                "final_sql": result.final_sql,
                "was_corrected": len(result.correction_history) > 0,
                "correction_steps": correction_steps,
                "schema_context": schema_info,
                "result": {"columns": result.column_names, "rows": rows},
                "explanation": result.explanation,
                "latency": round(result.latency, 2),
                "validation": validation,
                "verification": verification,
                "sql_confidence": round(result.sql_confidence, 4),
                "guardrails": guardrails_info,
            })
        except Exception as e:
            emit("error", {"message": str(e)})
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, None)  # sentinel

    executor_future = loop.run_in_executor(None, run_pipeline)

    while True:
        msg = await queue.get()
        if msg is None:
            break
        event_type, data = msg
        yield f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    await executor_future


# ────────────────────────────────────────────────────────────
# Experiment management (in-memory store)
# ────────────────────────────────────────────────────────────

@dataclass
class ExperimentState:
    """In-memory representation of a running/completed experiment."""
    id: str
    dataset: str
    status: str  # "running" | "completed" | "failed"
    config: dict
    created_at: str
    total_samples: int = 0
    current: int = 0
    metrics: dict | None = None
    detailed_results: list[dict] = dc_field(default_factory=list)
    correction_progress: list[dict] = dc_field(default_factory=list)
    error_distribution: list[dict] = dc_field(default_factory=list)
    error_message: str | None = None
    # WebSocket subscribers
    ws_subscribers: list[Any] = dc_field(default_factory=list)


# Global experiment store
_experiments: dict[str, ExperimentState] = {}
_running_experiment_id: str | None = None


def get_experiment(experiment_id: str) -> ExperimentState | None:
    return _experiments.get(experiment_id)


def list_experiments(
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[ExperimentState], int]:
    """Return experiments filtered/paginated."""
    exps = list(_experiments.values())
    # Sort by created_at descending
    exps.sort(key=lambda e: e.created_at, reverse=True)
    if status:
        exps = [e for e in exps if e.status == status]
    total = len(exps)
    return exps[offset : offset + limit], total


def is_experiment_running() -> bool:
    return _running_experiment_id is not None


async def broadcast_ws(experiment_id: str, message: dict):
    """Send a JSON message to all WebSocket subscribers of an experiment."""
    exp = _experiments.get(experiment_id)
    if not exp:
        return
    disconnected = []
    for ws in exp.ws_subscribers:
        try:
            await ws.send_json(message)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        exp.ws_subscribers.remove(ws)


async def run_experiment(experiment_id: str):
    """
    Execute the full evaluation pipeline as a background task.
    Streams progress via WebSocket.
    """
    global _running_experiment_id

    exp = _experiments.get(experiment_id)
    if exp is None:
        return

    try:
        config = load_config()
        # Override config with experiment settings
        config["llm"]["model"] = exp.config["model"]
        config["correction"]["max_rounds"] = exp.config["max_rounds"]
        config["correction"]["semantic_threshold"] = exp.config["semantic_threshold"]

        dataset = exp.config["dataset"]

        # Load examples
        if not EVALUATE_AVAILABLE:
            raise RuntimeError("evaluate.py module not importable")

        if dataset == "hrdb":
            dev_path = config["evaluation"]["hrdb_dev_path"]
            if not os.path.isabs(dev_path):
                dev_path = os.path.join(PROJECT_ROOT, dev_path)
            examples = load_hrdb_dev(dev_path)
        elif dataset == "bird":
            dev_path = config["evaluation"]["bird_dev_path"]
            if not os.path.isabs(dev_path):
                dev_path = os.path.join(PROJECT_ROOT, dev_path)
            examples = load_bird_dev(dev_path)
        else:
            raise ValueError(f"Unknown dataset: {dataset}")

        # Apply sample_count limit
        sample_count = exp.config.get("sample_count")
        if sample_count is not None and sample_count < len(examples):
            examples = examples[:sample_count]

        exp.total_samples = len(examples)

        # Load few-shot examples
        few_shot_examples = load_few_shot_examples(dataset, config)

        # Ablation 플래그 구성
        ablation_dict = exp.config.get("ablation")
        ablation_flags = None
        if ablation_dict and SRC_AVAILABLE:
            from src.sc_tsql import AblationFlags
            ablation_flags = AblationFlags(**ablation_dict)

        # Evaluation loop
        pipeline_cache: dict[str, SCTSQL] = {}
        validator = ExecutionValidator()

        pred_results_list: list = []
        gold_results_list: list = []
        correction_logs: list[dict] = []
        latency_logs: list[float] = []
        all_error_types: list[str] = []

        # For correction progress tracking per round
        round_corrections: dict[int, int] = {}  # round -> newly_corrected count
        cumulative_correct = 0

        for i, example in enumerate(examples):
            db_id = example["db_id"]
            question = example["question"]
            gold_sql = example["gold_sql"]

            try:
                db_path = resolve_db_path(dataset, db_id)
            except FileNotFoundError:
                # Skip missing databases
                exp.current = i + 1
                continue

            if db_id not in pipeline_cache:
                try:
                    pipeline_cache[db_id] = SCTSQL(db_path, config, few_shot_examples, ablation=ablation_flags)
                except Exception as init_err:
                    exp.current = i + 1
                    await broadcast_ws(experiment_id, {
                        "type": "log",
                        "entry": {
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "level": "error",
                            "message": f"[PIPELINE INIT FAILED] {db_id}: {init_err}",
                        },
                    })
                    # 초기화 실패 시 실험 자체를 중단 (모든 쿼리가 같은 이유로 실패하므로)
                    raise RuntimeError(f"Pipeline initialization failed: {init_err}") from init_err

            pipeline = pipeline_cache[db_id]

            try:
                result = pipeline.run(question)
            except Exception as e:
                # Record failure
                pred_results_list.append([])
                gold_results_list.append(execute_gold_sql(gold_sql, db_path))
                latency_logs.append(0.0)
                correction_logs.append({"had_error": True, "corrected_successfully": False})

                exp.current = i + 1
                detail_entry = {
                    "index": i,
                    "db_id": db_id,
                    "question": question,
                    "gold_sql": gold_sql,
                    "predicted_sql": "",
                    "correct": False,
                    "latency": 0.0,
                    "correction_rounds": 0,
                    "correction_history": [],
                }
                exp.detailed_results.append(detail_entry)

                # Send progress
                await broadcast_ws(experiment_id, {
                    "type": "progress",
                    "current": i + 1,
                    "total": exp.total_samples,
                    "status": "running",
                    "current_item": {
                        "index": i,
                        "db_id": db_id,
                        "question": question[:80],
                        "correct": False,
                        "latency": 0.0,
                        "correction_rounds": 0,
                    },
                })
                await broadcast_ws(experiment_id, {
                    "type": "log",
                    "entry": {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "level": "error",
                        "message": f"[{i+1}/{exp.total_samples}] ERROR - {db_id}: {str(e)[:100]}",
                    },
                })
                await asyncio.sleep(0)
                continue

            # Gold results
            gold_results = execute_gold_sql(gold_sql, db_path)

            pred_results_list.append(result.results)
            gold_results_list.append(gold_results)
            latency_logs.append(result.latency)

            pred_set = set(result.results) if result.results else set()
            gold_set = set(gold_results) if gold_results else set()
            is_correct = pred_set == gold_set

            had_error = result.total_correction_rounds > 0
            corrected_successfully = had_error and is_correct

            correction_logs.append({
                "had_error": had_error,
                "corrected_successfully": corrected_successfully,
            })

            # Track error types
            for ch in result.correction_history:
                et = ch.get("error_type", "UNKNOWN")
                all_error_types.append(et)

            if is_correct:
                cumulative_correct += 1

            detail_entry = {
                "index": i,
                "db_id": db_id,
                "question": question,
                "gold_sql": gold_sql,
                "predicted_sql": result.final_sql,
                "correct": is_correct,
                "latency": round(result.latency, 2),
                "correction_rounds": result.total_correction_rounds,
                "correction_history": result.correction_history,
            }

            # Add validation/verification for detailed view
            if result.final_validation is not None:
                detail_entry["final_validation"] = {
                    "success": result.final_validation.success,
                    "error_type": result.final_validation.error_type,
                    "error_message": result.final_validation.error_message,
                    "is_empty": result.final_validation.is_empty,
                    "is_excessive": result.final_validation.is_excessive,
                    "row_count": result.final_validation.row_count,
                }
            if result.final_verification is not None:
                detail_entry["final_verification"] = {
                    "back_translation": result.final_verification.back_translation,
                    "similarity_score": result.final_verification.similarity_score,
                    "is_consistent": result.final_verification.is_consistent,
                    "mismatch_diagnosis": result.final_verification.mismatch_diagnosis,
                }
            if result.final_validation and result.final_validation.success:
                rows_as_dicts = []
                for row_tuple in result.results[:50]:  # Cap at 50 rows for storage
                    row_dict = {}
                    for ci, col_name in enumerate(result.column_names):
                        row_dict[col_name] = row_tuple[ci] if ci < len(row_tuple) else None
                    rows_as_dicts.append(row_dict)
                detail_entry["result"] = {
                    "columns": result.column_names,
                    "rows": rows_as_dicts,
                }

            exp.detailed_results.append(detail_entry)
            exp.current = i + 1

            # WebSocket progress
            status_str = "OK" if is_correct else "FAIL"
            rounds_info = f" (corrected x{result.total_correction_rounds})" if had_error else ""
            await broadcast_ws(experiment_id, {
                "type": "progress",
                "current": i + 1,
                "total": exp.total_samples,
                "status": "running",
                "current_item": {
                    "index": i,
                    "db_id": db_id,
                    "question": question[:80],
                    "correct": is_correct,
                    "latency": round(result.latency, 1),
                    "correction_rounds": result.total_correction_rounds,
                },
            })
            await broadcast_ws(experiment_id, {
                "type": "log",
                "entry": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "level": "info",
                    "message": (
                        f"[{i+1}/{exp.total_samples}] {status_str} - {db_id}: "
                        f"{question[:60]}...{rounds_info} ({result.latency:.1f}s)"
                    ),
                },
            })

            # Yield control to event loop periodically
            await asyncio.sleep(0)

        # ── Compute final metrics ──
        total_evaluated = len(pred_results_list)
        if METRICS_AVAILABLE and total_evaluated > 0:
            ex = execution_accuracy(pred_results_list, gold_results_list)
            csr = correction_success_rate(correction_logs)
            avg_lat = average_latency(latency_logs)
        else:
            ex = 0.0
            csr = 0.0
            avg_lat = 0.0

        exp.metrics = {
            "execution_accuracy": round(ex, 4),
            "correction_success_rate": round(csr, 4),
            "average_latency": round(avg_lat, 2),
            "total_evaluated": total_evaluated,
        }

        # ── Correction progress (per-round cumulative accuracy) ──
        # Build by scanning detailed_results
        max_rounds_seen = max(
            (d["correction_rounds"] for d in exp.detailed_results),
            default=0,
        )
        correction_progress = []
        # Round 0: initially correct (no corrections needed)
        initially_correct = sum(
            1 for d in exp.detailed_results
            if d["correct"] and d["correction_rounds"] == 0
        )
        if total_evaluated > 0:
            correction_progress.append({
                "round": 0,
                "cumulative_accuracy": round(initially_correct / total_evaluated, 4),
                "newly_corrected": 0,
            })
            cumul = initially_correct
            for r in range(1, max_rounds_seen + 1):
                newly = sum(
                    1 for d in exp.detailed_results
                    if d["correct"] and d["correction_rounds"] == r
                )
                cumul += newly
                correction_progress.append({
                    "round": r,
                    "cumulative_accuracy": round(cumul / total_evaluated, 4),
                    "newly_corrected": newly,
                })
        exp.correction_progress = correction_progress

        # ── Error distribution ──
        error_counter = Counter(all_error_types)
        exp.error_distribution = [
            {"error_type": et, "count": cnt}
            for et, cnt in error_counter.most_common()
        ]

        exp.status = "completed"

        # Send completed message
        await broadcast_ws(experiment_id, {
            "type": "completed",
            "metrics": exp.metrics,
        })

    except Exception as e:
        exp.status = "failed"
        exp.error_message = str(e)
        await broadcast_ws(experiment_id, {
            "type": "error",
            "message": f"Evaluation failed: {str(e)}",
        })
    finally:
        _running_experiment_id = None


def resolve_pipeline_preset(mode: str) -> dict:
    """
    파이프라인 프리셋을 ablation 플래그 + config 오버라이드로 변환한다.

    | Mode      | schema_linker | few_shot | correction | semantic_verifier |
    |-----------|--------------|----------|------------|------------------|
    | zero-shot | OFF          | 0        | OFF        | OFF              |
    | din-sql   | ON           | 0        | OFF        | OFF              |
    | dail-sql  | ON           | 3        | OFF        | OFF              |
    | chess     | ON           | 3        | ON (K=1)   | OFF              |
    | sc-tsql   | ON           | 3        | ON (K=3)   | ON               |
    """
    presets = {
        "zero-shot": {
            "ablation": {
                "disable_schema_linker": True,
                "disable_execution_validator": False,
                "disable_semantic_verifier": True,
                "disable_correction_loop": True,
            },
            "max_rounds": 0,
        },
        "din-sql": {
            "ablation": {
                "disable_schema_linker": False,
                "disable_execution_validator": False,
                "disable_semantic_verifier": True,
                "disable_correction_loop": True,
            },
            "max_rounds": 0,
        },
        "dail-sql": {
            "ablation": {
                "disable_schema_linker": False,
                "disable_execution_validator": False,
                "disable_semantic_verifier": True,
                "disable_correction_loop": True,
            },
            "max_rounds": 0,
        },
        "chess": {
            "ablation": {
                "disable_schema_linker": False,
                "disable_execution_validator": False,
                "disable_semantic_verifier": True,
                "disable_correction_loop": False,
            },
            "max_rounds": 1,
        },
        "sc-tsql": {
            "ablation": {
                "disable_schema_linker": False,
                "disable_execution_validator": False,
                "disable_semantic_verifier": False,
                "disable_correction_loop": False,
            },
            "max_rounds": 3,
        },
    }
    if mode not in presets:
        raise ValueError(f"Unknown pipeline mode: {mode}. Must be one of {list(presets.keys())}")
    return presets[mode]


def create_experiment(
    dataset: str,
    model: str | None,
    max_rounds: int,
    semantic_threshold: float,
    sample_count: int | None,
    pipeline_mode: str | None = None,
    ablation: dict | None = None,
) -> ExperimentState:
    """Create a new experiment record and return it (does not start execution)."""
    global _running_experiment_id

    if _running_experiment_id is not None:
        raise ValueError("An experiment is already running")

    if dataset not in ("hrdb", "bird"):
        raise ValueError("Invalid dataset. Must be 'hrdb' or 'bird'")

    # 프리셋 적용: pipeline_mode가 지정되면 ablation과 max_rounds를 오버라이드
    if pipeline_mode:
        preset = resolve_pipeline_preset(pipeline_mode)
        ablation = preset["ablation"]
        max_rounds = preset["max_rounds"]

    resolved_model = model or CONFIG["llm"]["model"]
    exp_id = f"exp_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

    # Estimate total samples
    total_samples = _estimate_sample_count(dataset, sample_count)

    exp = ExperimentState(
        id=exp_id,
        dataset=dataset,
        status="running",
        config={
            "dataset": dataset,
            "model": resolved_model,
            "max_rounds": max_rounds,
            "semantic_threshold": semantic_threshold,
            "sample_count": sample_count,
            "pipeline_mode": pipeline_mode,
            "ablation": ablation,
        },
        created_at=datetime.now(timezone.utc).isoformat(),
        total_samples=total_samples,
    )

    _experiments[exp_id] = exp
    _running_experiment_id = exp_id
    return exp


def _estimate_sample_count(dataset: str, sample_count: int | None) -> int:
    """Estimate the number of samples for a given dataset."""
    try:
        if dataset == "hrdb":
            dev_path = CONFIG["evaluation"]["hrdb_dev_path"]
            if not os.path.isabs(dev_path):
                dev_path = os.path.join(PROJECT_ROOT, dev_path)
            if os.path.isfile(dev_path):
                with open(dev_path, "r") as f:
                    data = json.load(f)
                total = len(data)
            else:
                total = 150  # Default HR-DB dev count
        elif dataset == "bird":
            dev_path = CONFIG["evaluation"]["bird_dev_path"]
            if not os.path.isabs(dev_path):
                dev_path = os.path.join(PROJECT_ROOT, dev_path)
            if os.path.isfile(dev_path):
                with open(dev_path, "r") as f:
                    data = json.load(f)
                total = len(data)
            else:
                total = 1534  # Default BIRD dev count
        else:
            total = 0
    except Exception:
        total = 150 if dataset == "hrdb" else 1534

    if sample_count is not None:
        return min(sample_count, total)
    return total


# ────────────────────────────────────────────────────────────
# K-Sweep batch management
# ────────────────────────────────────────────────────────────

@dataclass
class BatchState:
    """K-Sweep 배치 실험 상태."""
    batch_id: str
    k_values: list[int]
    experiment_ids: list[str]
    status: str  # "running" | "completed" | "failed"
    current_k: int | None = None
    completed_count: int = 0
    ws_subscribers: list[Any] = dc_field(default_factory=list)


_batches: dict[str, BatchState] = {}


def get_batch(batch_id: str) -> BatchState | None:
    return _batches.get(batch_id)


def create_k_sweep(
    dataset: str,
    model: str | None,
    semantic_threshold: float,
    sample_count: int | None,
    k_values: list[int],
) -> BatchState:
    """K-Sweep 배치를 생성한다. 각 K값에 대해 ExperimentState를 미리 만들어둔다."""
    if _running_experiment_id is not None:
        raise ValueError("An experiment is already running")

    batch_id = f"batch_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    experiment_ids = []

    resolved_model = model or CONFIG["llm"]["model"]
    total_samples = _estimate_sample_count(dataset, sample_count)

    for k in sorted(k_values):
        exp_id = f"{batch_id}_k{k}"
        ablation = None
        if k == 0:
            ablation = {
                "disable_schema_linker": False,
                "disable_execution_validator": False,
                "disable_semantic_verifier": False,
                "disable_correction_loop": True,
            }

        exp = ExperimentState(
            id=exp_id,
            dataset=dataset,
            status="pending",
            config={
                "dataset": dataset,
                "model": resolved_model,
                "max_rounds": k,
                "semantic_threshold": semantic_threshold,
                "sample_count": sample_count,
                "pipeline_mode": None,
                "ablation": ablation,
            },
            created_at=datetime.now(timezone.utc).isoformat(),
            total_samples=total_samples,
        )
        _experiments[exp_id] = exp
        experiment_ids.append(exp_id)

    batch = BatchState(
        batch_id=batch_id,
        k_values=sorted(k_values),
        experiment_ids=experiment_ids,
        status="running",
    )
    _batches[batch_id] = batch
    return batch


async def run_k_sweep(batch_id: str):
    """K-Sweep 배치의 각 실험을 순차적으로 실행한다."""
    global _running_experiment_id

    batch = _batches.get(batch_id)
    if batch is None:
        return

    try:
        for i, exp_id in enumerate(batch.experiment_ids):
            exp = _experiments.get(exp_id)
            if exp is None:
                continue

            batch.current_k = batch.k_values[i]
            exp.status = "running"
            _running_experiment_id = exp_id

            # Broadcast batch progress
            for ws in batch.ws_subscribers:
                try:
                    await ws.send_json({
                        "type": "batch_progress",
                        "batch_id": batch_id,
                        "current_k": batch.current_k,
                        "completed_count": batch.completed_count,
                        "total_k": len(batch.k_values),
                    })
                except Exception:
                    pass

            await run_experiment(exp_id)

            batch.completed_count = i + 1

        batch.status = "completed"
    except Exception as e:
        batch.status = "failed"
    finally:
        _running_experiment_id = None
        batch.current_k = None

        # Broadcast batch completed
        for ws in batch.ws_subscribers:
            try:
                await ws.send_json({
                    "type": "batch_completed",
                    "batch_id": batch_id,
                    "status": batch.status,
                    "experiment_ids": batch.experiment_ids,
                })
            except Exception:
                pass
