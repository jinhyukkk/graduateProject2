"""
메인 평가 스크립트.
HR-DB / BIRD dev set에 대해 SC-TSQL 파이프라인 또는 베이스라인 모델을 실행하고
EX, CSR, Avg Latency를 출력한다.

사용 예:
  python evaluate.py --config configs/config.yaml --dataset bird --model sc_tsql
  python evaluate.py --config configs/config.yaml --dataset bird --model dail_sql
  python evaluate.py --config configs/config.yaml --dataset bird --model mac_sql
  python evaluate.py --config configs/config.yaml --dataset bird --model zeroshot
"""

import argparse
import json
import os
import random
import sqlite3
import time
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))
from pathlib import Path

import yaml

from src.sc_tsql import SCTSQL, AblationFlags
from src.execution_validator import ExecutionValidator
from src.metrics import (
    execution_accuracy,
    correction_success_rate,
    average_latency,
    intent_match_score,
)
from src.baselines.dail_sql import DAILSQLBaseline
from src.baselines.mac_sql import MACSQLBaseline
from src.baselines.zeroshot import ZeroShotBaseline


def load_hrdb_dev(dev_path: str) -> list[dict]:
    """
    HR-DB dev set을 로드한다.
    각 항목: {"question": str, "SQL": str, "db_id": "hrdb", "difficulty": str}
    """
    with open(dev_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    examples = []
    for item in data:
        examples.append({
            "question": item["question"],
            "gold_sql": item.get("SQL", item.get("query", "")),
            "db_id": item.get("db_id", "hrdb"),
            "difficulty": item.get("difficulty", ""),
            "evidence": "",  # HRDB는 외부 evidence 없음
            "question_id": item.get("id"),
        })
    return examples


def load_bird_dev(dev_path: str) -> list[dict]:
    """
    BIRD dev set을 로드한다.
    각 항목: {"question": str, "SQL": str, "db_id": str, "evidence": str}
    BIRD의 evidence(외부 지식)는 도메인 힌트로 프롬프트에 포함된다.
    """
    with open(dev_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    examples = []
    for item in data:
        examples.append({
            "question": item["question"],
            "gold_sql": item.get("SQL", item.get("query", "")),
            "db_id": item["db_id"],
            "evidence": item.get("evidence", ""),
            "difficulty": item.get("difficulty", ""),
            "question_id": item.get("question_id"),
        })
    return examples


def get_db_path(dataset: str, db_id: str, config: dict) -> str:
    """데이터셋과 db_id로 SQLite DB 파일 경로를 반환한다."""
    if dataset == "hrdb":
        return config["evaluation"]["hrdb_db_path"]
    elif dataset == "bird":
        base_dir = os.path.dirname(config["evaluation"]["bird_dev_path"])
        return os.path.join(base_dir, "dev_databases", db_id, f"{db_id}.sqlite")
    else:
        raise ValueError(f"Unknown dataset: {dataset}")


def execute_gold_sql(sql: str, db_path: str) -> list[tuple]:
    """정답 SQL을 실행하여 결과를 반환한다."""
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5.0)
        cursor = conn.cursor()
        cursor.execute(sql)
        results = cursor.fetchall()
        conn.close()
        return results
    except Exception:
        return []


def load_few_shot_examples(dataset: str, config: dict) -> list[dict]:
    """
    Few-shot 후보를 로드한다.
    HR-DB / BIRD 모두 dev set 자체를 활용 (same-DB leave-one-out).
    각 질의 실행 시 동일 db_id 내 현재 질문을 제외한 예시만 사용한다.
    """
    if dataset == "hrdb":
        source_path = config["evaluation"]["hrdb_dev_path"]
    elif dataset == "bird":
        source_path = config["evaluation"]["bird_dev_path"]
    else:
        return []

    if not os.path.exists(source_path):
        print(f"[WARN] Few-shot source file not found: {source_path}. Proceeding without few-shot examples.")
        return []

    with open(source_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    examples = []
    for item in data:
        examples.append({
            "query": item.get("question", ""),
            "sql": item.get("query", item.get("SQL", "")),
            "schema": "",  # 스키마는 동적으로 로드됨
            "db_id": item.get("db_id", ""),
        })
    return examples


def get_full_schema(db_path: str) -> dict:
    """
    SQLite DB에서 전체 스키마를 읽어 반환한다.
    베이스라인 모델에 전달할 schema dict를 구성한다.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
    )
    tables = [row[0] for row in cursor.fetchall()]

    all_columns: dict[str, list[str]] = {}
    fk_list = []
    schema_lines = []
    for table in tables:
        cursor.execute(f"PRAGMA table_info(`{table}`);")
        cols_info = cursor.fetchall()
        cols = [col[1] for col in cols_info]
        col_types = {col[1]: col[2] for col in cols_info}
        all_columns[table] = cols

        col_defs = ", ".join(
            f"{c} {col_types.get(c, 'TEXT')}" for c in cols
        )
        schema_lines.append(f"CREATE TABLE {table} ({col_defs});")

        cursor.execute(f"PRAGMA foreign_key_list(`{table}`);")
        for fk in cursor.fetchall():
            fk_list.append({"from": f"{table}.{fk[3]}", "to": f"{fk[2]}.{fk[4]}"})

    conn.close()
    return {
        "tables": tables,
        "columns": all_columns,
        "foreign_keys": fk_list,
        "schema_text": "\n\n".join(schema_lines),
    }


def run_baseline_evaluation(
    config: dict,
    dataset: str,
    model_name: str,
    sample: int | None = None,
    seed: int = 42,
    resume: bool = True,
):
    """
    베이스라인 모델(dail_sql / mac_sql / zeroshot)로 평가를 실행한다.

    SC-TSQL과 동일한 데이터셋·샘플링·DB 경로를 사용하여
    공정 비교가 가능하도록 한다.
    """
    print(f"=== Baseline Evaluation: {model_name.upper()} on {dataset.upper()} ===")
    print(f"LLM: {config['llm']['model']}, temperature={config['llm']['temperature']}")
    print()

    # 체크포인트 경로 (베이스라인은 ablation='none' 고정)
    ckpt_path = _checkpoint_path(config, dataset, model_name, seed, sample, "none")

    # 데이터 로드
    if dataset == "hrdb":
        examples = load_hrdb_dev(config["evaluation"]["hrdb_dev_path"])
    elif dataset == "bird":
        examples = load_bird_dev(config["evaluation"]["bird_dev_path"])
    else:
        raise ValueError(f"Unknown dataset: {dataset}")

    print(f"Loaded {len(examples)} examples from {dataset}")

    if sample is not None and sample < len(examples):
        random.seed(seed)
        examples = random.sample(examples, sample)
        print(f"Sampled {sample} examples (seed={seed})")

    # 모델 초기화
    if model_name == "dail_sql":
        model = DAILSQLBaseline(config)
        # DAIL-SQL: few-shot 풀 로딩.
        # BIRD: train.json(9428개, dev와 DB 완전 분리)을 풀로 사용 — DAIL-SQL 원논문 표준.
        # HRDB: 별도 train 세트가 없어 dev 세트에서 leave-one-out으로 풀 구성.
        if dataset == "bird":
            bird_dir = Path(config["evaluation"]["bird_dev_path"]).parent
            train_path = bird_dir / "train.json"
            pool_path = str(train_path) if train_path.exists() else config["evaluation"]["bird_dev_path"]
            # dev_tables.json은 dev 전용; train DB에는 tables 메타가 없으므로 미지정.
            tables_path = str(bird_dir / "dev_tables.json") if pool_path.endswith("dev_300.json") or pool_path.endswith("dev.json") else None
            n_loaded = model.load_few_shot_pool(pool_path, tables_path=tables_path)
            pool_src = "train.json" if pool_path == str(train_path) else "dev.json"
            print(f"DAIL-SQL few-shot pool: {n_loaded} examples loaded (source={pool_src})")
        else:  # hrdb
            pool_path = config["evaluation"]["hrdb_dev_path"]
            n_loaded = model.load_few_shot_pool(pool_path, tables_path=None)
            print(f"DAIL-SQL few-shot pool: {n_loaded} examples loaded (source=hrdb dev, leave-one-out)")
    elif model_name == "mac_sql":
        model = MACSQLBaseline(config)
    elif model_name == "zeroshot":
        model = ZeroShotBaseline(config)
    else:
        raise ValueError(f"Unknown baseline model: {model_name}")

    print()

    pred_results_list = []
    gold_results_list = []
    latency_logs = []
    cost_logs: list[dict] = []
    detailed_results = []
    schema_cache: dict[str, dict] = {}

    # 체크포인트 로드
    state = _load_checkpoint(ckpt_path) if resume else None
    if state is not None:
        print(f"[Resume] checkpoint 발견: {ckpt_path.name} ({len(state.get('processed_indices', []))}/{len(examples)} 처리됨)")
        pred_results_list = [tuple(map(tuple, r)) for r in state.get("pred_results_list", [])]
        gold_results_list = [tuple(map(tuple, r)) for r in state.get("gold_results_list", [])]
        latency_logs = state.get("latency_logs", [])
        cost_logs = state.get("cost_logs", [])
        detailed_results = state.get("detailed_results", [])
        processed_indices = set(state.get("processed_indices", []))
    else:
        processed_indices = set()

    for i, example in enumerate(examples):
        if i in processed_indices:
            continue
        db_id = example["db_id"]
        question = example["question"]
        gold_sql = example["gold_sql"]
        db_path = get_db_path(dataset, db_id, config)

        if not os.path.exists(db_path):
            print(f"[{i+1}/{len(examples)}] SKIP - DB not found: {db_path}")
            continue

        # 스키마 캐시 (동일 DB 반복 로딩 방지)
        if db_id not in schema_cache:
            try:
                schema_cache[db_id] = get_full_schema(db_path)
            except Exception as e:
                print(f"[{i+1}/{len(examples)}] SKIP - Schema error for {db_id}: {e}")
                continue

        schema = schema_cache[db_id]

        # 예측 실행
        evidence = example.get("evidence", "")
        try:
            if model_name == "dail_sql":
                # DAIL-SQL leave-one-out: question_id로 자기 자신 제외
                query_id = example.get("question_id")
                pred = model.predict(question, schema, db_path, query_id=query_id, evidence=evidence)
            else:
                pred = model.predict(question, schema, db_path, evidence=evidence)
        except Exception as e:
            print(f"[{i+1}/{len(examples)}] ERROR - {db_id}: {e}")
            pred_results_list.append([])
            gold_results_list.append(execute_gold_sql(gold_sql, db_path))
            latency_logs.append(0.0)
            continue

        # 예측 SQL 실행
        pred_sql = pred.get("sql", "")
        pred_results = execute_gold_sql(pred_sql, db_path) if pred_sql else []
        gold_results = execute_gold_sql(gold_sql, db_path)

        pred_results_list.append(pred_results)
        gold_results_list.append(gold_results)
        latency_logs.append(pred.get("latency", 0.0))
        cost_logs.append(pred.get("cost", {"prompt_tokens": 0, "completion_tokens": 0}))

        pred_set = set(pred_results)
        gold_set = set(gold_results)
        status = "OK" if pred_set == gold_set else "FAIL"
        error_tag = f" [ERR: {pred.get('error', '')[:40]}]" if pred.get("error") else ""
        print(
            f"[{i+1}/{len(examples)}] {status} - {db_id}: {question[:60]}...{error_tag}"
            f" ({pred.get('latency', 0):.1f}s)"
        )

        detailed_results.append({
            "index": i,
            "db_id": db_id,
            "question": question,
            "gold_sql": gold_sql,
            "predicted_sql": pred_sql,
            "correct": pred_set == gold_set,
            "latency": pred.get("latency", 0.0),
            "cost": pred.get("cost", {}),
            "error": pred.get("error"),
        })
        processed_indices.add(i)

        # 매 샘플 후 체크포인트 저장
        _save_checkpoint(ckpt_path, {
            "processed_indices": sorted(processed_indices),
            "pred_results_list": [list(r) for r in pred_results_list],
            "gold_results_list": [list(r) for r in gold_results_list],
            "latency_logs": latency_logs,
            "cost_logs": cost_logs,
            "detailed_results": detailed_results,
        })

    # 메트릭 계산
    print()
    print("=" * 60)
    print(f"Results: {model_name.upper()} on {dataset.upper()}")
    print("=" * 60)

    ex = execution_accuracy(pred_results_list, gold_results_list)
    avg_lat = average_latency(latency_logs)
    total_prompt = sum(c.get("prompt_tokens", 0) for c in cost_logs)
    total_completion = sum(c.get("completion_tokens", 0) for c in cost_logs)

    print(f"EX  (Execution Accuracy): {ex:.4f} ({ex*100:.1f}%)")
    print(f"Avg Latency:              {avg_lat:.2f}s")
    print(f"Total tokens:             prompt={total_prompt}, completion={total_completion}")
    print(f"Total examples evaluated: {len(pred_results_list)}")
    print()

    # 결과 저장
    os.makedirs(config["output"]["results_dir"], exist_ok=True)
    timestamp = datetime.now(KST).strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(
        config["output"]["results_dir"],
        f"results_{dataset}_{model_name}_{timestamp}.json",
    )
    output_data = {
        "dataset": dataset,
        "model": model_name,
        "seed": seed,
        "sample": sample,
        "timestamp": timestamp,
        "config": {
            "llm_model": config["llm"]["model"],
        },
        "metrics": {
            "execution_accuracy": ex,
            "average_latency": avg_lat,
            "total_prompt_tokens": total_prompt,
            "total_completion_tokens": total_completion,
            "total_evaluated": len(pred_results_list),
        },
        "detailed_results": detailed_results,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    # 정상 완료 시 체크포인트 삭제
    if ckpt_path.exists():
        ckpt_path.unlink()

    print(f"Results saved to: {output_path}")
    return output_data


ABLATION_PRESETS = {
    "none": AblationFlags(),
    # RQ1 순수 테스트: NLI 모델/reranker는 유지, NLI 기반 교정 트리거만 비활성화
    # (disable_semantic_verifier와 달리 초기 SQL 생성은 동일하게 유지됨)
    "no_nli": AblationFlags(disable_nli_correction_trigger=True),
    # RQ2: 오류 유형별 지시문 → 단일 공용 지시문
    "no_routing": AblationFlags(use_generic_correction_prompt=True),
    # Improvement #3: 교정 이력 참조 제거
    "no_history": AblationFlags(disable_correction_history=True),
    # 전체 교정 루프 비활성화 (하한선)
    "no_loop": AblationFlags(disable_correction_loop=True),
    # Schema linker 비활성 (전체 스키마 사용)
    "no_schema_linker": AblationFlags(disable_schema_linker=True),
    # (참고) NLI verifier 자체를 제거하는 구버전 no_nli — reranker도 함께 꺼짐
    "no_nli_full": AblationFlags(disable_semantic_verifier=True),
    # Cross-encoder reranking만 비활성화
    "no_reranking": AblationFlags(disable_reranking=True),
}


def _checkpoint_path(config: dict, dataset: str, model_name: str, seed: int,
                     sample: int | None, ablation_name: str) -> Path:
    ckpt_dir = Path(config["output"]["checkpoint_dir"])
    ckpt_dir.mkdir(parents=True, exist_ok=True)
    n_part = f"n{sample}" if sample else "nall"
    return ckpt_dir / f"ckpt_{dataset}_{model_name}_{ablation_name}_seed{seed}_{n_part}.json"


def _load_checkpoint(ckpt_path: Path) -> dict | None:
    if not ckpt_path.exists():
        return None
    try:
        with open(ckpt_path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[WARN] checkpoint 로드 실패({ckpt_path.name}): {e}")
        return None


def _save_checkpoint(ckpt_path: Path, state: dict):
    tmp = ckpt_path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False)
    tmp.replace(ckpt_path)


def run_evaluation(
    config: dict,
    dataset: str,
    sample: int | None = None,
    seed: int = 42,
    ablation_name: str = "none",
    resume: bool = True,
):
    """전체 평가를 실행한다."""
    ablation = ABLATION_PRESETS.get(ablation_name)
    if ablation is None:
        raise ValueError(f"Unknown ablation: {ablation_name}. Choices: {list(ABLATION_PRESETS)}")

    print(f"=== SC-TSQL Evaluation on {dataset.upper()} ===")
    print(f"Config: max_rounds={config['correction']['max_rounds']}, "
          f"semantic_threshold={config['correction']['semantic_threshold']}, "
          f"ablation={ablation_name}")
    print()

    # 데이터 로드
    if dataset == "hrdb":
        examples = load_hrdb_dev(config["evaluation"]["hrdb_dev_path"])
    elif dataset == "bird":
        examples = load_bird_dev(config["evaluation"]["bird_dev_path"])
    else:
        raise ValueError(f"Unknown dataset: {dataset}")

    print(f"Loaded {len(examples)} examples from {dataset}")

    # 샘플링
    if sample is not None and sample < len(examples):
        random.seed(seed)
        examples = random.sample(examples, sample)
        print(f"Sampled {sample} examples (seed={seed})")

    # Few-shot 후보 로드
    few_shot_examples = load_few_shot_examples(dataset, config)
    print(f"Loaded {len(few_shot_examples)} few-shot candidates")
    print()

    # 체크포인트 로드 (있으면 처리된 인덱스 skip)
    ckpt_path = _checkpoint_path(config, dataset, "sc_tsql", seed, sample, ablation_name)
    state = _load_checkpoint(ckpt_path) if resume else None
    if state is not None:
        print(f"[Resume] checkpoint 발견: {ckpt_path.name} ({len(state.get('processed_indices', []))}/{len(examples)} 처리됨)")
        pred_results_list = [tuple(map(tuple, r)) for r in state.get("pred_results_list", [])]
        gold_results_list = [tuple(map(tuple, r)) for r in state.get("gold_results_list", [])]
        correction_logs = state.get("correction_logs", [])
        latency_logs = state.get("latency_logs", [])
        intent_logs = state.get("intent_logs", [])
        confidence_logs = state.get("confidence_logs", [])
        stage_latency_logs = state.get("stage_latency_logs", {})
        detailed_results = state.get("detailed_results", [])
        processed_indices = set(state.get("processed_indices", []))
    else:
        pred_results_list = []
        gold_results_list = []
        correction_logs = []
        latency_logs = []
        intent_logs = []
        confidence_logs = []
        stage_latency_logs = {}
        detailed_results = []
        processed_indices = set()

    # DB별로 파이프라인 캐시 (동일 DB는 재사용)
    pipeline_cache = {}
    validator = ExecutionValidator()

    for i, example in enumerate(examples):
        if i in processed_indices:
            continue
        db_id = example["db_id"]
        question = example["question"]
        gold_sql = example["gold_sql"]
        db_path = get_db_path(dataset, db_id, config)

        if not os.path.exists(db_path):
            print(f"[{i+1}/{len(examples)}] SKIP - DB not found: {db_path}")
            continue

        # Same-DB leave-one-out: 현재 질문을 제외한 동일 db_id 예시만 사용
        db_few_shot = [
            ex for ex in few_shot_examples
            if ex["db_id"] == db_id and ex["query"] != question
        ]

        # 파이프라인 초기화 (DB별 캐시)
        if db_id not in pipeline_cache:
            try:
                pipeline_cache[db_id] = SCTSQL(db_path, config, db_few_shot, ablation=ablation)
            except Exception as e:
                print(f"[{i+1}/{len(examples)}] SKIP - Pipeline init error for {db_id}: {e}")
                continue

        pipeline = pipeline_cache[db_id]

        # Few-shot 예시를 현재 질문에 맞게 업데이트 (leave-one-out)
        pipeline.sql_generator.few_shot_examples = db_few_shot
        pipeline.sql_generator._example_embeddings = None  # 임베딩 캐시 무효화

        # SC-TSQL 실행
        try:
            result = pipeline.run(question, evidence=example.get("evidence", ""))
        except Exception as e:
            print(f"[{i+1}/{len(examples)}] ERROR - {db_id}: {e}")
            pred_results_list.append([])
            gold_results_list.append(execute_gold_sql(gold_sql, db_path))
            latency_logs.append(0.0)
            correction_logs.append({"had_error": True, "corrected_successfully": False})
            processed_indices.add(i)
            continue

        # 정답 SQL 실행
        gold_results = execute_gold_sql(gold_sql, db_path)

        # 결과 수집
        pred_results_list.append(result.results)
        gold_results_list.append(gold_results)
        latency_logs.append(result.latency)

        # RQ1: 의도 일치 점수 수집 (NLI 검증이 수행된 항목만)
        if result.final_verification is not None:
            intent_logs.append({
                "score": float(result.final_verification.similarity_score),
                "is_consistent": bool(result.final_verification.is_consistent),
            })

        # Phase 2: SQL 생성 신뢰도 수집
        confidence_logs.append(result.sql_confidence)

        # Phase 2: 단계별 latency 누적
        for stage, t in result.stage_latency.items():
            if stage not in stage_latency_logs:
                stage_latency_logs[stage] = []
            stage_latency_logs[stage].append(t)

        # 교정 로그
        had_error = result.total_correction_rounds > 0
        pred_set = set(result.results) if result.results else set()
        gold_set = set(gold_results) if gold_results else set()
        corrected_successfully = had_error and (pred_set == gold_set)

        correction_logs.append({
            "had_error": had_error,
            "corrected_successfully": corrected_successfully,
        })

        # 상세 결과 기록
        detailed_results.append({
            "index": i,
            "db_id": db_id,
            "question": question,
            "gold_sql": gold_sql,
            "predicted_sql": result.final_sql,
            "correct": pred_set == gold_set,
            "latency": result.latency,
            "stage_latency": result.stage_latency,
            "sql_confidence": result.sql_confidence,
            "correction_rounds": result.total_correction_rounds,
            "correction_history": result.correction_history,
        })
        processed_indices.add(i)

        # 매 샘플 후 체크포인트 저장 (크래시 시 재개 가능)
        _save_checkpoint(ckpt_path, {
            "processed_indices": sorted(processed_indices),
            "pred_results_list": [list(r) for r in pred_results_list],
            "gold_results_list": [list(r) for r in gold_results_list],
            "correction_logs": correction_logs,
            "latency_logs": latency_logs,
            "intent_logs": intent_logs,
            "confidence_logs": confidence_logs,
            "stage_latency_logs": stage_latency_logs,
            "detailed_results": detailed_results,
        })

        # 진행 상황 출력
        status = "OK" if pred_set == gold_set else "FAIL"
        rounds_info = f" (corrected x{result.total_correction_rounds})" if had_error else ""
        conf_info = f" conf={result.sql_confidence:.2f}"
        print(f"[{i+1}/{len(examples)}] {status} - {db_id}: {question[:60]}...{rounds_info}{conf_info} ({result.latency:.1f}s)")

    # 메트릭 계산
    print()
    print("=" * 60)
    print(f"Results for {dataset.upper()}")
    print("=" * 60)

    ex = execution_accuracy(pred_results_list, gold_results_list)
    csr = correction_success_rate(correction_logs)
    avg_lat = average_latency(latency_logs)
    intent = intent_match_score(
        intent_logs,
        threshold=config["correction"]["semantic_threshold"],
    )

    # Phase 2: 단계별 평균 latency 계산
    avg_stage_latency = {
        stage: round(sum(times) / len(times), 3)
        for stage, times in stage_latency_logs.items()
    }
    avg_confidence = sum(confidence_logs) / len(confidence_logs) if confidence_logs else 0.0

    print(f"EX  (Execution Accuracy):      {ex:.4f} ({ex*100:.1f}%)")
    print(f"CSR (Correction Success Rate): {csr:.4f} ({csr*100:.1f}%)")
    print(
        f"IMS (Intent-Match Score):      mean={intent['mean_score']:.4f}, "
        f"consistency@{intent['threshold']}={intent['consistency_rate']*100:.1f}% "
        f"(n={intent['n']})"
    )
    print(f"Avg Confidence (SQL gen):      {avg_confidence:.4f}")
    print(f"Avg Latency (total):           {avg_lat:.2f}s")

    # Phase 2: 단계별 latency 보고
    if avg_stage_latency:
        print("  Stage Breakdown:")
        for stage, t in sorted(avg_stage_latency.items()):
            print(f"    {stage:<30} {t:.3f}s")

    print(f"Total examples evaluated:      {len(pred_results_list)}")
    print()

    # 결과 저장
    os.makedirs(config["output"]["results_dir"], exist_ok=True)
    timestamp = datetime.now(KST).strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(
        config["output"]["results_dir"],
        f"results_{dataset}_sc_tsql_{ablation_name}_seed{seed}_{timestamp}.json",
    )

    output_data = {
        "dataset": dataset,
        "model": "sc_tsql",
        "ablation": ablation_name,
        "seed": seed,
        "sample": sample,
        "timestamp": timestamp,
        "config": {
            "llm_model": config["llm"]["model"],
            "max_rounds": config["correction"]["max_rounds"],
            "semantic_threshold": config["correction"]["semantic_threshold"],
        },
        "metrics": {
            "execution_accuracy": ex,
            "correction_success_rate": csr,
            "intent_match": intent,
            "average_latency": avg_lat,
            "avg_sql_confidence": avg_confidence,
            "avg_stage_latency": avg_stage_latency,
            "total_evaluated": len(pred_results_list),
        },
        "detailed_results": detailed_results,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    # 정상 완료 시 체크포인트 삭제
    if ckpt_path.exists():
        ckpt_path.unlink()

    print(f"Results saved to: {output_path}")
    return output_data


def main():
    parser = argparse.ArgumentParser(description="SC-TSQL Evaluation Script")
    parser.add_argument(
        "--config",
        type=str,
        default="configs/config.yaml",
        help="Path to config YAML file",
    )
    parser.add_argument(
        "--dataset",
        type=str,
        choices=["hrdb", "bird"],
        default="hrdb",
        help="Dataset to evaluate on (hrdb or bird)",
    )
    parser.add_argument(
        "--model",
        type=str,
        choices=["sc_tsql", "dail_sql", "mac_sql", "zeroshot"],
        default="sc_tsql",
        help="Model to evaluate: sc_tsql (제안 모델) | dail_sql | mac_sql | zeroshot",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=None,
        help="Number of examples to sample (default: all). Sampled randomly with fixed seed.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for sampling (default: 42)",
    )
    parser.add_argument(
        "--ablation",
        type=str,
        choices=list(ABLATION_PRESETS.keys()),
        default="none",
        help=("Ablation preset for SC-TSQL. "
              "none(기본) | no_nli(RQ1: -NLI) | no_routing(RQ2: -typed routing) | "
              "no_history(improvement #3 제거) | no_loop(전체 교정 비활성) | "
              "no_schema_linker(전체 스키마 사용)"),
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="기존 체크포인트가 있어도 처음부터 재실행한다.",
    )
    args = parser.parse_args()

    with open(args.config, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    resume = not args.no_resume
    if args.model == "sc_tsql":
        run_evaluation(
            config, args.dataset, sample=args.sample, seed=args.seed,
            ablation_name=args.ablation, resume=resume,
        )
    else:
        if args.ablation != "none":
            print(f"[WARN] --ablation은 sc_tsql 모델에만 적용됩니다. 무시합니다.")
        run_baseline_evaluation(
            config, args.dataset, args.model, sample=args.sample, seed=args.seed,
            resume=resume,
        )


if __name__ == "__main__":
    main()
