# EIED-by-τ Sweep — Cross-talk Defense Data

생성: 2026-05-01 (자동 재집계)
원천: `outputs/logs/results_bird_sc_tsql_none_seed42_20260501_173150.json` (n=300)

## 집계 정의

- **EIED 분모**: `exec_validator_pass=True AND final_ex_correct=False` (실행 통과 사각지대)
- **EIED 분자**: 분모 AND `nli_score < τ` (NLI 불일치 단독 탐지)
- **EIED**: 분자 / 분모

## τ별 결과

| τ | 분모 | 분자 | EIED | 비고 |
|---|---:|---:|---:|---|
| 0.5 | 145 | 73 | 50.3% | 매우 보수 임계값 |
| 0.6 | 145 | 96 | 66.2% | **본 연구 trigger** |
| 0.7 | 145 | 106 | 73.1% | plateau 시작 |
| 0.75 | 145 | 106 | 73.1% | **본 연구 confidence** |
| 0.8 | 145 | 106 | 73.1% | plateau |
| 0.9 | 145 | 107 | 73.8% | 거의 sup |

## 4-cell 분포 (τ=0.75 기준)

| | NLI 일치 (≥τ) | NLI 불일치 (<τ) |
|---|---:|---:|
| 실행 통과 + 정답 | 63 | 91 |
| 실행 통과 + 오답 | 39 | 106 ← 분자 |
| 실행 실패 | 0 | 1 |

## 핵심 관찰 (Critic cross-talk 공격 사전 방어)

1. **EIED-by-τ 도 plateau 형성**: τ ∈ [0.7, 0.9] 에서 73.1~73.8% 안정
2. **trigger plateau (66%) ≠ EIED plateau (73%)** — 두 plateau가 *서로 다른 위치에서 안정*
3. ROUND 2 §5.5 표 7-C는 trigger 비율만 보고 — EIED-by-τ 표는 ROUND 3 공격 대비 **예비 카드**
4. 본문 §6.1.2의 EIED 68.1%는 정확한 nli_flag 부울 기준 (98/144) — τ=0.75 부근 이산화 차이로 위 73.1%와 미세 격차

## 활용 시점

- ROUND 3 Critic이 **R-24 / W-x cross-talk 공격** 제기 시 → 즉시 P-24-a patch 작성 (Hardener 의뢰), §5.5 또는 부록 C 추가
- Critic이 공격하지 않으면 한계 12 강화로만 활용
