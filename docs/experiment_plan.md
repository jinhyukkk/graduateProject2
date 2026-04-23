# 논문 완성을 위한 실험 목록

**프로젝트**: 자기교정 Text-to-SQL (NLI 의미 검증 + 오류 유형별 교정 지시문)
**대상**: 한국IT서비스학회 (KITS) 제출본
**마감**: 2026-05-08
**작성일**: 2026-04-23

---

## 연구 질문 (Research Questions)

- **RQ1.** 생성된 SQL을 자연어로 역번역해 NLI로 의미 일치를 판정하는 방식이, 기존 실행 기반 검증과 **별개로** 성능에 기여하는가?
- **RQ2.** 진단된 오류 유형별로 **다른 교정 지시문**을 쓰는 것이, 단일 공용 지시문보다 정확한가?

각 실험은 RQ1, RQ2, 또는 양쪽의 증거를 확보하기 위해 수행된다.

---

## A. 핵심 실험 — Main Results (필수)

Table 1(논문 §5.1 주 결과표)의 근거를 구성한다.

| ID | 실험 조건 | 데이터셋 | 샘플 | 모델 | 목적 |
|----|---|---|---|---|---|
| **A1** | SC-TSQL (제안 모델, 전 구성요소 활성) | BIRD dev | 300 | gpt-4o | Table 1 주인공 |
| **A2** | ZeroShot | BIRD dev | 300 | gpt-4o | 하한선 (few-shot·교정 없음) |
| **A3** | DAIL-SQL (경량 래퍼) | BIRD dev | 300 | gpt-4o | SoTA few-shot 비교 |
| **A4** | MAC-SQL (경량 래퍼) | BIRD dev | 300 | gpt-4o | SoTA multi-agent 비교 |
| **A5** | SC-TSQL | HRDB | 30 | gpt-4o | 실무 스키마(577 테이블) 검증 |
| **A6** | ZeroShot | HRDB | 30 | gpt-4o | HRDB 비교 |
| **A7** | DAIL-SQL | HRDB | 30 | gpt-4o | HRDB 비교 |
| **A8** | MAC-SQL | HRDB | 30 | gpt-4o | HRDB 비교 |

**보고 지표**: EX (Execution Accuracy), CSR (Correction Success Rate), IMS@0.75 (Intent-Match Score), Avg Latency, Token Cost

---

## B. 어블레이션 — Research Questions (필수)

Table 2(논문 §6 RQ 어블레이션)의 근거. A1과의 ΔEX로 각 구성요소 기여도를 정량화.

| ID | 실험 조건 | 대응 RQ | A1 대비 기대 효과 |
|----|---|---|---|
| **B1** | SC-TSQL **−NLI** (`--ablation no_nli`) | RQ1 | EX 저하 ⇒ NLI의 독립 기여 입증 |
| **B2** | SC-TSQL **−typed routing** (`--ablation no_routing`) | RQ2 | EX 저하 ⇒ 유형별 지시문의 우월성 입증 |
| **B3** | SC-TSQL **−correction history** (`--ablation no_history`) | Improvement #3 | EX 저하 ⇒ 교정 이력 제공의 효과 |

**모두 BIRD dev 300 + gpt-4o로 실행**. HRDB 어블레이션은 표본 30으로 검정력이 약해 생략.

---

## C. 통계 신뢰성 — Confidence Intervals (권장)

Peer review 방어·결과 변동성 정량화. 표본 하나에 의존하지 않기 위해.

| ID | 실험 | 방법 |
|----|---|---|
| **C1** | A1, B1, B2를 **seed=123, 2026** 으로 재실행 | 3 seed 평균 ± std, paired bootstrap 95% CI, p-value |

추가 실행 수: A1/B1/B2 × 2 seed = **6회**.

---

## D. 추가 분석 (A~C 결과에서 재집계 가능, 일부만 추가 실행)

논문 §6 심화 분석. 대부분 재집계, D3만 새 실행 필요.

| ID | 분석 | 데이터 소스 | 추가 실행? |
|----|---|---|---|
| **D1** | Difficulty별 EX (simple/moderate/challenging) | A1 detailed_results | ✗ |
| **D2** | Error-type별 CSR (E1~E8 + SEMANTIC_MISMATCH) | A1 correction_history | ✗ |
| **D3** | NLI threshold sweep (θ=0.6/0.7/0.75/0.8) | 별도 실행 (BIRD 100 × 4) | ✓ 4회 |
| **D4** | Correction round별 성공률 분포 (1·2·3라운드 수렴 비율) | A1 재집계 | ✗ |
| **D5** | DB별 EX (BIRD 11개 DB 서브테이블) | A1~A4 재집계 | ✗ |
| **D6** | Cost-latency 표 (token×$ vs EX) | A1~A8 cost 로그 | ✗ |
| **D7** | 정성 사례 분석 (SC-TSQL만 맞춘 10~15건 + 공통 오류 5건) | A1~A4 detailed_results 수동 선별 | ✗ |

---

## E. 논문 산출물 (실험 결과 → 지면)

| 지면 요소 | 구성 | 근거 실험 |
|---|---|---|
| **Table 1** | Main EX/CSR/IMS/Latency 비교표 | A1~A8 |
| **Table 2** | 어블레이션 기여도 | A1 vs B1, B2, B3 |
| **Table 3** | Difficulty별 EX 세분화 | D1 |
| **Table 4** (선택) | NLI threshold 민감도 | D3 |
| **Figure 1** | SC-TSQL 파이프라인 아키텍처 | `docs/sc_tsql_architecture.svg` |
| **Figure 2** | Correction round 수렴 히스토그램 | D4 |
| **Figure 3** (선택) | NLI threshold sweep 곡선 | D3 |
| **Appendix A** | 정성 사례 (SQL diff) | D7 |
| **Appendix B** | HRDB 30 쿼리 목록 | `data/raw/hrdb/dev.json` |

---

## 실행 규모 요약

| 범위 | 실행 수 | 예상 비용 (gpt-4o) | 예상 시간 |
|---|---|---|---|
| **최소 (A+B)** | 11 | ~$87 | ~11시간 |
| **권장 (A+B+C)** | 17 | ~$170 | ~20시간 |
| **풀 (A+B+C+D3)** | 21 | ~$200 | ~24시간 |

모든 실행은 체크포인트가 자동 저장되어 중단 후 재개 가능.

---

## 실행 명령어 참조

```bash
# 단일 조건 실행
python evaluate.py --config configs/config_gpt4o.yaml --dataset bird --model sc_tsql --seed 42                       # A1
python evaluate.py --config configs/config_gpt4o.yaml --dataset bird --model zeroshot --seed 42                      # A2
python evaluate.py --config configs/config_gpt4o.yaml --dataset bird --model dail_sql --seed 42                      # A3
python evaluate.py --config configs/config_gpt4o.yaml --dataset bird --model mac_sql  --seed 42                      # A4
python evaluate.py --config configs/config_gpt4o.yaml --dataset hrdb --model sc_tsql  --seed 42                      # A5~A8 (model만 변경)

# 어블레이션
python evaluate.py --config configs/config_gpt4o.yaml --dataset bird --model sc_tsql --seed 42 --ablation no_nli     # B1
python evaluate.py --config configs/config_gpt4o.yaml --dataset bird --model sc_tsql --seed 42 --ablation no_routing # B2
python evaluate.py --config configs/config_gpt4o.yaml --dataset bird --model sc_tsql --seed 42 --ablation no_history # B3

# 일괄 실행 (A1~A8 + B1~B3)
bash scripts/run_full_experiments.sh                              # 단일 seed (A+B)
SEEDS="42 123 2026" bash scripts/run_full_experiments.sh          # A+B+C
BIRD_SAMPLE=20 HRDB_SAMPLE=5 bash scripts/run_full_experiments.sh configs/config.yaml  # Phase 1 sanity (gpt-4o-mini)

# 결과 요약
python scripts/summarize_results.py --dataset bird --seed 42
python scripts/summarize_results.py --dataset hrdb --seed 42
```

---

## 실험 공정성 원칙 (KITS 제출 전 점검)

1. **동일 LLM 백본**: 모든 방법이 gpt-4o-2024-11-20 사용 (temperature=0).
2. **동일 샘플링**: 같은 seed·dev set·DB 경로.
3. **Evidence 필드**: BIRD `evidence`(외부 지식 힌트)를 모든 방법에 일관 포함.
4. **DAIL-SQL few-shot 풀**: BIRD train.json(9428개, dev와 DB 완전 분리) 사용 — 원논문 표준.
5. **베이스라인 재구현**: 논문 인용 수치 대신 GPT-4o로 재실행한 값 보고.
6. **HRDB**: 스키마만 실제 구조, 데이터는 합성 (§3에 명시).
7. **Retry/체크포인트**: 5회 지수 백오프, 샘플당 atomic write로 재현성 보장.

---

## 상태 체크리스트 (2026-04-23)

- [x] SC-TSQL 파이프라인 (improvement #1~#3 포함) 구현 완료
- [x] 베이스라인 3종 구현·동작 검증
- [x] BIRD dev_300 stratified sampling
- [x] HRDB 30 쿼리 확장 (실제 물리 테이블 기반)
- [x] DAIL-SQL 풀 train.json 전환 + 임베딩 배치화
- [x] Retry 래퍼 11개 OpenAI 호출 적용
- [x] 체크포인트/재개 로직 통합
- [x] Ablation CLI (`--ablation`)
- [x] BIRD evidence 통합 (SC-TSQL + 3 베이스라인)
- [x] 일괄 실행 스크립트 + 결과 요약 스크립트
- [ ] A1~A8 본 실험 실행 (미실행)
- [ ] B1~B3 어블레이션 실행 (미실행)
- [ ] C1 멀티시드 (선택)
- [ ] D1~D7 분석 (실행 후 수행)
- [ ] 논문 Table/Figure 구성
- [ ] KITS 양식 최종 편집
