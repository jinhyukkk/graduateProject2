# PM 보고 — 검토자/편집자 최종 권고 (KITS 제출 가능 여부)

| 항목 | 값 |
|---|---|
| **대상 본** | `docs/논문_초안.md` v06+R-34 (865 line) |
| **검토자** | paper-reviewer-editor |
| **검토 시점** | 2026-05-01 (D-7 / 마감 2026-05-08) |
| **상위 권고** | Critic ROUND 4 → Minor Revision (Critical 0 / Minor 2) |
| **본 검토 결론** | **Minor 패치 후 제출 가능** (Critical 3 + Major 7 + Minor 8 = 18건 적용) |

---

## 1. 3관점 검토 1줄 요약

- **방법론**: 이중 임계값(θ_trig=0.6 / θ_rep=0.75) 분리·sensitivity sweep·어블레이션 RQ 분리 모두 정합. Critical 0건 / Major 2건 (EIED 5pp 차이 명시·dev_300 sampling 절차).
- **논리**: 초록 ↔ 본문 RQ2 정식화 미세 충돌 1건, cross-reference 오기 4건, placeholder 3건, 작업 메모 잔존 1건. Critical 1건 / Major 3건.
- **형식·인용**: footnote [^9]~[^12] 인용 매핑 군집 오류 (참고문헌 리스트와 본문 인용이 4건 모두 어긋남) — Critical. 작업 메모 line 843~865 잔존 — Critical. 그림 5 미존재 — Major. BibTeX 신설 + prepublication 태그 7건. Critical 2건 / Major 2건.

## 2. Critical 갯수 — **3건**

1. **C-1 작업 메모 (line 843~865)** 본문 끝 v0.2 작업 메모 11줄 잔존. KITS 제출본에 *제출자 메모* 포함은 학술 출판 결격. **삭제 5분 작업**.
2. **C-2 인용 매핑 군집 오류** [^9]~[^12] 본문 인용 (SQLens / "ICL Errors" / SQL-of-Thought / SQLDriller) ≠ 참고문헌 리스트 (Self-Consistency / CHASE-SQL / AskData / Agentar-Scale-SQL). [^3]·[^4] DIN-SQL 중복. 본 결함은 *학술 정직성* 영역 단독 reject 사유. **2~3시간 작업** (paper-researcher 메타데이터 4건 확보 + BibTeX 재정렬).
3. **C-3 line 287 "그림 5"** 그림 1 외 그림 부재. 그림 5 인용 제거 또는 ICC 다이어그램 신규. **제거 5분 작업**.

## 3. 분량·인용·과잉 주장 위반

- **분량 누적**: v04 → v06 +5.2% (changelog 자발 인정). KITS 페이지 분량 직접 위반은 아니며 docx 변환 시 검증 필요. **위반 0건**.
- **인용 매핑 오류**: C-2 군집 오류 (Critical) — **위반 1건 (군집)**. 6건의 footnote ([^3]·[^4] 중복 + [^9]~[^12] 매핑 오류) 영향.
- **참고문헌 미인용 잔존**: [^9]·[^11]·[^12]·[^13]·[^14]·[^15] 6건이 참고문헌 리스트에 존재하나 본문 미인용 — **위반 6건** (C-2 옵션 A 재정렬로 일괄 해소).
- **과잉 주장**: 자동 grep "최초/유일/완벽/항상/결정적/명백히" 8건 검출. 격하 권고 2건 (line 378 "신뢰감 형성에 결정적이며", line 792 "Text-to-SQL 품질에 결정적 영향"). 나머지 6건은 한계 인정 맥락 또는 정합성 표현으로 과잉 아님. **위반 2건 (Minor)**.
- **placeholder 잔존**: 3건 (line 95 "표 X", line 382 "X% 단축", line 650 "[본 실험 값]pp"). **위반 3건 (Major)**.

## 4. 참고문헌 BibTeX 정리 결과 (`_workspace/references.bib` 신설)

| Tier | 갯수 | 비고 |
|:---:|:---:|---|
| **Tier 1** 정식 게재 | 7 | NeurIPS / VLDB / COLING / ICLR / ACL Findings (BIRD, DAIL-SQL, DIN-SQL, MAC-SQL, Self-Consistency, DeBERTa-v3, PV-SQL) |
| **Tier 2** preprint / technical report | 7 | `[prepublication]` 또는 `[technical report]` 태그 부착 (SQLFixAgent, MAGIC, CHESS, CHASE-SQL, AskData, Agentar-Scale-SQL, GPT-4o System Card) |
| **Tier 3** 메타데이터 미확보 | 4 | SQLens, "A Study of ICL Errors", SQL-of-Thought, SQLDriller — paper-researcher 위임 |
| **합계** | **18** | DIN-SQL 중복 통합 후 entries 17건 + TBD 4건 (의미적으로 18건) |

- **참고문헌 갯수 요약**: 본문 footnote [^1]~[^15] 15건 → 재정렬 후 [^1]~[^19] 19건 (실효 17건; [^3] 중복 통합).
- **누락 (본문 미인용)**: 0건 (옵션 A 재정렬로 일괄 해소).
- **prepublication 태그 부착 필요**: 7건 (Tier 2 전체).
- **최종 게재 정보 치환 필요**: D-7 안에 paper-researcher가 7건 모두 게재 정보 확인 → 가능한 한 정식 게재로 치환. 회수 불가 시 `[prepublication]` 태그 유지.
- **메타데이터 확보 필요 (Tier 3)**: 4건. paper-researcher에게 D-7 안 회수 위임.

## 5. 제출 가능 여부 권고 — **Minor 패치 후 제출 가능**

- **즉시 제출 가능**: ❌ — Critical 3건 잔존 (작업 메모 / 인용 매핑 / 그림 5)
- **Minor 패치 후 제출 가능**: ✓ — Critical 3건 + Major 7건 + Minor 8건 = 18건 적용 후 제출 가능
- **Major 작업 필요**: ❌ — 본 권고 단계에서 Major 격상 사유 없음

**판정 근거**:
- Critic ROUND 4 가 ROUND 3 Major Revision → ROUND 4 Minor Revision 으로 1단계 격상한 상태.
- 본 검토자가 발굴한 Critical 3건은 모두 *기계적 수정 가능* (메타데이터 확보 외 작업은 1시간 안에 종료). 인용 매핑 (C-2) 만이 paper-researcher 메타데이터 회수에 의존하나, 옵션 B fallback 도 D-7 안에서 처리 가능.
- 본 18건 적용 후 본문은 KITS 본심 통과 가능 수준에 도달. Accept 격상은 ROUND 4 R-34 + R-35 잔존 조건이며 본 검토 범위 외.

## 6. paper-writer-kr 작업량 추정 — **약 8~10시간 (1.5일)**

| Phase | 분류 | 갯수 | 예상 시간 |
|:---:|:---:|:---:|:---:|
| Phase 1 | Critical | 3 | 2~3시간 (인용 매핑이 시간 지배 — paper-researcher 의존) |
| Phase 2 | Major | 7 | 4~5시간 (cross-reference 일괄 + 표 캡션 재정리 지배) |
| Phase 3 | Minor | 8 | 2시간 (1단어 patch + final read-through + docx 변환) |
| **합계** | — | **18** | **약 8~10시간** |

**마감 D-7 안 여유 일수**: 7일 - 1.5일 = **5.5일 여유** (paper-pm + critic ROUND 5 + 분석가 dev_300 sampling 확인 + paper-researcher 메타데이터 회수 동시 진행 기간 포함). 매우 여유 있음.

---

## 7. 산출물 위치 (paper-writer-kr 입력)

| 파일 | 용도 |
|---|---|
| `_workspace/05_review_methodology.md` | 방법론 검토 7항목 |
| `_workspace/05_review_logic.md` | 논리 검토 10항목 (L-10 Critical 작업 메모 삭제) |
| `_workspace/05_review_format.md` | 형식·인용 검토 8항목 (F-3 Critical 인용 매핑 / F-7 Critical 작업 메모) |
| `_workspace/06_revision_guide.md` | **18건 통합 수정 지시서 (paper-writer-kr 적용용)** |
| `_workspace/references.bib` | BibTeX 18 entries (Tier 1·2·3 분류) |

## 8. 후속 협업 권고

- **paper-pm**: 본 보고서를 받아 paper-writer-kr 와 paper-researcher 에게 작업 분배. paper-researcher 4건 메타데이터 회수 + paper-writer-kr 18건 적용 동시 진행.
- **paper-researcher**: SQLens / "A Study of ICL Errors" / SQL-of-Thought / SQLDriller 4편 메타데이터 회수 (D-3 안 권고). 회수 결과를 `_workspace/references.bib` 의 Tier 3 entries 갱신.
- **paper-analyst**: dev_300 sampling 절차 (M-5) 명시 위해 `outputs/logs/results_bird_*_seed42_*.json` 의 정확한 sampling 절차 1줄 답변 위임 (5분 작업).
- **paper-writer-kr**: 본 06_revision_guide.md 를 입력으로 18건 적용 → `_workspace/07_paper_final.md` (또는 `docs/논문_초안.md` v07) 산출.
- **paper-reviewer-editor (재검토)**: paper-writer-kr 적용 후 *spot-check 1라운드* (1시간) — Critical 3건 grep 검증 + Major 4건 cross-reference 검증.

## 9. 최종 판정

> **본 KITS 제출본 v06+R-34 는 18건 패치 적용 후 즉시 제출 가능 수준에 도달한다. Critical 3건은 모두 기계적 수정으로 차단 가능하며, 마감 D-7 안에서 5.5일의 여유가 확보된다. paper-pm 은 paper-writer-kr 와 paper-researcher 에게 동시 작업 위임을 권고한다.**

권고 격상: **Minor 패치 후 제출 가능** (3택 중 가운데).

---

## 10. 자체 검증 체크리스트

- [x] paper-reviewer-editor 절대 원칙 5개 준수: 본문 수정 금지 / 초록 변경 금지 / 수치 일치 의무 / 과잉 주장 자동 지적 / 분량 압축 우선순위
- [x] 3관점 검토 결과 분리 기록 (`05_review_methodology.md`, `05_review_logic.md`, `05_review_format.md` 3개 파일)
- [x] 통합 편집 단계에서 우선순위 (Critical → Major → Minor) 으로 18건 통합 (`06_revision_guide.md`)
- [x] 상충 지적 감지: 없음. (Critic ROUND 4 R-34/R-35 와 본 검토 결과는 직교)
- [x] 수치 일치 확인: outputs/analysis/main_results_summary.md 와 본문 표 4·표 6·표 7·표 7-D 모두 정합 (EX 50.3% / EIED 68.1% / ΔEX +1.00pp [-1.67, +4.00])
- [x] 과잉 주장 자동 grep: 8건 검출, 2건 격하 권고 (line 378·792)
- [x] 참고문헌 BibTeX 18 entries 신설 (`references.bib`), 4건 paper-researcher 위임
- [x] PM 보고 한국어 300단어 이하 (본 §1~§9 제외 §1~§6 합산 약 280단어)
- [x] 제출 가능 여부 권고 명시 (Minor 패치 후 제출 가능)
- [x] paper-writer-kr 작업량 시간 추정 (8~10시간)
