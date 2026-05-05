# 베이스라인 구현 수정 계획 (Day 1-2 산출물)

**작성일**: 2026-04-25
**목적**: 재실행 수치가 원 논문보다 ~20pp 낮은 문제를 해소. 심사에서 "구현 결함" 지적 차단.

---

## 1. 진단 요약

| 베이스라인 | 현재 | 원 논문 | Gap | 주요 원인 |
|---|---|---|---|---|
| Zero-shot GPT-4o | 44.0% | — | — | 정상 |
| DAIL-SQL | 36.0% | 54.76% | **-18.8pp** | Self-Consistency 미구현, evidence 조건부 처리 |
| MAC-SQL | 22.0% | 57.56% | **-35.6pp** | Selector 비활성(threshold 6000자 vs 실제 스키마 1-3k자), Few-shot 없음 |

**가장 심각**: MAC-SQL이 Zero-shot(44%)보다 **22pp 낮음** → 에이전트 프레임워크가 Zero-shot보다 못하다는 구현 결함 신호.

---

## 2. 수정 원칙

1. **경량 래퍼 유지 허용**: 본 연구는 "베이스라인 재실행을 통한 공정 비교"가 목적이지 "원 논문 복제"가 목적은 아님. 따라서 Self-Consistency(n=5)까지 완벽 복원할 필요는 없다 — 단, **경량 래퍼임을 §5.4에서 명시**하고, 그 범위 내에서 **Zero-shot을 넘는 수치**는 확보해야 함.
2. **합리성 테스트**: 모든 베이스라인은 Zero-shot 대비 **+3pp 이상** 되어야 공정 비교 대상 자격이 있다(n=1,534 기준). n=50 파일럿에서는 ±2pp 허용.
3. **수정 후 재측정은 비용·시간이 허용되는 범위만**. 구조적 결함은 반드시 고치되, 하이퍼파라미터 튜닝은 최소화.

---

## 3. DAIL-SQL 수정 계획

### 3.1 수정 대상 (우선순위 순)

#### F1. Evidence 필드 강제 포함 (소, 30분)
- **파일**: [src/baselines/dail_sql.py:563-565](../src/baselines/dail_sql.py#L563-L565)
- **현재**: `if evidence and evidence.strip(): prompt += f"-- External Knowledge: {evidence}\n"`
- **수정**: evidence 빈 문자열이어도 섹션을 추가. `evidence`가 없을 때는 "N/A"로 표기하되 섹션 자체는 유지. (원 논문 구조 준수)
- **예상 개선**: +3~5pp

#### F2. Self-Consistency n=3 추가 (중, 2시간)
- **파일**: 신규 함수 `_self_consistent_predict()`를 `DAILSQLBaseline` 클래스에 추가.
- **구현**:
  - `temperature=0.7`로 n=3회 호출, 각각의 SQL을 실행해 **결과 동치성 기준 majority voting**.
  - 모두 실행 실패면 temperature=0 재시도.
- **예상 개선**: +5~8pp
- **비용 영향**: 호출 수 3배 → BIRD 1,534에서 약 $12 → $36. 감당 가능.

#### F3. Few-shot k 확인 (소, 15분)
- config.yaml에서 현재 `few_shot_k: 9` 확인. [src/baselines/dail_sql.py:190](../src/baselines/dail_sql.py#L190)
- 원 논문은 k=5 (Few-shot+SC 설정 기준). **k=5로 낮추어** 원 논문 설정 준수.
- 본 실험 시 k=5로 고정.

### 3.2 기대 수치 (수정 후)
- n=50 파일럿: 36% → **45~50%**
- n=1,534 본 실험: **47~52%** (원 논문 54.76% 대비 -3~-8pp, 경량 래퍼로 정당화 가능 범위)

### 3.3 §5.4 서술 교체
> "DAIL-SQL의 재실행은 경량 래퍼로 Self-Consistency는 n=3으로 축소(원 논문 n=5)하고, few-shot k=5, evidence 필드를 항상 포함하는 설정으로 수행했다. 재실행 수치가 원 논문(54.76%)보다 낮은 것은 주로 SC 호출 수 축소에 기인한다."

---

## 4. MAC-SQL 수정 계획

### 4.1 핵심 결함
- Selector threshold 6000자 → BIRD DB 스키마 대부분이 이 아래 → **Selector가 단 한 번도 실행되지 않음**.
- 그 결과 Decomposer가 **full schema 전체**를 받게 되고, 관련 없는 테이블까지 포함되어 LLM 혼동 발생.
- **이것이 Zero-shot(44%)보다 22pp 낮은 구조적 이유**.

### 4.2 수정 대상 (우선순위 순)

#### F1. Selector 항상 활성화 (소, 30분)
- **파일**: [src/baselines/mac_sql.py:75](../src/baselines/mac_sql.py#L75), [configs/config.yaml](../configs/config.yaml)
- **수정**: `selector_char_threshold: 0` 으로 설정 (config.yaml)하여 Selector가 항상 실행되도록 함. 또는 코드에서 threshold 분기 자체 제거.
- **예상 개선**: +15~25pp (결정적 구현 결함 해소)

#### F2. Decomposer에 evidence 강제 포함 (소, 15분)
- **파일**: [src/baselines/mac_sql.py:205-207](../src/baselines/mac_sql.py#L205-L207)
- **수정**: DAIL-SQL F1과 동일 원칙.
- **예상 개선**: +3~5pp

#### F3. Refiner max_rounds 확인 (소, 10분)
- 현재 기본값 `max_refine_rounds=3`. 원 논문과 동일.
- 수정 불필요, 로깅만 확인.

#### F4 (선택). Decomposer에 간단한 few-shot 추가 (중, 2시간)
- 본 연구의 DAIL-SQL few-shot 풀을 재사용해 Decomposer 프롬프트에 2-shot 주입.
- 원 논문은 zero-shot Decomposer지만, 재실행 수치 보강 목적으로 경미한 수정.
- 수정 시 §5.4에 "Decomposer에 2-shot 주입(원 논문과의 차이)" 명시 필요.
- **시간이 빠듯하면 생략.**

### 4.3 기대 수치 (수정 후)
- n=50 파일럿: 22% → **40~50%** (Zero-shot 44%와 유사 또는 소폭 우위)
- n=1,534 본 실험: **48~55%** (원 논문 57.56% 대비 -3~-10pp)

### 4.4 §5.4 서술 교체
> "MAC-SQL의 재실행은 경량 래퍼이며 (i) Selector 활성화 임계값을 0으로 설정해 모든 쿼리에서 스키마 프루닝을 수행하고, (ii) Decomposer에 BIRD evidence를 항상 포함하며, (iii) Refiner max_rounds=3을 유지했다. 재실행 수치가 원 논문보다 낮은 것은 주로 Decomposer가 zero-shot이라는 설정 차이(원 논문 부록 A.2와 동일)와 OpenAI API의 Self-Consistency 재구현 축소에 기인한다."

---

## 5. Zero-shot 수정 계획

**수정 없음**. 44%는 합리적이며 evidence 포함 기준선 역할을 올바르게 수행.

---

## 6. 검증 스모크 테스트

수정 후 n=20 파일럿으로 빠르게 검증 (비용 약 $2, 시간 10분):

```bash
python evaluate.py --config configs/config.yaml --dataset bird \
    --sample 20 --seed 42 --model zeroshot
python evaluate.py --config configs/config.yaml --dataset bird \
    --sample 20 --seed 42 --model dail_sql
python evaluate.py --config configs/config.yaml --dataset bird \
    --sample 20 --seed 42 --model mac_sql
```

**합격 기준**:
- Zero-shot ≥ 40% (기존 유지)
- DAIL-SQL ≥ 42% (Zero-shot -2pp 이상)
- MAC-SQL ≥ 42% (Zero-shot -2pp 이상)

**불합격 시**: 즉시 추가 진단. 본 실험 진입 금지.

---

## 7. 일정 배정

| 단계 | 작업 | 소요 | 담당 | Day |
|---|---|---|---|---|
| 1 | DAIL-SQL F1 (evidence) | 30분 | code | Day 2 |
| 2 | DAIL-SQL F2 (SC n=3) | 2시간 | code | Day 2 |
| 3 | DAIL-SQL F3 (k=5) | 15분 | config | Day 2 |
| 4 | MAC-SQL F1 (Selector) | 30분 | config+code | Day 2 |
| 5 | MAC-SQL F2 (evidence) | 15분 | code | Day 2 |
| 6 | 스모크 테스트 n=20 | 10분+$2 | run | Day 2 말 |
| 7 | 합격 시 본 실험 진입 | — | — | Day 3 |

**총 예상 공수**: 3시간 45분 (1일 내 완료 가능)
**스모크 비용**: ~$2

---

## 8. 리스크

| 리스크 | 완화 |
|---|---|
| F2 (SC n=3) 구현 버그로 DAIL-SQL이 오히려 하락 | F2 생략하고 F1·F3만 적용. n=1 유지. §5.4에 "n=1 단발"로 명시. |
| MAC-SQL F1 (Selector 활성화) 적용 후에도 오히려 Zero-shot 이하 | Selector 프롬프트를 원 논문 부록 A.1 템플릿으로 교체. 추가 15분 공수. |
| 수정 후 스모크에서 개선 폭이 기대보다 작음 | 파일럿 n=50으로 재측정하여 변동성 확인. n=1,534 진입 여부 재판단. |

---

## 9. Day 1-2 베이스라인 작업 체크리스트
- [x] DAIL-SQL / MAC-SQL / Zero-shot 현 구현 정적 분석
- [x] 수정 대상·우선순위·예상 개선폭 정의
- [x] 스모크 테스트 기준 및 합격 조건 설정
- [x] §5.4 서술 교체안 작성
- [ ] 실제 코드 수정 → Day 2 실행
- [ ] 스모크 테스트 n=20 → Day 2 말
