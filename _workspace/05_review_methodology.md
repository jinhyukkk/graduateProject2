# 05 Review — 방법론 검토 (Methodology)

| 항목 | 값 |
|---|---|
| **대상 본** | `docs/논문_초안.md` v06+R-34 (865 line, 2026-05-02 적용본) |
| **검토 시점** | 2026-05-01 (D-7) |
| **상위 권고** | Critic ROUND 4 → Minor Revision (Critical 0 / Minor 2) |
| **본 검토 관점** | 연구 설계의 내부 정합성·NLI 임계값·어블레이션 RQ 분리·재현성 |
| **수치 원천** | `outputs/analysis/main_results_summary.md` |

---

## M-1. NLI 역번역 정의·임계값·도메인 적합성 — **Acceptable**

- **정의** (§4.4.2): `ICS = 0.6·P_fwd(entailment) + 0.4·P_bwd(entailment)` — 비대칭 보정이 명시되어 재현 가능. 모델 `cross-encoder/nli-deberta-v3-base`까지 명시.
- **이중 임계값** (§4.4.2 line 295~298, §5.1.1 line 402): θ_trig=0.6 (교정 트리거) vs θ_rep=0.75 (보고 지표 / 4-cell 라벨링) 분리가 일관 적용. ROUND 3 R-26 patch로 본문 0.5 vs 0.6 모순이 0.6으로 통일됨.
- **도메인 적합성**: 한국어 → 영어 번역 경유로 NLI를 운영함이 §6.4 한계 3에 자발 인정됨. EIED 절대값의 변동 가능성은 명기되어 있으나 *방향성*은 변경 없을 것이라는 추정도 한계 안에 편입.
- **잔여 우려**: 영어 NLI에 한국어 도메인 용어 번역을 경유하는 측정의 *방향성 자체*에 대한 외부 검증은 없음. 본 제출본 한정에서는 "한계 자발 인정 + 향후 과제"로 흡수 가능.

## M-2. 어블레이션 4종(A0/A1/A3/A4)의 RQ 분리 — **Acceptable**

- A1 (−NLI 교정 트리거 / `disable_nli_correction_trigger`)이 RQ1 *교정 모드*를 분리 검증, 표 2의 4-cell 분포와 EIED 보조 지표가 RQ1 *진단 모드*를 분리 검증. RQ1을 두 모드로 분해해 평가하는 설계는 적절.
- A3 (−유형 라우팅)이 RQ2를 직접 검증. 다만 *전역 EX 차이*는 통계적으로 무의미(+0.67pp [-2.00, +3.33])이고, 유형별 ECR(표 6: E3 +12.5pp, E7 +11.4pp)이 RQ2의 *부분적 우위*를 지지. ROUND 3 R-28 patch로 본문 표현 격하 적용 완료.
- A4 (−correction history)는 RQ에 포함되지 않은 보조 어블레이션. ΔEX = -0.33pp [-2.33, +1.67]로 사실상 무영향이며, 이를 §5.5에서 *Improvement #3*로 정직 라벨링.
- **잔여 우려**: 어블레이션 표본 수가 8~12건으로 작은 ECR 분해(표 6)는 paired bootstrap CI/Fisher's exact 미보고. 본문이 §6.4 한계 9·12로 자발 인정. **Minor 권고: 표 6 caption에 "표본 한계"를 1줄 인용** 권장.

## M-3. 지표 정의 일관성 (EIED 분모/분자) — **Major (보고 정합성)**

- **§3.2 표 2** (line 184~189): NLI 일치/불일치를 ICS ≥ 0.75 라벨로 표기 → 분모 144 (실행 통과 + 오답).
- **§5.5 표 7-D** (line 548~557): 분모 145 (`exec_validator_pass=True ∧ final_ex_correct=False`) — boundary 1건 차이.
- **§6.1.2 line 636**: 144 분모(`nli_flag` 부울) vs 145 분모(`nli_score` 이산화) 차이를 footnote `[^EIED-tau]`로 명시.
- **§5.5 line 561 footnote `[^EIED-tau]`**: τ=0.75에서 EIED 73.1% (분자/분모 = 106/145) vs §6.1.2 본문 EIED 68.1% (98/144) — 약 5pp 격차를 boundary 이산화 차이로 설명.
- **검토자 의견**: ROUND 3 R-29 patch로 boundary 차이는 명시 완료. **단 73.1% vs 68.1% 차이가 *동일 표본*의 *동일 임계값*에서 5pp 변동한다는 사실 자체가 reviewer 인상에 *측정 잡음 5pp* 신호로 읽힐 위험이 있음**. 표 7-D 본문에 "본 표 7-D 73.1%는 표 2의 68.1%와 1건 boundary + 이산화 차이의 합으로 발생, plateau 영역(τ≥0.7) 안정성에 영향 없음" 1줄 *주석 강화*를 Minor 권고.

## M-4. paired bootstrap 95% CI의 적절성 — **Acceptable**

- §5.5 표 7 caption에 `n=10,000` bootstrap iteration 명시. CI 폭은 ±2~5pp 수준으로 표본 크기(n=300)에 적정.
- **다중 비교 보정**: 한계 9에서 "다중 비교 보정 후 신뢰구간이 점추정의 7~8배"로 자발 인정. 본 제출본의 *통계적 무의미* 결론은 효과 부재가 아닌 *본 표본 규모에서 검출 불가*로 정직히 격하됨.
- **잔여 우려**: 표 6 ECR 분해의 paired bootstrap CI/Fisher's exact 미보고는 §6.3 line 747~755에서 자발 인정. ECR 분해는 본 제출본의 RQ2 *방어 진술*에 직접 의존하므로, **표 6 caption에 "표본 8~12건 한정, CI/Fisher's exact 미보고"를 1줄 명시** 권장. (Minor)

## M-5. 재현 가능성 — **Acceptable (단 1건 Major 위험)**

- 모델: `gpt-4o-2024-11-20`, 임베딩 `text-embedding-3-large`, NLI `cross-encoder/nli-deberta-v3-base`, seed=42, max_rounds K=3, θ_trig=0.6, θ_rep=0.75 — 모두 §5.1.1에 명시.
- 데이터: BIRD dev_300 (정확 split 기록은 §5.1.1에서 *공개된 dev 1,534 중 300 sample*로 모호 — 정확 인덱스 또는 sampling seed 미공개). **Major 권고: §5.1.1에 dev_300 sampling 절차(첫 300건 / random seed 42 sample / stratified 등) 1줄 명시**.
- 파일럿 로그 경로 (line 862~865): `outputs/logs/results_bird_*_seed42_*.json` — 외부 reviewer 재현 시 commit hash 부재. ROUND 3 R-25 patch로 commit hash 인용 자체를 *완전 삭제*했으므로 본 제출본의 정직성은 보존되나, **재현 가능성을 위해 부록 또는 footnote에 *제출 시점 commit*을 정직 인정으로 1건 추가** 권장. (Minor)

## M-6. self-consistency k=5 외부 흡수 명시 — **Acceptable**

- §1.3 line 81 박스에 "Self-Consistency k=5는 외부 SOTA에서 검증된 흡수 기법으로 별도 카운트하지 않음" 명문화.
- §4.3.1 line 264~273에서 SC k=5 결합 메커니즘 + 비용 곡선 (응답시간 약 3.5배, 토큰 5배) 명시.
- **표 4 line 485**: SC k=5 Full 변형의 BIRD 메인 측정이 *향후 측정* 표시 (footnote 19). 핵심 정량 결론이 SC-TSQL no_sc(k=1) 어블레이션에 의존함을 정직 인정.
- **잔여 우려 없음**: SC k=5의 *4계층 기여 외부 흡수* 라벨링은 ROUND 3 R-24 patch로 영문 Abstract에도 정합 적용됨.

## M-7. 진단 가설 임계값(EIED ≥ 30%) — **Acceptable (단 R-34 Minor 잔존)**

- §3.2 line 204·206 + §6.4 한계 7 line 766: "사전 등록 임계값이 아니다" 정직 인정. ROUND 3 R-25 patch로 footnote 16의 commit hash 허위 인용 *완전 삭제*.
- **§6.1.2 line 638** 의 "*분석 시점에 정식화*했다" 표현이 *사전 등록 부재* 자발 인정과 어구 충돌 가능성 (Critic ROUND 4 R-34) — 단독으로는 Minor. **편집 단계에서 *"분석 시점에 정식화*"를 *"분석 보고 시점에 정성 기준으로 도출*"로 1단어 강화** 권장.

---

## 방법론 검토 종합

| 우선순위 | 항목 | 권고 |
|:---:|---|---|
| Major | M-3 (EIED 분자/분모 5pp 차이 명시 강화) | 표 7-D 본문에 "5pp 차이는 boundary 이산화" 1줄 주석 |
| Major | M-5 (dev_300 sampling 절차 1줄 명시) | §5.1.1 dev_300 split 명시 |
| Minor | M-1 (한국어 NLI 한계 자발 인정 OK, 추가 작업 불요) | — |
| Minor | M-2 (표 6 caption 표본 한계 1줄) | — |
| Minor | M-4 (표 6 caption CI 미보고 명시 1줄) | — |
| Minor | M-5b (제출 시점 commit hash 정직 footnote 1건) | — |
| Minor | M-7 (line 638 "사전 설정"→"분석 보고 시점에 정식화") | R-34 1단어 patch |

**Critical: 0건**. 본 제출본의 방법론은 KITS 본심 통과 가능 수준에 도달했다.

**핵심 강점**:
- 이중 임계값 분리(θ_trig=0.6 / θ_rep=0.75)와 sensitivity sweep(표 7-C·표 7-D)으로 결과 친화적 선택 의혹 차단
- 어블레이션 A0/A1/A3/A4가 RQ1·RQ2를 분리 검증
- 한계 15건 (특히 한계 4·7·8·9·10·12·15) 자발 인정으로 정직성 확보

**핵심 약점**:
- ECR 분해(표 6) 표본 8~12건은 본 표본 규모 한정 결론 — 본문 자발 인정으로 흡수
- 재현 가능성을 위한 commit hash 인용은 ROUND 3 R-25 patch로 *완전 삭제* 됨 (정직성 vs 재현성 trade-off)
