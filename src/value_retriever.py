"""
Value Retriever — DB content 기반 값 후보 검색 (Section 4.2 보강).

자연어 쿼리에서 값 후보(고유명사, 숫자, 따옴표 내 문자열)를 추출하고,
SQLite DB의 실제 컬럼 값과 fuzzy 매칭해 '값 힌트' 블록을 생성한다.

목적: WHERE 절 값 오류(대소문자·공백·약어) 방지.
    예: "flying" → DB 실제값 "Flying" / "East Bohemia" → "east Bohemia"

비용: LLM 호출 없음 (정규식 + SQLite 쿼리). 일반적으로 < 100ms/query.
"""

import re
import sqlite3
import logging
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


# 쿼리에서 값 후보 추출용 정규식
_QUOTED = re.compile(r"""['"]([^'"]+)['"]""")           # 'Foo', "Bar"
_CAPWORDS = re.compile(r"\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){0,3})\b")  # 고유명사 (최대 4단어)
_NUMBER = re.compile(r"\b\d+(?:\.\d+)?\b")
_DATE = re.compile(r"\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b")

# 값 검색 제외어 (일반 대명사/조동사/SQL 키워드 · 자주 오검출)
_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "and", "or", "not", "for", "with", "by", "in", "on", "at", "of", "to", "from",
    "what", "which", "who", "when", "where", "why", "how",
    "all", "any", "each", "every", "such", "same", "this", "that",
    "do", "does", "did", "has", "have", "had", "can", "will", "would", "should",
    "list", "show", "find", "give", "tell", "count", "name",
    "sql", "database", "table",
}


def extract_value_candidates(query: str) -> list[str]:
    """쿼리에서 값 후보를 추출한다. 중복 제거 후 반환."""
    cands = set()

    # 따옴표 안은 우선 신뢰 (사용자가 명시적으로 값을 표기)
    for m in _QUOTED.findall(query):
        if len(m) >= 2:
            cands.add(m.strip())

    # 고유명사 (대문자로 시작하는 단어/구)
    for m in _CAPWORDS.findall(query):
        clean = m.strip()
        if len(clean) >= 2 and clean.lower() not in _STOPWORDS:
            cands.add(clean)

    # 날짜/숫자
    for m in _DATE.findall(query):
        cands.add(m)
    for m in _NUMBER.findall(query):
        # 단독 1~2자리 숫자는 노이즈 (예: "top 5")
        if len(m) >= 3 or (len(m) >= 1 and "." in m):
            cands.add(m)

    return sorted(cands, key=lambda s: -len(s))  # 긴 후보 우선


def _similarity(a: str, b: str) -> float:
    """간단한 문자열 유사도 (대소문자 무시)."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


class ValueRetriever:
    """
    DB content 기반 값 검색기.

    Args:
        db_path: SQLite DB 파일 경로
        max_candidates_per_column: 컬럼당 매칭 반환 상한 (기본 3)
        min_similarity: 유사도 최소 임계 (기본 0.7)
        max_column_distinct: 컬럼당 스캔할 distinct 값 상한 (기본 500)
        timeout: SQLite 쿼리 타임아웃 (초)
    """

    def __init__(
        self,
        db_path: str,
        max_candidates_per_column: int = 3,
        min_similarity: float = 0.7,
        max_column_distinct: int = 500,
        timeout: float = 3.0,
    ):
        self.db_path = db_path
        self.max_candidates_per_column = max_candidates_per_column
        self.min_similarity = min_similarity
        self.max_column_distinct = max_column_distinct
        self.timeout = timeout

    def _get_text_columns(self, selected_schema: dict) -> list[tuple[str, str]]:
        """선택된 스키마에서 (table, column) 쌍 목록을 반환한다 (TEXT 타입만)."""
        pairs = []
        columns_map = selected_schema.get("columns", {}) if isinstance(selected_schema, dict) else {}
        tables = selected_schema.get("tables", []) if isinstance(selected_schema, dict) else []

        conn = None
        try:
            conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True, timeout=self.timeout)
            cursor = conn.cursor()
            for table in tables:
                if table not in columns_map:
                    continue
                try:
                    cursor.execute(f"PRAGMA table_info(`{table}`);")
                    info = {row[1]: (row[2] or "").upper() for row in cursor.fetchall()}
                except Exception:
                    continue
                for col in columns_map[table]:
                    col_type = info.get(col, "TEXT")
                    if any(t in col_type for t in ("TEXT", "VARCHAR", "CHAR", "STRING", "CLOB")):
                        pairs.append((table, col))
        finally:
            if conn:
                conn.close()
        return pairs

    def _search_column(self, conn, table: str, column: str, candidate: str) -> list[str]:
        """해당 컬럼에서 candidate와 유사한 값을 반환 (fuzzy 매칭)."""
        hits = []
        cursor = conn.cursor()

        # 1단계: 대소문자 무시 LIKE (빠름)
        try:
            like_pattern = f"%{candidate}%"
            cursor.execute(
                f"SELECT DISTINCT `{column}` FROM `{table}` "
                f"WHERE `{column}` IS NOT NULL AND LOWER(`{column}`) LIKE LOWER(?) "
                f"LIMIT ?",
                (like_pattern, self.max_candidates_per_column * 3),
            )
            for (val,) in cursor.fetchall():
                if val is None:
                    continue
                sval = str(val)
                sim = _similarity(candidate, sval)
                hits.append((sval, sim))
        except Exception as e:
            logger.debug(f"LIKE search failed {table}.{column}: {e}")

        # 완전 일치 우선, 다음으로 유사도 순
        hits.sort(key=lambda x: (-(x[0].lower() == candidate.lower()), -x[1]))
        seen = set()
        result = []
        for val, sim in hits:
            if val in seen:
                continue
            seen.add(val)
            if sim >= self.min_similarity:
                result.append(val)
            if len(result) >= self.max_candidates_per_column:
                break
        return result

    def retrieve(self, query: str, selected_schema: dict) -> dict:
        """
        쿼리와 선택된 스키마를 받아 값 힌트 딕셔너리를 반환한다.

        Returns:
            {
                "candidates_extracted": [str],          # 쿼리에서 뽑은 후보
                "matches": {                             # 후보별 DB 매칭
                    candidate: [{"table": str, "column": str, "values": [str]}]
                },
                "prompt_block": str,                     # 프롬프트 삽입용 블록
            }
        """
        candidates = extract_value_candidates(query)
        if not candidates:
            return {"candidates_extracted": [], "matches": {}, "prompt_block": ""}

        text_columns = self._get_text_columns(selected_schema)
        if not text_columns:
            return {"candidates_extracted": candidates, "matches": {}, "prompt_block": ""}

        matches = {}
        conn = None
        try:
            conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True, timeout=self.timeout)
            for cand in candidates:
                col_matches = []
                for table, column in text_columns:
                    vals = self._search_column(conn, table, column, cand)
                    if vals:
                        col_matches.append({"table": table, "column": column, "values": vals})
                if col_matches:
                    matches[cand] = col_matches
        finally:
            if conn:
                conn.close()

        return {
            "candidates_extracted": candidates,
            "matches": matches,
            "prompt_block": self._format_prompt_block(matches),
        }

    @staticmethod
    def _format_prompt_block(matches: dict) -> str:
        """매칭 결과를 프롬프트 블록 텍스트로 변환한다."""
        if not matches:
            return ""
        lines = ["## Value Hints (DB 실제 값 — WHERE 절 작성 시 이 철자를 정확히 사용)"]
        for cand, cols in matches.items():
            for cm in cols:
                vals_str = ", ".join(f"'{v}'" for v in cm["values"])
                lines.append(f"- '{cand}' → {cm['table']}.{cm['column']} 실제값: {vals_str}")
        return "\n".join(lines) + "\n"
