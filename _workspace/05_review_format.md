# 05 Review — 형식·인용 검토 (Format / Citation)

| 항목 | 값 |
|---|---|
| **대상 본** | `docs/논문_초안.md` v06+R-34 (865 line) |
| **상위 권고** | Critic ROUND 4 → Minor Revision (Critical 0 / Minor 2) |
| **본 검토 관점** | KITS 양식·인용 매핑 정합·표 그림 캡션·BibTeX·과잉 주장 |
| **양식 자료** | `_workspace/05_KITS_submission_guidelines.md` (없음 — `docs/한국IT서비스학회 초록1.docx` 양식 추정) |

---

## F-1. KITS 양식 (분량·섹션·표·그림) — **Acceptable (단 분량 누적 1건)**

- **본문 분량**: 865 line (v04 → v06 누적 +5.2%). KITS 양식 페이지 분량 위반은 페이지 단위로 산정되며 본 markdown line 기준은 *직접 위반 신호 아님*. 단, *제출 시 docx 변환에서 분량 초과 가능성*은 v06 changelog(line 40)에서 자발 인정.
- **섹션 구조**: 국문 요약 → Abstract → 제1~6장 (서론·관련연구·오류분석·제안·실험·고찰결론) — KITS 양식 표준에 부합.
- **표·그림 라벨**: 표 1~13 (단 표 7은 표 7 / 7-C / 7-D 세 부속표로 구성, 7-A·7-B는 누락) + 그림 1 (line 243). KITS 양식상 표 라벨은 일련번호이므로 *7-C, 7-D* 라벨이 reviewer 인상평가에서 *표 7 본체에 대한 sub-table* 로 자연스럽게 흡수될 가능성 높음.
- **편집 권고 (Minor)**: 표 7-A·7-B 부재가 reviewer 의문을 부르면, 표 7-C·7-D를 *표 7 부속표 (a)·(b)*로 라벨 재정리 또는 표 8·9 (현재 향후 측정)와 충돌 없는 새 일련번호로 재할당 검토.

## F-2. 한국어 학술 톤 일관성 — **Acceptable**

- 1인칭 표현 ("본 연구는 …"), 수동태 ("…된다"), 학술 어휘 일관 적용.
- 영어 약어 (NLI, ICC, EIED, ICS, EX, CSR 등) 첫 등장 시 풀어쓰기 + 약어 병기 일관 적용.
- 영문 직역 표현은 §2.2 (B), §4.4.2 등에서 자연스럽게 한국어화됨.

## F-3. 인용 스타일 — **CRITICAL (인용 매핑 군집 오류)**

본 항목은 v06 본문에서 가장 심각한 결함이다. **footnote `[^9]` ~ `[^15]`의 본문 인용과 참고문헌 리스트가 완전히 불일치한다**.

### 본문 인용 (§2.2 line 122) vs 참고문헌 리스트 (line 833~839) 매핑

| footnote | 본문 인용 (line) | 참고문헌 리스트 (line) | 정합 |
|:---:|---|---|:---:|
| [^9] | "**SQLens**" — line 122 | "Wang, X. et al. *Self-Consistency Improves Chain-of-Thought…* ICLR 2023" — line 833 | **불일치** |
| [^10] | "*A Study of ICL-Based Text-to-SQL Errors*" — line 122 + line 151 | "Pourreza, M. et al. *CHASE-SQL…* arXiv:2410.01943, 2024" — line 834 | **불일치** |
| [^11] | "**SQL-of-Thought**" — line 122 | "Shkapenyuk, V. et al. *AskData + GPT-4o…* 2025" — line 835 | **불일치** |
| [^12] | "**SQLDriller**" — line 122 | "Sun, Y. et al. *Agentar-Scale-SQL…* arXiv:2509.24403, 2025" — line 836 | **불일치** |

### 참고문헌 리스트의 미인용 잔존 (line 833~839)

| footnote | 참고문헌 | 본문 인용 | 정합 |
|:---:|---|---|:---:|
| [^9] | Wang (Self-Consistency, ICLR 2023) | 본문 미인용 | **누락** |
| [^10] | Pourreza (CHASE-SQL) | line 122·151은 *별 논문* 인용 (오기) | **누락** |
| [^11] | Shkapenyuk (AskData) | 본문 미인용 (line 77, line 493에서 "AskData + GPT-4o 77.64%" 인용 부분만 footnote 없음) | **누락** |
| [^12] | Sun (Agentar-Scale-SQL) | 본문 미인용 (line 77, line 493 "Agentar-Scale-SQL 74.90%" 인용 부분 footnote 없음) | **누락** |
| [^13] | Tian (PV-SQL) | 본문 미인용 | **누락** |
| [^14] | He (DeBERTa-v3) | 본문 미인용 (NLI 모델 `cross-encoder/nli-deberta-v3-base` 인용 부분에 footnote 없음) | **누락** |
| [^15] | OpenAI (GPT-4o System Card) | 본문 미인용 | **누락** |

### [^3] [^4] 중복

- [^3] line 827 = "Pourreza, M., Rafiei, D. *DIN-SQL…* NeurIPS 2023"
- [^4] line 828 = "Pourreza, M., Rafiei, D. *DIN-SQL…* NeurIPS 2023. (재인용)"
- 본문 line 58 [^3] (BIRD GPT-4 EX 60% 인용 맥락)·line 60 [^4] (DIN-SQL 자기교정) — [^3]은 *DIN-SQL*이지만 line 58 맥락은 *BIRD 60% 보고 논문*을 인용해야 함 → **본문 [^3] 매핑 자체가 부적절**.

### Critical 판정 근거

- KITS reviewer 가 본 인용 매핑 오류를 잡으면 *학술 정직성* 영역에서 단독 reject 사유로 작동.
- ROUND 4 critic이 *외부 사실 검증*을 ROUND 3 R-25에서 commit hash 허위 인용으로 단독 reject 사유로 다뤘던 전례 — **본 인용 매핑 오류는 그보다 심각**.
- **편집 권고 (Critical)**: 본 reject 차단을 위해 다음 두 가지 중 하나 채택:
  - **(A) 참고문헌 리스트를 본문 인용과 정합하도록 재정렬**: [^9] = SQLens, [^10] = "A Study of ICL Errors", [^11] = SQL-of-Thought, [^12] = SQLDriller 로 변경. 단 SQLens·SQL-of-Thought·SQLDriller의 정확한 학술 메타데이터 확보가 D-7 안에서 가능한지 paper-researcher에게 우선 질의.
  - **(B) 본문 인용을 참고문헌 리스트에 맞춰 자기교정**: §2.2 line 122의 SQLens·SQL-of-Thought·SQLDriller 인용 자체를 *대표 사례*로 약화하고 footnote 제거. (B)는 본문 정직성을 직접 손상시키므로 (A) 우선.

## F-4. 표·그림 캡션·번호 정합 — **Major (4건)**

- **L-8과 일치**: 본문 cross-reference 4건 오기 (line 95 "표 X", line 521 "표 3", line 646 "표 4", line 745 "표 3", line 857 "표 2-B").
- **표 일련번호**: 표 1, 2, 3, 4, 5, 6, 7, 7-C, 7-D, 8, 9, 10, 11, 12, 13. 표 7-A·7-B 누락(F-1 참조).
- **그림 라벨**: 그림 1 (line 243). 본문 다른 곳에 그림 5 (line 287 "그림 5") 인용이 있으나 *실제 그림 부재*. **편집 권고 (Major): line 287의 "그림 5" 인용 제거 또는 ICC 모듈 다이어그램 신규 첨부**.

## F-5. 참고문헌 BibTeX — **Major (신설 + prepublication 태그 검증)**

본 검토자가 `_workspace/references.bib`를 신설하며, 본문 [^1] ~ [^15]의 BibTeX 변환을 별도 파일로 산출한다.

### prepublication / 최종 게재 정보 검증

| 인용 | 현 표기 | 실제 게재 정보 | 권고 |
|---|---|---|---|
| [^1] BIRD | NeurIPS 2023 | NeurIPS 2023 (정식) | OK |
| [^2] DAIL-SQL | VLDB 2024 | VLDB 2024 (정식) | OK |
| [^3]·[^4] DIN-SQL | NeurIPS 2023 | NeurIPS 2023 (정식) | 중복 통합 |
| [^5] MAC-SQL | COLING 2024 | COLING 2024 (정식) | OK |
| [^6] SQLFixAgent | 2024 | arXiv:2406.13408 (preprint, 2024) | **`[prepublication]` 태그 필요** |
| [^7] MAGIC | 2024 | arXiv:2406.12692 (preprint, 2024) | **`[prepublication]` 태그 필요** |
| [^8] CHESS | 2024 | arXiv:2405.16755 (preprint, 2024) — VLDB 2025 후속 가능성 | **`[prepublication]` 태그 필요** |
| [^9] Self-Consistency | ICLR 2023 | ICLR 2023 (정식) | OK (단 본문 미인용) |
| [^10] CHASE-SQL | arXiv:2410.01943, 2024 | arXiv preprint (2024) — ICLR 2025 발표 가능성 | **`[prepublication]` 태그** |
| [^11] AskData | 2025 | BIRD 리더보드 자체 보고 — 학술 게재 불명 | **`[prepublication]` 또는 *technical report*** |
| [^12] Agentar-Scale-SQL | arXiv:2509.24403, 2025 | arXiv preprint (2025) | **`[prepublication]` 태그** |
| [^13] PV-SQL | Findings of ACL 2026 | ACL 2026 Findings (정식 — 가정) | OK |
| [^14] DeBERTa-v3 | ICLR 2023 | ICLR 2023 (정식) | OK |
| [^15] GPT-4o System Card | 2024-08 | OpenAI tech report (정식 발표 아님) | **`[prepublication]` 또는 *technical report* 태그** |

**판정**: prepublication 태그 부착 대상 7건 ([^6], [^7], [^8], [^10], [^11], [^12], [^15]). 최종 게재 정보 확인은 paper-researcher에게 1건씩 위임 권장.

## F-6. 과잉 주장 자동 grep — **Acceptable (단 1건 격하 권고)**

`최초 / 유일 / 완벽 / 항상 / 결정적 / 명백히` 자동 grep 결과 (8건):

| line | 표현 | 맥락 | 판정 |
|:---:|---|---|:---:|
| 95 | "운영 가이드라인은 ... HITL 트리아지 임계값 설계의 정량 근거로 환원" | 기여 6 | 과잉 아님 |
| 204 | "결정적 영향을 줌을 실증" (스키마 링킹) | 한계 인정 맥락 | 과잉 아님 |
| 378 | "신뢰감 형성에 결정적이며" | 시연 시스템 | **격하 권고** ("핵심적이며" 또는 "주요 결정 요소") |
| 427 | "ICS는 EX를 **대체하지 않으며**, 항상 EX와 병기" | 방법론 원칙 (절대성 OK) | 과잉 아님 |
| 650 | "도메인별 스키마 접근 인프라는 여전히 결정적이다" | 한계 인정 맥락 | 과잉 아님 |
| 770 | "자사 환경 calibration은 ... 권고된다" | 일반 표현 | 과잉 아님 |
| 792 | "한글 컬럼 설명 메타데이터 주입이 EX를 20→40%로 상승시킨 관측은 ... Text-to-SQL 품질에 결정적 영향을 준다는 사실을 실증한다" | 결론 §6.5 | **격하 권고** ("결정적 영향" → "주된 영향") |
| 794 | "*SQL 신뢰도·실행 결과 상태·NLI 점수의 결합 조건*에 따른 차등 운영 액션" | 운영 가이드라인 | 과잉 아님 |

**격하 권고 2건** (line 378, 792). 단독으로는 모두 Minor.

## F-7. 작업 메모 (line 856~865) — **Critical (제출 차단)**

L-10 과 동일 — 본문 끝의 v0.2 작업 메모 11줄 (line 843~865) 완전 삭제 필수.

## F-8. footnote 본문 정합 — **Acceptable**

- footnote `[^16]`, `[^17]`, `[^18]`, `[^19]`, `[^EIED-cite]`, `[^EIED-tau]` 모두 본문 inline (mid-document) 위치. KITS 양식상 footnote는 *각 페이지 하단 번호 footnote*가 표준이므로, markdown footnote 정의가 본문 inline에 있는 것은 *docx 변환 시 페이지 하단으로 자동 재배치* 가능성에 의존.
- **편집 권고 (Minor)**: docx 변환 검증 시 footnote 자동 변환을 확인하고, 변환 실패 시 본문 끝 *각주* 섹션으로 통합 이동.

---

## 형식·인용 검토 종합

| 우선순위 | 항목 | 권고 |
|:---:|---|---|
| **Critical** | F-3 (인용 매핑 군집 오류 — [^9]~[^12] 4건 + [^3]·[^4] 중복) | 참고문헌 리스트 재정렬 또는 본문 인용 자기교정 |
| **Critical** | F-7 (작업 메모 line 843~865 삭제) | 제출 전 반드시 삭제 |
| Major | F-4 (표 그림 cross-reference 4건 오기) | 본문 일괄 검색·치환 |
| Major | F-4b (line 287 "그림 5" 미존재) | 인용 제거 또는 그림 신규 |
| Major | F-5 (BibTeX 신설 + prepublication 태그 7건) | `references.bib` 신설 |
| Minor | F-1 (표 7-A·7-B 누락 라벨) | 부속표 (a)·(b) 라벨로 재정리 |
| Minor | F-6 (line 378·792 "결정적" 격하) | 표현 1단어 수정 |
| Minor | F-8 (footnote docx 변환 검증) | 변환 후 위치 확인 |

**Critical 2건**. 본 두 건은 *제출 차단 사유*이며 paper-writer-kr이 적용 후에만 KITS 본심 회부 가능.
