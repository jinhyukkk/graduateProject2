"""
Schema Linker (Section 4.2)
임베딩 기반 스키마 검색 + LLM 기반 최종 선택.
"""

import os
import json
import sqlite3
import numpy as np
import faiss
from openai import OpenAI

from src.openai_retry import chat_completion, embeddings as embeddings_call


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
        self.index = None
        self.index_texts = []
        self.index_meta = []
        self.build_index()

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

    def build_index(self):
        """
        Section 4.2: FAISS 인덱스 구성.
        각 테이블과 컬럼을 텍스트로 변환하여 임베딩 후 인덱스에 추가한다.
        코사인 유사도를 위해 L2 정규화 후 Inner Product 인덱스를 사용한다.
        """
        texts = []
        meta = []

        for table_name, table_info in self.schema_metadata.items():
            # 테이블 수준 텍스트
            col_names = [c["name"] for c in table_info["columns"]]
            table_text = f"Table: {table_name}. Columns: {', '.join(col_names)}."
            if table_info["foreign_keys"]:
                fk_strs = [
                    f"{fk['from_column']} -> {fk['to_table']}.{fk['to_column']}"
                    for fk in table_info["foreign_keys"]
                ]
                table_text += f" Foreign keys: {', '.join(fk_strs)}."
            texts.append(table_text)
            meta.append({"type": "table", "table": table_name})

            # 컬럼 수준 텍스트
            for col in table_info["columns"]:
                col_text = f"Table: {table_name}, Column: {col['name']}, Type: {col['type']}."
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
        """후보 테이블/컬럼을 LLM에게 전달할 텍스트로 포맷한다."""
        lines = []
        lines.append("### Candidate Tables")
        for t in candidates["tables"]:
            table_name = t["table"]
            cols = self.schema_metadata[table_name]["columns"]
            col_strs = [f"{c['name']} ({c['type']})" for c in cols]
            fks = self.schema_metadata[table_name]["foreign_keys"]
            fk_strs = [
                f"{fk['from_column']} REFERENCES {fk['to_table']}({fk['to_column']})"
                for fk in fks
            ]
            lines.append(f"\nTable: {table_name} (relevance: {t['score']:.3f})")
            lines.append(f"  Columns: {', '.join(col_strs)}")
            if fk_strs:
                lines.append(f"  Foreign Keys: {', '.join(fk_strs)}")

        lines.append("\n### Top Candidate Columns")
        for c in candidates["columns"]:
            lines.append(f"  {c['table']}.{c['column']} (relevance: {c['score']:.3f})")

        return "\n".join(lines)

    def _build_schema_text(self, selected: dict) -> str:
        """선택된 스키마를 CREATE TABLE DDL 형태로 변환한다."""
        lines = []
        for table_name in selected.get("tables", []):
            if table_name not in self.schema_metadata:
                continue
            table_info = self.schema_metadata[table_name]
            selected_cols = selected.get("columns", {}).get(table_name, None)

            col_defs = []
            for col in table_info["columns"]:
                if selected_cols is None or col["name"] in selected_cols:
                    sample = col.get("sample_values", [])
                    comment = f"  -- e.g.: {', '.join(sample)}" if sample else ""
                    col_defs.append(f"  {col['name']} {col['type']}{comment}")

            fk_defs = []
            for fk in table_info["foreign_keys"]:
                fk_defs.append(
                    f"  FOREIGN KEY ({fk['from_column']}) REFERENCES {fk['to_table']}({fk['to_column']})"
                )

            create_stmt = f"CREATE TABLE {table_name} (\n"
            create_stmt += ",\n".join(col_defs + fk_defs)
            create_stmt += "\n);"
            lines.append(create_stmt)

        return "\n\n".join(lines)
