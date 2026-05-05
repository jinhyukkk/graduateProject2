"""reasoning_chunk SSE 이벤트가 점진적으로 흐르는지 1개 시나리오로 점검한다.

각 chunk 도착 시각을 기록해, OpenAI streaming이 실제로 토큰 단위로
들어오는지(즉, 클라이언트가 ChatGPT 같은 글자 흐름을 볼 수 있는지) 검증.
"""

import json
import time
import urllib.request

API = "http://localhost:8000/api/query/stream"
QUESTION = "각 부서의 인원수와 평균 근속연수를 같이 보여줘"


def main() -> int:
    payload = json.dumps({
        "query": QUESTION,
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

    print(f"Q: {QUESTION}\n{'─' * 70}")

    t0 = time.time()
    chunks: list[tuple[float, str]] = []
    cur_event = None
    accumulated = ""
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
                if cur_event == "reasoning_chunk":
                    text = data.get("text", "")
                    accumulated += text
                    chunks.append((t, text))
                    # 줄바꿈 단위로 진행 출력 (원본 문자는 stdout에 그대로 흘려보냄)
                    print(text, end="", flush=True)
                elif cur_event == "sql_generated":
                    print(f"\n\n[{t:5.2f}s] sql_generated → {data.get('sql', '')[:140]}")
                elif cur_event == "result":
                    print(f"[{t:5.2f}s] result rows={len(data.get('result', {}).get('rows', []))} latency={data.get('latency', 0):.2f}s")
                elif cur_event == "error":
                    print(f"\n[{t:5.2f}s] ERROR: {data.get('message')}")
                cur_event = None
            elif line == "":
                cur_event = None

    print(f"\n{'─' * 70}")
    print(f"reasoning_chunk events: {len(chunks)}")
    if chunks:
        first_t = chunks[0][0]
        last_t = chunks[-1][0]
        avg_size = sum(len(c[1]) for c in chunks) / len(chunks)
        print(f"first chunk arrived at: {first_t:.2f}s")
        print(f"last chunk arrived at: {last_t:.2f}s  (span {last_t - first_t:.2f}s)")
        print(f"avg chunk size: {avg_size:.1f} chars")
        print(f"total reasoning chars: {len(accumulated)}")
        if last_t - first_t > 0.5:
            print("✓ Reasoning streamed progressively (good UX)")
        else:
            print("⚠ All chunks arrived almost at once — buffering may be present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
