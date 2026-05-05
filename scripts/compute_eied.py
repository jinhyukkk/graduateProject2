"""EIED — NLI 독립 탐지율 산출 스크립트.

§5.2.3 정의:
    EIED = |{q : exec_valid(q)=True ∧ EX(q)=0 ∧ ICS(q)<θ}|
         / |{q : exec_valid(q)=True ∧ EX(q)=0}|

즉 실행 검증을 통과한 쿼리 중 실제로는 오답인 *사각지대* 쿼리에 한정해,
NLI가 ICS<θ로 단독 탐지한 비율을 계산한다. evaluate.py가 출력하는
detailed_results JSON을 입력으로 받는다.

사용법:
    python scripts/compute_eied.py outputs/logs/<run>/detailed_results.json
    또는
    python scripts/compute_eied.py outputs/logs/<run>/  # 디렉토리 자동 탐색
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def compute_eied(records: list[dict]) -> dict:
    """detailed_results 리스트로부터 EIED 및 관련 지표를 계산한다."""
    total = len(records)
    if total == 0:
        return {"total": 0, "note": "empty input"}

    # NLI 유효성: nli_score가 None이 아닌 샘플만 분석 대상
    nli_records = [r for r in records if r.get("nli_score") is not None]
    n_nli = len(nli_records)

    exec_pass = [r for r in nli_records if r.get("exec_validator_pass") is True]
    exec_pass_correct = [r for r in exec_pass if r.get("final_ex_correct") is True]
    blind_spot = [r for r in exec_pass if r.get("final_ex_correct") is False]
    eied_caught = [r for r in blind_spot if r.get("nli_flag") is True]

    overall_correct = sum(1 for r in records if r.get("final_ex_correct"))

    return {
        "total_samples": total,
        "samples_with_nli": n_nli,
        "exec_pass": len(exec_pass),
        "exec_pass_correct": len(exec_pass_correct),
        "blind_spot": len(blind_spot),
        "eied_caught_by_nli": len(eied_caught),
        "EIED": (len(eied_caught) / len(blind_spot)) if blind_spot else None,
        "overall_EX": overall_correct / total,
        "exec_pass_rate": len(exec_pass) / n_nli if n_nli else None,
        "blind_spot_rate_among_exec_pass": (len(blind_spot) / len(exec_pass)) if exec_pass else None,
    }


def find_results_file(arg: str) -> Path:
    p = Path(arg)
    if p.is_file():
        return p
    if p.is_dir():
        candidates = list(p.glob("**/detailed_results.json"))
        if not candidates:
            raise FileNotFoundError(f"No detailed_results.json under {p}")
        # 가장 최근 파일 우선
        return max(candidates, key=lambda x: x.stat().st_mtime)
    raise FileNotFoundError(arg)


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python scripts/compute_eied.py <detailed_results.json | run_dir>")
        return 1

    path = find_results_file(sys.argv[1])
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    records = data if isinstance(data, list) else data.get("detailed_results", [])

    metrics = compute_eied(records)

    print(f"Source: {path}")
    print("─" * 60)
    eied = metrics.get("EIED")
    eied_str = f"{eied * 100:.1f}%" if eied is not None else "N/A"
    print(f"Total samples:                    {metrics['total_samples']}")
    print(f"Samples with NLI verification:    {metrics['samples_with_nli']}")
    print(f"Exec validator pass (no err):     {metrics['exec_pass']}")
    print(f"  ├─ correct (EX=1):              {metrics['exec_pass_correct']}")
    print(f"  └─ blind spot (EX=0):           {metrics['blind_spot']}")
    print(f"     └─ NLI caught (ICS<θ):       {metrics['eied_caught_by_nli']}")
    print()
    print(f"  Overall EX:                     {metrics['overall_EX'] * 100:.1f}%")
    print(f"  ★ EIED (NLI 독립 탐지율):       {eied_str}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
