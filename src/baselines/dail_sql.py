"""
DAIL-SQL Lightweight Wrapper (Section 5).
Gao et al. (2024) "Text-to-SQL Empowered by Large Language Models: A Benchmark Evaluation"
VLDB 2024. https://github.com/BeachWang/DAIL-SQL

핵심 아이디어 — DAIL Selection:
  1. Question masking: DB 엔티티(테이블명/컬럼명)를 <mask>, 값을 <unk>로 치환
  2. Masked question 임베딩 간 Euclidean distance로 후보를 정렬
  3. 후보의 gold SQL skeleton과 target SQL skeleton 간 Jaccard similarity ≥ threshold인
     예시를 우선 선택, 부족하면 threshold 미만에서 폴백
  4. Code Representation + DAIL Organization 프롬프트:
     /* Given the following database schema: */  {DDL}
     /* Answer the following: {example_q} */  {example_sql}
     ...
     /* Answer the following: {target_q} */  SELECT

경량 래퍼 타협 사항 (논문 본문에 명시 필요):
  - 임베딩 모델: sentence-transformers 대신 OpenAI embedding 사용 (동일 LLM 환경 통일).
    OpenAI embedding은 정규화되어 반환되므로 Euclidean distance와 cosine 기반 정렬이 동치.
  - 예비(preliminary) SQL 생성 생략: target의 SQL skeleton 대신 gold SQL skeleton만 활용.
  - Self-consistency 생략: n=1, temperature=0 ("without SC" 구성, 논문에서도 보고됨).
  - k는 config에서 설정 (논문 최적 k=9, 비용상 k=3~5 허용).
"""

import json
import re
import time
import logging
from pathlib import Path

import numpy as np

from src.baselines.base import BaselineModel, extract_sql

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
#  유틸리티: SQL skeleton, Question masking                            #
# ------------------------------------------------------------------ #

# SQL 키워드 — skeleton에서 보존할 토큰
_SQL_KEYWORDS = {
    "select", "from", "where", "and", "or", "not", "in", "between", "like",
    "is", "null", "join", "inner", "left", "right", "outer", "cross", "on",
    "group", "by", "order", "having", "limit", "offset", "union", "all",
    "intersect", "except", "distinct", "as", "case", "when", "then", "else",
    "end", "asc", "desc", "exists", "count", "sum", "avg", "min", "max",
    "cast", "coalesce", "ifnull", "nullif", "iif", "with",
    "*", "(", ")", ",", "=", "<", ">", "<=", ">=", "!=", "<>", "+", "-",
    "/", "||",
}


def sql2skeleton(sql: str) -> str:
    """
    SQL을 skeleton으로 변환한다 (DAIL-SQL 공식 구현 참조).

    테이블명, 컬럼명, 문자열 리터럴, 숫자를 모두 '_'로 치환하고
    SQL 키워드와 구조만 남긴다.

    예:
      SELECT name FROM students WHERE age > 20
      → select _ from _ where _ > _
    """
    # 문자열 리터럴 제거: 'xxx' 또는 "xxx"
    s = re.sub(r"'[^']*'", "_", sql)
    s = re.sub(r'"[^"]*"', "_", s)

    # 토큰화: 괄호, 쉼표, 연산자를 분리
    s = re.sub(r"([(),=<>!+\-/|])", r" \1 ", s)
    tokens = s.lower().split()

    skeleton_tokens = []
    for tok in tokens:
        tok = tok.strip("`[]")
        if not tok:
            continue
        # 숫자 → _
        if re.match(r"^-?\d+(\.\d+)?$", tok):
            skeleton_tokens.append("_")
        # SQL 키워드 → 그대로
        elif tok in _SQL_KEYWORDS:
            skeleton_tokens.append(tok)
        # 그 외 (테이블명, 컬럼명 등) → _
        else:
            skeleton_tokens.append("_")

    # 연속된 _ 축약
    result = []
    for tok in skeleton_tokens:
        if tok == "_" and result and result[-1] == "_":
            continue
        result.append(tok)
    return " ".join(result)


def skeleton_jaccard(sql_a: str, sql_b: str) -> float:
    """두 SQL skeleton 간의 Jaccard similarity를 계산한다."""
    tokens_a = set(sql2skeleton(sql_a).split())
    tokens_b = set(sql2skeleton(sql_b).split())
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)


def mask_question(question: str, schema: dict) -> str:
    """
    Question masking: 질의에서 DB 엔티티(테이블명, 컬럼명)를 <mask>로,
    숫자/날짜 값을 <unk>로 치환한다.

    DAIL-SQL 논문의 schema linking 기반 마스킹을 경량으로 재현.
    정확한 schema linking 없이 schema의 테이블명/컬럼명을 패턴 매칭한다.

    Args:
        question: 원본 자연어 질의
        schema: {"tables": [str], "columns": {table: [cols]}} 또는
                {"schema_text": str} (DDL에서 엔티티를 추출)
    """
    masked = question

    # 테이블명, 컬럼명 수집
    entities: set[str] = set()
    if "tables" in schema:
        for t in schema["tables"]:
            entities.add(t.lower())
    if "columns" in schema:
        for cols in schema["columns"].values():
            for c in cols:
                entities.add(c.lower())
    # schema_text에서 추출 (fallback)
    if not entities and "schema_text" in schema:
        # CREATE TABLE xxx (...) 에서 테이블명 추출
        for m in re.finditer(r"CREATE\s+TABLE\s+(\w+)", schema["schema_text"], re.IGNORECASE):
            entities.add(m.group(1).lower())
        # 컬럼명 추출: 줄 시작의 공백+이름+타입 패턴
        for m in re.finditer(r"^\s+(\w+)\s+(?:TEXT|INTEGER|REAL|NUMERIC|BLOB|VARCHAR|INT|FLOAT|DATE|BOOLEAN)",
                             schema["schema_text"], re.MULTILINE | re.IGNORECASE):
            entities.add(m.group(1).lower())

    # 긴 엔티티부터 치환 (부분 매칭 방지)
    for entity in sorted(entities, key=len, reverse=True):
        if len(entity) < 2:
            continue
        # 단어 경계를 이용한 대소문자 무시 치환
        masked = re.sub(
            r"\b" + re.escape(entity) + r"\b",
            "<mask>",
            masked,
            flags=re.IGNORECASE,
        )

    # 숫자/날짜 값 → <unk>
    masked = re.sub(r"\b\d{4}[-/]\d{2}[-/]\d{2}\b", "<unk>", masked)  # 날짜
    masked = re.sub(r"\b\d+(\.\d+)?\b", "<unk>", masked)  # 숫자

    return masked


# ------------------------------------------------------------------ #
#  DAILSQLBaseline                                                     #
# ------------------------------------------------------------------ #

class DAILSQLBaseline(BaselineModel):
    """
    Section 5: DAIL-SQL 경량 래퍼.

    DAIL Selection (EUCDISMASKPRESKLSIMTHR) 알고리즘을 재현:
      1. Masked question embedding 간 Euclidean distance로 후보 정렬
      2. SQL skeleton Jaccard ≥ threshold인 예시 우선 선택
      3. Code Representation + DAIL Organization 프롬프트

    하이퍼파라미터 (configs/config.yaml):
      - baselines.dail_sql.few_shot_k: 선택할 예시 수 (기본 9, 논문 최적)
      - baselines.dail_sql.skeleton_sim_threshold: skeleton Jaccard 임계값 (기본 0.85)
      - embedding.model: 임베딩 모델
    """

    def __init__(self, config: dict, few_shot_pool: list[dict] | None = None):
        """
        Args:
            config: configs/config.yaml에서 로드된 설정
            few_shot_pool: Few-shot 후보 풀. 각 항목:
                {"query": str, "sql": str, "schema": str, "db_id": str, "question_id": int}
                None이면 빈 풀로 시작 — load_few_shot_pool()로 로드해야 함.
        """
        super().__init__(config)

        dail_config = config.get("baselines", {}).get("dail_sql", {})
        self.few_shot_k = dail_config.get("few_shot_k", 9)
        self.skeleton_sim_threshold = dail_config.get("skeleton_sim_threshold", 0.85)
        self.embedding_model = config["embedding"]["model"]

        self.few_shot_pool = few_shot_pool or []
        self._pool_embeddings: np.ndarray | None = None
        self._pool_masked_questions: list[str] | None = None

    # ------------------------------------------------------------------ #
    #  Few-shot 풀 로딩                                                   #
    # ------------------------------------------------------------------ #

    def load_few_shot_pool(
        self,
        data_path: str,
        tables_path: str | None = None,
        db_base_dir: str | None = None,
        exclude_query_ids: set[int] | None = None,
    ) -> int:
        """
        BIRD train set (또는 다른 분리된 데이터)에서 few-shot 풀을 로드한다.

        주의: dev.json을 풀로 쓰면 data leakage. train.json을 사용해야 한다.
        train set이 없으면 dev.json에서 로드하되, predict 시 동일 query_id를
        제외하고 논문에 이 제한을 명시한다.

        Args:
            data_path: train.json 또는 dev.json 경로
            tables_path: tables.json 경로 (스키마 DDL 구성용)
            db_base_dir: databases/ 디렉토리 경로
            exclude_query_ids: 풀에서 제외할 query_id 집합

        Returns:
            로드된 예시 수
        """
        data_file = Path(data_path)
        if not data_file.exists():
            logger.warning("Few-shot pool file not found: %s", data_path)
            return 0

        with open(data_file, encoding="utf-8") as f:
            examples = json.load(f)

        # 스키마 DDL 매핑
        schema_map: dict[str, str] = {}
        if tables_path and Path(tables_path).exists():
            schema_map = self._build_schema_map(tables_path)
        elif db_base_dir and Path(db_base_dir).exists():
            schema_map = self._build_schema_map_from_dbs(db_base_dir)

        # 스키마를 dict 형태로도 준비 (question masking용)
        schema_dict_map: dict[str, dict] = {}
        if tables_path and Path(tables_path).exists():
            schema_dict_map = self._build_schema_dict_map(tables_path)

        exclude = exclude_query_ids or set()
        pool = []
        for ex in examples:
            qid = ex.get("question_id", -1)
            if qid in exclude:
                continue
            db_id = ex.get("db_id", "")
            schema_ddl = schema_map.get(db_id, "")
            schema_dict = schema_dict_map.get(db_id, {"schema_text": schema_ddl})
            pool.append({
                "query": ex["question"],
                "masked_query": mask_question(ex["question"], schema_dict),
                "sql": ex.get("SQL", ""),
                "sql_skeleton": sql2skeleton(ex.get("SQL", "")),
                "schema": schema_ddl,
                "db_id": db_id,
                "question_id": qid,
            })

        self.few_shot_pool = pool
        self._pool_embeddings = None  # 캐시 초기화
        self._pool_masked_questions = None
        logger.info("Loaded %d few-shot examples from %s", len(pool), data_path)
        return len(pool)

    @staticmethod
    def _build_schema_dict_map(tables_path: str) -> dict[str, dict]:
        """tables.json에서 db_id → {"tables": [...], "columns": {...}} 매핑."""
        with open(tables_path, encoding="utf-8") as f:
            tables_data = json.load(f)

        result = {}
        for db_info in tables_data:
            db_id = db_info["db_id"]
            table_names = db_info["table_names_original"]
            columns_raw = db_info["column_names_original"]
            columns: dict[str, list[str]] = {}
            for tbl_idx, col_name in columns_raw:
                if tbl_idx < 0:
                    continue
                tbl_name = table_names[tbl_idx] if tbl_idx < len(table_names) else ""
                columns.setdefault(tbl_name, []).append(col_name)
            result[db_id] = {"tables": table_names, "columns": columns}
        return result

    @staticmethod
    def _build_schema_map(tables_path: str) -> dict[str, str]:
        """dev_tables.json에서 db_id → CREATE TABLE DDL 문자열 매핑."""
        with open(tables_path, encoding="utf-8") as f:
            tables_data = json.load(f)

        schema_map = {}
        for db_info in tables_data:
            db_id = db_info["db_id"]
            table_names = db_info["table_names_original"]
            columns = db_info["column_names_original"]
            col_types = db_info.get("column_types", [])
            raw_pks = db_info.get("primary_keys", [])
            primary_keys: set[int] = set()
            for pk in raw_pks:
                if isinstance(pk, list):
                    primary_keys.update(pk)
                else:
                    primary_keys.add(pk)

            table_columns: dict[int, list[str]] = {}
            for col_idx, (tbl_idx, col_name) in enumerate(columns):
                if tbl_idx < 0:
                    continue
                col_type = col_types[col_idx] if col_idx < len(col_types) else "TEXT"
                pk_marker = " PRIMARY KEY" if col_idx in primary_keys else ""
                table_columns.setdefault(tbl_idx, []).append(
                    f"  {col_name} {col_type}{pk_marker}"
                )

            ddl_lines = []
            for tbl_idx, tbl_name in enumerate(table_names):
                cols = table_columns.get(tbl_idx, [])
                ddl_lines.append(f"CREATE TABLE {tbl_name} (\n" + ",\n".join(cols) + "\n);")

            schema_map[db_id] = "\n\n".join(ddl_lines)
        return schema_map

    @staticmethod
    def _build_schema_map_from_dbs(db_base_dir: str) -> dict[str, str]:
        """dev_databases/에서 .sqlite 파일로부터 DDL 직접 추출."""
        import sqlite3
        schema_map = {}
        base = Path(db_base_dir)
        for db_dir in base.iterdir():
            if not db_dir.is_dir():
                continue
            db_file = db_dir / f"{db_dir.name}.sqlite"
            if not db_file.exists():
                continue
            try:
                conn = sqlite3.connect(str(db_file))
                cursor = conn.execute(
                    "SELECT sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL"
                )
                ddls = [row[0] for row in cursor.fetchall()]
                conn.close()
                schema_map[db_dir.name] = "\n\n".join(ddls)
            except Exception as e:
                logger.warning("Failed to read schema from %s: %s", db_file, e)
        return schema_map

    # ------------------------------------------------------------------ #
    #  임베딩 & 유사도                                                     #
    # ------------------------------------------------------------------ #

    def _get_embedding(self, texts: list[str]) -> np.ndarray:
        """OpenAI 임베딩 API로 텍스트 리스트를 임베딩한다.

        OpenAI Embeddings API는 요청당 최대 2048개 입력 제한이 있어 배치 처리.
        """
        batch_size = 2048
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            response = self.client.embeddings.create(
                model=self.embedding_model,
                input=batch,
            )
            all_embeddings.extend(item.embedding for item in response.data)
        return np.array(all_embeddings, dtype=np.float32)

    def _compute_pool_embeddings(self):
        """Few-shot 풀의 masked question 임베딩을 미리 계산한다 (1회만)."""
        if not self.few_shot_pool or self._pool_embeddings is not None:
            return
        # masked question을 임베딩 (논문: question masking 후 임베딩)
        self._pool_masked_questions = [
            ex.get("masked_query", ex["query"]) for ex in self.few_shot_pool
        ]
        self._pool_embeddings = self._get_embedding(self._pool_masked_questions)

    def _euclidean_distance(self, a: np.ndarray, b: np.ndarray) -> np.ndarray:
        """
        Euclidean distance를 계산한다. a: (1, d), b: (n, d) -> (n,)

        참고: OpenAI embedding은 정규화되어 반환되므로
        euclidean_distance = sqrt(2 - 2 * cosine_similarity).
        정규화 벡터에서는 cosine 기반 정렬과 동치이나, 논문 원안의 metric을 따른다.
        """
        diff = b - a  # (n, d)
        return np.sqrt(np.sum(diff ** 2, axis=-1))  # (n,)

    # ------------------------------------------------------------------ #
    #  DAIL Selection: 2단계 필터링                                        #
    # ------------------------------------------------------------------ #

    def _select_few_shot(
        self,
        question: str,
        schema: dict,
        exclude_query_id: int | None = None,
    ) -> list[dict]:
        """
        DAIL Selection (EUCDISMASKPRESKLSIMTHR):
          1. Masked question 임베딩 간 Euclidean distance로 후보 정렬
          2. SQL skeleton Jaccard ≥ threshold인 예시 우선 선택
          3. 부족하면 threshold 미만에서 폴백

        경량 래퍼 타협: target의 예비 SQL skeleton 대신 gold SQL skeleton만 사용.
        따라서 skeleton Jaccard 비교는 pool 예시 간에만 수행.
        target SQL이 없으면 skeleton 필터링을 distance 정렬만으로 대체한다.

        Args:
            question: 자연어 질의
            schema: 스키마 정보 dict (question masking에 사용)
            exclude_query_id: 제외할 query_id
        """
        if not self.few_shot_pool:
            logger.warning("Few-shot pool is empty — falling back to zero-shot behavior")
            return []

        self._compute_pool_embeddings()

        # Step 1: Masked question 임베딩 → Euclidean distance
        masked_q = mask_question(question, schema)
        query_emb = self._get_embedding([masked_q])
        distances = self._euclidean_distance(query_emb, self._pool_embeddings)

        # 자기 자신 제외
        if exclude_query_id is not None:
            for i, ex in enumerate(self.few_shot_pool):
                if ex.get("question_id") == exclude_query_id:
                    distances[i] = np.inf

        # Step 2: Distance 기준 정렬
        sorted_indices = np.argsort(distances)

        # Step 3: Skeleton Jaccard threshold 기반 2단계 필터링
        # 경량 래퍼에서는 target SQL skeleton이 없으므로,
        # pool 내 가장 가까운 예시의 skeleton을 대리(proxy)로 사용.
        # 1차: threshold 이상인 예시를 distance 순으로 수집
        # 2차: 부족하면 threshold 미만에서 distance 순으로 폴백
        top_k = min(self.few_shot_k, len(self.few_shot_pool))

        # 가장 가까운 예시의 SQL skeleton을 proxy target skeleton으로 사용
        proxy_idx = sorted_indices[0]
        proxy_skeleton = self.few_shot_pool[proxy_idx].get("sql_skeleton", "")

        above_threshold = []
        below_threshold = []
        for idx in sorted_indices:
            if distances[idx] == np.inf:
                continue
            ex = self.few_shot_pool[idx]
            ex_skeleton = ex.get("sql_skeleton", "")
            if proxy_skeleton and ex_skeleton:
                # skeleton 토큰 Jaccard
                tokens_a = set(proxy_skeleton.split())
                tokens_b = set(ex_skeleton.split())
                jaccard = len(tokens_a & tokens_b) / len(tokens_a | tokens_b) if (tokens_a | tokens_b) else 0.0
            else:
                jaccard = 0.0

            if jaccard >= self.skeleton_sim_threshold:
                above_threshold.append(idx)
            else:
                below_threshold.append(idx)

            if len(above_threshold) >= top_k:
                break

        # 합쳐서 K개
        selected_indices = (above_threshold + below_threshold)[:top_k]
        return [self.few_shot_pool[i] for i in selected_indices]

    # ------------------------------------------------------------------ #
    #  predict                                                             #
    # ------------------------------------------------------------------ #

    def predict(
        self,
        question: str,
        schema: dict,
        db_path: str,
        query_id: int | None = None,
        evidence: str = "",
    ) -> dict:
        """
        DAIL-SQL 방식으로 SQL을 생성한다.

        Args:
            question: 자연어 질의
            schema: 스키마 정보 (schema_text 키 필수, tables/columns 선택)
            db_path: SQLite DB 파일 경로 (미사용)
            query_id: few-shot 풀에서 자기 자신 제외용 ID

        Returns:
            표준 결과 딕셔너리
        """
        start_time = time.time()
        schema_text = schema.get("schema_text", "")
        total_prompt_tokens = 0
        total_completion_tokens = 0

        try:
            # Step 1: DAIL Selection
            selected_examples = self._select_few_shot(
                question, schema, exclude_query_id=query_id
            )

            # Step 2: Code Representation + DAIL Organization 프롬프트
            prompt = self._build_prompt(question, schema_text, selected_examples, evidence)
            messages = [{"role": "user", "content": prompt}]

            # Step 3: SQL 생성
            response = self._call_llm(messages)
            raw_output = response["content"]
            sql = extract_sql("SELECT " + raw_output) if raw_output else ""
            total_prompt_tokens += response["prompt_tokens"]
            total_completion_tokens += response["completion_tokens"]

            latency = time.time() - start_time
            return self._make_result(
                sql=sql,
                raw_output=raw_output,
                prompt_tokens=total_prompt_tokens,
                completion_tokens=total_completion_tokens,
                latency=latency,
            )

        except Exception as e:
            latency = time.time() - start_time
            logger.error("DAILSQLBaseline.predict failed: %s", e)
            return self._make_result(
                sql="",
                raw_output="",
                prompt_tokens=total_prompt_tokens,
                completion_tokens=total_completion_tokens,
                latency=latency,
                error=str(e),
            )

    # ------------------------------------------------------------------ #
    #  프롬프트: Code Representation + DAIL Organization                   #
    # ------------------------------------------------------------------ #

    def _build_prompt(
        self,
        question: str,
        schema_text: str,
        examples: list[dict],
        evidence: str = "",
    ) -> str:
        """
        DAIL-SQL 논문의 Code Representation + DAIL Organization 프롬프트.
        evidence가 제공되면 schema 다음에 hint 블록으로 삽입.
        """
        parts = []
        parts.append("/* Given the following database schema: */")
        parts.append(schema_text)
        parts.append("")

        if evidence and evidence.strip():
            parts.append(f"/* External knowledge / hint: {evidence.strip()} */")
            parts.append("")

        for ex in examples:
            parts.append(f"/* Answer the following: {ex['query']} */")
            parts.append(ex["sql"])
            parts.append("")

        parts.append(f"/* Answer the following: {question} */")
        parts.append("SELECT ")

        return "\n".join(parts)
