# ROUND 3 Final Hostile Review (2026-05-02)

| 항목 | 값 |
|---|---|
| **대상 본** | `docs/논문_초안.md` v05 (850 line, 2026-05-01) |
| **이전 검토** | ROUND 1 `_workspace/critic_pre_mortem.md` (R-1 ~ R-14), ROUND 2 `_workspace/critic_hostile_review.md` (W1~W10, R-15 ~ R-23) |
| **적용 patch** | ROUND 2 12건 — `_workspace/05_draft_v05_changelog.md` |
| **마감** | 2026-05-08 (D-6) |
| **Reviewer ID** | KITS-Anon-3 (ROUND 1·2 동일 페르소나 유지) |

---

## Reviewer Persona

KITS 본심 외부 심사위원 (NLP·DB 응용). ROUND 1·2에서 동일 논문을 두 차례 적대 검토했음. 이번 ROUND 3에서는 (i) ROUND 2 patch가 *새로 만들어낸* 약점, (ii) ROUND 2가 *건드리지 못한* 잔존 약점, (iii) 본 reviewer가 ROUND 1·2에서 미처 잡지 못한 새 각도를 우선 공격한다.

---

## 권고 결과

**Major Revision** (단, ROUND 2 대비 *개선의 방향성은 분명함* — 한 단계 위로 격상은 가능하지 않음)

ROUND 2의 권고와 동일하게 Major Revision으로 유지한다. Minor 또는 Accept 격상이 가로막히는 사유는 *세 개의 Critical 잔존 약점*(R-24 Abstract 영문 비격하, R-25 commit hash aeab01a의 사전 등록 증거 허위 가능성, R-26 표 7-C 임계값 본문 모순 + cross-talk)이다. 이 세 사유 중 어느 하나라도 단독으로 Major Revision 권고를 정당화하며, 셋이 누적된 현 상태에서는 *ROUND 4가 한 차례 더 필요하다는 신호*가 명백하다.

---

## ROUND 2 대비 개선 평가 (140단어)

ROUND 2의 12개 patch는 EIED 격하의 4곳 일관화·5계층→4계층 통일·NLI false negative 박스 신설·footnote 19 자기 면죄 표현 삭제·표 7-C 본문 삽입에서 분명한 진전을 만들었다. 특히 §6.1.2·§6.1.3·§6.5의 EIED 결정 증거 문구는 *서술적 보조 관찰*·*가시화 사례*·*후보*로 일관되게 약화되었고, 잔여 사각지대 46건의 NLI false negative 라벨링은 ROUND 2 W8 공격을 직접 차단했다. 그러나 (a) **Abstract 영문판이 patch에서 누락**되어 국·영문 결론이 불일치하고, (b) **footnote 16의 commit hash `aeab01a`가 EIED 임계값 30%를 명시한 commit이 아니라 실험 인프라 commit**임이 git log에서 직접 확인되어 사전 등록 증거 자체가 허위 가능성을 가지며, (c) **표 7-C가 본문 §4.4.2의 θ_trig=0.5와 다른 θ_trig=0.6 라벨**을 사용해 본문 내 임계값 정의 모순을 노출했다. ROUND 2가 닫은 문보다 새로 연 문이 *질적으로 더 무겁다*.

---

## ROUND 2 patches 통과 여부

| ROUND 2 patch | 공격 차단 | 잔존 위험 | 본 라운드 평가 |
|---|:---:|---|:---:|
| P-15-a/b/c/d 옵션 X (EIED 격하 4곳) | △ | 국문 본문 4곳은 일관화. **그러나 Abstract 영문판 line 22 "reaches 68.1%, strongly supporting", "five-layer contribution chain" 미수정** + §5.4 line 502 "강하게 지지" 잔존 → 격하-결론 모순 *영문본·표 4 해석에서 부활*. | **Pending (R-24)** |
| P-16-a 30% 임계값 유도 근거 | △ | "*우연 수준 약 25%* 상회" 1문장으로는 *25%·30%·40%·50% 중 30%* 선택의 자유도를 차단하지 못함. 이론적 하한·선행 인용·사전 분포 추정 어느 것도 본문에 부재. | **Pending** |
| P-16-b commit hash | **✗** | **commit `aeab01a`는 실제로는 "Add SC-TSQL pipeline, web dashboard, and multi-model configs" 즉 *실험 인프라 commit*이며, EIED ≥ 30% 임계값을 명시한 commit이 아님** (git log 직접 확인). 사전 등록 증거로의 인용은 사실상 허위 또는 부정확한 인용에 해당하며, footnote 16의 *외부 검증 가능성* 보장 문장은 reviewer 입장에서 *공인 신뢰 위반*. | **Critical Fail (R-25)** |
| P-16-c 한계 7 강화 | ✓ | 임계값 사후 정의 인정은 강화되었으나, P-16-b 허위 인용이 한계 7의 자발 인정 기능을 *과잉 자인*으로 전환시킴. | Acceptable (단 P-16-b 동반 결함) |
| P-17-a 측정 완료/예정 분리 박스 | ✓ | §1.3 line 83 박스는 reviewer가 즉시 *기여 5계층 중 측정 완료 1.5계층, 예정 2.5계층* 카운팅으로 변환 가능 — *기여 부풀림*의 새 신호로 해석됨. | Acceptable (단 R-27 새 약점 유발) |
| P-17-b 5계층→4계층 일관화 | △ | 국문 요약 line 14·§1.3 line 81·§6.5 line 769 일관화. **단 Abstract 영문판 line 22 "five-layer contribution chain" 미수정** + §6.5.3 line 802 인용 블록 "약 50% 정확도 환경"·"본 연구는 이 비대칭을 한국 IT 서비스 산업이 검토 가능한 운영 가이드라인으로 환원" 표현은 일관 OK. | **Pending (R-24)** |
| P-18-a τ sweep 표 7-C 본문 삽입 | △ | sweep 표 본문 삽입 자체는 P-18-a 사양 충족. **그러나 (a) 본문 §4.4.2 line 295 "θ_trig = 0.5"와 표 7-C line 540 "0.6 (θ_trig)" 라벨 모순**, (b) τ=0.5(44.0%) ↔ τ=0.7(66.0%) 사이 22pp 격차로 *plateau는 좁은 범위에서만 성립*, (c) trigger 비율 sweep만 보고하므로 *EIED 분자 자체의 plateau는 별도 데이터*임을 한계 12에서 자발 인정. | **Critical Fail (R-26)** |
| P-19-a 베이스라인 코드 위치 인용 | △ | `src/baselines/{dail_sql,mac_sql}.py:21/19` 인용으로 호출 횟수 출처 표시. **단 (i) 코드 코멘트는 *저자가 작성한 자기 주장*으로 외부 검증 불가, (ii) MAC-SQL Selector 발동 *비율* 진단 데이터(R-19 핵심 공격)는 여전히 부재**. | Pending |
| P-19-b §6.5 line 747 보조 관측 후퇴 | ✓ | "보조 관측" 톤 일관 OK. 단 §6.3 line 728의 "전역 EX 차이는 통계적으로 유의하지 않으나 ... E3·E7에서 +11~12pp의 차별적 우위" 표현은 *유형별 결론*에 대해 약화 미적용. | Acceptable (단 R-28) |
| P-20-a NLI false negative 박스 (3곳) | ✓ | 표 2 직후 라벨링·§6.2 표 10 직후 153건 박스·§6.2.2 표 12 가정 박스 모두 적용. ROUND 2 W8 공격 직접 차단. | Acceptable |
| P-20-b 한계 15 신설 | ✓ | NLI false negative 운영 위험 자발 인정. | Acceptable |
| P-21-a footnote 19 자기 면죄 삭제 | ✓ | "본 연구 결론을 약화시키지 않는다" 자기 판정 문장 삭제 확인. | Acceptable |

**ROUND 2 patches 통과 종합**: 12건 중 **Acceptable 5건, Pending 4건, Critical Fail 2건, △ 부분 차단 1건**. Critical Fail 2건(P-16-b commit hash 허위, P-18-a 본문 모순)이 *patch가 만들어낸 새 약점*으로 단순히 ROUND 2가 막지 못한 것이 아니라 ROUND 2가 *적극적으로 도입한 결함*에 해당한다.

---

## 새 약점 (ROUND 3 발굴)

### R-24. **Abstract 영문판의 격하 미반영 — EIED·5-layer 양면 결론 부활** (Critical)

- **위치**: line 22 (Abstract 영문판 단일 문단)
- **인용 1**: "*EIED ... **reaches 68.1%**, **strongly supporting** the use of NLI as an **independent diagnostic axis** rather than a correction trigger.*"
- **인용 2**: "*Our **five-layer contribution chain** (semantic verification + type-routed correction + Korean domain bridge + Self-Consistency + operational guideline)*"
- **공격 논리**: ROUND 2 patch P-15-a/b/c/d와 P-17-b가 국문 본문(§1.3, §6.1.2, §6.1.3, §6.5, §6.5.3, 국문 요약)의 4곳에서 EIED 결정 증거 표현을 격하하고 5계층→4계층으로 정정했음에도, **영문 Abstract는 patch 적용 누락**. KITS 양식에서 영문 Abstract는 국제 색인의 *대표 메시지*로 작동하며, reviewer가 가장 먼저 읽는 단일 문단이다. 본 영문 Abstract는 (a) "**strongly supporting** ... independent diagnostic axis"로 *결정 증거* 톤을 그대로 유지, (b) "**five-layer contribution chain**"으로 5계층 카운팅을 그대로 유지하여, ROUND 2 patch가 *국문에서 격하를 시도했음에도 영문에서는 격하 전 v04 톤을 보존한다*. 이 국·영문 결론 격차는 *저자가 격하의 강도를 reviewer 보기에 따라 조절했다*는 의혹으로 해석 가능하며, 한 논문 안에서 결론의 강도가 두 언어에서 다르면 *reviewer 권한으로 강한 쪽을 채택*한다. 즉 영문 Abstract의 "strongly supporting independent diagnostic axis" + "five-layer contribution chain" 표현이 reviewer가 인용할 *대표 결론*이 되며, 그 결론은 ROUND 2 패치 이전 v04와 동일하다. 따라서 ROUND 2 P-15·P-17의 격하 효과는 *Abstract 차원에서 무효*다.
- **방어 가능성**: High (영문 Abstract 1문단 patch로 즉시 차단 가능). 단 본 ROUND 3 시점 본문에는 미적용.
- **심각도**: **Critical** — 단독으로도 Major Revision 권고 정당화.

### R-25. **footnote 16의 commit hash `aeab01a`는 EIED 임계값 commit이 아닌 실험 인프라 commit — 사전 등록 증거의 허위 인용 의혹** (Critical)

- **위치**: §3.2 line 200 footnote 16, §6.4 한계 7 line 751
- **인용**: "*RQ1의 세 모드 분해(중복/교정 기여/독립 탐지)와 진단 가설 임계값 EIED ≥ 30%는 `_workspace/01_experiment_spec.md`(2026-04-14, **commit `aeab01a`**)와 `_workspace/02_narrative_reframing.md`(2026-04-26)에 기록되어 있으며, 본 실험 EX·EIED 수치 확정 시점(2026-05-01) 이전에 외부 검증 가능한 git commit hash + timestamp로 정식화하였다. 본 commit은 force push·rebase 없이 보존되었음을 본 저자가 보증한다.*"
- **공격 논리**: 인용된 commit `aeab01a`의 실제 commit message는 git log 직접 확인 결과 "**Add SC-TSQL pipeline, web dashboard, and multi-model configs**"이다. 즉 본 commit은 *실험 인프라·웹 대시보드·다중 모델 설정의 통합 업데이트*에 해당하며, **"진단 가설 임계값 EIED ≥ 30%"를 명시 등록한 commit이 아니다**. footnote 16은 본 commit을 *임계값 30%의 사전 등록 증거*로 인용하고 있으나, 본 commit의 실제 변경 내용과 commit message가 임계값 30%와 무관하므로, reviewer 입장에서 본 인용은 **(i) 사전 등록 증거의 부정확한 표시**, **(ii) 외부 검증 가능성 보장 문장의 신뢰 위반**, **(iii) "force push·rebase 없이 보존을 본 저자가 보증한다"는 자기 보증의 공허화**를 동시에 노출한다. ROUND 2 P-16-b가 PM Escalate P6 응답으로 commit hash를 *추가*했음에도, *해당 hash가 임계값을 명시한 commit이 아닌 사실*이 P-16-b를 사전 등록 증거의 *반증*으로 전환시킨다. footnote 16은 적용 *전*보다 *후*가 reviewer에게 더 위험한 신호를 보내는 patch가 되었다.
- **방어 가능성**: Low — *임계값 30%를 실제로 명시한 commit hash*가 별도로 존재하지 않는다면 P-16-b는 철회되거나 footnote 16의 commit hash 인용 자체가 삭제되어야 함. 사후 작성된 commit으로 갈음하면 *사전 등록*의 의미 자체가 소멸.
- **심각도**: **Critical** — 사전 등록 부재의 자발 인정은 한계 7로 막을 수 있으나 *허위 사전 등록 증거 인용*은 학술 정직성 문제로 격상됨.

### R-26. **§5.5 표 7-C — 본문 §4.4.2 임계값 정의와의 모순 + cross-talk 잔존** (Critical)

- **위치**: §5.5 line 540 (표 7-C "0.6 (θ_trig)" 라벨), §4.4.2 line 295 (본문 "θ_trig = 0.5"), §5.1.1 line 400 ("θ_trig=0.5"), §6.4 한계 12 line 756
- **공격 논리 1 (본문 모순)**: §4.4.2 line 295는 "*교정 트리거 임계값 θ_trig = 0.5*"로 *0.5*를 명시한다. §5.1.1 line 400도 "θ_trig=0.5"이다. 그러나 §5.5 표 7-C line 540은 "**0.6 (θ_trig)** | 58.3 (175/300) | 본 연구 교정 트리거 임계값"이라 표기하고, 표 7-C 핵심 관찰 line 546은 "*이중 임계값(θ_trig=0.6, θ_rep=0.75)*"으로 0.6을 사용한다. 본 연구가 사용한 θ_trig 값이 **0.5인지 0.6인지가 본문 내에서 양립 불가능하게 진술**되며, ROUND 2 changelog 자체가 line 138에서 "*sweep 데이터의 τ=0.6은 θ_trig=0.5(본문 §4.4.2)와 다소 차이*"라 자인했음에도 본문 patch는 이 모순을 해소하지 못했다. reviewer가 가장 단순한 사실 검증으로 즉시 잡는 결함이며, *임계값을 결과 친화적으로 두 개 운용*했다는 의혹의 직접 증거로 작동한다 — 표 7-C에서 0.6을 *본 연구 교정 트리거*라 라벨하고 본문에서 0.5라 라벨하면, 어느 쪽이 진짜 운영값인지 reviewer가 결정하지 못한다.
- **공격 논리 2 (plateau 폭의 비좁음)**: 표 7-C는 τ=0.5에서 trigger 비율 **44.0%**(132/300), τ=0.6에서 **58.3%**(175/300), τ=0.7에서 **66.0%**(198/300)이다. 즉 τ ∈ [0.5, 0.7] 구간에서 trigger 비율은 22pp 변동하며, plateau는 *τ ∈ [0.7, 0.9]의 좁은 범위에서만* 형성된다. 본 sweep 결과를 "*임계값 sensitivity가 낮은 plateau 영역에 위치*"라 해석한 line 546의 결론은 plateau 영역을 *본 연구가 채택한 θ_rep=0.75 부근으로 한정*했을 때만 성립하며, *τ ∈ [0.5, 0.7]의 22pp 격차*는 sensitivity가 *높음*을 보여준다. 즉 sweep 결과를 plateau로 *해석할 수 있는 범위 자체가 결과 친화적*이며, 표 7-C는 plateau 메시지의 *반증 증거*로도 동시에 읽힌다.
- **공격 논리 3 (cross-talk 잔존)**: ROUND 2 hardener 자체가 *cross-talk 약점*을 인지하고 `_workspace/eied_by_tau_sweep.md`에 EIED-by-τ 데이터(τ ∈ [0.7, 0.9]에서 EIED **73.1~73.8%** plateau)를 사전 보유했음에도, 표 7-C는 *trigger 비율*만 제시하고 EIED 분자 자체의 plateau는 본문에 노출하지 않았다. §6.4 한계 12 line 756이 "*EIED·ΔEX의 임계값별 변동은 본 마감 안에서 별도 산출하지 못했다*"고 자발 인정한 것은 사실과 다른 자인 — 데이터는 보유 중이며 본문 노출만 회피한 것. reviewer 입장에서 *trigger 비율 plateau는 EIED 분자 plateau를 보장하지 않음*이라는 cross-talk 공격은 한계 12 자발 인정만으로는 차단되지 않는다.
- **방어 가능성**: Low — (i) 본문 모순은 §4.4.2 또는 표 7-C 한쪽 수정으로만 해소, (ii) plateau 폭은 본문 해석 자체의 결과 친화성을 노출, (iii) cross-talk는 EIED-by-τ 표를 본문에 추가하지 않으면 차단 불가. 세 약점이 동시에 작동.
- **심각도**: **Critical**

### R-27. **§1.3 line 83 측정 완료/향후 측정 분리 박스 — 본 제출본 *기여 5층 중 측정 완료 1.5층* 카운팅 노출** (Major)

- **위치**: §1.3 line 83 (P-17-a 박스), §1.3 line 85~95 (기여 1~6 항목), §6.4 한계 13 line 757
- **공격 논리**: P-17-a 박스는 본 제출본의 *정량 측정 완료* 영역을 (i) 기여 2의 EIED 보조 관찰, (ii) 기여 2·3의 어블레이션 4종, (iii) 평가 인프라의 베이스라인 5종 비교로 *세 항목*에 한정한다. 그러나 §1.3은 기여 1~6의 6개 항목을 나열한다(기여 4 SC k=5는 별도 카운트하지 않음을 주석 처리). reviewer가 본 박스를 *kategorical reduction*으로 변환하면: 기여 1 시연 시스템 = 정성·예정, 기여 2 ICC·EIED = 부분 측정, 기여 3 유형 라우팅 = 어블레이션 측정, 기여 5 평가 인프라 = HRDB 257건 자동 검증·시연 페르소나 36회·K sweep 모두 *향후 측정*으로 격하(§5.4·§5.6·§5.7), 기여 6 운영 가이드라인 = 정성 표(§6.2 표 10). 즉 *본 제출본의 정량 기여*는 기여 2의 EIED + 기여 2·3의 어블레이션 4종 = **사실상 1.5계층**이며, 나머지 2.5계층은 *서술·정성·예정*이다. ROUND 2 P-17-a 박스가 reviewer에게 *기여 카운팅의 자기 부정* 신호를 *명시적으로* 제공한 셈이다. 4계층 일관화 patch P-17-b는 카운팅을 4로 줄였으나, 박스가 노출한 *측정 완료 1.5층 vs 향후 2.5층* 비대칭은 4계층 카운팅 자체가 *본 제출본 분량으로 정당화 가능한가*라는 단일 사유로 Major Revision 격상 가능.
- **방어 가능성**: Med (P-17-a 박스를 1문단으로 압축하거나, 기여 4·5·6을 *방법론 골격*으로 격하해 카운팅 일치를 맞춤).
- **심각도**: **Major**

### R-28. **§6.3 RQ2 결론 — E3 ECR 12.5%(1/8 성공)에 의존한 결론이 "발견 지향" 톤 통일에서 누락** (Major)

- **위치**: §6.3 line 728~740 (RQ2 답)
- **공격 논리**: ROUND 1 R-3·ROUND 2 W7이 표본 6~12건 cherry-picking 잔존을 지적했고, ROUND 2는 R-3를 *D-5 별도 처리*로 격리했다. v05에서 §6.3 line 740은 "*본 실험 표본 크기(유형당 6~12건)로 강한 확정 진술을 내리기엔 한계가 있으며, n=1,534 전체 평가로 확정함이 적절하다*"고 자발 인정한다. 그러나 line 740 *직전*인 line 728~733은 "*A0(typed routing)이 다음 유형에서 명백한 우위를 보인다*: E3 Schema +12.5pp, E7 Empty Result +11.4pp"라는 *결정 톤* 결론을 그대로 유지한다. RQ1은 "*독립 진단 축의 후보*"로 격하했으나 RQ2는 "*명백한 우위*"로 격하 미적용 — 동일 논문 내에서 두 RQ의 *결론 강도가 비대칭*이다. E3 ECR 12.5%는 *8건 중 1건 성공*인데 "명백한 우위"라 표현하는 것은 paired bootstrap 95% CI 또는 Fisher's exact 보고 부재 상태에서 reviewer 권한으로 즉시 후퇴 요구된다. ROUND 2가 RQ1을 격하하면서 RQ2를 격하하지 않은 것은 *부분 격하의 비정합* 신호다.
- **방어 가능성**: Med (E3·E7 ΔECR을 95% CI 또는 Fisher's exact로 보고 + line 728의 "명백한 우위" 표현 약화).
- **심각도**: **Major**

### R-29. **§6.1.2 line 621 + §6.4 한계 15의 *분모 혼동* — 31.9% vs 153건 환산의 산술 모순** (Minor → Major 가능)

- **위치**: §6.1.2 line 621, §6.4 한계 15 line 759, §6.2 표 10 직후 박스 line 660, §6.2.2 표 12 직전 박스 line 698
- **공격 논리**: §6.1.2 line 621은 "*잔여 사각지대 = NLI false negative ... 사각지대 144건 중 31.9%(46/144)*"라 정확히 분모를 144로 명시한다. 한계 15 line 759는 "*1,000건/일 트래픽 기준 약 153건이 자동 통과*"라 한다. 그러나 1,000건 기준으로 환산하면 (i) 144 분모 기준 31.9% × 1,000 = 319건, (ii) 300 분모 기준 46/300 × 1,000 = **153건**. 즉 *1,000건/일 기준 153건 환산*은 *300 분모(전체 BIRD dev_300)* 기준이지 *144 분모(사각지대)* 기준이 아니다. reviewer는 본문이 *31.9%* 비율과 *153건* 환산을 같은 라인에 두면서 분모 전환을 명시하지 않은 결함으로 즉시 잡는다. 추가로 §6.2.2 표 12 line 706의 "잘못된 의사결정 노출 약 80건"은 표 12 직전 박스 line 698의 자발 인정 "*표 12의 80건은 NLI 일치 자동 통과 영역의 일부 추정*"으로 부분 변호되었으나, *1,000건 기준 153건이 노출됨*과 *80건 추정* 사이의 격차는 박스 부착으로도 *73건의 미설명 격차*가 남는다.
- **방어 가능성**: High (분모 명시·재계산으로 즉시 차단).
- **심각도**: **Minor** (단독), **Major** (R-25 commit hash 허위 + R-29 분모 혼동 누적 시 *수치 정합 결함*으로 격상).

### R-30. **§5.4 line 502 (c) — "EIED는 별도 차원에서 *강하게 지지*" 격하 누락** (Major)

- **위치**: §5.4 line 502 (핵심 관측 (c))
- **인용**: "*(c) **EIED는 별도 차원에서 강하게 지지**.* EX 관점에서 SC-TSQL의 우위가 사라진 반면, NLI는 ... **EIED = 68.1%**를 기록했다. 즉 SC-TSQL의 가치는 EX 향상이 아니라 *실행 정확도가 가리는 의미 오류의 정량화*에 있다(§6.1.2 상술)."
- **공격 논리**: ROUND 2 P-15-a/b/c/d가 EIED 결정 증거 표현을 격하한 4곳(§6.1.2, §6.1.3, §6.5, §6.5.3) 외에 *§5.4 line 502 핵심 관측 (c)*가 격하 patch에서 누락되었다. 본 라인은 *표 4 직후의 본 실험 핵심 관측*에 위치하므로, EIED를 본 실험의 결정 증거로 *강하게* 사용한다. ROUND 2 changelog가 자체 검증 체크리스트 line 25에서 `grep "결정적 메시지\|결정적 증거..."` 잔존 0건을 보고했으나, 본 grep는 *"강하게 지지"*를 검색 대상에 포함하지 않았다. 즉 자체 검증 grep의 *키워드 누락*으로 patch 효과가 본 라인에서 *통과처럼 보였으나 실제로는 미적용*. reviewer가 본 라인의 "강하게 지지"·"기록했다"·"가치는 ... 의미 오류의 정량화에 있다"의 톤을 §6.1.2의 격하 톤과 비교하면 *patch 일관성 붕괴*가 된다.
- **방어 가능성**: High (1라인 patch).
- **심각도**: **Major** (R-24 영문 Abstract와 결합 시 *본문 격하의 일관성*에 대한 신뢰 추가 손상).

### R-31. **§6.2 운영 가이드라인 표 10·12의 *EIED 68% → 비용 절감 환산* — 격하된 EIED를 ROI 환산에 결정 증거로 사용** (Major)

- **위치**: §6.2 표 10 line 660 박스, §6.2.1 line 690 (S2 시나리오 "EIED=68%가 보장하는 *2/3 사각지대 차단 효과*"), §6.2.2 line 710 ("EIED=68%가 *비용 절감 메커니즘의 정량 근거*로 직접 환원된다")
- **공격 논리**: §1.3·§6.1.2·§6.5·§6.5.3에서 EIED를 *서술적 보조 관찰*·*가시화 사례*·*결정 증거 아님*으로 격하했으나, §6.2의 운영 가이드라인 부속(표 10 박스·시나리오 S2·표 12 ROI 환산)은 EIED 68%를 *2/3 사각지대 차단 보장*·*비용 절감 메커니즘의 정량 근거*로 사용한다. 즉 격하된 보조 관찰 지표가 *운영 가이드라인의 결정 환산값*으로 그대로 인용된다. ROUND 2 P-15는 §1.3·§6.1.3·§6.5의 결론 절을 격하했으나 *§6.2 운영 가이드라인 안의 EIED 인용*은 patch 대상 외였으며, 본 reviewer 관점에서는 *격하의 형식과 사용의 실질이 §6.2에서 양립 불가*라는 ROUND 2 W1의 변형이 §6.2에서 *재발*한다. EIED를 *결정 증거 아님*으로 격하했다면 §6.2의 *2/3 차단 보장*·*비용 절감 정량 근거* 표현은 동일 톤으로 약화되어야 한다.
- **방어 가능성**: Med (S2 시나리오·표 12 환산 표현을 *본 표본 추정 기반*으로 약화).
- **심각도**: **Major**

### R-32. **§5.4 표 4 — DIN-SQL 행 "[본 실험 채움]" 미입력 (placeholder 잔존)** (Minor → Major)

- **위치**: §5.4 표 4 line 481
- **인용**: "*DIN-SQL (경량 래퍼, k=1) | [본 실험 채움] | — | — | — | [본 실험 채움]*"
- **공격 논리**: 본 표 4의 DIN-SQL 행은 두 셀(EX, 평균 응답시간)이 `[본 실험 채움]`이라는 명시적 placeholder로 남아 있다. §1.3 기여 5는 "*DAIL-SQL · MAC-SQL · DIN-SQL 공식 구현을 동일한 gpt-4o-2024-11-20 백본으로 래핑하고 BIRD 공식 평가 스크립트로 일괄 측정*"한다고 약속했고, 국문 요약 line 14·Abstract line 22도 "DIN-SQL"을 4개 베이스라인 중 하나로 명시했다. 그러나 본 핵심 결과 표에 DIN-SQL 측정값이 *부재*하므로, *4개 베이스라인 동일 백본 재실행*이라는 §1.3 기여 5의 약속이 본 제출본에서 *3개 베이스라인 + DIN-SQL placeholder*로 축소된다. ROUND 2 changelog는 본 placeholder를 자체 검증에서 잡지 못했다. reviewer는 placeholder 잔존을 *본 제출본의 작업 미완 신호*로 간주하며, KITS 본심에서 *본문 placeholder 1건*은 단독 Minor revision 사유다.
- **방어 가능성**: High (DIN-SQL 측정 또는 placeholder 행 삭제 + 국문 요약·Abstract의 "DIN-SQL" 인용 정정).
- **심각도**: **Minor** (단독), **Major** (R-27 측정 범위 압축과 결합 시 *기여 5 평가 인프라*의 약속 미이행 신호로 격상).

### R-33. **국문 요약 line 14 "본 표본 규모에서 지지" + Abstract line 22 "strongly supporting" — 동일 결과의 국·영문 결론 강도 비대칭** (Critical)

- **위치**: 국문 요약 line 14, Abstract line 22
- **공격 논리**: 동일한 EIED 68.1% 관측에 대해 국문은 "*본 BIRD dev_300 표본에서 ... 본 표본 규모에서 **지지**하였다(통계적 일반화 한계는 §6.4)*"로 약화 톤을 사용하나, Abstract 영문은 "*reaches 68.1%, **strongly supporting** the use of NLI as an independent diagnostic axis*"로 *결정 톤*을 그대로 유지한다. R-24의 부분 집합이지만 *동일 단락 내 결론 강도 비대칭*은 별도 약점으로 카운트된다 — 한 논문 안에서 동일 데이터의 결론이 *지지(weak)* vs *strongly supporting(strong)*으로 갈리면, reviewer는 *저자가 두 독자층(국문 reviewer vs 영문 색인)에 다른 메시지를 보낸다*는 의심을 갖는다. 이는 학술 정직성 신호 손상이다.
- **방어 가능성**: High (Abstract 1문장 patch).
- **심각도**: **Critical** (R-24의 일부이나 표면화된 단일 사실로 분리 카운트).

---

## 잔여 우려 (Critical 이상만)

| # | 약점 | 심각도 | 단독 차단 가능성 |
|---|---|:---:|:---:|
| R-24 | Abstract 영문 격하 미반영 | Critical | High (1문단 patch) |
| R-25 | commit `aeab01a` 사전 등록 증거 허위 | Critical | Low (실제 임계값 commit 부재 시 철회 필수) |
| R-26 | 표 7-C 본문 모순 + cross-talk | Critical | Low (3 약점 동시 작동) |
| R-33 | 국·영문 결론 강도 비대칭 | Critical | High |
| R-27 | 측정 완료 1.5층 vs 4계층 카운팅 | Major | Med |
| R-28 | RQ2 "명백한 우위" 격하 누락 | Major | Med |
| R-30 | §5.4 line 502 "강하게 지지" 잔존 | Major | High |
| R-31 | §6.2 EIED 68% ROI 환산 격하 누락 | Major | Med |
| R-29 | 31.9% vs 153건 분모 혼동 | Minor→Major | High |
| R-32 | DIN-SQL placeholder 잔존 | Minor→Major | High |

**총평**: ROUND 2 통과 12 patches 중 *Critical Fail 2건*(P-16-b, P-18-a) + *Pending 4건*에 더하여 ROUND 3가 새로 발굴한 *Critical 4건*(R-24, R-25, R-26, R-33). 본 4건 중 단독 차단 가능성 *High*는 R-24·R-33뿐이며, R-25는 *임계값 30%를 명시한 commit이 실제로 존재하지 않는다면* 사전 등록 증거 자체를 철회하거나 footnote 16 인용을 삭제해야 한다.

---

## Confidence (1~5)

**4** (높은 자신, ROUND 2와 동일 유지)

근거:
- v05 본문 850 line 직접 인용 검증 (line 14, 22, 83, 85, 87, 95, 200, 204, 206, 295, 400, 423, 476~487, 502, 540, 546, 604, 615, 621, 660, 690, 698, 706, 710, 728, 751, 756, 759 등 주요 위치 모두 추적).
- commit `aeab01a` git log 직접 확인 (R-25 외부 검증 완료).
- ROUND 2 changelog의 자체 검증 grep 키워드 한계 식별 (R-30 "강하게 지지" 누락).
- `_workspace/eied_by_tau_sweep.md` 데이터 vs 본문 표 7-C 데이터 격차 직접 비교 (R-26 cross-talk 근거).
- Confidence 5 부여를 가로막는 사유: R-25의 *임계값 30%를 실제로 명시한 commit hash가 별도 존재할 가능성*을 본 reviewer가 외부에서 검증하지 못했음. 만약 그런 별도 commit이 존재하면 R-25는 Critical → Minor로 격하될 여지.

---

## 최종 판정 한 줄

**이 논문은 v05 상태에서 Major Revision 권고. ROUND 2 patch 12건 중 P-16-b·P-18-a가 새 Critical 약점을 도입했고, ROUND 3가 발굴한 R-24·R-25·R-33이 Abstract 영문판 미반영·commit hash 허위 인용 의혹·국영문 결론 비대칭으로 단일 적용 시 Major Revision을 정당화한다. ROUND 4 (D-2 / D-1) patch가 최소 R-24·R-25·R-30·R-32 4건은 적용되어야 KITS 본심 통과 가능성이 의미 있다.**

---

## 자체 검증 체크리스트

- [x] paper-critic.md 절대 원칙 5개 준수: reject 사유 발굴 / 협력 금지 / 인상비평 금지 / 본문 근거 의무 / 수정 제안 금지
- [x] Critical 등급 절제 사용: R-24·R-25·R-26·R-33 4건만 Critical (R-32는 Minor→Major 조건부)
- [x] 모든 새 약점에 본문 line 번호·표 번호 인용
- [x] 검토자(reviewer-editor)와 다른 각도: ROUND 1·2가 *기여 카운팅 축소·격하-결론 모순*에 집중했다면, ROUND 3는 *국·영문 비대칭 (R-24·R-33)·외부 사실 검증 불일치 (R-25 commit hash)·표 7-C cross-talk 잔존 (R-26)*으로 다른 각도 공격
- [x] ROUND 2 patches 12건 통과 평가 표 (Acceptable 5 / Pending 4 / Critical Fail 2 / 부분 차단 1)
- [x] 새 약점 R-24 ~ R-33 (총 10개) 발굴
- [x] 한국어 학술 톤 유지, 자기 변호 표현 없음, 수정 제안 없음(공격만)
- [x] 권고 결과 Major Revision 명시 (Minor/Accept 미격상 사유 명확)

