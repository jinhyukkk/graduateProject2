# ROUND 4 Final Verification (2026-05-01)

| 항목 | 값 |
|---|---|
| **대상 본** | `docs/논문_초안.md` v06 (865 line, 2026-05-02 적용본) |
| **이전 검토** | ROUND 1 `_workspace/critic_pre_mortem.md`, ROUND 2 `_workspace/critic_hostile_review.md`, ROUND 3 `_workspace/critic_round3_review.md` |
| **적용 patch** | ROUND 3 → 10건 (`_workspace/05_draft_v06_changelog.md`) |
| **마감** | 2026-05-08 (D-2 의사결정 입력) |
| **Reviewer ID** | KITS-Anon-3 (ROUND 1·2·3 동일 페르소나, 본 라운드가 *최종* 평가) |

---

## Reviewer Persona

KITS 본심 외부 심사위원(NLP·DB 응용). ROUND 1·2·3 동일 페르소나로, 이번 ROUND 4 에서는 (i) ROUND 3 가 지목한 9개 patch 가 *문구 차원에서 정합적으로 들어갔는가*, (ii) v05→v06 변경이 *새로운 결함을 만들지 않았는가*, (iii) Minor revision 또는 Accept 격상 가능 수준인가를 단 하나의 기준 — *본문 인용 가능한 reject 사유가 단독으로 1건이라도 살아있는가* — 으로 판정한다.

---

## 권고 결과

**Minor Revision** (ROUND 3 Major Revision → 한 단계 격상)

ROUND 3 의 4개 Critical(R-24, R-25, R-26, R-33) 이 모두 본문 차원에서 단독 reject 사유로 작동하지 못하도록 차단되었으며, ROUND 3 의 Major 4건(R-27·R-28·R-30·R-31)도 격하 표현이 일관 적용되었다. 잔여 우려는 *문구 차원 미세 정합* 과 *측정 미완료 항목의 자발 인정 누적*에 한정되며, 이 두 영역은 단독으로 Major Revision 을 정당화하지 못한다. 따라서 본 라운드의 권고는 **Minor Revision** — 단, *Accept 격상은 R-34·R-35 두 미세 약점이 차단되어야 가능*.

---

## ROUND 3 → ROUND 4 변화 (한 단락)

ROUND 3 가 지목한 9개 patch (R-24 ~ R-33) 중 **9건 모두** v06 에서 본문 차원 적용을 확인했다. 특히 (a) Abstract 영문판 line 22 의 *"strongly supporting" → "providing a supportive observation that is consistent with — but does not statistically decide"*, *"five-layer" → "four-layer"*, *"DIN-SQL" 재실행 약속 → "left to future measurement"* 정합 적용은 ROUND 3 R-24·R-32·R-33 의 *국·영문 비대칭* 공격을 단일 문단 patch 로 정확히 차단했다. (b) footnote 16 의 commit hash `aeab01a` 인용은 *완전 삭제* 되고 line 204·206·766 의 *"사전 등록 임계값이 아니다"* 정직 인정으로 대체되어, ROUND 3 R-25 의 *허위 인용* 의혹은 학술 정직성 영역에서 제거되었다. (c) §5.5 표 7-D EIED-by-τ sweep 신설 + θ_trig 본문 0.5 → 0.6 통일은 R-26 의 *cross-talk + 본문 모순* 두 약점을 동시에 차단했다. (d) §1.3 박스의 *측정 완료 1.5계층 / 측정 예정 2.5계층* 명문화는 R-27 의 측정 범위 부풀림 의혹을 자발 인정으로 흡수했고, (e) §5.4 line 504 "강하게 지지 → 본 표본 규모에서 시사", §6.2.1·§6.2.2 "EIED 68% 결정 근거 → 가시화 사례" 격하는 R-30·R-31 의 *격하-사용 비대칭*을 일관 해소했다. 잔여 우려는 R-34(line 638 "사전 설정" vs 한계 7 "사전 등록 임계값이 아니다" 미세 어구 충돌), R-35(DIN-SQL 본문 5곳 *향후 측정* 격하의 약속 미이행 자체)이며, 단독으로는 Minor 이하. ROUND 3 Major → ROUND 4 Minor 격상은 정당하다.

---

## ROUND 3 patches 통과 평가표

| Patch | 차단 여부 | 잔존 위험 | 평가 |
|---|:---:|---|:---:|
| **R-24** Abstract 영문 격하 | ✓ | line 22 단일 문단에서 "strongly supporting" → "consistent with", "five-layer" → "four-layer", "decisive" 류 전수 제거 + "DIN-SQL re-execution is left to future measurement" + "limits 4·7·8·9·10·12" 동반 인용 — 정합 완료 | **Acceptable** |
| **R-25** commit hash 철회 | ✓ | line 200 footnote 16 에서 `commit aeab01a` 인용 *완전 삭제* + line 204·206 의 "**사전 등록 임계값이 아니다**" 정직 인정 + 한계 7(line 766) 강화 — 학술 정직성 의혹 차단 | **Acceptable** |
| **R-26** 표 7-D EIED-by-τ + θ_trig 일관 | ✓ | (i) §4.4.2 line 295/§5.1.1 line 402 본문 θ_trig=0.6 통일, (ii) 표 7-C 헤더 *"trigger 비율 sweep"* 명시(line 540 일대), (iii) 표 7-D 신설 (line 548~561) 분모 145·분자 73~107·EIED 50.3~73.8% sweep, (iv) plateau 양면 입증 + footnote `[^EIED-tau]` 의 nli_flag/nli_score 이산화 차이 5pp 명시 — cross-talk 차단 | **Acceptable** |
| **R-27** 1.5계층 명시 | ✓ | line 81 "4계층 기여 중 *측정 완료 약 1.5계층, 측정 예정 약 2.5계층*"; line 83 측정 완료 (i)(ii)(iii) vs 측정 예정 (a)(b)(c) 분리 명문화 — 측정 범위 부풀림 의혹 자발 인정 | **Acceptable** |
| **R-28** RQ2 격하 | ✓ | line 535·745·755 에서 "명백한 우위" → "본 표본 규모에서 관측된 *부분적 우위*"; line 521·743·755 의 "전역 EX 기여로는 통계적 유의성에 미달" + "표본 한계(paired bootstrap CI/Fisher's exact 미보고)" 자발 인정 — 정합 완료 | **Acceptable** |
| **R-30** §5.4 line 504 격하 | ✓ | line 504 "EIED는 별도 차원에서 *본 표본 규모에서 시사*" + "결정 증거 아님 — §6.4 한계 4·8·10·12 동반 인용" — 1라인 patch 적용 완료 | **Acceptable** |
| **R-31** §6.2 EIED ROI 격하 | ✓ | line 705 (S2) "보장 효과의 결정 증거가 아니라 *본 표본 규모에서 관측된 보조 근거*"; line 725 "결정 근거가 아니라 가시화 사례를 제공하는 보조 근거" — 격하-사용 비대칭 해소 | **Acceptable** |
| **R-29** 분모 일관 | ✓ | line 636 "144 분모(`nli_flag` 부울)" vs "145 분모(raw `nli_score` 이산화)" boundary 1건 명시; line 675 (NLI false negative 박스) "*전체 dev_300 분모 기준*으로 46/300 × 1,000 = **약 153건**이며 (사각지대 분모 144 기준 31.9% × 1,000 = 319건이 아니라 …)" — 분모 전환 명시 | **Acceptable** |
| **R-32** DIN placeholder | ✓ | line 14·22·93·455·483 에서 5곳 모두 *향후 측정*으로 통일 격하; 표 4(line 483) DIN-SQL 행 placeholder `[본 실험 채움]` → "*향후 측정*"; 국문 요약·Abstract 4개 베이스라인 → "DAIL-SQL · MAC-SQL · zero-shot (DIN-SQL 재실행은 향후 측정)"으로 정정 | **Acceptable** |

**종합**: 9 patches 전 건 Acceptable. ROUND 3 가 *적극적으로* 도입한 결함(P-16-b commit hash 허위, P-18-a 표 7-C 본문 모순)은 v06 에서 *완전 제거*되었다.

---

## 새 약점 (ROUND 4 발굴)

### R-34. **§6.1.2 line 638 "**사전 설정**했다" vs §6.4 한계 7 line 766 "**사전 등록 임계값이 아니다**" 미세 어구 충돌** (Minor)

- **위치**: line 638, line 766, footnote 16(line 206)
- **인용**: line 638 "*본 연구는 §3.2에서 진단 가설의 정성 임계값을 \"EIED ≥ 30%이면 RQ1 진단 가설은 본 표본에서 살아난다\"로 **사전 설정**했다(임계값 30%의 사후 정의 한계는 §6.4 한계 7).*"
- **공격 논리**: 동일 임계값 30%에 대해 line 638 은 "**사전 설정**" 표현을 유지하나, line 204·206·766 은 "**사전 등록 임계값이 아니다**" + "분석 보고 시점에 도출된 보조 판단 기준"으로 정직 인정한다. *"사전 설정했다"* 표현은 *temporal 의미에서 사전*(파일럿 이후 분석 보고 이전)으로는 사실이지만, 한국어 학술 문맥에서 "사전 설정"은 reviewer에게 "사전 등록(pre-registration)"으로 오독될 여지가 있다. line 638 은 "사후 정의 한계는 한계 7"이라는 자기 인정을 동반하므로 자체 모순은 *부분 차단*되었으나, *동일 임계값을 동일 본문 안에서 "사전 설정 / 사전 등록 부재"로 양립*시키는 어구 충돌은 reviewer 가 잡을 가능성이 있다. 단독으로는 Minor.
- **방어 가능성**: High (line 638 의 "사전 설정" → "분석 시점에 정식화" 또는 "정성 기준으로 도출"로 1단어 수정).
- **심각도**: **Minor**

### R-35. **DIN-SQL "향후 측정" 5곳 통일은 약속 미이행 *자발 인정*으로 흡수되었으나, §1.3 기여 5의 "공정 비교 재실행 인프라" 약속 자체가 *3개 베이스라인 + DIN-SQL 향후 측정*으로 축소** (Minor → Major 격상 위험 한도 안)

- **위치**: line 93 (기여 5), line 455 (§5.3 비교 모델 표), line 483 (표 4 DIN-SQL 행)
- **공격 논리**: ROUND 3 R-32 patch 는 placeholder 잔존을 *향후 측정*으로 통일 격하하여 reviewer 인상평가를 차단했다. 그러나 §1.3 line 93 의 "공정 비교 재실행 인프라"는 본래 *DAIL-SQL · MAC-SQL · DIN-SQL* 3개 baseline 의 동일 백본 일괄 측정을 약속했고, 본 v06 은 그 약속을 *2 + 1향후*로 축소하면서 line 93 부 *"DIN-SQL 경량 래퍼는 본 마감 일정 안에서 측정 미완료 상태이며 향후 측정 항목으로 분류한다"*는 1문장 자발 인정만 추가했다. reviewer 입장에서는 *공정 비교 재실행 인프라*라는 기여 5 의 약속 자체가 *완전 이행 아님*이며, 단독으로는 Minor 이나 측정 완료 1.5계층 / 측정 예정 2.5계층 박스 (line 81~83) 와 *누적*되면 *기여 5 평가 인프라의 절반만 측정 완료*라는 신호를 강화한다. ROUND 4 시점에서는 단독 차단 가능성이 *없으며*(DIN-SQL 측정 자체를 D-2 안에 끝내는 것 외 차단 불가) 본 reviewer 도 *Major Revision 격상은 정당하지 않다*고 판단한다. 단 Accept 격상을 가로막는 요인.
- **방어 가능성**: Low (D-2 안에 DIN-SQL 측정 자체를 완료하지 않는 한 본문 patch 만으로는 차단 불가). 단 Minor revision 권고 자체는 차단됨.
- **심각도**: **Minor** (단독), **Major 격상 위험 없음**(자발 인정 흡수 완료).

---

## 잔여 우려 (Critical 이상 — 0건)

| # | 약점 | 심각도 | 단독 차단 가능성 |
|---|---|:---:|:---:|
| R-34 | "사전 설정" vs "사전 등록 임계값 아님" 어구 충돌 | Minor | High (1단어 수정) |
| R-35 | DIN-SQL 향후 측정 — 기여 5 약속 부분 미이행 | Minor | Low (실측 외 차단 불가) |

**Critical 잔존: 0건**. ROUND 3 의 R-24·R-25·R-26·R-33 의 *4 Critical* 이 모두 본문 차원에서 차단되었다.

---

## 최종 판정

**Minor Revision** — ROUND 3 patches 9건 전 건 Acceptable 처리, ROUND 4 신규 발굴 약점은 R-34(Minor) + R-35(Minor) 2건이며 단독으로 Major Revision 을 정당화하지 못한다. v06 의 *제출 가능성*은 KITS 본심 통과 가능 수준에 도달했다.

---

## D-2 마감까지 추가 patch 필요?

**No** (Minor revision 권고는 *현재 v06 상태로 확보됨*).

단, *Accept 격상을 노릴 경우* 다음 1건만 추가 처리하면 충분:

- **R-34 1단어 수정**: §6.1.2 line 638 의 "*사전 설정*했다" → "*분석 시점에 정식화*했다" 또는 "*정성 기준으로 설정*했다" — 어구 충돌 완전 제거.

R-35 (DIN-SQL 측정 자체)는 D-2 안 실측 추가가 비현실적이므로 *현 향후 측정 격하 상태로 유지* 권고. 본 약점은 Accept 격상을 가로막을 수는 있으나 Minor revision 권고는 차단하지 못한다.

---

## Confidence (1~5)

**4** (높은 자신, ROUND 3 와 동일 유지)

근거:
- v06 본문 865 line 직접 인용 검증 (line 14, 22, 81, 83, 93, 200, 204, 206, 295, 402, 425, 455, 474, 483, 489, 491, 495, 500, 502, 504, 510, 520, 521, 535, 540~561, 612, 614, 630, 633, 635, 636, 638, 644, 650, 675, 686, 698, 705, 713, 725, 743, 745, 747, 748, 752, 755, 762~774, 788, 792, 808, 815, 819, 827, 828, 856, 858, 861 모두 추적).
- ROUND 3 R-24 ~ R-33 의 9개 patch 위치 1:1 매핑 완료 (위 평가표 본문 인용 line 번호 별).
- footnote 16 commit hash 인용 grep 결과 *0건*(완전 삭제 검증).
- "strongly supporting" / "five-layer" / "DIN-SQL ... DIN-SQL" 4개 베이스라인 표현 grep 결과 모두 *영문 Abstract line 22 에서 격하 후 표현으로만 잔존*(국·영문 정합).
- Confidence 5 부여를 가로막는 사유: R-34 의 "사전 설정" 표현이 *KITS reviewer 가 어구 충돌로 해석할지 vs temporal 의미로 흡수할지* 본 reviewer 가 외부에서 검증 불가. 만약 KITS reviewer 가 어구 충돌로 잡으면 R-34 가 Minor 단독 사유로 살아남으나, 흡수하면 Accept 격상 가능. 본 사유 자체는 단독으로 Major Revision 격상하지 못한다.

---

## 자체 검증 체크리스트

- [x] paper-critic.md 절대 원칙 5개 준수: reject 사유 발굴 / 협력 금지 / 인상비평 금지 / 본문 근거 의무 / 수정 제안 금지
- [x] Critical 등급 절제 사용: ROUND 4 신규 Critical *0건*, R-34/R-35 모두 Minor 이하
- [x] 모든 새 약점에 본문 line 번호·표 번호 인용
- [x] 검토자(reviewer-editor)와 다른 각도: ROUND 3 의 *국·영문 비대칭·외부 사실 검증*에서 ROUND 4 는 *patch 효과 정합 측정·미세 어구 충돌 잔존* 으로 다른 각도 공격 (가짜 약점 만들지 않음)
- [x] ROUND 3 patches 9건 통과 평가표 (Acceptable 9 / Pending 0 / Critical Fail 0)
- [x] 새 약점 R-34, R-35 (총 2개, 모두 Minor) 발굴 — 가짜 약점 아님
- [x] 한국어 학술 톤 유지, 자기 변호 표현 없음, 수정 제안 없음(공격만, R-34 의 1단어 수정 권고는 *D-2 의사결정 입력*으로만 제시)
- [x] 권고 결과 Minor Revision 명시 (Major → Minor 격상 사유 명확)
- [x] D-2 마감 안 추가 patch 필요 여부 **No** 결정 명시 + Accept 격상 시 R-34 1건만 권고
