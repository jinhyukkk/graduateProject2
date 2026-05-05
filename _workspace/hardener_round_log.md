# Hardener Round Log — Critic ↔ Hardener 공방 기록

| 항목 | 값 |
|---|---|
| **트리거** | paper-critic의 적대 공격에 대한 hardener 응답 라운드 추적 |
| **마감** | 2026-05-08 (KITS 제출, D-7 환경) |
| **현재 라운드** | D-3 → D-2 (ROUND 2) |

---

## ROUND 1 — D-6 → D-5 (2026-04-26 ~ 2026-04-30)

### 1차 공격 (paper-critic Pre-mortem)

- 산출물: `_workspace/critic_pre_mortem.md`
- 카드: R-1 ~ R-14 (Critical 5건, Major 7건, Minor 2건)
- 핵심 카드:
  - R-1 (Zero-shot이 모든 베이스라인을 이김 → 구현 결함 의혹)
  - R-2 (RQ1 사후 재정의 HARK)
  - R-6 (EIED NLI 자기 채점 순환 논증)
  - R-9 (임계값 사후 보정, 민감도 분석 부재)
  - R-12 (표 4·5·8·9 미수집)

### 1차 방어 (paper-hardener)

- 산출물:
  - `_workspace/hardener_defense_matrix.md` (R-1 ~ R-14, 4수단 평가)
  - `_workspace/hardener_patches.md` (P-1-a ~ P-14-b, 26개 patch)
  - `_workspace/hardener_limitations.md` (S4 한계 6~14 신규 + 한계 1·3·4 강화)
- 채택 전략 요약:
  - Critical 5건: 모두 정면돌파 조합 (S1+S2+S4 또는 S1+S2+S3)
  - 1일 초과 실험은 자동 S4 전환 (R-6 GPT-judge ablation, R-10 어휘 ablation, R-14 한국어 NLI)
  - PM escalate P1~P4 정의

### 1차 본문 적용 (paper-writer-kr v04)

- 산출물: `docs/논문_초안.md` v04 (822 line, v03 대비 −1.08%)
- 적용된 patch:
  - P-2-a/b/c (RQ1 발견 지향 정직화)
  - P-6-a/b/c (EIED 보조 관찰 격하 4곳)
  - P-9-a/c (이중 임계값 정의 + Limitation)
  - P-12-a/b (표 4 SC k=5 / 표 5 / 표 8 / 표 9 *향후 측정* 격하)
  - P-1-a/b (베이스라인 경량 래퍼 한정)
- changelog: `_workspace/05_draft_v04_changelog.md`

---

## ROUND 2 — D-3 → D-2 (2026-05-01)

### 2차 공격 (paper-critic Hostile Review)

- 산출물: `_workspace/critic_hostile_review.md`
- 권고: **Major Revision (경계선 Reject)**, Confidence 4/5
- 핵심 발견:
  - **W1 / R-15 — EIED 격하-결론 모순** (Critical, 단일 사유 reject 가능)
    - §1.3 line 85 + §6.5.3 line 776에서 EIED를 *서술적 보조 관찰*로 격하
    - 그러나 §6.1.2 line 604 + §6.5 line 745 *2.27배* 표현은 *결정 증거*로 그대로 사용
  - **W2 / R-16 — 30% 임계값 사후 정의** (Critical)
    - footnote 16은 *기록 시점*만 입증, *값 선택 자유도*는 차단 못 함
  - **W3 / R-17 — 정량 측정 범위 압축** (Major→Critical)
    - §1.3 6개 기여 중 정량 측정된 *남은 기여* = BIRD dev_300 EX 50.3% 1건
  - **W4 / R-18 — 이중 임계값 sweep 본문 부재** (Critical)
    - 부록 C *계획만* 약속, 본 제출본에 데이터 없음
- 추가 카드: R-19 (MAC Selector 진단 부재), R-20 (NLI false negative 운영 위험), R-21 (footnote 19 자기 면죄), R-22 (5/6계층 카운팅 불일치), R-23 (발견 지향 vs 결정적 메시지 모순)
- patch 효과 진단:
  - **Critical 5건 중 완전 통과 0건**
  - R-6, R-9는 patch가 새 약점 생성 (✗ 격상)
  - R-1, R-2, R-12는 부분 차단 (△)

### 2차 방어 (paper-hardener)

- 산출물 (본 라운드):
  - `_workspace/hardener_defense_matrix.md` ## ROUND 2 섹션
  - `_workspace/hardener_patches.md` ## ROUND 2 PATCHES 섹션
  - `_workspace/hardener_limitations.md` # ROUND 2 갱신
  - `_workspace/hardener_round_log.md` (본 파일, 신규)
- **핵심 결정 — W1 옵션 X 채택**:
  - 옵션 X: 결론 절(§6.1.2 / §6.1.3 / §6.5)도 격하에 맞춰 약화
  - 옵션 Y: 격하를 철회하고 EIED를 강한 위치로 복귀 (기각)
  - 채택 사유:
    1. v04에서 이미 격하 4곳 적용했으므로 결론 약화가 *정합적 일관화*
    2. 옵션 Y는 R-6 자기 채점 의혹·R-15·R-16 모두 다시 마주해야 함 — 단일 라운드 해소 불가
    3. S4 회피 + R-17 측정 범위 압축 흐름과 정합
    4. reviewer가 가장 신뢰하는 서사는 *낮은 자신감의 일관 표현*
- 4수단 평가 (ROUND 2 카드별):
  - R-15 / W1: S1 + S2 + S4 (옵션 X)
  - R-16 / W2: S1 + S2 + S4
  - R-17 / W3: S1 + S2 + S4
  - R-18 / W4: S3 (조건부) + S4 fallback — **PM escalate P5**
  - R-19 / W6: S1 + S2
  - R-20: S1 + S2 + S3 + S4
  - R-21 / W9: S1 (즉시)
  - R-22 / W10: S1 (R-17 통합)
  - R-23 / W5: S1 (R-15 통합)
- 신규 patch: P-15-a ~ P-23-a (12개)
- 누적 분량 추가: ROUND 1 +0 line (v03 → v04 −1.08%) + ROUND 2 +18~25 line ≈ **+2.2~3.0%**

### PM Escalate (D-3 신규)

| ID | 항목 | 마감 | 의뢰 대상 | ROUND 1과 관계 |
|---|---|---|---|---|
| **P5** | R-18 raw 로그 보존 여부 점검 + paper-analyst sweep 의뢰 | D-2 정오 (2026-05-02) | paper-engineer → paper-analyst | ROUND 1 P2 갱신 |
| **P6** | R-16 commit hash 확정 | D-2 | paper-engineer | 신규 |
| **P7** | R-17/R-19 측정 가능 재점검 (SC k=5, MAC Selector) | D-2 | paper-engineer | ROUND 1 P1·P3 갱신 |

### 2차 본문 적용 (paper-writer-kr 예정)

- 대상: ROUND 2 PATCHES 12개 (P-15-* ~ P-23-*)
- 우선순위:
  - 1순위 (D-2): P-15-a/b/c/d, P-17-a/b, P-16-a/c, P-21-a (옵션 X 일관화)
  - 2순위 (PM escalate 후): P-16-b, P-18-a 또는 P-18-b
  - 3순위 (D-2 안): P-19-a/b, P-20-a/b
- 본문 톤 위반 의심 마킹: P-15-a/b/c (메인 메시지 한 단계 더 약화), P-17-a (방어조 위험)

---

## 다음 라운드 (예상) — D-2 → D-1

### 3차 공격 (paper-critic 재호출 예상)

- ROUND 2 patch 적용 후 paper-critic을 재호출하여 R-15·R-18·W1 재공격이 통과 못하는지 확인
- 예상 잔존 위험:
  - R-15 옵션 X 적용 후: 본문 메시지 톤이 *낮은 자신감*으로 일관, reviewer가 톤 약화의 *일관성*을 정직성 신호로 받을 가능성 높음
  - R-18 옵션 B fallback 적용 시: *결과 친화적 선택* 의혹은 자발 인정으로 무력화되나 *완전 차단*은 불가
  - R-17 측정 범위 압축: *측정 완료/예정 분리*로 reviewer가 기여 카운팅 정직성을 확인
- 예상 새 카드:
  - 옵션 X 약화 후의 *결론 약함* 자체가 reject 사유가 될 위험 (Major Revision → Reject 전환 가능성)
  - 본 라운드의 잔존 약점: ROUND 2 R-19 Selector 진단 부재가 S3 (escalate P7) 결과에 따라 살아남을 수 있음

### 회피 한계점

- **3 라운드 후에도 미해결 시 PM 결정 입력**: paper-hardener.md 절차에 따라 `_workspace/critic_unresolved.md`로 이관
- ROUND 3에서도 R-15·R-18이 살아남으면 본 연구의 *EIED 결론 자체*를 본문에서 삭제하고 *RQ1 답을 "교정 엔진 무의미"만으로 정식화*하는 옵션 Z 검토 필요 (PM 권고)

---

## 라운드 통계

| 라운드 | Critic 카드 수 | Hardener patch 수 | S4 회피 채택 | 본문 분량 변화 |
|---|---:|---:|---:|---:|
| ROUND 1 (D-6→D-5) | R-1~R-14 (14) | P-1-a~P-14-b (26) | 9건 (한계 6~14) | v03→v04 −1.08% |
| ROUND 2 (D-3→D-2) | R-15~R-23, W1~W10 (9 카드 + 10 weakness) | P-15-a~P-23-a (12) | 4건 (한계 7·8·12·15) | +2.2~3.0% 예상 |
| **누적** | **23 카드** | **38 patch** | **13건 한계** | **+1.1~1.9% 누적** |

---

## 자체 검증

- [x] ROUND 1, ROUND 2 모두 기록됨
- [x] 옵션 X (결론 약화) vs 옵션 Y (격하 철회) 결정과 사유 명시
- [x] PM escalate 신규 P5/P6/P7 정의
- [x] 다음 라운드 예상 위협과 옵션 Z fallback 명시
- [x] 한국어 학술 톤 유지
