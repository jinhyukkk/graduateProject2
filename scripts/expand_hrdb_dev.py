"""HRDB dev.json 확장 생성기.

기존 dev.json (30 questions)을 시드로 삼아 GPT-4o로 추가 질문-SQL 쌍을
생성한다. populated 7개 테이블(THRM100/THRM151/TORG101/TCPN203/TCPN303/
TTIM413/TTIM511)에 한정하며, 각 후보 SQL을 즉시 실행해 검증 통과한 것만 수록.

5 persona × {simple, medium, hard} 매트릭스로 다양성 확보.

산출물: data/raw/hrdb/dev_expanded.json
실행: PYTHONPATH=. python scripts/expand_hrdb_dev.py --target 150
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

ROOT = Path(__file__).resolve().parents[1]
HRDB_DIR = ROOT / "data" / "raw" / "hrdb"
DB_PATH = HRDB_DIR / "hrdb.sqlite"
SEED_PATH = HRDB_DIR / "dev.json"
OUT_PATH = HRDB_DIR / "dev_expanded.json"

POPULATED = ["THRM100", "THRM151", "TORG101", "TCPN203", "TCPN303", "TTIM413", "TTIM511"]

PERSONAS = [
    "인사 운영자 (HR Operator) — 직원 명단·재직 상태·부서 발령",
    "급여 담당자 (Payroll) — 월별 총지급액·비과세·실수령액·세금/보험 차감",
    "인사 기획자 (HR Planner) — 조직별 인원·직급 분포·근속·신규 입사 추세",
    "근태 관리자 (Time Mgr) — 시간외 근무·야간 근무·휴일 근무·근무시간",
    "휴가 관리자 (Leave Mgr) — 연차/휴가 생성·사용·잔여, 부서별 사용률",
]

DIFFICULTIES = ["simple", "medium", "hard"]


def load_schema_text() -> str:
    """populated 7개 테이블의 스키마를 LLM 프롬프트용 텍스트로 변환."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    parts = []
    for t in POPULATED:
        c.execute(f'PRAGMA table_info("{t}")')
        cols = c.fetchall()
        c.execute(f'SELECT * FROM "{t}" LIMIT 2')
        sample = c.fetchall()
        col_defs = ", ".join(f"{r[1]} {r[2]}" for r in cols)
        parts.append(f"### {t}\nCREATE TABLE {t} ({col_defs});")
        if sample:
            col_names = [r[1] for r in cols]
            for row in sample:
                kv = {k: v for k, v in zip(col_names, row) if v is not None}
                # 너무 길면 줄임
                kv_str = ", ".join(f"{k}={v!r}" for k, v in list(kv.items())[:8])
                parts.append(f"  -- sample row: {kv_str}")
    conn.close()
    return "\n".join(parts)


def load_seed_examples() -> list[dict]:
    with open(SEED_PATH, encoding="utf-8") as f:
        return json.load(f)


PROMPT_TEMPLATE = """당신은 한국어 인사(HR) 도메인의 Text-to-SQL 평가 데이터 생성 전문가입니다.
아래 HRDB 스키마와 시드 예시를 참고하여, *실제 실행 가능한* (질문, SQL) 쌍을 새로 만드세요.

## HRDB 스키마 (7개 populated 테이블)
{schema}

## 도메인 규칙
- THRM151은 인사발령 이력 테이블이며, EDATE IS NULL 인 행이 *현재 발령 상태*를 나타낸다.
- 재직자 = THRM151.STATUS_CD = 'S10' AND EDATE IS NULL
- 이름·성별 등 기본정보는 THRM100, 부서 정보는 TORG101, 발령 이력은 THRM151 join.
- JIKGUB_CD/JIKGUB_NM, JIKCHAK_CD/JIKCHAK_NM, ORG_CD/ORG_NM 등은 코드/명칭 페어. JOIN 시 *_CD = *_CD 로 연결한다.
- 급여 명세는 TCPN303, 급여 이체는 TCPN203 (PAY_ACTION_CD 예: 'P202603' = 2026년 3월).
- 시간외/야간 통계는 TTIM413 (YM 형식 'YYYYMM'), 휴가 통계는 TTIM511 (YY 형식 'YYYY').

## 시드 예시 (참고용 — 동일 표현은 피하고 *다양성*을 우선)
{seed_examples}

## 생성 지시
- persona: {persona}
- difficulty: {difficulty}
- count: {n}개 — 서로 *다른 패턴* (집계/조인/그룹/필터/시간 윈도우 등)으로 다양화

각 항목은 다음 JSON 형식으로 반환하세요. 코드 블록 없이 JSON 배열 단독으로:

[
  {{
    "question": "한국어 자연어 질문 (간결, 1문장)",
    "SQL": "실행 가능한 SQLite SQL (테이블 alias 사용, 코드/명칭 매핑 정확)",
    "difficulty": "{difficulty}",
    "persona": "{persona_short}",
    "rationale": "이 질문이 검증하는 SQL 패턴 1줄 요약"
  }},
  ...
]

중요:
- SQL은 반드시 위 7개 테이블만 사용. 다른 테이블 참조 금지.
- difficulty=simple: 단일 테이블, 1~2개 조건. medium: 2~3 테이블 JOIN, GROUP BY. hard: 다중 JOIN + 서브쿼리/HAVING/윈도우.
- "올해" 같은 상대 시간 표현은 피하고, 명시적 연/월(예: 2026, 202603)을 사용.
- 코드 컬럼만 SELECT 하지 말고 명칭 컬럼도 함께 SELECT (예: JIKGUB_CD만이 아니라 JIKGUB_NM도 같이).
- 결과가 빈 행이 안 나오도록 데이터에 존재하는 코드/명칭(예: STATUS_CD='S10' 재직, JIKGUB_NM='부장' 등)을 우선 사용.
- 시드와 *다른* 질문을 만들 것.
"""


def call_gpt4o(client: OpenAI, prompt: str, max_retries: int = 5) -> str:
    """429(rate limit)와 일시적 5xx에 대해 backoff 재시도."""
    delay = 8.0
    for attempt in range(max_retries):
        try:
            resp = client.chat.completions.create(
                model="gpt-4o-2024-11-20",
                temperature=0.8,
                max_completion_tokens=3500,
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.choices[0].message.content
        except Exception as e:
            msg = str(e)
            is_retryable = "rate_limit" in msg or "429" in msg or "5" in msg[:5]
            if attempt == max_retries - 1 or not is_retryable:
                raise
            time.sleep(delay)
            delay *= 1.5
    return ""


def parse_json_array(raw: str) -> list[dict]:
    """LLM 응답에서 JSON 배열을 robust하게 추출."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    # 첫 [ ~ 마지막 ] 만 잘라서 시도
    m = re.search(r"\[.*\]", raw, re.DOTALL)
    if m:
        raw = m.group(0)
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def execute_sql(sql: str, timeout: float = 5.0) -> tuple[bool, int, str]:
    """SQL을 실행하고 (성공여부, 행수, 에러메시지)를 반환."""
    try:
        conn = sqlite3.connect(DB_PATH, timeout=timeout)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute(sql)
        rows = c.fetchall()
        conn.close()
        return True, len(rows), ""
    except Exception as e:
        return False, 0, str(e)[:200]


def generate_batch(
    client: OpenAI,
    schema: str,
    seed_examples: list[dict],
    persona: str,
    difficulty: str,
    n: int,
) -> list[dict]:
    """1개 (persona, difficulty) 셀에 대해 n개의 질문-SQL을 생성하고 검증."""
    seed_sample = "\n".join(
        f"- ({s['difficulty']}) {s['question']}\n  SQL: {s['SQL']}"
        for s in seed_examples[:6]
    )
    # persona 라벨: 괄호 앞 한국어 명사 그대로 사용 (예: "인사 운영자")
    persona_short = persona.split(" (")[0].strip()
    prompt = PROMPT_TEMPLATE.format(
        schema=schema,
        seed_examples=seed_sample,
        persona=persona,
        persona_short=persona_short,
        difficulty=difficulty,
        n=n,
    )
    raw = call_gpt4o(client, prompt)
    items = parse_json_array(raw)
    valid = []
    for it in items:
        sql = (it.get("SQL") or "").strip().rstrip(";")
        if not sql or "SELECT" not in sql.upper():
            continue
        ok, nrows, err = execute_sql(sql)
        if not ok:
            continue
        if nrows == 0:
            # 빈 결과는 검증 가치 낮음 — 제외
            continue
        valid.append({
            "question": it.get("question", "").strip(),
            "SQL": sql,
            "difficulty": difficulty,
            "persona": persona_short,
            "rationale": it.get("rationale", "").strip(),
            "row_count": nrows,
        })
    return valid


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=150,
                    help="목표 검증 통과 항목 수 (default 150)")
    ap.add_argument("--per-cell", type=int, default=12,
                    help="cell(persona×difficulty)당 한 번에 요청할 후보 수")
    args = ap.parse_args()

    load_dotenv(ROOT / ".env")
    if not os.environ.get("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY 미설정", file=sys.stderr)
        return 1

    client = OpenAI()
    schema = load_schema_text()
    seeds = load_seed_examples()
    print(f"Schema: {sum(len(p) for p in schema.split(chr(10)))} chars over {len(POPULATED)} tables")
    print(f"Seed examples: {len(seeds)}")
    print(f"Target: {args.target} valid items")
    print(f"Cells: {len(PERSONAS) * len(DIFFICULTIES)} (persona × difficulty)")

    # Cell 단위 병렬 호출
    cells = [(p, d) for p in PERSONAS for d in DIFFICULTIES]
    all_valid: list[dict] = []

    started = time.time()
    # TPM 30K 제한 고려: max_workers=3로 동시성 낮추고, 셀 간 0.5s 짧은 페이싱
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {}
        for i, (p, d) in enumerate(cells):
            futures[pool.submit(generate_batch, client, schema, seeds, p, d, args.per_cell)] = (p, d)
            time.sleep(0.3)
        for fut in as_completed(futures):
            p, d = futures[fut]
            try:
                items = fut.result()
            except Exception as e:
                print(f"[FAIL] {p[:20]} / {d}: {str(e)[:80]}")
                continue
            all_valid.extend(items)
            print(f"[OK] {p[:20]:<22} / {d:<6} → +{len(items)} (total {len(all_valid)})")

    # 부족하면 추가 round
    rounds = 1
    while len(all_valid) < args.target and rounds < 3:
        rounds += 1
        print(f"\n=== Round {rounds}: short of target ({len(all_valid)}/{args.target}) ===")
        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = {
                pool.submit(generate_batch, client, schema, seeds + all_valid[:20], p, d, args.per_cell): (p, d)
                for p, d in cells
            }
            for fut in as_completed(futures):
                p, d = futures[fut]
                try:
                    items = fut.result()
                except Exception:
                    continue
                all_valid.extend(items)

    # 중복 제거 (질문 텍스트 기준)
    seen = set()
    deduped = []
    for it in all_valid:
        q = it["question"].strip()
        if q in seen:
            continue
        seen.add(q)
        deduped.append(it)

    # 시드와도 중복 체크
    seed_qs = {s["question"].strip() for s in seeds}
    deduped = [it for it in deduped if it["question"].strip() not in seed_qs]

    # 최종 정렬: difficulty → persona
    diff_order = {"simple": 0, "medium": 1, "hard": 2}
    deduped.sort(key=lambda x: (diff_order.get(x["difficulty"], 9), x.get("persona", "")))

    # ID 부여 + dev 형식 통일
    final = []
    for i, it in enumerate(deduped):
        final.append({
            "id": f"hrdb_ext_{i:03d}",
            "question": it["question"],
            "SQL": it["SQL"],
            "db_id": "hrdb",
            "difficulty": it["difficulty"],
            "persona": it["persona"],
            "rationale": it.get("rationale", ""),
        })

    OUT_PATH.write_text(
        json.dumps(final, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    elapsed = time.time() - started
    print(f"\n=== Done: {len(final)} items in {elapsed:.0f}s ===")
    print(f"  saved to {OUT_PATH}")
    # difficulty 분포
    from collections import Counter
    print("  difficulty dist:", Counter(x["difficulty"] for x in final))
    print("  persona dist:   ", Counter(x.get("persona", "?") for x in final))
    return 0


if __name__ == "__main__":
    sys.exit(main())
