"""
실험 결과 집계/비교 스크립트.

사용법:
  python scripts/summarize_results.py                    # 모든 결과 요약
  python scripts/summarize_results.py --seed 42          # 특정 seed
  python scripts/summarize_results.py --dataset bird     # 특정 데이터셋

각 실행 조건(sc_tsql none/no_nli/no_routing/no_history + 3 baselines)을
한 표로 비교하고 RQ1/RQ2 어블레이션 기여도를 계산한다.
"""

import argparse
import glob
import json
import os
from collections import defaultdict


def find_latest_per_condition(dataset: str, seed: int | None):
    """각 (dataset, model, ablation, seed) 조합에 대해 가장 최근 결과 파일을 반환."""
    pattern = f"outputs/logs/results_{dataset}_*.json"
    files = sorted(glob.glob(pattern))
    latest = {}
    for path in files:
        try:
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
        except Exception:
            continue
        ds = d.get("dataset", "?")
        model = d.get("model", "sc_tsql")
        ablation = d.get("ablation", "none") if model == "sc_tsql" else "-"
        s = d.get("seed", 42)
        if seed is not None and s != seed:
            continue
        key = (ds, model, ablation, s)
        # 타임스탬프 기반 최신 선택 (파일명 끝에 timestamp)
        latest[key] = (path, d)
    return latest


def print_table(results: dict, dataset: str):
    rows = [(k, v[1]) for k, v in results.items() if k[0] == dataset]
    if not rows:
        return
    # 정렬 우선순위: sc_tsql(none) → 베이스라인 → 어블레이션
    order = {"sc_tsql_none": 0, "zeroshot": 1, "dail_sql": 2, "mac_sql": 3,
             "sc_tsql_no_nli": 4, "sc_tsql_no_routing": 5, "sc_tsql_no_history": 6}
    def sort_key(r):
        k = r[0]
        tag = f"{k[1]}_{k[2]}" if k[1] == "sc_tsql" else k[1]
        return order.get(tag, 99)
    rows.sort(key=sort_key)

    print(f"\n{'='*90}")
    print(f"  {dataset.upper()} Results")
    print(f"{'='*90}")
    print(f"  {'Condition':<30} {'n':>4} {'EX':>8} {'CSR':>8} {'IMS@0.75':>10} {'Latency':>10}")
    print(f"  {'-'*88}")

    sc_full_ex = None
    for (ds, model, abl, seed), d in rows:
        m = d.get("metrics", {})
        ex = m.get("execution_accuracy", 0) * 100
        csr = m.get("correction_success_rate", 0) * 100 if "correction_success_rate" in m else None
        ims = m.get("intent_match", {}).get("consistency_rate", 0) * 100 if "intent_match" in m else None
        lat = m.get("average_latency", 0)
        n = m.get("total_evaluated", 0)

        tag = f"{model} ({abl})" if model == "sc_tsql" else model
        csr_str = f"{csr:>7.1f}%" if csr is not None else f"{'—':>8}"
        ims_str = f"{ims:>9.1f}%" if ims is not None else f"{'—':>10}"

        print(f"  {tag:<30} {n:>4} {ex:>7.1f}% {csr_str} {ims_str} {lat:>9.2f}s")

        if model == "sc_tsql" and abl == "none":
            sc_full_ex = ex

    # 어블레이션 기여도 분석
    if sc_full_ex is not None:
        print(f"\n  {'-'*88}")
        print(f"  ▶ Ablation contribution (SC-TSQL full EX = {sc_full_ex:.1f}%):")
        for (ds, model, abl, seed), d in rows:
            if model != "sc_tsql" or abl in ("none", "-"):
                continue
            ex = d.get("metrics", {}).get("execution_accuracy", 0) * 100
            delta = sc_full_ex - ex
            label = {
                "no_nli": "RQ1: NLI semantic verifier",
                "no_routing": "RQ2: Error-typed routing",
                "no_history": "Imp #3: Correction history",
                "no_loop": "Full correction loop",
                "no_schema_linker": "Schema linker (top-K pruning)",
            }.get(abl, abl)
            print(f"     {label:<40} contribution = {delta:+.1f}pp  (EX w/o = {ex:.1f}%)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--dataset", type=str, choices=["bird", "hrdb", "all"], default="all")
    args = parser.parse_args()

    bird_results = find_latest_per_condition("bird", args.seed)
    hrdb_results = find_latest_per_condition("hrdb", args.seed)

    if args.dataset in ("bird", "all"):
        print_table(bird_results, "bird")
    if args.dataset in ("hrdb", "all"):
        print_table(hrdb_results, "hrdb")

    # 전체 개요
    all_results = {**bird_results, **hrdb_results}
    print(f"\n총 {len(all_results)}개 조건 결과 집계됨.")


if __name__ == "__main__":
    main()
