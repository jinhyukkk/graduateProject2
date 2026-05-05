# 본 실험 실행 계획 (Day 1-2 산출물, 2026-04-25 방향 전환 반영)

**작성일**: 2026-04-25
**대상 기간**: Day 3 ~ Day 10 (2026-04-27 ~ 2026-05-04)
**목적**: 재프레이밍된 서사(§02_narrative_reframing.md)와 수정된 베이스라인(§03_baseline_fix_plan.md)을 기반으로, 본 실험 1회 실행으로 논문 본문을 확정한다.

**방향 전환 내역 (2026-04-25 최종)**:
- 백본: **GPT-4o-2024-11-20 유지** (초록 제출 시 정한 조건 준수, 석사 개인 연구 비용 현실성)
- 평가: 자체 set 비교 → **BIRD 공식 `evaluation.py`** (30초 타임아웃, 난이도별 집계, multiprocessing)
- 비교군: MAC-SQL 재포함 (GPT-4o 환경에서 관측된 수치를 정직하게 보고. "고성능 LLM에서 복잡한 프롬프트 기법의 한계 효용"이라는 §6.3 고찰과 일관)
- 서사: "자기교정 프레임워크의 EX 향상"에서 "**의도 일치 진단·교정 프로토콜**"로 재프레이밍. 제목 변경 반영
- 파일럿 RQ1 Null 관측을 **논문 기여로 전환** — "GPT-4o급 LLM에서는 교정 엔진이 아닌 독립 진단 축(실행 검증이 통과시킨 사각지대 중 NLI가 잡아내는 비율)이 실무 운영에 더 적합하다"는 발견으로 §6.1에 명시. 본 버전은 신조어·약어를 도입하지 않고 서술형으로 보고한다.

---

## 1. 실험 범위 축소 결정

### 1.1 원 계획의 문제
- 11 조건 × 2 환경(BIRD+HRDB) = 22 run. GPT-4o 기준 예상 비용 ~$87, 11시간.
- **CSR=0%** 파일럿 관측으로 일부 ablation의 한계 효용이 확인됨 → **비용 효율이 낮은 조건은 n=300 서브셋**으로 대체.

### 1.2 최종 실행 세트

#### A. BIRD dev 전체 (n=1,534) — 6 조건 (GPT-4o 백본, 공식 평가)
| # | 조건 | RQ | 목적 |
|---|---|---|---|
| A0 | Full SC-TSQL | Primary | 메인 수치 |
| A1 | −NLI 트리거 (`disable_nli_correction_trigger`) | RQ1 Primary | NLI 트리거 EX 기여 분리 |
| A3 | −유형 라우팅 (`disable_type_routing`) | RQ2 | 유형별 프롬프트 기여 분리 |
| — | Zero-shot GPT-4o | 기준선 | §5.4 표 2-B |
| — | DAIL-SQL (경량 래퍼) | 경쟁군 | §5.4 표 2-B |
| — | MAC-SQL (경량 래퍼) | 경쟁군 | §5.4 표 2-B |

**MAC-SQL 재포함 근거**: GPT-4o 환경에서 관측된 경량 래퍼 수치(파일럿 n=50에서 22%)를 정직하게 보고한다. 이는 "원 논문 수치 재현 실패"가 아니라 "**고성능 LLM에서 복잡한 프롬프트 기법의 한계 효용**"이라는 본 연구의 §6.3 핵심 관측과 합치한다.

#### B. BIRD dev 서브셋 (n=300, stratified) — 2 조건
| # | 조건 | RQ | 목적 |
|---|---|---|---|
| A2 | −역번역 (NLI에 SQL 문자열 직접 입력) | RQ1 보강 | 역번역의 기여 분리 |
| A5 | K=1 (교정 1회만) | 민감도 | §5.6 |

#### C. HRDB (n=30) — 5 조건 (GPT-4-turbo 백본)
모두 n=30에서 실행 (표본 한계로 case study 위치):
- Full SC-TSQL
- −NLI 트리거
- −한글 메타 (`disable_korean_metadata`)
- Zero-shot
- DAIL-SQL

---

## 2. 비용·시간 추정

### 2.1 BIRD (GPT-4o-2024-11-20, $2.50/1M in + $10/1M out)
| 조건 | n | 1건 평균 지연 | 1건 평균 토큰 | 예상 비용 | 예상 시간 |
|---|---|---|---|---|---|
| Full SC-TSQL | 1,534 | 10.5s | ~6k / 400 | ~$30 | 4.5h |
| −NLI 트리거 | 1,534 | 9.5s | ~5k / 400 | ~$25 | 4.0h |
| −유형 라우팅 | 1,534 | 10.0s | ~5.5k / 400 | ~$27 | 4.3h |
| Zero-shot | 1,534 | 2.5s | ~650 / 50 | ~$3 | 1.1h |
| DAIL-SQL (경량 래퍼) | 1,534 | 4.5s | ~1k / 100 | ~$5 | 1.9h |
| MAC-SQL (경량 래퍼) | 1,534 | 8.0s | ~1.4k / 700 | ~$18 | 3.4h |
| A2 (n=300) | 300 | 10.5s | ~6k / 400 | ~$6 | 0.9h |
| A5 (n=300) | 300 | 6.0s | ~4k / 300 | ~$3 | 0.5h |
| **소계** | — | — | — | **~$117** | **~21h** |

(실측 스모크 토큰을 반영한 재추정. 이전 $35 추정은 SC-TSQL 프롬프트 복잡도 과소평가였고, 실제로는 $117 선. MAC 포함 반영.)

### 2.2 HRDB (GPT-4o)
| 조건 | n | 예상 비용 | 예상 시간 |
|---|---|---|---|
| Full × 5 조건 | 30 × 5 | ~$2 | 0.5h |

### 2.3 총합
**비용 ~$120, 시간 ~22h** (병렬화 없이 직렬 실행, GPT-4o 백본 기준)

- 메인 수치(Full SC-TSQL, Zero-shot, A1, A3)는 n=1,534 유지.
- 경량 래퍼 베이스라인(DAIL, MAC)도 n=1,534 유지 → §5.4 공정 비교 주장 확실화.
- 서브셋 조건(A2 역번역, A5 K=1)은 n=300 유지 (민감도·보강 용도).
- 병렬 실행(2 프로세스)으로 ~12h 축소 가능.
- **예산 상한 $150 내 여유 확보**, 석사 개인 연구 범위.

---

## 3. 실행 순서 (Day 3-10)

### Day 3 (오전): 베이스라인 수정 배포·스모크
- 03_baseline_fix_plan.md 작업 완료
- n=20 스모크 테스트 → 합격 확인

### Day 3 (오후) ~ Day 4: BIRD n=1,534 메인 3 조건
- A0 (Full) → A1 (−NLI) → A3 (−라우팅) 순차 실행
- 체크포인트 JSON 저장 확인
- 실행 중 문제 발생 시 Day 5에 복구 여유 확보

### Day 5: BIRD 베이스라인 2 조건 (n=1,534)
- Zero-shot, DAIL-SQL (수정판)

### Day 6 (오전): BIRD 서브셋 3 조건 (n=300)
- MAC-SQL, A2, A5

### Day 6 (오후) ~ Day 7: HRDB 4 조건 (n=30)
- 모두 GPT-4o 통일 (파일럿은 mini였음)
- Full, −NLI, Zero-shot, DAIL-SQL

### Day 8: 분석 스크립트 실행
- NLI 독립 탐지 비율(사각지대 한정) 계산, paired bootstrap 95% CI, ECR@type 집계
- `scripts/summarize_results.py` + 신설 `scripts/compute_eied.py`, `scripts/compute_ci.py`

### Day 9: 본 실험 예비일
- 재실행·오류 복구·추가 스팟 체크 시간

### Day 10: 본 실험 종료 선언, 산출물 동결
- 모든 결과 JSON을 `outputs/logs/final_run/`로 이관
- 표·그림 소스 데이터 고정

---

## 4. HRDB 백본 통일 (파일럿 mini → 본 실험 GPT-4o)

### 4.1 배경
- 파일럿에서 HRDB는 **GPT-4o-mini**로 측정됨 (비용 최적화)
- 초안 §5.3은 "모든 모델을 GPT-4o-2024-11-20으로 통일"이라고 명시 → **자가모순**
- 해결: 본 실험 HRDB 4 조건 모두 **GPT-4o로 재측정**, 파일럿 수치는 초안에서 제거 또는 각주 처리

### 4.2 한글 컬럼 메타데이터 효과 재검증
- 파일럿(mini): 20% → 40% (+20pp)
- 본 실험(GPT-4o): mini 기준 상승폭이 유지되는지 확인
- **시나리오 A**: +20pp 재현 → §6.4 핵심 기여로 유지
- **시나리오 B**: 감소 (e.g., +10pp) → §6.4 서술 축소, "mini에서 크고 4o에서 작다"로 재해석
- **시나리오 C**: 무효 → §6.4에서 제거, §6.3 한계로 이동

### 4.3 Ablation 설계
HRDB n=30에서 `disable_korean_metadata` 플래그를 추가하여 동일 조건으로 측정:
```bash
python evaluate.py --dataset hrdb --model sc_tsql \
    --ablation none --sample 30 --seed 42
python evaluate.py --dataset hrdb --model sc_tsql \
    --ablation no_korean_metadata --sample 30 --seed 42
```

**구현 필요**: `src/schema_linker.py`에 `disable_korean_metadata` 플래그 추가 (~30분)

---

## 5. 분석 스크립트 요구사항

### 5.1 NLI 독립 탐지 비율 (사각지대 한정)

정의(논문 §5.2.3 동일): 실행 검증이 성공으로 판정했으나 EX=0인 사각지대 쿼리 집합에서, NLI가 `ICS < θ`로 불일치 판정한 비율.

```
blind_spot = {q : exec_validator_pass(q) == True AND final_ex_correct(q) == False}
독립 탐지 비율 = |{q in blind_spot : ics(q) < θ}| / |blind_spot|
```

(운영 편의상 아래 스크립트 내부 변수명은 `eied`로 유지되나, 논문·보고서 표기는 "NLI 독립 탐지 비율" 또는 "사각지대 탐지 비율"로 통일한다.)
```python
# scripts/compute_eied.py
import json, glob
for log_path in glob.glob("outputs/logs/*_sc_tsql_none_seed42_*.json"):
    data = json.load(open(log_path))
    samples = data["samples"]
    # 실행 검증은 통과(exec fail 없음)했으나 EX=0인 쿼리
    blind_spot = [s for s in samples
                  if s.get("exec_validator_pass") == True
                  and s.get("final_ex_correct") == False]
    flagged = [s for s in blind_spot if s.get("ics") < 0.75]
    eied = len(flagged) / len(blind_spot) if blind_spot else 0.0
    print(f"{log_path}: EIED = {eied*100:.1f}% ({len(flagged)}/{len(blind_spot)})")
```

### 5.2 Paired Bootstrap 95% CI
Full vs A1 Δ EX의 95% 신뢰구간.

```python
# scripts/compute_ci.py (의사코드)
import numpy as np
pairs = [(ex_full[i], ex_a1[i]) for i in range(1534)]
diffs = []
for _ in range(10000):
    idx = np.random.choice(1534, 1534, replace=True)
    d = np.mean([pairs[i][0] for i in idx]) - np.mean([pairs[i][1] for i in idx])
    diffs.append(d)
lo, hi = np.percentile(diffs, [2.5, 97.5])
print(f"ΔEX = {np.mean(diffs)*100:.1f}pp, 95% CI [{lo*100:.1f}, {hi*100:.1f}]")
```

### 5.3 오류 유형별 ECR
Full vs A3 각 유형별 "교정 후 EX=1" 비율 비교 → §6.2 표 3.

---

## 6. 결과 해석 규칙 (사전 고정)

### 6.1 RQ1 판정 규칙

| 조건 | 판정 |
|---|---|
| Δ(Full−A1) 95% CI lower > 0 AND 사각지대 독립 탐지 ≥ 30% | **RQ1 Yes** (교정 + 탐지 모두 유효) → Secondary 서사 |
| Δ(Full−A1) 95% CI lower ≤ 0 AND 사각지대 독립 탐지 ≥ 30% | **RQ1 Partial** (탐지만 유효) → Primary 서사 ★기대 케이스 |
| Δ(Full−A1) 95% CI upper < 0 | **RQ1 No 방향** (NLI가 해로움) → Primary 서사 + §6.1에 경고 추가 |
| 사각지대 독립 탐지 < 30% | **RQ1 Null** → Primary 서사 축소, 방법론 가치로만 논문화 |

### 6.2 RQ2 판정 규칙

| 조건 | 판정 |
|---|---|
| Δ(Full−A3) 95% CI lower > 0 전체 EX 기준 | **RQ2 Yes (전역)** |
| ECR@{E3, E4, E_intent}에서 Full > A3 | **RQ2 Yes (유형 특정)** ★현실적 기대 |
| 어느 유형도 유의한 차이 없음 | **RQ2 No** → §6.2에서 솔직 보고, 향후 과제로 |

### 6.3 판정 결과의 §6 서술 자동 분기
- Day 10 결과 확정 직후, `scripts/summarize_results.py`의 출력을 보고 §6.1·§6.2 서술을 두 버전(Yes/No) 중 하나로 치환.
- 두 버전 초안은 Day 8에 미리 작성.

---

## 7. 체크포인트·리스크 관리

### 7.1 체크포인트
- 매 30건마다 JSON 저장 (`_checkpoint_path` 기존 구조 활용)
- Day 3-7 각 조건 시작 전 `git tag exp-start-<condition>` 부여

### 7.2 리스크
| 리스크 | 완화 |
|---|---|
| OpenAI API rate limit | `src/openai_retry.py` 5회 백오프 기 적용, 동시 1 프로세스만 사용 |
| 중간 크래시 | 체크포인트로 재개. 매 조건 시작 시 `--no-resume` 옵션 사용 여부 수동 판단 |
| 예상 시간 초과 (>24h) | Day 9 예비일 활용. 그래도 부족 시 A2/A5 서브셋 n=100으로 재축소 |
| 예상 비용 초과 | 현재 $46 예상, 상한 $80 설정. 실시간 모니터링 |
| 사각지대 독립 탐지 기대치(≥30%) 미달 | Primary 서사에서도 생존 가능하게 설계됨. §6에 "탐지 기여 제한적" 보고. |

---

## 8. Day 1-2 실행 계획 작업 체크리스트
- [x] 실험 범위 축소 및 n 결정 (1,534 / 300 / 30 분리)
- [x] 비용·시간 상세 추정 (~$46, ~20h)
- [x] 일별 실행 순서 (Day 3-10)
- [x] HRDB 백본 통일 계획 및 disable_korean_metadata ablation 추가
- [x] 분석 스크립트 요구사항 (사각지대 NLI 독립 탐지·CI·ECR)
- [x] RQ1/RQ2 판정 규칙 사전 고정
- [ ] `scripts/compute_eied.py`, `compute_ci.py` 구현 → Day 8
- [ ] `disable_korean_metadata` 플래그 구현 → Day 3
- [ ] 실행 순서 shell 스크립트 신설 → Day 3
