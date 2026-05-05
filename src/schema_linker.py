"""
Schema Linker (Section 4.2)
임베딩 기반 스키마 검색 + LLM 기반 최종 선택.
"""

import hashlib
import logging
import os
import json
import sqlite3
import time
import numpy as np
import faiss
from openai import OpenAI

from src.openai_retry import chat_completion, embeddings as embeddings_call

logger = logging.getLogger(__name__)

# FAISS 인덱스 디스크 캐시 — 백엔드 재시작 시 OpenAI 임베딩 API를 다시 호출하지
# 않도록 (db_mtime, embedding_model, column_descriptions_mtime)별로 캐시한다.
_DEFAULT_CACHE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "outputs", "cache", "schema_linker",
)


class SchemaLinker:
    """
    Section 4.2: 자연어 질의에 관련된 테이블/컬럼을 검색하고 선택한다.

    1단계: text-embedding-3-large로 질의와 스키마 메타데이터를 임베딩하여
           코사인 유사도 기반 상위 K개 후보를 추출한다.
           S_relevance(q, s_i) = (q⃗ · s⃗_i) / (|q⃗| |s⃗_i|)  # Eq. (1)
    2단계: GPT-4o로 최소 필요 스키마를 선택한다 (외래키 관계 포함).
    """

    def __init__(self, db_path: str, config: dict):
        """
        Args:
            db_path: SQLite 데이터베이스 파일 경로
            config: configs/config.yaml에서 로드된 설정 딕셔너리
        """
        self.db_path = db_path
        self.config = config
        self.client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        self.embedding_model = config["embedding"]["model"]
        self.top_k_tables = config["schema_linker"]["top_k_tables"]
        self.top_k_columns = config["schema_linker"]["top_k_columns"]
        self.llm_model = config["llm"]["model"]

        self.schema_metadata = self._load_schema_metadata()
        self.column_descriptions = self._load_column_descriptions()
        self.index = None
        self.index_texts = []
        self.index_meta = []
        self.build_index()

    def _load_column_descriptions(self) -> dict:
        """DB 같은 디렉토리의 column_descriptions.json이 있으면 로드한다.
        HRDB의 경우 물리 테이블명 → 한글 컬럼 설명 매핑.
        """
        import os as _os
        desc_path = _os.path.join(_os.path.dirname(self.db_path), "column_descriptions.json")
        if not _os.path.exists(desc_path):
            return {}
        try:
            with open(desc_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {k: v for k, v in data.items() if not k.startswith("_")}
        except Exception:
            return {}

    def _load_schema_metadata(self) -> dict:
        """DB에서 테이블명, 컬럼명, 타입, 외래키, 예시값을 로드한다."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 테이블 목록
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tables = [row[0] for row in cursor.fetchall()]

        metadata = {}
        for table in tables:
            # 컬럼 정보
            cursor.execute(f"PRAGMA table_info(`{table}`);")
            columns = []
            for col_info in cursor.fetchall():
                col_name = col_info[1]
                col_type = col_info[2]
                # 예시값 가져오기 (최대 3개)
                try:
                    cursor.execute(
                        f"SELECT DISTINCT `{col_name}` FROM `{table}` WHERE `{col_name}` IS NOT NULL LIMIT 3;"
                    )
                    sample_values = [str(row[0]) for row in cursor.fetchall()]
                except Exception:
                    sample_values = []
                columns.append({
                    "name": col_name,
                    "type": col_type,
                    "sample_values": sample_values,
                })

            # 외래키 정보
            cursor.execute(f"PRAGMA foreign_key_list(`{table}`);")
            foreign_keys = []
            for fk in cursor.fetchall():
                foreign_keys.append({
                    "from_column": fk[3],
                    "to_table": fk[2],
                    "to_column": fk[4],
                })

            metadata[table] = {
                "columns": columns,
                "foreign_keys": foreign_keys,
            }

        conn.close()
        return metadata

    def _get_embedding(self, texts: list[str]) -> np.ndarray:
        """OpenAI 임베딩 API로 텍스트 리스트를 임베딩한다.

        OpenAI Embeddings API는 요청당 최대 2048개 입력 제한이 있으므로
        2048개씩 배치로 나눠 호출한다.
        """
        batch_size = 2048
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            response = embeddings_call(
                self.client,
                model=self.embedding_model,
                input=batch,
            )
            all_embeddings.extend(item.embedding for item in response.data)
        return np.array(all_embeddings, dtype=np.float32)

    def _cache_key(self) -> str:
        """캐시 키 — db 파일 mtime + size, embedding_model, column_descriptions mtime."""
        try:
            db_stat = os.stat(self.db_path)
            db_sig = f"{int(db_stat.st_mtime)}-{db_stat.st_size}"
        except OSError:
            db_sig = "nodb"
        desc_path = os.path.join(os.path.dirname(self.db_path), "column_descriptions.json")
        desc_sig = "0"
        if os.path.exists(desc_path):
            try:
                desc_sig = str(int(os.stat(desc_path).st_mtime))
            except OSError:
                pass
        raw = f"{os.path.abspath(self.db_path)}|{db_sig}|{self.embedding_model}|{desc_sig}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def _cache_dir(self) -> str:
        return os.path.join(_DEFAULT_CACHE_DIR, self._cache_key())

    def _try_load_cache(self) -> bool:
        """디스크 캐시에서 FAISS 인덱스·텍스트·메타를 복원한다. 성공 시 True."""
        cdir = self._cache_dir()
        emb_path = os.path.join(cdir, "embeddings.npy")
        texts_path = os.path.join(cdir, "texts.json")
        meta_path = os.path.join(cdir, "meta.json")
        if not (os.path.exists(emb_path) and os.path.exists(texts_path) and os.path.exists(meta_path)):
            return False
        try:
            embeddings = np.load(emb_path)
            with open(texts_path, "r", encoding="utf-8") as f:
                texts = json.load(f)
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
        except Exception as exc:
            logger.warning("FAISS 캐시 로드 실패(%s) — 재구축 진행", exc)
            return False
        if not texts or len(texts) != embeddings.shape[0]:
            return False
        dim = embeddings.shape[1]
        index = faiss.IndexFlatIP(dim)
        index.add(embeddings)
        self.index = index
        self.index_texts = texts
        self.index_meta = meta
        logger.info(
            "FAISS 인덱스 캐시 적중: %s (texts=%d, dim=%d)", cdir, len(texts), dim,
        )
        return True

    def _save_cache(self, embeddings: np.ndarray, texts: list[str], meta: list[dict]) -> None:
        cdir = self._cache_dir()
        try:
            os.makedirs(cdir, exist_ok=True)
            np.save(os.path.join(cdir, "embeddings.npy"), embeddings)
            with open(os.path.join(cdir, "texts.json"), "w", encoding="utf-8") as f:
                json.dump(texts, f, ensure_ascii=False)
            with open(os.path.join(cdir, "meta.json"), "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False)
            logger.info("FAISS 인덱스 캐시 저장: %s", cdir)
        except Exception as exc:
            logger.warning("FAISS 캐시 저장 실패(%s) — 다음 부팅에서 재계산됨", exc)

    def build_index(self):
        """
        Section 4.2: FAISS 인덱스 구성.
        각 테이블과 컬럼을 텍스트로 변환하여 임베딩 후 인덱스에 추가한다.
        코사인 유사도를 위해 L2 정규화 후 Inner Product 인덱스를 사용한다.

        디스크 캐시가 유효하면 OpenAI 임베딩 API를 호출하지 않고 즉시 복원한다.
        """
        t_start = time.time()
        if self._try_load_cache():
            logger.info("schema_linker 인덱스 복원 완료 (%.2fs)", time.time() - t_start)
            return

        texts = []
        meta = []

        for table_name, table_info in self.schema_metadata.items():
            # 한글 설명 매핑 (있으면 검색 품질 대폭 향상 — HRDB 핵심 개선)
            col_desc_map = self.column_descriptions.get(table_name, {}) if self.column_descriptions else {}
            table_desc = col_desc_map.get("_desc", "")

            # 테이블 수준 텍스트 — 한글 설명 포함
            col_names = [c["name"] for c in table_info["columns"]]
            table_text = f"Table: {table_name}. Columns: {', '.join(col_names)}."
            if table_desc:
                table_text = f"Table: {table_name} ({table_desc}). Columns: {', '.join(col_names)}."
            if table_info["foreign_keys"]:
                fk_strs = [
                    f"{fk['from_column']} -> {fk['to_table']}.{fk['to_column']}"
                    for fk in table_info["foreign_keys"]
                ]
                table_text += f" Foreign keys: {', '.join(fk_strs)}."
            texts.append(table_text)
            meta.append({"type": "table", "table": table_name})

            # 컬럼 수준 텍스트 — 한글 설명 + 예시값 모두 포함
            for col in table_info["columns"]:
                col_text = f"Table: {table_name}, Column: {col['name']}, Type: {col['type']}."
                kor_desc = col_desc_map.get(col["name"], "")
                if kor_desc:
                    col_text += f" Meaning: {kor_desc}."
                if col["sample_values"]:
                    col_text += f" Examples: {', '.join(col['sample_values'])}."
                texts.append(col_text)
                meta.append({"type": "column", "table": table_name, "column": col["name"]})

        if not texts:
            # 빈 DB인 경우
            self.index = faiss.IndexFlatIP(1)
            self.index_texts = []
            self.index_meta = []
            return

        embeddings = self._get_embedding(texts)
        # L2 정규화 → Inner Product = 코사인 유사도  # Eq. (1)
        faiss.normalize_L2(embeddings)

        dim = embeddings.shape[1]
        self.index = faiss.IndexFlatIP(dim)
        self.index.add(embeddings)
        self.index_texts = texts
        self.index_meta = meta
        # 정규화된 임베딩을 디스크 캐시에 저장 — 재시작 시 OpenAI API 재호출 회피
        self._save_cache(embeddings, texts, meta)
        logger.info(
            "schema_linker 인덱스 신규 빌드 완료 (%.2fs, texts=%d)",
            time.time() - t_start, len(texts),
        )

    def _retrieve_candidates(self, query: str) -> dict:
        """코사인 유사도로 상위 K개 테이블과 컬럼 후보를 추출한다."""
        query_emb = self._get_embedding([query])
        faiss.normalize_L2(query_emb)

        # 전체에서 충분한 수의 후보를 검색
        k = min(self.top_k_tables + self.top_k_columns, self.index.ntotal)
        if k == 0:
            return {"tables": [], "columns": []}

        scores, indices = self.index.search(query_emb, k)

        candidate_tables = []
        candidate_columns = []
        seen_tables = set()

        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:
                continue
            entry = self.index_meta[idx]
            if entry["type"] == "table" and len(candidate_tables) < self.top_k_tables:
                if entry["table"] not in seen_tables:
                    candidate_tables.append({
                        "table": entry["table"],
                        "score": float(score),
                        "text": self.index_texts[idx],
                    })
                    seen_tables.add(entry["table"])
            elif entry["type"] == "column" and len(candidate_columns) < self.top_k_columns:
                candidate_columns.append({
                    "table": entry["table"],
                    "column": entry["column"],
                    "score": float(score),
                    "text": self.index_texts[idx],
                })

        return {"tables": candidate_tables, "columns": candidate_columns}

    def link(self, query: str) -> dict:
        """
        Section 4.2: 관련 스키마를 반환한다.

        Args:
            query: 자연어 질의

        Returns:
            dict with keys:
                - tables: 선택된 테이블 이름 리스트
                - columns: {table: [columns]} 형태
                - foreign_keys: 관련 외래키 리스트
                - schema_text: LLM 프롬프트용 스키마 텍스트
        """
        candidates = self._retrieve_candidates(query)

        # 후보 정보를 LLM에게 전달하여 최종 선택
        candidate_info = self._format_candidates(candidates)

        # Section 4.2: GPT-4o로 최종 관련 테이블/컬럼 선택
        prompt = f"""You are a database schema expert. Given a natural language query and candidate schema elements, select the minimal set of tables and columns needed to answer the query.

## Natural Language Query
{query}

## Candidate Schema Elements
{candidate_info}

## Instructions
1. Select only the tables and columns that are necessary to answer the query.
2. Include foreign key relationships needed for JOINs.
3. Return your answer in the following JSON format:

```json
{{
  "tables": ["table1", "table2"],
  "columns": {{
    "table1": ["col1", "col2"],
    "table2": ["col3"]
  }},
  "foreign_keys": [
    {{"from": "table1.col1", "to": "table2.col3"}}
  ]
}}
```

Return ONLY the JSON, no other text."""

        response = chat_completion(
            self.client,
            model=self.llm_model,
            temperature=self.config["llm"]["temperature"],
            max_completion_tokens=self.config["llm"]["max_tokens"],
            messages=[{"role": "user", "content": prompt}],
        )

        result_text = response.choices[0].message.content.strip()
        # JSON 블록 추출
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0].strip()
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0].strip()

        selected = json.loads(result_text)

        # 스키마 텍스트 생성 (SQL Generator에서 사용)
        schema_text = self._build_schema_text(selected)
        selected["schema_text"] = schema_text

        return selected

    def _format_candidates(self, candidates: dict) -> str:
        """후보 테이블/컬럼을 LLM에게 전달할 텍스트로 포맷한다.
        column_descriptions가 있으면 한글 설명을 각 컬럼에 덧붙여 혼동을 줄인다 (예: 직급 vs 직책).
        """
        lines = []
        lines.append("### Candidate Tables")
        for t in candidates["tables"]:
            table_name = t["table"]
            cols = self.schema_metadata[table_name]["columns"]
            col_desc_map = self.column_descriptions.get(table_name, {}) if self.column_descriptions else {}
            tbl_desc = col_desc_map.get("_desc", "")

            def _col_str(c):
                desc = col_desc_map.get(c['name'], "")
                base = f"{c['name']} ({c['type']})"
                return f"{base} — {desc}" if desc else base

            col_strs = [_col_str(c) for c in cols]
            fks = self.schema_metadata[table_name]["foreign_keys"]
            fk_strs = [
                f"{fk['from_column']} REFERENCES {fk['to_table']}({fk['to_column']})"
                for fk in fks
            ]
            tbl_hdr = f"Table: {table_name} (relevance: {t['score']:.3f})"
            if tbl_desc:
                tbl_hdr += f" — {tbl_desc}"
            lines.append(f"\n{tbl_hdr}")
            lines.append(f"  Columns: {', '.join(col_strs)}")
            if fk_strs:
                lines.append(f"  Foreign Keys: {', '.join(fk_strs)}")

        lines.append("\n### Top Candidate Columns")
        for c in candidates["columns"]:
            lines.append(f"  {c['table']}.{c['column']} (relevance: {c['score']:.3f})")

        return "\n".join(lines)

    def _build_schema_text(self, selected: dict) -> str:
        """선택된 스키마를 CREATE TABLE DDL 형태로 변환한다.

        column_descriptions.json이 존재하면 테이블/컬럼 한글 설명을 주석으로 주입한다
        (HRDB처럼 Oracle-style 물리명에 의미를 제공하는 경우 EX 개선에 기여).
        """
        lines = []

        # 시연 점검에서 확인된 실패: gpt-4o-mini가 X_CD(코드)와 Y_NM(명칭) 페어를
        # = 비교로 직접 JOIN해 0행을 반환. 페어 컬럼을 미리 식별해 "JOIN 값 도메인 주의"
        # 안내를 schema_text 상단에 추가한다 (sql_generator의 가이드 3번을 보강).
        code_name_pairs = self._detect_code_name_pairs(selected)

        for table_name in selected.get("tables", []):
            if table_name not in self.schema_metadata:
                continue
            table_info = self.schema_metadata[table_name]
            selected_cols = selected.get("columns", {}).get(table_name, None)

            # 한글 설명 매핑 (없으면 빈 딕셔너리)
            col_desc_map = self.column_descriptions.get(table_name, {}) if self.column_descriptions else {}
            table_desc = col_desc_map.get("_desc", "")

            col_defs = []
            for col in table_info["columns"]:
                if selected_cols is None or col["name"] in selected_cols:
                    sample = col.get("sample_values", [])
                    parts = []
                    kor_desc = col_desc_map.get(col["name"], "")
                    if kor_desc:
                        parts.append(kor_desc)
                    if sample:
                        parts.append(f"e.g.: {', '.join(sample)}")
                    # X_CD/Y_NM 페어이면 "code-style"/"name-style" 라벨로 표시해
                    # JOIN 시 값 도메인 매칭 실수를 줄인다.
                    if col["name"].endswith("_CD"):
                        parts.append("[code-style; join code-to-code only]")
                    elif col["name"].endswith("_NM"):
                        parts.append("[name-style; for display, not for JOIN to _CD]")
                    comment = f"  -- {' | '.join(parts)}" if parts else ""
                    col_defs.append(f"  {col['name']} {col['type']}{comment}")

            fk_defs = []
            for fk in table_info["foreign_keys"]:
                fk_defs.append(
                    f"  FOREIGN KEY ({fk['from_column']}) REFERENCES {fk['to_table']}({fk['to_column']})"
                )

            tbl_comment = f"  -- {table_desc}" if table_desc else ""
            create_stmt = f"CREATE TABLE {table_name} ({tbl_comment}\n"
            create_stmt += ",\n".join(col_defs + fk_defs)
            create_stmt += "\n);"
            lines.append(create_stmt)

        body = "\n\n".join(lines)

        # 페어 컬럼이 발견되면 상단 안내 추가
        if code_name_pairs:
            pair_lines = "\n".join(
                f"-- {tbl}.{cd}  ↔  {tbl}.{nm}   (join via {cd}, display via {nm})"
                for tbl, cd, nm in code_name_pairs
            )
            body = (
                "-- JOIN safety hints — paired (code, name) columns detected.\n"
                "-- Prefer JOIN on the *_CD column; SELECT the *_NM column for display.\n"
                f"{pair_lines}\n\n"
                + body
            )

        return body

    def _detect_code_name_pairs(self, selected: dict) -> list[tuple[str, str, str]]:
        """선택된 테이블 내에서 X_CD ↔ X_NM 페어 컬럼을 찾는다.

        예: THRM151의 (JIKGUB_CD, JIKGUB_NM) — 시연 점검에서 confused join이 발생.
        반환: [(table, cd_col, nm_col), ...]
        """
        pairs = []
        for table_name in selected.get("tables", []):
            if table_name not in self.schema_metadata:
                continue
            cols = {c["name"] for c in self.schema_metadata[table_name]["columns"]}
            for col in cols:
                if col.endswith("_CD"):
                    nm_candidate = col[:-3] + "_NM"
                    if nm_candidate in cols:
                        pairs.append((table_name, col, nm_candidate))
        return pairs
