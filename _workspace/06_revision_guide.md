# 06 Revision Guide — 통합 수정 지시서 (paper-writer-kr 적용용)

| 항목 | 값 |
|---|---|
| **대상 본** | `docs/논문_초안.md` v06+R-34 (865 line, 2026-05-02 적용본) |
| **마감** | 2026-05-08 (D-7) |
| **수정 적용자** | paper-writer-kr |
| **제출 가능 권고** | **Critical 패치 후 제출 가능** (Critical 3건 + Major 7건 적용 시) |
| **출처** | `_workspace/05_review_methodology.md` + `05_review_logic.md` + `05_review_format.md` |

---

## 0. 적용 우선순위 요약

| 분류 | 갯수 | 적용 가능 시간 (paper-writer-kr 기준) |
|:---:|:---:|:---:|
| **Critical** | 3 | 2~3시간 |
| **Major** | 7 | 4~5시간 |
| **Minor** | 8 | 2시간 |
| **합계** | **18** | **약 8~10시간 (1.5일)** |

마감 D-7 안에서 충분히 처리 가능한 분량.

---

## 1. CRITICAL — 제출 차단 (즉시 적용)

### C-1. 본문 끝 작업 메모 완전 삭제 (line 843 ~ 865) ★ 최우선

**위치**: `docs/논문_초안.md` line 843 ~ 865 (총 23줄)

**삭제 대상 (전 영역)**:
```
**※ 본 초안 상태 요약 (2026-04-25, v0.2)**
**실험 파일럿 반영 내역 (v0.1 → v0.2)**: ... (10줄)
**남은 작업 (본 실험 후)**: ... (4줄)
**파일럿 확정 수치 원본 로그**: ... (4줄)
```

**조치**: line 843 ~ 865 전체 *삭제*. line 821 "## 참고 문헌"의 마지막 entry [^15] (line 839) 이후를 본문 종결로 처리.

**근거**: KITS 제출본에 *제출자 작업 메모*가 포함되면 학술 출판 결격 사유.

---

### C-2. 인용 매핑 군집 오류 차단 (footnote [^3] ~ [^15])

**위치**: 본문 §2.2 line 122, §1.2 line 58 / line 60, §2.1 line 111, §1.2 line 77, §5.4 line 493, §4.4.2 line 290, 참고문헌 line 825 ~ 839.

**문제 요지**: 본문 인용 매핑과 참고문헌 리스트가 *완전히* 불일치. 특히 [^9] ~ [^12]는 본문 인용 (SQLens / "A Study of ICL Errors" / SQL-of-Thought / SQLDriller) 과 참고문헌 (Self-Consistency / CHASE-SQL / AskData / Agentar-Scale-SQL) 이 4건 모두 어긋남.

**조치 옵션 (A 우선 권장)**:

#### 옵션 A. 참고문헌 리스트 재정렬 (본문 인용을 참고문헌에 맞춤)

참고문헌 [^1] ~ [^17]을 다음과 같이 *재정렬*하여 본문 인용 매핑과 1:1 정합:

```
[^1]: Li, J. et al. *Can LLM Already Serve as A Database Interface? A BIg Bench…* NeurIPS 2023.
[^2]: Gao, D. et al. *Text-to-SQL Empowered by Large Language Models (DAIL-SQL).* VLDB 2024.
[^3]: 삭제 (DIN-SQL 중복) — 본문 line 58의 [^3] 인용은 *BIRD GPT-4 60% 보고* 맥락이므로 [^1]만으로 충분 또는 line 58을 [^1]로 단일화.
[^4]: Pourreza, M., Rafiei, D. *DIN-SQL: Decomposed In-Context Learning…* NeurIPS 2023.
[^5]: Wang, B. et al. *MAC-SQL: A Multi-Agent Collaborative Framework for Text-to-SQL.* COLING 2024.
[^6]: Cen, J. et al. *SQLFixAgent: Towards Semantic-Accurate SQL Generation…* arXiv:2406.13408, 2024. [prepublication]
[^7]: Askari, A. et al. *MAGIC: Generating Self-Correction Guideline for In-Context Text-to-SQL.* arXiv:2406.12692, 2024. [prepublication]
[^8]: Talaei, S. et al. *CHESS: Contextual Harnessing for Efficient SQL Synthesis.* arXiv:2405.16755, 2024. [prepublication]
[^9]: SQLens (정식 메타데이터 paper-researcher 확보 필요 — preprint 또는 EMNLP/AAAI 검증)
[^10]: "A Study of In-Context-Learning-Based Text-to-SQL Errors" (preprint 또는 NAACL/EMNLP — paper-researcher 확보 필요)
[^11]: SQL-of-Thought (preprint — paper-researcher 확보 필요)
[^12]: SQLDriller (preprint — paper-researcher 확보 필요)
[^13]: Pourreza, M. et al. *CHASE-SQL: Multi-Path Reasoning…* arXiv:2410.01943, 2024. [prepublication]
[^14]: Shkapenyuk, V. et al. *AskData + GPT-4o…* 2025. [technical report]
[^15]: Sun, Y. et al. *Agentar-Scale-SQL…* arXiv:2509.24403, 2025. [prepublication]
[^16]: Tian, Y., Zhang, T. *PV-SQL: Synergizing Database Probing…* Findings of ACL 2026.
[^17]: He, P. et al. *DeBERTa-v3.* ICLR 2023.
[^18]: Wang, X. et al. *Self-Consistency Improves Chain-of-Thought…* ICLR 2023.
[^19]: OpenAI. *GPT-4o System Card.* 2024-08. [technical report]
```

본문 인용 위치도 동시 갱신:
- line 77 (BIRD 리더보드 컨텍스트 1·2위 인용 부분): `[^14]` (AskData), `[^15]` (Agentar-Scale-SQL), `[^13]` (CHASE-SQL) footnote 추가.
- line 290 (NLI DeBERTa-v3 모델 인용): `[^17]` 추가.
- line 122 (`Self-Consistency` 만 본문에 추가 등장) footnote 별도 처리 또는 §4.3.1 line 264 SC k=5 결합 부분에 [^18] 추가.

#### 옵션 B. 본문 인용 자기교정 (참고문헌 리스트를 유지)

본문 §2.2 line 122 의 SQLens / SQL-of-Thought / SQLDriller 인용을 *대표 사례*로 약화하고 footnote 제거. 대신:
- "A Study of In-Context-Learning-Based Text-to-SQL Errors" 인용은 §3.1 오류 분류 체계의 핵심 근거이므로 *참고문헌 리스트에 신규 entry 추가* 필수.
- §1.2 line 58의 [^3] (DIN-SQL을 BIRD 60% 보고 맥락에 잘못 인용)은 [^1]로 통합.

**선택**: paper-researcher가 D-7 안에 SQLens·SQL-of-Thought·SQLDriller·"A Study of ICL Errors" 4편의 정확한 메타데이터를 확보 가능하면 옵션 A. 불가하면 옵션 B (인용 약화).

**근거**: 인용 매핑 오류는 reviewer가 단독 reject 사유로 작동시킬 수 있는 *학술 정직성* 결함. ROUND 4 critic도 ROUND 3 R-25 (commit hash 허위 인용)를 단독 Critical로 다룬 전례.

---

### C-3. line 287 "그림 5" 인용 제거 또는 그림 신규

**위치**: line 287 "다음 세 단계로 구성된다(그림 5)."

**문제**: 그림 1 (line 243) 외 다른 그림이 본문에 부재. 그림 2·3·4·5 모두 미존재.

**조치 (둘 중 하나)**:
- (A) line 287의 "(그림 5)" 인용 *제거* — "다음 세 단계로 구성된다." 로 변경.
- (B) ICC 모듈 다이어그램을 SVG/PNG로 신규 첨부 (paper-writer-kr 관할 외 — 분석가/엔지니어 영역).

**우선**: (A) — 본 검토자가 D-7 안 신규 그림 첨부의 제작 비용을 권고하지 않음.

---

## 2. MAJOR — 제출 전 필수

### M-1. cross-reference 표 번호 4건 일괄 수정

| line | 현 표기 | 수정 |
|:---:|---|---|
| 95 | "§6.2 표 X" | "§6.2 표 10" |
| 521 | "(아래 표 3)" | "(아래 표 6)" |
| 646 | "§6.2 표 4의 케이스 #2" | "§6.2 표 10의 케이스 #2" |
| 745 | "§5.5의 표 3" | "§5.5의 표 6" |

**조치**: 본문 search-and-replace 4건 일괄 적용.

### M-2. Placeholder 3건 치환

| line | 현 표기 | 수정 권고 |
|:---:|---|---|
| 95 | "운영 표(§6.2 표 X)" | "운영 표(§6.2 표 10)" — M-1과 동일 |
| 382 | "평균 체감 응답 시간을 *X%* 단축한다(§5.6)" | *향후 측정* 격하 또는 *정성 관찰*로 약화. 정량 측정 미확보로 구체값 *X%* 표기 불가. |
| 650 | "한글 컬럼 설명 메타데이터 주입이 EX에 **[본 실험 값]pp**의 기여를 보였으며" | "한글 컬럼 설명 메타데이터 주입이 EX에 **+20pp**의 기여를 보였으며 (HRDB 파일럿, 20→40%; 본 실험 재측정은 §6.4 한계 13으로 향후)" |

### M-3. RQ2 정식화 초록 정합성 인정 (1문장 추가)

**위치**: §6.3 line 743 또는 §1.2 line 71 직후

**추가 권고 (§6.3 line 743 직후)**:
> "초록(`docs/초록.md`)의 RQ2 정식화는 *전역 향상*을 묻는 형태이나, 본 KITS 제출본은 표본 한계로 *유형 한정 부분적 우위*로 답을 격하한다. 초록 원문은 변경 금지 기준이며, 본문의 격하는 §6.4 한계 9·12에 자발 인정으로 흡수된다."

**근거**: docs/초록.md의 RQ2 정식화는 변경 금지 기준이고, 본문 격하 결정과 미세 충돌. 본문에서 1문장 자발 인정으로 흡수.

### M-4. EIED 분자/분모 5pp 차이 명시 강화

**위치**: §5.5 표 7-D 직후 line 559 (현 "핵심 관찰" 단락) 또는 footnote `[^EIED-tau]`

**추가 권고 (footnote 강화)**:
> 본 표 7-D 73.1% (τ=0.75) 와 §6.1.2 본문 EIED 68.1% (98/144) 의 5pp 차이는 (i) boundary 1건 차이 (분모 145 vs 144) + (ii) `nli_score` 이산화 vs `nli_flag` 부울의 산출 방식 차이의 합이며, plateau 영역 (τ ≥ 0.7) 안정성 (73.1~73.8%) 에는 영향이 없다. 본 5pp 격차는 측정 잡음이 아니라 *분모/분자 기준 정의 차이*에서 도출된다.

**근거**: ROUND 4 critic이 잡지 않은 *측정 잡음 5pp 인상*을 차단.

### M-5. dev_300 sampling 절차 1줄 명시

**위치**: §5.1.1 line 396 또는 line 398 평가 환경 박스 직후

**추가 권고**:
> "본 실험은 BIRD dev 1,534 질의 중 첫 300건 (또는 seed=42 기반 random sample 300건) 을 사용한다 — 정확한 sampling 절차는 `outputs/logs/results_bird_*_seed42_*.json` 파일명 prefix 기준."

**근거**: 재현 가능성 확보. 현 본문은 dev_300의 정확한 split 절차를 명시하지 않아 reviewer 가 재현 시 confusion 가능.

### M-6. 표 7 부속표 라벨 재정리

**위치**: §5.5 표 7-C (line 537), 표 7-D (line 548)

**조치 권고**:
- 표 7-A·7-B 누락이 *표 7 본체의 부속표가 아님*이 reviewer 인상에 결함으로 잡힐 수 있음.
- 둘 중 하나:
  - (A) 표 7-C·7-D 라벨을 *표 7 (a) trigger 비율 sweep* / *표 7 (b) EIED sweep*으로 재정리.
  - (B) 표 7-C → 표 8, 표 7-D → 표 9로 재할당하고 현 표 8·9 (시연 페르소나 / K sweep, 둘 다 향후 측정) 를 표 10·11로 밀어내는 일괄 재번호.

**우선**: (A) — 분량 변동 최소.

### M-7. 표 6 caption 표본 한계 1줄

**위치**: §5.5 표 6 line 525 caption

**추가 권고**:
> "**표 6. 오류 유형별 교정 성공률 (ECR, BIRD n=300)** — A0(typed routing) vs A3(generic prompt). *유형당 표본 8~12건으로 paired bootstrap CI / Fisher's exact 미보고 — §6.4 한계 9 동반 인용 의무.*"

---

## 3. MINOR — 제출 가능 (격상 시 처리)

### m-1. line 638 "분석 시점에 정식화" → "분석 보고 시점에 정성 기준으로 도출"

ROUND 4 R-34 1단어 patch. Accept 격상 시 권장.

### m-2. line 378 "결정적이며" → "주된 결정 요소이며"

과잉 주장 격하.

### m-3. line 792 "결정적 영향을 준다는" → "주된 영향을 준다는"

과잉 주장 격하.

### m-4. §1.3 박스에 "6 항목 = 4 계층" 매핑 1줄

**추가 권고 (line 83 박스 직후)**:
> "본 §1.3의 항목 1~6은 4계층 기여를 세분 표기한 것이며, *별도 카운트하지 않은 항목 4 (SC k=5 외부 흡수)*를 제외하면 항목 1 / 항목 2·3 / 항목 5 / 항목 6 이 각각 계층 1·2·3·4 에 정확히 대응한다."

### m-5. 영문 Abstract Two findings ↔ 국문 요약 단일 발견 격차

본 제출본 한정 흡수. 추가 작업 불요.

### m-6. footnote `[^EIED-cite]` 정의 위치

**확인**: footnote `[^EIED-cite]`가 정의 (definition) 형태로 본문 어디에도 등장하지 않음. line 491 직후에 정의 등장:
```
[^EIED-cite]: EIED는 본 연구의 *서술적 보조 관찰 지표*로, ...
```

→ 정합 OK. 별도 조치 불요.

### m-7. 제출 시점 commit hash 정직 footnote 1건

ROUND 3 R-25 patch로 commit hash 인용 *완전 삭제*되었으나, 재현 가능성을 위해 부록 또는 footnote에 *제출 시점 commit*을 정직 인정으로 추가 권고. Accept 격상 시.

### m-8. footnote docx 변환 검증

KITS 양식 docx 변환 후 footnote 자동 재배치 확인. 변환 후 paper-writer-kr 가 직접 검증.

---

## 4. 초록 정합성 보호 — 변경 금지

`docs/초록.md`는 절대 변경 금지. 본문이 초록과 모순되면 *본문* 수정으로 해소 (M-3 적용 사례).

---

## 5. paper-writer-kr 적용 순서 권고

1. **Phase 1 — Critical (2~3시간)**:
   - C-1 작업 메모 삭제 (5분)
   - C-3 line 287 "그림 5" 제거 (5분)
   - C-2 인용 매핑 — 옵션 A로 진행. paper-researcher 에게 SQLens·SQL-of-Thought·SQLDriller·"A Study of ICL Errors" 메타데이터 4건 즉시 위임. 메타데이터 회수 후 BibTeX 정렬 (2시간)
2. **Phase 2 — Major (4~5시간)**:
   - M-1·M-2 placeholder + cross-reference 일괄 수정 (1시간)
   - M-3 RQ2 정식화 초록 인정 1문장 (10분)
   - M-4 EIED 5pp footnote 강화 (15분)
   - M-5 dev_300 sampling 1줄 (10분)
   - M-6 표 7 부속표 라벨 재정리 (1시간 — 표 캡션 일괄 검색·치환)
   - M-7 표 6 caption 표본 한계 1줄 (5분)
3. **Phase 3 — Minor (2시간)**:
   - m-1 ~ m-3 1단어 patch (15분)
   - m-4 §1.3 매핑 1줄 (10분)
   - m-7 commit hash footnote (15분)
   - 본문 final read-through + docx 변환 (1.5시간)

**완료 후**: `_workspace/07_paper_final.md` 신설 또는 `docs/논문_초안.md` v07로 갱신.

---

## 6. 적용 후 reviewer-editor 재검토 권고

paper-writer-kr 가 위 18건 적용 완료 후, reviewer-editor 가 *spot-check 1라운드* (1시간) 로 다음을 검증:
- C-1 / C-3 완전 삭제 grep 검증
- C-2 인용 매핑 1:1 검증 (footnote ↔ 참고문헌 표 일대일)
- M-1 cross-reference 4건 grep 검증
- M-2 placeholder 3건 잔존 검증

검증 통과 시 PM에게 *제출 가능* 권고 보고.
