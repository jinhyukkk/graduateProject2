"""페르소나별 데모 시나리오 smoke test — streaming API에 4개 질의를 순차 던지고
각 이벤트의 도착 시각, SQL, 교정 발동 여부를 시각적으로 출력한다.

목적: 시연 흐름이 (1) 단계별로 자연스럽게 스트리밍되는지, (2) 캐시·병렬화 후
체감 응답이 빠른지, (3) 어려운 질의에서 교정이 발동하는지 점검.
"""

import json
import sys
import time
import urllib.request

API = "http://localhost:8000/api/query/stream"

SCENARIOS = [
    # 기본 (이전 측정에서 정답)
    ("인력 현황", "재직 중인 전체 직원 수를 알려줘"),
    ("조직", "개발1팀 소속 직원 명단을 보여줘"),
    ("급여", "직급별 평균 급여를 비교해줘"),
    ("분석", "근속연수 5년 이상 직원이 몇 명이야?"),
    # 도전적 시나리오 — 정확도 약점 노출용
    ("교차집계", "부서별 평균 급여를 높은 순으로 보여줘"),
    ("서브쿼리", "전체 평균 급여보다 많이 받는 직원이 몇 명이야?"),
    ("시간계산", "올해 입사한 직원 중 이사 직급은 몇 명?"),
    ("성별집계", "여성 직원 비율은 얼마야?"),
    # 더 어려운 케이스 — CoT/도메인 룰 검증
    ("멀티집계", "부서별 직급 분포를 보여줘"),
    ("HAVING", "평균 급여가 500만원 이상인 부서만 알려줘"),
    ("부정필터", "올해 퇴사하지 않은 사람 중 5년차 이상은 몇 명이야?"),
    ("조건요약", "각 부서의 인원수와 평균 근속연수를 같이 보여줘"),
]


def stream_one(label: str, question: str) -> dict:
    """SSE 스트리밍을 라인 단위로 읽어 이벤트 타임라인을 출력한다."""
    print(f"\n{'━' * 70}")
    print(f"[{label}] {question}")
    print("━" * 70)

    payload = json.dumps({
        "query": question,
        "db_id": "hrdb",
        "dataset": "hrdb",
        "conversation_history": [],
    }).encode()

    req = urllib.request.Request(
        API,
        data=payload,
        headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
        method="POST",
    )

    t0 = time.time()
    summary = {"events": [], "sql": None, "corrected": False, "rounds": 0, "ex_ok": None}
    cur_event = None
    with urllib.request.urlopen(req, timeout=120) as resp:
        for raw in resp:
            line = raw.decode("utf-8").rstrip()
            if line.startswith("event:"):
                cur_event = line.split(":", 1)[1].strip()
            elif line.startswith("data:") and cur_event:
                payload_str = line.split(":", 1)[1].strip()
                try:
                    data = json.loads(payload_str)
                except Exception:
                    data = {}
                t = time.time() - t0
                summary["events"].append((t, cur_event))
                if cur_event == "step":
                    print(f"  {t:5.2f}s  · step={data.get('stage'):<14} round={data.get('round','-')}")
                elif cur_event == "sql_generated":
                    sql = data.get("sql", "").replace("\n", " ")
                    print(f"  {t:5.2f}s  ✎ sql_generated conf={data.get('confidence'):.3f}")
                    print(f"           → {sql[:140]}{'…' if len(sql) > 140 else ''}")
                    summary["sql"] = sql
                elif cur_event == "validated":
                    ok = data.get("success")
                    err = data.get("error_type")
                    icon = "✓" if ok else "✗"
                    print(f"  {t:5.2f}s  {icon} validated success={ok} error_type={err}")
                elif cur_event == "verified":
                    sc = data.get("score", 0.0)
                    cons = data.get("is_consistent")
                    bt = (data.get("back_translation") or "").strip().replace("\n", " ")
                    print(f"  {t:5.2f}s  ⊕ verified ICS={sc:.3f} consistent={cons}")
                    if bt:
                        print(f"           ← back-tr: {bt[:120]}{'…' if len(bt) > 120 else ''}")
                elif cur_event == "corrected":
                    summary["corrected"] = True
                    summary["rounds"] = max(summary["rounds"], data.get("round", 0))
                    print(f"  {t:5.2f}s  ↻ corrected round={data.get('round')} type={data.get('error_type')} rolled_back={data.get('rolled_back', False)}")
                elif cur_event == "explanation":
                    txt = (data.get("text") or "").replace("\n", " ")
                    print(f"  {t:5.2f}s  💬 explanation: {txt[:140]}{'…' if len(txt) > 140 else ''}")
                elif cur_event == "result":
                    rows = data.get("result", {}).get("rows", []) if isinstance(data.get("result"), dict) else []
                    print(f"  {t:5.2f}s  ✓ result rows={len(rows)} latency={data.get('latency', 0):.2f}s was_corrected={data.get('was_corrected')}")
                    summary["ex_ok"] = True
                elif cur_event == "error":
                    print(f"  {t:5.2f}s  ✗ ERROR: {data.get('message')}")
                    summary["ex_ok"] = False
                cur_event = None  # SSE: blank line ends the event
            elif line == "":
                cur_event = None

    summary["wall"] = time.time() - t0
    print(f"  └─ wall={summary['wall']:.2f}s  events={len(summary['events'])}  corrected={summary['corrected']}  rounds={summary['rounds']}")
    return summary


def main() -> int:
    summaries = []
    for label, q in SCENARIOS:
        try:
            s = stream_one(label, q)
            s["label"] = label
            summaries.append(s)
        except Exception as e:
            print(f"  [FAIL] {label}: {e}")
            summaries.append({"label": label, "wall": -1, "ex_ok": False, "corrected": False, "rounds": 0})

    print(f"\n{'═' * 70}")
    print("SUMMARY (요약)")
    print("═" * 70)
    print(f"{'페르소나':<10} {'질의':<32} {'시간':>7} {'교정':>5} {'라운드':>5} {'성공':>5}")
    for s in summaries:
        wall = f"{s['wall']:.2f}s" if s.get('wall', -1) > 0 else "FAIL"
        succ = "✓" if s.get("ex_ok") else "✗"
        corr = "✓" if s.get("corrected") else "-"
        q_excerpt = next((q for lab, q in SCENARIOS if lab == s["label"]), "")[:30]
        print(f"{s['label']:<10} {q_excerpt:<32} {wall:>7} {corr:>5} {s.get('rounds', 0):>5} {succ:>5}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
