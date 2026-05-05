"""
HR-DB SQLite 데이터베이스 생성 스크립트.
Result_11.xlsx(실제 HR 시스템 스키마)에서 테이블 구조를 읽어
hrdb.sqlite를 생성하고 주요 테이블에 합성 데이터를 삽입한다.

사용법:
    python data/raw/hrdb/build_db.py
"""

import re
import sqlite3
from pathlib import Path

import openpyxl

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent
EXCEL_PATH = PROJECT_ROOT / "Result_11.xlsx"
DB_PATH = SCRIPT_DIR / "hrdb.sqlite"
SCHEMA_SQL_PATH = SCRIPT_DIR / "create_schema.sql"


# ------------------------------------------------------------------ #
#  Oracle → SQLite 타입 변환                                           #
# ------------------------------------------------------------------ #

def oracle_to_sqlite(oracle_type: str) -> str:
    if not oracle_type:
        return "TEXT"
    t = oracle_type.strip().upper()
    if t.startswith(("VARCHAR2", "NVARCHAR2", "CHAR", "NCHAR", "CLOB", "NCLOB")):
        return "TEXT"
    m = re.match(r"NUMBER\s*\(\s*\d+\s*,\s*(\d+)\s*\)", t)
    if m:
        return "REAL" if int(m.group(1)) > 0 else "INTEGER"
    if re.match(r"NUMBER", t) or t.startswith(("INT", "SMALLINT")):
        return "INTEGER"
    if t.startswith(("FLOAT", "DOUBLE", "BINARY_FLOAT", "BINARY_DOUBLE", "REAL")):
        return "REAL"
    if t.startswith(("DATE", "TIMESTAMP")):
        return "TEXT"
    if t.startswith(("BLOB", "RAW")):
        return "BLOB"
    return "TEXT"


# ------------------------------------------------------------------ #
#  Excel 스키마 로딩                                                   #
# ------------------------------------------------------------------ #

def load_schema(excel_path: Path) -> dict:
    """Excel 'Result 1' 시트에서 테이블 스키마를 로드한다."""
    wb = openpyxl.load_workbook(str(excel_path))
    ws = wb["Result 1"]

    tables: dict = {}
    for row in ws.iter_rows(min_row=2, values_only=True):
        tbl, tbl_desc, col, col_ord, dtype, nullable, col_desc = row
        if not tbl or not col:
            continue
        if tbl not in tables:
            tables[tbl] = {"desc": tbl_desc or "", "columns": []}
        tables[tbl]["columns"].append({
            "name": col,
            "order": col_ord or 999,
            "oracle_type": dtype or "VARCHAR2(100)",
            "nullable": nullable or "Y",
            "desc": col_desc or "",
        })

    for tbl in tables:
        tables[tbl]["columns"].sort(key=lambda x: x["order"])

    return tables


# ------------------------------------------------------------------ #
#  DDL 생성                                                            #
# ------------------------------------------------------------------ #

def make_create_sql(tbl_name: str, info: dict) -> str:
    col_defs = []
    for col in info["columns"]:
        stype = oracle_to_sqlite(col["oracle_type"])
        notnull = "" if col["nullable"] == "Y" else " NOT NULL"
        col_defs.append(f"    {col['name']} {stype}{notnull}")
    cols_str = ",\n".join(col_defs)
    comment = f"  -- {info['desc']}" if info["desc"] else ""
    return f"CREATE TABLE IF NOT EXISTS {tbl_name} (\n{cols_str}\n);{comment}"


# ------------------------------------------------------------------ #
#  합성 데이터                                                          #
# ------------------------------------------------------------------ #

ENTER_CD = "C001"

# 회사 코드
ORGS = [
    # (ORG_CD, ORG_NM, ORG_ENG_NM, ORG_TYPE, SDATE)
    ("D0100", "경영지원본부",    "Management Support HQ",  "W2001", "20200101"),
    ("D0110", "인사팀",          "HR Team",                 "W2002", "20200101"),
    ("D0120", "총무팀",          "General Affairs Team",    "W2002", "20200101"),
    ("D0130", "재무팀",          "Finance Team",            "W2002", "20200101"),
    ("D0200", "개발본부",        "Development HQ",          "W2001", "20200101"),
    ("D0210", "개발1팀",         "Dev Team 1",              "W2002", "20200101"),
    ("D0220", "개발2팀",         "Dev Team 2",              "W2002", "20200101"),
    ("D0230", "QA팀",            "QA Team",                 "W2002", "20200101"),
    ("D0300", "영업본부",        "Sales HQ",                "W2001", "20200101"),
    ("D0310", "영업1팀",         "Sales Team 1",            "W2002", "20200101"),
    ("D0320", "영업2팀",         "Sales Team 2",            "W2002", "20200101"),
    ("D0400", "연구소",          "R&D Center",              "W2001", "20200101"),
    ("D0410", "연구개발팀",      "R&D Team",                "W2002", "20200101"),
]

# 직급코드 (H20010)
JIKGUB = [
    ("J01", "사원"),
    ("J02", "주임"),
    ("J03", "대리"),
    ("J04", "과장"),
    ("J05", "차장"),
    ("J06", "부장"),
    ("J07", "이사"),
]

# 직책코드 (H20020)
JIKCHAK = [
    ("T01", "팀원"),
    ("T02", "파트장"),
    ("T03", "팀장"),
    ("T04", "본부장"),
    ("T05", "이사"),
]

# 재직상태 (H10010)
STATUS = [
    ("S10", "재직"),
    ("S20", "휴직"),
    ("S30", "퇴직"),
]

# 20명 사원 (SABUN, 성명, 성별, 생년월일, 입사일, 조직코드, 직급, 직책, 재직상태, 퇴직일)
EMPLOYEES = [
    ("S00001", "김철수", "M", "19880515", "20150301", "D0110", "J06", "T03", "S10", None),
    ("S00002", "이영희", "F", "19920710", "20180601", "D0210", "J04", "T01", "S10", None),
    ("S00003", "박민준", "M", "19950220", "20200102", "D0210", "J03", "T01", "S10", None),
    ("S00004", "정수진", "F", "19901130", "20160401", "D0120", "J05", "T02", "S10", None),
    ("S00005", "최동현", "M", "19870812", "20130801", "D0300", "J06", "T04", "S10", None),
    ("S00006", "한지민", "F", "19940308", "20190301", "D0310", "J03", "T01", "S10", None),
    ("S00007", "윤성호", "M", "19961125", "20210701", "D0220", "J02", "T01", "S10", None),
    ("S00008", "임수현", "F", "19930617", "20170901", "D0230", "J04", "T01", "S10", None),
    ("S00009", "장태양", "M", "19891004", "20140201", "D0130", "J05", "T03", "S10", None),
    ("S00010", "오지은", "F", "19970222", "20220301", "D0410", "J02", "T01", "S10", None),
    ("S00011", "백준호", "M", "19850930", "20110601", "D0400", "J07", "T05", "S10", None),
    ("S00012", "송미래", "F", "19991215", "20230801", "D0210", "J01", "T01", "S10", None),
    ("S00013", "류현우", "M", "19920405", "20180401", "D0320", "J04", "T02", "S10", None),
    ("S00014", "신은서", "F", "19960718", "20210101", "D0230", "J02", "T01", "S10", None),
    ("S00015", "강도현", "M", "19880123", "20120901", "D0110", "J05", "T02", "S10", None),
    ("S00016", "조유나", "F", "19940912", "20190601", "D0130", "J04", "T01", "S10", None),
    ("S00017", "서준혁", "M", "19971130", "20220601", "D0310", "J02", "T01", "S10", None),
    ("S00018", "권아영", "F", "19910825", "20150901", "D0410", "J05", "T02", "S10", None),
    ("S00019", "황진우", "M", "19931020", "20170201", "D0220", "J04", "T01", "S10", None),
    ("S00020", "문소희", "F", "20001107", "20240301", "D0210", "J01", "T01", "S10", None),
]

# 급여 기준 (사원번호 → 기본급)
BASE_SAL = {
    "S00001": 6500000, "S00002": 4200000, "S00003": 3800000,
    "S00004": 5500000, "S00005": 7000000, "S00006": 3900000,
    "S00007": 3300000, "S00008": 4100000, "S00009": 5800000,
    "S00010": 3100000, "S00011": 8000000, "S00012": 2900000,
    "S00013": 4300000, "S00014": 3200000, "S00015": 5600000,
    "S00016": 4400000, "S00017": 3100000, "S00018": 5700000,
    "S00019": 4200000, "S00020": 2800000,
}

PAY_ACTION_CD = "P202603"   # 2026년 3월 급여
YM = "202603"


def insert_synthetic_data(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()

    # ── TORG900: 법인 ────────────────────────────────────────────────
    cur.execute(f"""
        INSERT INTO TORG900 (ENTER_CD, ENTER_NM, ENTER_ENG_NM, DOMAIN, USE_YN)
        VALUES ('{ENTER_CD}', '(주)국민테크', 'Kookmin Tech Inc.', 'kookmin.com', 'Y')
    """)

    # ── TORG101: 조직 ────────────────────────────────────────────────
    for org_cd, org_nm, org_eng_nm, org_type, sdate in ORGS:
        cur.execute("""
            INSERT INTO TORG101
                (ENTER_CD, ORG_CD, SDATE, ORG_NM, ORG_ENG_NM, ORG_TYPE, VISUAL_YN)
            VALUES (?, ?, ?, ?, ?, ?, 'Y')
        """, (ENTER_CD, org_cd, sdate, org_nm, org_eng_nm, org_type))

    # ── THRM100: 인사마스터 ───────────────────────────────────────────
    for sabun, name, sex, bir, emp_ymd, org_cd, jikgub, jikchak, status, ret_ymd in EMPLOYEES:
        cur.execute("""
            INSERT INTO THRM100
                (ENTER_CD, SABUN, SEX_TYPE, NAME, BIR_YMD, EMP_YMD, RET_YMD)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (ENTER_CD, sabun, sex, name, bir, emp_ymd, ret_ymd))

    # ── THRM151: 개인조직사항 ─────────────────────────────────────────
    for sabun, name, sex, bir, emp_ymd, org_cd, jikgub, jikchak, status, ret_ymd in EMPLOYEES:
        jikgub_nm = dict(JIKGUB).get(jikgub, "")
        jikchak_nm = dict(JIKCHAK).get(jikchak, "")
        status_nm = dict(STATUS).get(status, "재직")
        cur.execute("""
            INSERT INTO THRM151
                (ENTER_CD, SABUN, SDATE,
                 ORG_CD, STATUS_CD, STATUS_NM,
                 JIKGUB_CD, JIKGUB_NM, JIKCHAK_CD, JIKCHAK_NM)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (ENTER_CD, sabun, emp_ymd,
              org_cd, status, status_nm,
              jikgub, jikgub_nm, jikchak, jikchak_nm))

    # ── TCPN203: 급여대상자관리 ───────────────────────────────────────
    for sabun, name, sex, bir, emp_ymd, org_cd, jikgub, jikchak, status, ret_ymd in EMPLOYEES:
        jikgub_nm = dict(JIKGUB).get(jikgub, "")
        org_nm = next((o[1] for o in ORGS if o[0] == org_cd), "")
        cur.execute("""
            INSERT INTO TCPN203
                (ENTER_CD, PAY_ACTION_CD, SABUN,
                 NAME, EMP_YMD, STATUS_CD, STATUS_NM,
                 ORG_CD, ORG_NM, JIKGUB_CD, JIKGUB_NM,
                 PAY_PEOPLE_STATUS)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'C00001')
        """, (ENTER_CD, PAY_ACTION_CD, sabun,
              name, emp_ymd, status, dict(STATUS).get(status, "재직"),
              org_cd, org_nm, jikgub, jikgub_nm))

    # ── TCPN303: 월별급여실적 ─────────────────────────────────────────
    for sabun, name, sex, bir, emp_ymd, org_cd, jikgub, jikchak, status, ret_ymd in EMPLOYEES:
        base = BASE_SAL.get(sabun, 3000000)
        food = 200000
        car = 100000
        notax = food + car
        taxable = base
        income_tax = int(taxable * 0.033)
        resident_tax = int(income_tax * 0.1)
        ei = int(base * 0.009)
        np_ = int(base * 0.045)
        hi = int(base * 0.0354)
        hi2 = int(hi * 0.1282)
        total_ded = income_tax + resident_tax + ei + np_ + hi + hi2
        payment = base + notax - total_ded
        org_nm = next((o[1] for o in ORGS if o[0] == org_cd), "")
        cur.execute("""
            INSERT INTO TCPN303
                (ENTER_CD, PAY_ACTION_CD, SABUN, NAME, EMP_YMD,
                 ORG_CD,
                 JIKGUB_CD,
                 TOT_EARNING_MON, NOTAX_TOT_MON, NOTAX_FOOD_MON, NOTAX_CAR_MON,
                 TAXIBLE_EARN_MON,
                 ITAX_MON, RTAX_MON,
                 EI_EE_MON, NP_EE_MON, HI_EE_MON, HI_EE_MON2,
                 TOT_DED_MON, PAYMENT_MON,
                 WK_CNT)
            VALUES (?, ?, ?, ?, ?,
                    ?,
                    ?,
                    ?, ?, ?, ?,
                    ?,
                    ?, ?,
                    ?, ?, ?, ?,
                    ?, ?,
                    22)
        """, (
            ENTER_CD, PAY_ACTION_CD, sabun, name, emp_ymd,
            org_cd,
            jikgub,
            base + notax, notax, food, car,
            taxable,
            income_tax, resident_tax,
            ei, np_, hi, hi2,
            total_ded, payment,
        ))

    # ── TTIM511: 연차내역관리 ─────────────────────────────────────────
    import math
    for sabun, name, sex, bir, emp_ymd, org_cd, jikgub, jikchak, status, ret_ymd in EMPLOYEES:
        # 근속연수에 따라 연차 부여
        start_year = int(emp_ymd[:4])
        tenure = 2026 - start_year
        annual_days = min(15 + max(0, tenure - 3), 25)
        used = min(int(annual_days * 0.4), annual_days)
        rest = annual_days - used
        cur.execute("""
            INSERT INTO TTIM511
                (ENTER_CD, YY, SABUN, GNT_CD, USE_S_YMD, USE_E_YMD,
                 CRE_CNT, USE_CNT, USED_CNT, REST_CNT, CLOSE_YN)
            VALUES (?, '2026', ?, 'AL001', '20260101', '20261231',
                    ?, ?, ?, ?, 'N')
        """, (ENTER_CD, sabun, annual_days, annual_days, used, rest))

    # ── TTIM413: 월개인별근무시간집계 ─────────────────────────────────
    for sabun, name, sex, bir, emp_ymd, org_cd, jikgub, jikchak, status, ret_ymd in EMPLOYEES:
        actual = round(22 * 8.0, 2)       # 22일 * 8시간
        overtime = round(5.5, 2)
        night = round(1.0, 2)
        cur.execute("""
            INSERT INTO TTIM413
                (ENTER_CD, APPLY_YY, YM, SABUN,
                 MONTH_PLAN_WORK_TIME, MONTH_ACTUAL_WORK_TIME,
                 REWARD_OVER_TIME, REWARD_NIGHT_TIME)
            VALUES (?, '20260301', ?, ?,
                    ?, ?,
                    ?, ?)
        """, (ENTER_CD, YM, sabun, actual, actual, overtime, night))

    # ── TBEN002: 건강보험요율 ─────────────────────────────────────────
    cur.execute("""
        INSERT INTO TBEN002
            (ENTER_CD, SDATE, EDATE, HIGH_MON, LOW_MON, SELF_RATE, COMP_RATE, LONGTERMCARE_RATE)
        VALUES (?, '20240101', '20241231', 117594060, NULL, 0.03545, 0.03545, 0.1281)
    """, (ENTER_CD,))
    cur.execute("""
        INSERT INTO TBEN002
            (ENTER_CD, SDATE, EDATE, HIGH_MON, LOW_MON, SELF_RATE, COMP_RATE, LONGTERMCARE_RATE)
        VALUES (?, '20250101', NULL, 121116060, NULL, 0.03545, 0.03545, 0.1282)
    """, (ENTER_CD,))

    # ── TBEN003: 고용보험요율 ─────────────────────────────────────────
    cur.execute("""
        INSERT INTO TBEN003
            (ENTER_CD, SDATE, EDATE,
             UMEMP_SELF_RATE, UNEMP_COMP_RATE,
             EMP_SELF_RATE, EMP_COMP_RATE,
             ABILITY_SELF_RATE, ABILITY_COMP_RATE)
        VALUES (?, '20240101', '20241231',
                0.00900, 0.00900,
                0.00000, 0.00250,
                0.00000, 0.00250)
    """, (ENTER_CD,))
    cur.execute("""
        INSERT INTO TBEN003
            (ENTER_CD, SDATE, EDATE,
             UMEMP_SELF_RATE, UNEMP_COMP_RATE,
             EMP_SELF_RATE, EMP_COMP_RATE,
             ABILITY_SELF_RATE, ABILITY_COMP_RATE)
        VALUES (?, '20250101', NULL,
                0.00900, 0.00900,
                0.00000, 0.00250,
                0.00000, 0.00250)
    """, (ENTER_CD,))

    # ── TBEN004: 국민연금요율 ─────────────────────────────────────────
    cur.execute("""
        INSERT INTO TBEN004
            (ENTER_CD, SDATE, EDATE, HIGH_MON, LOW_MON, SELF_RATE, COMP_RATE)
        VALUES (?, '20240101', '20241231', 6170000, 370000, 0.04500, 0.04500)
    """, (ENTER_CD,))
    cur.execute("""
        INSERT INTO TBEN004
            (ENTER_CD, SDATE, EDATE, HIGH_MON, LOW_MON, SELF_RATE, COMP_RATE)
        VALUES (?, '20250101', NULL, 6370000, 390000, 0.04500, 0.04500)
    """, (ENTER_CD,))

    conn.commit()
    print("  합성 데이터 삽입 완료")


# ------------------------------------------------------------------ #
#  메인 빌드 함수                                                       #
# ------------------------------------------------------------------ #

def build():
    if not EXCEL_PATH.exists():
        raise FileNotFoundError(f"Excel 파일을 찾을 수 없습니다: {EXCEL_PATH}")

    print(f"Excel 로딩: {EXCEL_PATH}")
    tables = load_schema(EXCEL_PATH)
    print(f"  총 {len(tables)}개 테이블 파싱 완료")

    # DDL 생성 및 create_schema.sql 저장
    stmts = [make_create_sql(t, info) for t, info in tables.items()]
    with open(SCHEMA_SQL_PATH, "w", encoding="utf-8") as f:
        f.write("-- Auto-generated from Result_11.xlsx\n\n")
        f.write("\n\n".join(stmts))
    print(f"  스키마 SQL 저장: {SCHEMA_SQL_PATH}")

    # 기존 DB 삭제 후 재생성
    if DB_PATH.exists():
        DB_PATH.unlink()
        print(f"  기존 DB 삭제: {DB_PATH}")

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")

    print("  테이블 생성 중...")
    failed = 0
    for tbl_name, info in tables.items():
        sql = make_create_sql(tbl_name, info)
        try:
            conn.execute(sql)
        except Exception as e:
            print(f"    [WARN] {tbl_name}: {e}")
            failed += 1
    conn.commit()
    print(f"  테이블 생성 완료 ({len(tables) - failed}개 성공, {failed}개 실패)")

    print("  합성 데이터 삽입 중...")
    insert_synthetic_data(conn)

    conn.close()
    print(f"\nHR-DB 생성 완료: {DB_PATH}")

    # 결과 요약
    conn2 = sqlite3.connect(str(DB_PATH))
    cur = conn2.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    all_tables = [r[0] for r in cur.fetchall()]
    key_tables = [
        "TORG900", "TORG101", "THRM100", "THRM151",
        "TCPN203", "TCPN303", "TTIM511", "TTIM413",
        "TBEN002", "TBEN003", "TBEN004",
    ]
    print(f"\n총 테이블 수: {len(all_tables)}")
    print("\n[주요 테이블 행 수]")
    for t in key_tables:
        cur.execute(f'SELECT COUNT(*) FROM "{t}"')
        cnt = cur.fetchone()[0]
        cur.execute(f'PRAGMA table_info("{t}")')
        ncols = len(cur.fetchall())
        print(f"  {t:<20} {ncols:>3}컬럼  {cnt:>3}행")
    conn2.close()


if __name__ == "__main__":
    build()
