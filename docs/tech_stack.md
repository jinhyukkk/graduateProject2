# SC-TSQL 기술 스택

**프로젝트:** Self-Correcting Text-to-SQL (국민대학교 대학원 졸업프로젝트2)
**작성일:** 2026-04-18

---

## AI / ML

| 기술 | 역할 |
|---|---|
| **GPT-4o** (`gpt-4o-2024-11-20`) | SQL 생성·교정·결과 설명의 핵심 LLM |
| **text-embedding-3-large** (OpenAI) | 스키마 링킹 — 테이블·컬럼 임베딩 |
| **cross-encoder/nli-deberta-v3-base** (HuggingFace) | NLI 의도 일치 판정 (RQ1 핵심) |
| **Few-shot Prompting** | 구조·의미 유사도 가중합으로 3개 예시 선택 |
| **Prompt Engineering** | 오류 유형 8종별 전용 교정 지시문 (RQ2 핵심) |
| **logprob Confidence Scoring** | SQL 생성 신뢰도 자동 평가 |
| **cross-encoder Reranking** | 후보 SQL 2단계 재순위화 |

---

## 파이프라인 / 오케스트레이션

| 기술 | 역할 |
|---|---|
| **Multi-agent 구조** | Schema Linker → Generator → Validator → Verifier → Corrector 역할 분리 |
| **Self-Correction Loop** | 최대 K=3회 반복 교정 |
| **LangGraph** (StateGraph) | 조건 분기 기반 파이프라인 오케스트레이터 (`use_langgraph` 플래그로 교체 가능) |
| **Guardrails** | 입력 SQL 인젝션 차단, 출력 1,000행 제한·저신뢰 경고 |

---

## 백엔드 / 인프라

| 기술 | 역할 |
|---|---|
| **Python** | 전체 파이프라인 구현 언어 |
| **FastAPI** | 프론트엔드 ↔ 파이프라인 연결 API 서버 |
| **SQLite** | 실행 검증용 샌드박스 DB (읽기 전용, 5초 타임아웃) |
| **Docker** | 재현 가능한 실험 환경 패키징 |
| **GitHub Actions** | CI/CD 4단계 자동화 (구문검사·단위테스트·스키마검증·타입검사) |

---

## 프론트엔드

| 기술 | 역할 |
|---|---|
| **React + Vite** | 데모 UI |
| **Ant Design** | 파이프라인 상태 칩·테이블·레이아웃 컴포넌트 |
| **TypeScript** | 프론트엔드 타입 안전성 |

---

## 데이터 / 평가

| 기술 | 역할 |
|---|---|
| **BIRD 벤치마크** | 공개 Text-to-SQL 평가셋 (1,534 질의) |
| **HRDB (합성 데이터)** | 557개 테이블 기업 인사 DB — 스키마만 실제, 데이터는 합성 |
| **EX / ICS / CSR** | 실행 정확도·의도 일치 점수·교정 성공률 3중 지표 |

---

## 의도적으로 사용하지 않는 기술

| 기술 | 제외 이유 |
|---|---|
| PyTorch · Fine-tuning | API 호출 기반 설계, 자체 모델 훈련 없음 |
| GraphRAG · Knowledge Graph | 관계형 스키마로 충분 |
| Kubernetes · 클라우드 오케스트레이션 | 단일 서버 데모 수준 |
| NoSQL | SQL 실행 검증이 핵심, 연구 범위 외 |
| VLM · LAM | 텍스트 전용 파이프라인 |
