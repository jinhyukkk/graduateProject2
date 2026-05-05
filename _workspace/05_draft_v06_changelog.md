# Draft v05 → v06 Changelog (closeout patches against ROUND 3 Critic)

| 항목 | 값 |
|---|---|
| **대상 본** | `docs/논문_초안.md` |
| **이전 버전** | v05 (850 line, 2026-05-01) |
| **본 버전** | v06 (865 line, 2026-05-02 적용) |
| **분량 변동** | +15 line (+1.76%) — 누적 v04→v06 = +5.2% |
| **소스 보고서** | `_workspace/critic_round3_review.md` |
| **목표** | Major Revision → Minor Revision 이하로 격하 |

---

## 적용 patch 매핑 (10건 / 10건)

| R-x | 위치 | 변경 요지 | 분류 |
|---|---|---|:---:|
| **R-25** | §3.2 footnote 16, §6.4 한계 7 | commit hash `aeab01a` 인용 *철회*, 30% 임계값을 *분석 보고 시점 도출 보조 판단 기준* 으로 정직 인정. 한계 7 강화 — "사전 등록 임계값 부재" 자발 인정 + OSF 후속 권고 | Critical |
| **R-26** | §4.4.2, §5.1.1, §5.5 표 7-C 헤더, §5.5 표 7-D 신설 | (i) θ_trig 본문 0.5 → **0.6** 으로 통일 (표 7-C 라벨과 정합), (ii) 표 7-C 헤더에 "*trigger 비율* sweep" 명시, (iii) 표 7-D EIED-by-τ sweep 신설(τ=0.5~0.9, 분모 145, 분자 73~107), (iv) τ ∈ [0.7, 0.9] plateau 양면 입증 1문장 + footnote `[^EIED-tau]` 로 nli_flag/nli_score 이산화 차이(~5pp) 명시. 한계 12 부분 해소 ("EIED 산출 완료, ΔEX 임계값 변동만 향후") | Critical |
| **R-24, R-33** | Abstract 영문판 (line 22) | "strongly supporting" → "providing a supportive observation that is *consistent with*"; "five-layer contribution chain" → "**four-layer contribution chain**"; "decisive" 류 제거; "RQ1 corrective-mode hypothesis weakly negated" → "**weakly negated within our sample**"; "reaches 68.1%" → "is observed at 68.1% (98/144) within our BIRD dev_300 sample"; "(iv) Self-Consistency (k=5) ... (v)" → "(iv) integrated SC-TSQL system (Self-Consistency at k=5 absorbed, not counted)"; "DIN-SQL" 재실행 → "left to future measurement"; 한계 4·7·8·9·10·12 동반 인용 추가 | Critical |
| **R-27** | §1.3 기여 박스 | "4계층 기여" → "**4계층 기여 중 측정 완료 약 1.5계층, 측정 예정 약 2.5계층**" 으로 정량 명시; 측정 완료 1.5계층 (EIED + 어블레이션 4종 + 베이스라인 일부) vs 측정 예정 2.5계층 (시연 페르소나 36회 + HRDB 227건 + 운영 가이드라인 정성표) 분리 박스 명문화 | Major |
| **R-28** | §6.3 RQ2 답, §5.5 표 6 ECR 분해 함의 | "명백한 우위" → "본 표본 규모에서 관측된 *부분적 우위*"; "전역 EX 기여로는 통계적 유의성에 미달" 1문장 추가; "표본 한계 (paired bootstrap CI/Fisher's exact 미보고)" 자발 인정 추가 | Major |
| **R-30** | §5.4 line 502 (c) | "EIED는 별도 차원에서 *강하게 지지*" → "EIED는 별도 차원에서 *본 표본 규모에서 시사*"; "기록했다" → "관측되었다"; "가치는 ... 의미 오류의 정량화" → "본 표본 규모에서 시사" + 한계 4·8·10·12 동반 인용 | Major |
| **R-31** | §6.2.1 S2, §6.2.2 표 12 직후 | "EIED=68%가 보장하는 *2/3 사각지대 차단 효과*" → "본 표본의 EIED=68%(보조 관찰)가 *사각지대 가시화 사례*로 작동"; "EIED=68%가 *비용 절감 메커니즘의 정량 근거*로 직접 환원" → "*결정 근거가 아니라 가시화 사례를 제공하는 보조 근거*" | Major |
| **R-29** | §6.1.2 line 621, §6.2 표 10 직후 박스 | (a) §6.1.2 분모 144(nli_flag 부울 기준) vs 표 7-D 분모 145(nli_score 이산화 기준) 차이를 boundary 1건으로 명시 + footnote `[^EIED-tau]` 참조; (b) "1,000건/일 약 153건" 환산이 *전체 dev_300 분모 기준*(46/300×1,000)이지 *144 사각지대 분모 기준*(31.9%×1,000=319건)이 아님을 명시 | Minor |
| **R-32** | §1.3 기여 5, §5.3 비교 모델 표, §5.4 표 4 DIN-SQL 행, 국문 요약 line 14, Abstract 영문 line 22 | (a) 표 4 DIN-SQL placeholder `[본 실험 채움]` → "*향후 측정*"으로 격하; (b) 국문 요약 "DAIL-SQL · MAC-SQL · DIN-SQL · zeroshot 4개" → "DAIL-SQL · MAC-SQL · zero-shot (DIN-SQL 재실행은 향후 측정)"; (c) 영문 Abstract 동일 격하; (d) §1.3 기여 5 "DAIL-SQL · MAC-SQL · DIN-SQL ... 일괄 측정" → "DAIL-SQL · MAC-SQL ... DIN-SQL은 향후 측정" | Minor |

---

## 거부·변형한 patch

- **국문 요약 line 14 적극 격하 미적용**: 이미 v05에서 "*본 표본 규모에서 지지*"로 약화되어 있으므로 영문 Abstract 격하만 1:1 정렬했다. 추가 약화는 v05 톤 유지 정책상 불필요로 판단.
- **표 7-C trigger 비율 plateau 폭 (τ ∈ [0.5, 0.7] 22pp 격차) 변호 미보강**: ROUND 3 R-26 공격 논리 2 (plateau 폭 비좁음)는 표 7-D 의 EIED-by-τ plateau 양면 입증으로 *cross-talk 약점이 차단되면* 자동 약화된다고 판단. 별도 본문 변호 없이 "*양 표에서 τ ∈ [0.7, 0.9] plateau*" 1문장으로 충분.
- **footnote 16 commit hash 완전 삭제 vs 보존 — 삭제 채택**: PM Escalate P6 응답으로 추가된 commit hash 인용을 *완전 삭제* 하고 정직 인정 표현으로 대체. 부분 변경은 reviewer 의심을 증폭시킬 수 있다고 판단.

---

## 남은 위험 (ROUND 4 critic 시점 잔여)

1. **분량 누적**: v04→v06 +5.2% 로 KITS 양식 1% 한도 초과 (단 분량 자체는 KITS 양식 페이지 분량 위반 아님 — 본문 line 기준 누적치).
2. **DIN-SQL 향후 측정**: v06 에서 5곳 (국문 요약 / Abstract / §1.3 / §5.3 / §5.4) 모두 *향후 측정* 으로 통일했으나, "기여 5 약속" 자체는 미이행. Major 단독 사유로 격상되지 않을 정도까지만 격하.
3. **R-26 잔존**: 표 7-C plateau 폭 22pp 격차 자체는 본문 변호 없음. 표 7-D 추가로 EIED 분자 plateau 양면 입증으로 *cross-talk* 만 차단됨.
4. **R-25 정직 인정 효과**: 사전 등록 부재의 자발 인정으로 *허위 인용* 의혹은 차단되었으나, 임계값 30% 자체의 결과 친화성 의혹은 표 7-D 의 30% 미만 EIED 측정값 부재로 완전 차단되지 않음.

---

## ROUND 4 critic 의 잔여 reject 가능성 평가

**Low-Medium**

근거:
- **R-24·R-25·R-33 (Critical 3건)**: 각각 영문 Abstract 격하 / commit hash 철회 / 국·영문 정합 으로 단독 reject 사유는 차단됨.
- **R-26 (Critical)**: 표 7-D EIED-by-τ 추가로 cross-talk 약점이 차단되었으며 본문 모순(0.5 vs 0.6)은 0.6으로 통일 해소.
- **R-27·R-28·R-30·R-31 (Major 4건)**: 모두 격하 적용. ROUND 4 가 *동일 위치 재공격* 으로 Critical 격상하기는 어렵다.
- **R-29·R-32 (Minor 2건)**: 분모 명시 / placeholder 격하로 reviewer 인상평가 결함 차단.
- **잔여 reject 위험 — Medium 쪽으로 끄는 요인**: (a) DIN-SQL 측정 미이행 자체, (b) 분량 누적 +5.2%, (c) HRDB 정량 측정 범위 한정 (manual 30 only) — 본 3건은 v06 patch 범위 외이며 *Major Revision 격하* 자체는 막지만 *Minor Revision 미만* (Accept) 격상은 막을 수 있음.

따라서 ROUND 4 의 권고 결과는 **Minor Revision 가능성 우세, Major Revision 잔존 가능성 일부** 로 예상한다.
