"""논문 figure SVG 생성기.

생성 도면:
  fig_venn.svg          — 실행 축 × NLI 축 4-cell Venn (§3.2 / §6.1)
  fig_baseline_bars.svg — 베이스라인 EX 비교 막대 (§5.4)
  fig_op_tree.svg       — 운영 가이드라인 결정 트리 (§6.2)

수치는 outputs/analysis/main_results_summary.json에서 자동 로드한다.
요약이 없으면 placeholder 값을 사용한다 (논문 초안 작성 단계).
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "figures"
OUT.mkdir(parents=True, exist_ok=True)
ANALYSIS = ROOT / "outputs" / "analysis" / "main_results_summary.json"


def load_summary() -> dict:
    if ANALYSIS.exists():
        with open(ANALYSIS, encoding="utf-8") as f:
            return json.load(f)
    return {}


# -------------------------------------------------------------- 4-cell Venn
def fig_venn(
    n_total: int = 300,
    cell_tt: int = 132,  # exec=T ∧ NLI=T (둘 다 통과)
    cell_tf: int = 12,   # exec=T ∧ NLI=F (실행은 OK인데 NLI가 의심)
    cell_ft: int = 18,   # exec=F ∧ NLI=T (실행 실패인데 NLI는 OK)
    cell_ff: int = 138,  # exec=F ∧ NLI=F
    eied_caught: int = 98,
    blind_spot: int = 144,
) -> str:
    """실행축 × NLI축 4-cell Venn을 SVG로 그린다.

    셀 의미:
      TT: exec_pass + nli_pass (둘 다 통과 — 안전 영역)
      TF: exec_pass + nli_fail (실행은 통과지만 NLI가 의심 — 사각지대 후보)
      FT: exec_fail + nli_pass (실행 실패 — NLI는 의심 못 함)
      FF: exec_fail + nli_fail (둘 다 실패)
    """
    # SVG 캔버스
    W, H = 720, 460
    svg = []
    svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="-apple-system, BlinkMacSystemFont, sans-serif">')
    svg.append('<style>')
    svg.append('.cell{stroke:#333;stroke-width:1.2;}')
    svg.append('.lbl{font-size:12px;fill:#333;}')
    svg.append('.lbl-big{font-size:18px;font-weight:600;fill:#111;}')
    svg.append('.axis{font-size:13px;fill:#666;font-weight:500;}')
    svg.append('.title{font-size:16px;font-weight:700;fill:#111;}')
    svg.append('.eied{font-size:14px;font-weight:600;fill:#c0392b;}')
    svg.append('</style>')

    # 제목
    svg.append(f'<text x="{W//2}" y="28" text-anchor="middle" class="title">실행 검증축 × NLI 의도 일치축 — 사각지대 분포 (n={n_total})</text>')

    # 축 라벨
    svg.append(f'<text x="100" y="80" class="axis">실행 검증 (exec validator)</text>')
    svg.append(f'<text x="20" y="240" class="axis" transform="rotate(-90 20 240)">NLI 의미 검증 (ICS ≥ 0.75)</text>')

    # 4 cell 그리드
    cell_w, cell_h = 240, 130
    x0, y0 = 140, 100
    # exec col headers
    svg.append(f'<text x="{x0+cell_w//2}" y="{y0-10}" text-anchor="middle" class="lbl">exec_pass = True</text>')
    svg.append(f'<text x="{x0+cell_w+cell_w//2}" y="{y0-10}" text-anchor="middle" class="lbl">exec_pass = False</text>')
    # nli row headers
    svg.append(f'<text x="{x0-15}" y="{y0+cell_h//2+4}" text-anchor="end" class="lbl">NLI pass</text>')
    svg.append(f'<text x="{x0-15}" y="{y0+cell_h+cell_h//2+4}" text-anchor="end" class="lbl">NLI fail (ICS&lt;θ)</text>')

    # 4 cells with colors
    def cell(x, y, w, h, fill, n, label):
        svg.append(f'<rect class="cell" x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}"/>')
        svg.append(f'<text x="{x+w//2}" y="{y+h//2-6}" text-anchor="middle" class="lbl-big">{n}</text>')
        svg.append(f'<text x="{x+w//2}" y="{y+h//2+14}" text-anchor="middle" class="lbl">{label}</text>')

    cell(x0,            y0,            cell_w, cell_h, "#dff0d8", cell_tt, "둘 다 통과 (안전)")
    cell(x0 + cell_w,   y0,            cell_w, cell_h, "#fcf8e3", cell_ft, "실행 실패")
    cell(x0,            y0 + cell_h,   cell_w, cell_h, "#fde2e2", cell_tf, "★ 사각지대 후보")
    cell(x0 + cell_w,   y0 + cell_h,   cell_w, cell_h, "#f5b7b1", cell_ff, "둘 다 실패")

    # EIED 강조 박스
    eied_pct = round(100 * eied_caught / blind_spot, 1) if blind_spot else 0.0
    svg.append(f'<rect x="60" y="370" width="600" height="60" fill="#fff3f3" stroke="#c0392b" stroke-width="2" rx="8"/>')
    svg.append(f'<text x="80" y="395" class="eied">★ EIED (NLI 독립 탐지율) = {eied_pct}%</text>')
    svg.append(f'<text x="80" y="415" class="lbl">실행 통과한 사각지대(EX=0) {blind_spot}건 중 {eied_caught}건을 NLI가 단독 탐지 → "교정 트리거"가 아닌 "독립 진단 축" 운영 근거</text>')

    svg.append('</svg>')
    return "\n".join(svg)


# -------------------------------------------------------------- 베이스라인 막대
def fig_baseline_bars(
    bird_results: dict[str, float] | None = None,
    hrdb_results: dict[str, float] | None = None,
) -> str:
    """BIRD vs HRDB EX 막대 그래프 (모델 6개)."""
    bird = bird_results or {
        "Zero-shot": 50.7,
        "DAIL-SQL": 44.0,
        "MAC-SQL": 26.3,
        "DIN-SQL": 0.0,    # placeholder
        "SC-TSQL (no_sc)": 50.3,
        "SC-TSQL (Full)": 0.0,  # placeholder
    }
    hrdb = hrdb_results or {k: 0.0 for k in bird}

    W, H = 760, 420
    svg = []
    svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="-apple-system, BlinkMacSystemFont, sans-serif">')
    svg.append('<style>')
    svg.append('.bird{fill:#3498db;}.hrdb{fill:#e67e22;}')
    svg.append('.lbl{font-size:11px;fill:#333;}')
    svg.append('.title{font-size:16px;font-weight:700;fill:#111;}')
    svg.append('.axis{font-size:11px;fill:#666;}')
    svg.append('</style>')
    svg.append(f'<text x="{W//2}" y="26" text-anchor="middle" class="title">BIRD dev_300 vs HRDB n=257 — EX 비교 (GPT-4o-2024-11-20)</text>')

    # 축 (Y: 0~80%, X: 모델 6개)
    chart_x, chart_y = 80, 50
    chart_w, chart_h = 640, 300
    # y axis ticks
    for v in [0, 20, 40, 60, 80]:
        y = chart_y + chart_h - (v / 80) * chart_h
        svg.append(f'<line x1="{chart_x-4}" y1="{y}" x2="{chart_x+chart_w}" y2="{y}" stroke="#eee"/>')
        svg.append(f'<text x="{chart_x-8}" y="{y+4}" text-anchor="end" class="axis">{v}%</text>')
    # SOTA 참조선
    sota_y = chart_y + chart_h - (77.64 / 80) * chart_h
    svg.append(f'<line x1="{chart_x}" y1="{sota_y}" x2="{chart_x+chart_w}" y2="{sota_y}" stroke="#c0392b" stroke-dasharray="6 3" stroke-width="1.5"/>')
    svg.append(f'<text x="{chart_x+chart_w}" y="{sota_y-5}" text-anchor="end" class="lbl" fill="#c0392b">BIRD #1 (AskData + GPT-4o, 77.64%)</text>')

    # bars
    models = list(bird.keys())
    n = len(models)
    group_w = chart_w / n
    bar_w = group_w / 3.2
    for i, m in enumerate(models):
        cx = chart_x + group_w * (i + 0.5)
        # bird
        v_b = bird[m]
        h_b = (v_b / 80) * chart_h
        x_b = cx - bar_w - 2
        svg.append(f'<rect class="bird" x="{x_b}" y="{chart_y+chart_h-h_b}" width="{bar_w}" height="{h_b}"/>')
        svg.append(f'<text x="{x_b+bar_w/2}" y="{chart_y+chart_h-h_b-4}" text-anchor="middle" class="lbl">{v_b:.1f}</text>')
        # hrdb
        v_h = hrdb[m]
        h_h = (v_h / 80) * chart_h
        x_h = cx + 2
        svg.append(f'<rect class="hrdb" x="{x_h}" y="{chart_y+chart_h-h_h}" width="{bar_w}" height="{h_h}"/>')
        svg.append(f'<text x="{x_h+bar_w/2}" y="{chart_y+chart_h-h_h-4}" text-anchor="middle" class="lbl">{v_h:.1f}</text>')
        # x label
        svg.append(f'<text x="{cx}" y="{chart_y+chart_h+18}" text-anchor="middle" class="lbl">{m}</text>')

    # legend
    svg.append(f'<rect class="bird" x="{chart_x}" y="{chart_y+chart_h+40}" width="14" height="10"/>')
    svg.append(f'<text x="{chart_x+20}" y="{chart_y+chart_h+50}" class="lbl">BIRD dev_300</text>')
    svg.append(f'<rect class="hrdb" x="{chart_x+120}" y="{chart_y+chart_h+40}" width="14" height="10"/>')
    svg.append(f'<text x="{chart_x+140}" y="{chart_y+chart_h+50}" class="lbl">HRDB n=257</text>')

    svg.append('</svg>')
    return "\n".join(svg)


# -------------------------------------------------------------- 운영 가이드라인 트리
def fig_op_tree() -> str:
    """§6.2 운영 가이드라인 결정 트리."""
    W, H = 760, 540
    svg = []
    svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="-apple-system, BlinkMacSystemFont, sans-serif">')
    svg.append('<style>')
    svg.append('.box{fill:#fff;stroke:#333;stroke-width:1.5;}')
    svg.append('.lbl{font-size:12px;fill:#333;}')
    svg.append('.title{font-size:16px;font-weight:700;fill:#111;}')
    svg.append('.action{font-weight:600;}')
    svg.append('.action-auto{fill:#27ae60;}.action-warn{fill:#e67e22;}.action-hitl{fill:#c0392b;}.action-skip{fill:#7f8c8d;}')
    svg.append('.edge{stroke:#999;stroke-width:1.2;fill:none;}')
    svg.append('</style>')
    svg.append(f'<text x="{W//2}" y="28" text-anchor="middle" class="title">§6.2 NLI 검증 결과별 운영 가이드라인 (HITL 트리아지)</text>')

    def box(x, y, w, h, lines, action_class=None):
        svg.append(f'<rect class="box" x="{x}" y="{y}" width="{w}" height="{h}" rx="6"/>')
        for i, line in enumerate(lines):
            cls = "lbl"
            if action_class and i == 0:
                cls = f"lbl action {action_class}"
            svg.append(f'<text x="{x+w//2}" y="{y+18+i*16}" text-anchor="middle" class="{cls}">{line}</text>')

    def edge(x1, y1, x2, y2, label=""):
        svg.append(f'<line class="edge" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}"/>')
        if label:
            mx, my = (x1+x2)//2, (y1+y2)//2
            svg.append(f'<text x="{mx+5}" y="{my-3}" class="lbl">{label}</text>')

    # 루트
    box(280, 60, 200, 50, ["SQL 생성 + 실행"])
    edge(380, 110, 380, 145)
    box(280, 145, 200, 60, ["실행 통과?", "(exec_validator)"])
    edge(380, 205, 200, 240, "No")
    edge(380, 205, 560, 240, "Yes")

    # 실행 실패 분기
    box(80, 240, 220, 70, ["[자동 교정]", "유형별 라우팅 → 재생성", "max_rounds=3"], "action-auto")

    # 실행 통과 분기
    box(440, 240, 220, 70, ["NLI ICS ≥ θ?", "(θ=0.75)"])
    edge(550, 310, 290, 360, "No (사각지대 후보)")
    edge(550, 310, 660, 360, "Yes")

    # 사각지대 (HITL)
    box(150, 360, 280, 90, [
        "[HITL 트리아지]",
        "사용자에게 의도 재확인",
        "+ 결과 자연어 설명 동시 제시",
        "EIED 68.1%: 사각지대의 2/3 차단",
    ], "action-hitl")

    # 안전 영역
    box(540, 360, 200, 70, [
        "[자동 실행]",
        "결과를 사용자에 전달",
        "+ 확신도 표시",
    ], "action-auto")

    # 하단 박스: 결합 조건
    svg.append(f'<rect x="40" y="470" width="680" height="55" fill="#f8f9fa" stroke="#ccc" rx="6"/>')
    svg.append(f'<text x="380" y="490" text-anchor="middle" class="lbl"><tspan font-weight="700">결합 조건:</tspan> NLI ICS &lt; 0.75 AND SQL_confidence &gt; 0.7 → HITL 우선순위 高</text>')
    svg.append(f'<text x="380" y="510" text-anchor="middle" class="lbl">SC k=5 결과 다수결 일치도 &lt; 60% → 자동 교정 대신 HITL 라우팅</text>')

    svg.append('</svg>')
    return "\n".join(svg)


def main() -> int:
    summary = load_summary()
    # 기본 placeholder는 v0.4 본문 수치
    venn_data = summary.get("venn_4cell", {})
    eied = summary.get("eied", {})
    bird_ex = summary.get("bird_ex_by_model", {})
    hrdb_ex = summary.get("hrdb_ex_by_model", {})

    (OUT / "fig_venn.svg").write_text(fig_venn(
        n_total=venn_data.get("n_total", 300),
        cell_tt=venn_data.get("tt", 132),
        cell_tf=venn_data.get("tf", 12),
        cell_ft=venn_data.get("ft", 18),
        cell_ff=venn_data.get("ff", 138),
        eied_caught=eied.get("caught", 98),
        blind_spot=eied.get("blind_spot", 144),
    ), encoding="utf-8")

    (OUT / "fig_baseline_bars.svg").write_text(
        fig_baseline_bars(bird_ex or None, hrdb_ex or None),
        encoding="utf-8",
    )

    (OUT / "fig_op_tree.svg").write_text(fig_op_tree(), encoding="utf-8")

    print(f"Saved figures to {OUT}/")
    for f in OUT.glob("*.svg"):
        print(f"  {f.name}: {f.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
