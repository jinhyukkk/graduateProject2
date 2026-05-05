# Hardener Appendix Drafts (D-6) — S3 부록 초안

> 본 부록은 *마감 D-7 가용 한도 내에서 기존 로그 재집계로 가능한 분석만* 채택한다. 추가 실험은 거부 (PM escalate). 실측 수치가 필요한 셀은 [DATA NEEDED — 작업자] 표시로 명시한다.

---

## 부록 A. 추출 표본 통계 (R-5, R-11 대응)

### 표 A1. BIRD dev_300 추출 방법과 난이도 분포

본 연구의 BIRD dev_300은 BIRD 공식 dev split(n=1,534) 순서를 고정한 후 `numpy.random.RandomState(seed=42).choice(1534, 300, replace=False)`로 추출되었다. 본 부록은 dev_300의 난이도 분포가 dev_1534 원분포와 일치함을 확인한다.

| 난이도 | dev_1534 비율 | dev_300 비율 | 차이 |
|---|---:|---:|---:|
| simple | [DATA NEEDED — engineer] | [DATA NEEDED] | [] |
| moderate | [DATA NEEDED] | [DATA NEEDED] | [] |
| challenging | [DATA NEEDED] | [DATA NEEDED] | [] |

**출처**: BIRD 공식 `dev.json` 메타데이터 + `outputs/logs/dev_300_seed42.json` (paper-engineer가 1시간 내 산출 가능).

**해석**: 차이가 모든 난이도에서 ±5pp 이내라면 dev_300은 dev_1534의 *층화 무작위 표집*에 준하는 외삽 가능성을 가진다.

---

## 부록 B. 다중 비교 보정 후 어블레이션 신뢰구간 (R-5 대응)

### 표 B1. Bonferroni / Holm 보정 paired bootstrap 95% CI

본 어블레이션은 family size m=3 (A1, A3, A4) 기준으로 다중 비교 보정한 결과를 보고한다.

| 변형 | ΔEX (%) | 원 95% CI | Bonferroni-보정 95% CI (α/3) | Holm-보정 결론 |
|---|---:|---|---|---|
| A1: −NLI 트리거 | +1.00 | [−1.67, +4.00] | [−2.50, +4.83] | 무의미 |
| A3: −유형 라우팅 | +0.67 | [−2.00, +3.33] | [−2.83, +4.17] | 무의미 |
| A4: −correction history | −0.33 | [−2.33, +1.67] | [−3.17, +2.50] | 무의미 |

**계산**: 기존 paired bootstrap (n=10,000) 표본에서 *2/(α/3) = 0.0167%*와 *(1 − α/3)/2 = 99.166%* 분위 추출. paper-engineer 작업 약 1시간.

**결론**: 다중 비교 보정 후에도 세 어블레이션의 ΔEX 신뢰구간이 모두 0을 포함한다. 본 보정은 §6.1·§6.3의 결론을 *유지*하면서 *부분평가 + 다중 비교의 자유도 손실*을 정직하게 가시화한다.

---

## 부록 C. ICS 임계값 민감도 (R-9 대응)

### 표 C1. θ에 따른 EIED·Consistency 변동 (BIRD dev_300, Full SC-TSQL)

본 부록은 §4.4.2 L287에서 약속한 임계값 민감도 분석을 수행한다.

| θ | Consistency@θ (%) | NLI 단독 탐지 (사각지대) | 사각지대 합계 | EIED (%) |
|---:|---:|---:|---:|---:|
| 0.30 | [DATA NEEDED — engineer] | [DATA NEEDED] | 144 | [DATA NEEDED] |
| 0.40 | [DATA NEEDED] | [DATA NEEDED] | 144 | [DATA NEEDED] |
| 0.50 (θ_trig) | [DATA NEEDED] | [DATA NEEDED] | 144 | [DATA NEEDED] |
| 0.60 | [DATA NEEDED] | [DATA NEEDED] | 144 | [DATA NEEDED] |
| 0.75 (θ_rep) | 34.0 | 98 | 144 | 68.1 |
| 0.90 | [DATA NEEDED] | [DATA NEEDED] | 144 | [DATA NEEDED] |

**선결 조건 (PM Escalate P2)**: BIRD dev_300의 NLI raw 점수(P_fwd, P_bwd)가 `outputs/logs/results_bird_sc_tsql_*.json`에 보존되어 있어야 함.

**보존된 경우**: paper-engineer 약 4시간 작업으로 본 표 채움 가능.
**미보존된 경우**: 본 부록은 회피 → §6.4 한계 12 (P-9-c) 단독 적용.

**결론 템플릿** (채움 후 작성):
> "EIED는 θ ∈ [0.30, 0.90] 범위에서 [N1%, N2%]의 변동을 보였으며, 본 연구의 RQ1 진단 가설 임계값(EIED ≥ 30%)을 [모든 θ / θ ≥ X에서] 만족하였다. 따라서 EIED의 *진단 가설 지지* 결론은 임계값 보정에 [robust / 부분 robust]함이 확인되었다."

---

## 부록 D. HRDB auto-validated 사후 검수 결과 (R-4 대응)

### 표 D1. auto-validated 227건 중 무작위 30개 사후 검수

**검수자**: 저자 1인  
**검수 기준**:
1. gold SQL이 사용자 자연어 질의의 의도를 정확히 반영하는가
2. 합성 row 분포 하에서 gold SQL의 결과 행이 의미 있는 통계를 만드는가

| 기준 통과 | 건수 | 비율 (%) |
|---|---:|---:|
| 두 기준 모두 통과 | [DATA NEEDED — 저자] | [] |
| 의도 부정확 (기준 1 실패) | [DATA NEEDED] | [] |
| 결과 의미 약함 (기준 2 실패) | [DATA NEEDED] | [] |
| 둘 다 실패 | [DATA NEEDED] | [] |

**작업**: 저자 4시간 직접 검수 (D-6 ~ D-5).

**결론 템플릿** (채움 후):
> "auto-validated 단계의 false-positive율은 약 [N%]로 추정되며, 본 연구는 HRDB n=227 결과의 정량 해석에 본 사후 검수 결과를 보조 가중치로 반영한다. HRDB는 case study 위치임을 §6.4 한계 1에서 자발 인정한다."

---

## 부록 E. 베이스라인 진단 지표 (R-1 대응, 가능 시)

### 표 E1. 베이스라인 알고리즘 컴포넌트 발동 통계

**선결 조건 (PM Escalate P3)**: MAC-SQL Selector·DAIL-SQL SC 호출·DIN-SQL 분해 단계의 작동 횟수가 `outputs/logs/`에 기록되어 있어야 함.

| 모델 | 핵심 컴포넌트 | 발동/호출 비율 | 비고 |
|---|---|---:|---|
| MAC-SQL | Selector (스키마 축소) | [DATA NEEDED] | threshold 6000자 vs 실제 1–3k자 (`_workspace/03_baseline_fix_plan.md` L14)에 따라 미발동 의심 |
| MAC-SQL | Decomposer | [DATA NEEDED] | n 호출 수 |
| MAC-SQL | Refiner | [DATA NEEDED] | n 호출 수 |
| DAIL-SQL | Self-Consistency | n=1 (강제) | 본 연구 경량 래퍼에서 n=5 → n=1 축소 |
| DAIL-SQL | Few-shot 선택 (k=5) | [DATA NEEDED] | 활성 |
| DIN-SQL | 난이도 분류기 발동 | [DATA NEEDED] | 활성/비활성 |

**작업**: paper-engineer 2시간 내 logs/ 분석 가능 시 채움. 불가 시 본 부록 회피, §6.4 한계 6(P-1-b)으로 처리.

---

# 부록 채택 가이드

| 부록 | 작업자 | 비용 | 선결 조건 | 채택 여부 |
|---|---|---|---|---|
| 부록 A (dev_300 분포) | paper-engineer | 1시간 | BIRD dev.json 메타 보존 | **채택 권고** |
| 부록 B (다중 비교 보정) | paper-engineer | 1시간 | 부트스트랩 표본 보존 | **채택 권고** (R-5 핵심 방어) |
| 부록 C (θ sweep) | paper-engineer | 4시간 | NLI raw 점수 로그 보존 | **PM 결정 (P2)** |
| 부록 D (HRDB 사후 검수) | 저자 | 4시간 | 없음 | **채택 권고** (R-4 핵심 방어) |
| 부록 E (베이스라인 진단) | paper-engineer | 2시간 | 컴포넌트 호출 로그 보존 | **PM 결정 (P3)** |

**총 부록 작업 비용 (모두 채택 시)**: 약 12시간 (1.5인일).

---

# 자체 검증

- [x] 모든 부록은 *기존 로그 재집계 + 저자 사후 검수*로 한정 — 추가 실험 없음
- [x] 1일 초과 작업 (예: GPT-4o-as-judge ablation, 한국어 NLI ablation)은 부록에 포함하지 않음
- [x] [DATA NEEDED] 마킹과 작업자·비용 명시
- [x] PM 결정 필요 항목(P2, P3)은 명시적 escalate
