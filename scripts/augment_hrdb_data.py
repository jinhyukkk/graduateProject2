"""HRDB 데이터 증강 스크립트.

기존 hrdb.sqlite의 데이터(20명, 1개월 급여)를 *보존* 하면서
실험에 적합한 규모로 확장한다.

증강 후 규모:
  - THRM100 (직원 마스터):    20 → 200 (재직 175, 휴직 10, 퇴직 15)
  - THRM151 (인사발령 이력):  20 → 약 600 (직원당 평균 3 record, 승진/전배 이력)
  - TORG101 (조직):           13 → 25 (서브팀 추가)
  - TCPN303 (급여 명세):      20 → 200 × 16개월 = 3200 (재직자만, 2025-01~2026-04)
  - TCPN203 (급여 이체):      20 → 200 × 16개월 = 3200
  - TTIM413 (시간외 통계):    20 → 200 × 16개월 = 3200
  - TTIM511 (휴가):           20 → 200 × 2년(2025/2026) = 400

기존 20명은 SABUN S00001~S00020 그대로 유지 (dev seed 30 질문 호환).
새 180명은 SABUN S00021~S00200.

실행:
  PYTHONPATH=. python scripts/augment_hrdb_data.py
"""
from __future__ import annotations

import random
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "raw" / "hrdb" / "hrdb.sqlite"
BACKUP_PATH = ROOT / "data" / "raw" / "hrdb" / "hrdb_pre_augment.sqlite"

ENTER_CD = "C001"
SEED = 42
random.seed(SEED)

# 기존 직원은 S00001~S00020 (보존)
EXISTING_SABUNS = [f"S{i:05d}" for i in range(1, 21)]

# ---------------------------------------------------------------- 마스터 데이터 증강
# 기존 13개 + 새로 12개 추가 (서브팀)
NEW_ORGS = [
    ("D0140", "법무팀",        "Legal Team",            "W2002", "20210101"),
    ("D0150", "기획전략팀",    "Strategic Planning",    "W2002", "20210101"),
    ("D0240", "플랫폼개발팀",  "Platform Dev Team",     "W2002", "20220101"),
    ("D0250", "AI연구팀",      "AI Research Team",      "W2002", "20230101"),
    ("D0260", "보안팀",        "Security Team",         "W2002", "20220101"),
    ("D0330", "마케팅팀",      "Marketing Team",        "W2002", "20210101"),
    ("D0340", "영업관리팀",    "Sales Operations",      "W2002", "20210101"),
    ("D0420", "데이터분석팀",  "Data Analytics Team",   "W2002", "20220101"),
    ("D0500", "고객지원본부",  "Customer Support HQ",   "W2001", "20210101"),
    ("D0510", "CS운영팀",      "CS Operations Team",    "W2002", "20210101"),
    ("D0520", "CS교육팀",      "CS Training Team",      "W2002", "20220101"),
    ("D0600", "전략기획실",    "Strategy Planning Office","W2001", "20230101"),
]

ALL_ORG_CDS = [
    "D0100","D0110","D0120","D0130","D0140","D0150",
    "D0200","D0210","D0220","D0230","D0240","D0250","D0260",
    "D0300","D0310","D0320","D0330","D0340",
    "D0400","D0410","D0420",
    "D0500","D0510","D0520",
    "D0600",
]

JIKGUB = [("J01","사원"),("J02","주임"),("J03","대리"),("J04","과장"),
          ("J05","차장"),("J06","부장"),("J07","이사")]
JIKCHAK = [("T01","팀원"),("T02","파트장"),("T03","팀장"),("T04","본부장"),("T05","이사")]
STATUS = {"S10":"재직","S20":"휴직","S30":"퇴직"}

# 한국 성씨 + 이름 풀
SURNAMES = ["김","이","박","최","정","강","조","윤","장","임","한","오","서","신","권","황","안","송","류","전","홍","유","고","문","손","양","배","백","허","남","심","노","하","곽","성","차","주","우","구","원"]
FIRST_NAMES_M = ["민준","서준","도윤","예준","시우","주원","하준","지호","건우","우진","선우","연우","민재","현우","유준","정우","승호","태양","진우","성호","동현","태민","재현","수호","은우","지환","경민","영재","세준","찬호"]
FIRST_NAMES_F = ["서윤","지유","서연","하윤","민서","수아","지우","서현","하은","지민","채원","유나","예린","수빈","지원","채은","수연","미래","지은","아영","은서","수현","유진","미연","혜진","주희","나영","승희","경아","소영"]

# 기본급 범위 (직급별)
JIKGUB_BASE_SAL_RANGE = {
    "J01": (2500000, 3200000),
    "J02": (3000000, 3700000),
    "J03": (3500000, 4400000),
    "J04": (4200000, 5300000),
    "J05": (5000000, 6300000),
    "J06": (6000000, 7500000),
    "J07": (7800000, 9500000),
}

YEAR_MONTHS = []  # 2025-01 ~ 2026-04
for y in [2025, 2026]:
    for m in range(1, 13):
        if y == 2026 and m > 4:
            break
        YEAR_MONTHS.append(f"{y}{m:02d}")

# ---------------------------------------------------------------- helpers
def gen_employee(seq: int) -> dict:
    """seq는 21~200. 새 직원 합성."""
    sex = random.choice(["M","F"])
    first = random.choice(FIRST_NAMES_M if sex == "M" else FIRST_NAMES_F)
    surname = random.choice(SURNAMES)
    name = surname + first
    birth_year = random.randint(1968, 2002)
    birth_month = random.randint(1, 12)
    birth_day = random.randint(1, 28)
    bir = f"{birth_year}{birth_month:02d}{birth_day:02d}"
    # 입사: 출생 후 22~50년 사이, 그러나 2010~2025 범위
    earliest_emp_year = max(2010, birth_year + 22)
    emp_year = random.randint(earliest_emp_year, 2025)
    emp_month = random.randint(1, 12)
    emp_day = random.randint(1, 28)
    emp_ymd = f"{emp_year}{emp_month:02d}{emp_day:02d}"
    org_cd = random.choice(ALL_ORG_CDS)
    # 재직기간 대비 직급 부여
    tenure_yrs = 2026 - emp_year
    if tenure_yrs >= 12:
        jikgub = random.choices(["J05","J06","J07"], weights=[3,3,1])[0]
    elif tenure_yrs >= 7:
        jikgub = random.choices(["J04","J05"], weights=[3,2])[0]
    elif tenure_yrs >= 4:
        jikgub = random.choices(["J03","J04"], weights=[3,2])[0]
    elif tenure_yrs >= 2:
        jikgub = random.choices(["J02","J03"], weights=[2,1])[0]
    else:
        jikgub = "J01"
    # 직책: 직급 따라
    if jikgub == "J07":
        jikchak = "T05"
    elif jikgub == "J06":
        jikchak = random.choice(["T03","T04"])
    elif jikgub == "J05":
        jikchak = random.choice(["T02","T03"])
    else:
        jikchak = random.choice(["T01","T02"])
    # 재직상태: 87% 재직, 5% 휴직, 8% 퇴직
    r = random.random()
    if r < 0.87:
        status = "S10"
        ret_ymd = None
    elif r < 0.92:
        status = "S20"
        ret_ymd = None
    else:
        status = "S30"
        # 퇴직일은 입사 후 1년 이상, 2026년 이전
        ret_year = random.randint(emp_year + 1, 2025)
        ret_month = random.randint(1, 12)
        ret_day = random.randint(1, 28)
        ret_ymd = f"{ret_year}{ret_month:02d}{ret_day:02d}"
    # 기본급
    base_low, base_high = JIKGUB_BASE_SAL_RANGE[jikgub]
    base_sal = random.randint(base_low, base_high) // 100000 * 100000
    return {
        "sabun": f"S{seq:05d}",
        "name": name, "sex": sex, "bir": bir,
        "emp_ymd": emp_ymd, "ret_ymd": ret_ymd,
        "org_cd": org_cd, "jikgub": jikgub, "jikchak": jikchak,
        "status": status, "base_sal": base_sal,
    }


def jikgub_nm(cd: str) -> str:
    return dict(JIKGUB).get(cd, "")


def jikchak_nm(cd: str) -> str:
    return dict(JIKCHAK).get(cd, "")


def status_nm(cd: str) -> str:
    return STATUS.get(cd, "재직")


# ---------------------------------------------------------------- main
def main():
    if not DB_PATH.exists():
        raise FileNotFoundError(DB_PATH)

    # 백업
    if not BACKUP_PATH.exists():
        import shutil
        shutil.copy2(DB_PATH, BACKUP_PATH)
        print(f"backup → {BACKUP_PATH.name}")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 1) 새 조직 추가
    print("== 조직 12개 추가 ==")
    for cd, nm, eng, otype, sd in NEW_ORGS:
        cur.execute("""
            INSERT OR IGNORE INTO TORG101 (ENTER_CD, ORG_CD, SDATE, ORG_NM, ORG_ENG_NM, ORG_TYPE, VISUAL_YN)
            VALUES (?, ?, ?, ?, ?, ?, 'Y')
        """, (ENTER_CD, cd, sd, nm, eng, otype))
    conn.commit()

    # 기존 직원 데이터 로드 (BASE_SAL 추출용)
    cur.execute("SELECT SABUN FROM THRM100")
    existing_sabuns_in_db = {r[0] for r in cur.fetchall()}

    # 2) 180명 추가 직원 합성
    print(f"== 180명 신규 직원 합성 ==")
    new_emps = []
    seq = 21
    while len(new_emps) < 180:
        e = gen_employee(seq)
        if e["sabun"] not in existing_sabuns_in_db:
            new_emps.append(e)
            seq += 1
        else:
            seq += 1

    # 3) THRM100 INSERT
    for e in new_emps:
        cur.execute("""
            INSERT INTO THRM100 (ENTER_CD, SABUN, SEX_TYPE, NAME, BIR_YMD, EMP_YMD, RET_YMD)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (ENTER_CD, e["sabun"], e["sex"], e["name"],
              e["bir"], e["emp_ymd"], e["ret_ymd"]))

    # 4) THRM151: 신규 직원 현재 발령 + 일부 과거 이력
    print(f"== THRM151 인사발령 이력 (현재 + 과거) ==")
    for e in new_emps:
        # 현재 발령 (EDATE NULL = 현재)
        cur.execute("""
            INSERT INTO THRM151 (ENTER_CD, SABUN, SDATE, EDATE,
                                 ORG_CD, STATUS_CD, STATUS_NM,
                                 JIKGUB_CD, JIKGUB_NM, JIKCHAK_CD, JIKCHAK_NM)
            VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?)
        """, (ENTER_CD, e["sabun"], e["emp_ymd"],
              e["org_cd"], e["status"], status_nm(e["status"]),
              e["jikgub"], jikgub_nm(e["jikgub"]),
              e["jikchak"], jikchak_nm(e["jikchak"])))
        # 과거 이력 (랜덤 0~3건의 승진/전배)
        n_past = random.randint(0, 3)
        if n_past > 0:
            past_jikgub_idx = max(0, [j[0] for j in JIKGUB].index(e["jikgub"]) - n_past)
            for i in range(n_past):
                past_jikgub = JIKGUB[past_jikgub_idx + i][0]
                # 과거 시작일·종료일
                start_yr = int(e["emp_ymd"][:4]) + i*2
                end_yr = start_yr + 2
                if end_yr > 2026: end_yr = 2026
                past_org = random.choice(ALL_ORG_CDS)
                cur.execute("""
                    INSERT INTO THRM151 (ENTER_CD, SABUN, SDATE, EDATE,
                                         ORG_CD, STATUS_CD, STATUS_NM,
                                         JIKGUB_CD, JIKGUB_NM, JIKCHAK_CD, JIKCHAK_NM)
                    VALUES (?, ?, ?, ?, ?, 'S10', '재직', ?, ?, 'T01', '팀원')
                """, (ENTER_CD, e["sabun"], f"{start_yr}0101", f"{end_yr}1231",
                      past_org, past_jikgub, jikgub_nm(past_jikgub)))

    # 5) TCPN303 (월별 급여 명세) — 16개월
    print(f"== TCPN303 급여명세 ({len(YEAR_MONTHS)} 개월) ==")
    # 기존 직원 정보를 읽어서 모든 직원에게 다년 급여 부여
    cur.execute("""
        SELECT t.SABUN, t.NAME, t.EMP_YMD, t.RET_YMD,
               h.ORG_CD, h.JIKGUB_CD, h.JIKGUB_NM, h.STATUS_CD
        FROM THRM100 t
        LEFT JOIN THRM151 h ON t.SABUN = h.SABUN AND h.EDATE IS NULL
    """)
    all_emp_data = cur.fetchall()
    # 기존 BASE_SAL은 보존, 신규는 직급 기반
    base_sal_map = {}
    for sabun, name, emp_ymd, ret_ymd, org_cd, jikgub, jikgub_n, status in all_emp_data:
        if sabun in EXISTING_SABUNS:
            cur.execute("SELECT TOT_EARNING_MON, NOTAX_TOT_MON FROM TCPN303 WHERE SABUN=? LIMIT 1", (sabun,))
            r = cur.fetchone()
            if r:
                base_sal_map[sabun] = r[0] - r[1]  # base = total - notax
            else:
                base_sal_map[sabun] = 5000000
        else:
            jg = jikgub or "J03"
            low, high = JIKGUB_BASE_SAL_RANGE.get(jg, (3500000, 4500000))
            base_sal_map[sabun] = random.randint(low, high) // 100000 * 100000

    # 16개월 급여 INSERT (기존 P202603 한 건은 기존 직원만 존재 → 신규 직원의 P202603도 추가)
    for ym in YEAR_MONTHS:
        pay_action_cd = f"P{ym}"
        for sabun, name, emp_ymd, ret_ymd, org_cd, jikgub, jikgub_n, status in all_emp_data:
            # 입사 후, 퇴직 전 월만 급여 발생
            ym_int = int(ym)
            emp_int = int(emp_ymd[:6]) if emp_ymd else 200001
            if ym_int < emp_int:
                continue
            if ret_ymd:
                ret_int = int(ret_ymd[:6])
                if ym_int > ret_int:
                    continue
            # 휴직 중이면 절반 급여(연구 단순화)
            if status == "S20":
                multiplier = 0.5
            else:
                multiplier = 1.0
            base = int(base_sal_map.get(sabun, 4000000) * multiplier)
            food, car = 200000, 100000
            notax = food + car
            taxable = base
            ei = int(base * 0.009)
            np_ = int(base * 0.045)
            hi = int(base * 0.0354)
            hi2 = int(hi * 0.1282)
            itax = int(taxable * 0.033)
            rtax = int(itax * 0.1)
            tot_ded = ei + np_ + hi + hi2 + itax + rtax
            payment = base + notax - tot_ded

            # 기존 P202603은 이미 들어가 있을 수 있음 → INSERT OR IGNORE 패턴 대신 unique check
            cur.execute("SELECT 1 FROM TCPN303 WHERE PAY_ACTION_CD=? AND SABUN=?", (pay_action_cd, sabun))
            if cur.fetchone():
                continue
            cur.execute("""
                INSERT INTO TCPN303
                    (ENTER_CD, PAY_ACTION_CD, SABUN, NAME, EMP_YMD, ORG_CD, JIKGUB_CD,
                     TOT_EARNING_MON, NOTAX_TOT_MON, NOTAX_FOOD_MON, NOTAX_CAR_MON, TAXIBLE_EARN_MON,
                     ITAX_MON, RTAX_MON, EI_EE_MON, NP_EE_MON, HI_EE_MON, HI_EE_MON2,
                     TOT_DED_MON, PAYMENT_MON, WK_CNT)
                VALUES (?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?,
                        ?, ?, 22)
            """, (ENTER_CD, pay_action_cd, sabun, name, emp_ymd, org_cd, jikgub,
                  base + notax, notax, food, car, taxable,
                  itax, rtax, ei, np_, hi, hi2,
                  tot_ded, payment))

    # 6) TCPN203 (급여 이체) — 동일하게 16개월 × 직원
    print(f"== TCPN203 급여이체 ({len(YEAR_MONTHS)} 개월) ==")
    for ym in YEAR_MONTHS:
        pay_action_cd = f"P{ym}"
        for sabun, name, emp_ymd, ret_ymd, org_cd, jikgub, jikgub_n, status in all_emp_data:
            ym_int = int(ym)
            emp_int = int(emp_ymd[:6]) if emp_ymd else 200001
            if ym_int < emp_int: continue
            if ret_ymd and ym_int > int(ret_ymd[:6]): continue
            cur.execute("SELECT 1 FROM TCPN203 WHERE PAY_ACTION_CD=? AND SABUN=?", (pay_action_cd, sabun))
            if cur.fetchone(): continue
            org_nm = ""
            cur.execute("SELECT ORG_NM FROM TORG101 WHERE ORG_CD=? LIMIT 1", (org_cd,))
            r = cur.fetchone()
            if r: org_nm = r[0] or ""
            cur.execute("""
                INSERT INTO TCPN203 (ENTER_CD, PAY_ACTION_CD, SABUN, NAME, EMP_YMD,
                                     STATUS_CD, STATUS_NM,
                                     ORG_CD, ORG_NM, JIKGUB_CD, JIKGUB_NM,
                                     PAY_PEOPLE_STATUS)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'C00001')
            """, (ENTER_CD, pay_action_cd, sabun, name, emp_ymd,
                  status, status_nm(status),
                  org_cd, org_nm, jikgub, jikgub_n))

    # 7) TTIM413 (시간외 통계) — 16개월 × 직원
    print(f"== TTIM413 시간외통계 ({len(YEAR_MONTHS)} 개월) ==")
    for ym in YEAR_MONTHS:
        for sabun, name, emp_ymd, ret_ymd, org_cd, jikgub, jikgub_n, status in all_emp_data:
            ym_int = int(ym)
            emp_int = int(emp_ymd[:6]) if emp_ymd else 200001
            if ym_int < emp_int: continue
            if ret_ymd and ym_int > int(ret_ymd[:6]): continue
            if status == "S20":  # 휴직자는 시간외 0
                continue
            # 직급별 차등: 상위직급 시간외 더 많음
            ot_base = {"J01":3, "J02":4, "J03":5, "J04":6, "J05":8, "J06":10, "J07":12}.get(jikgub or "J03", 5)
            overtime = round(ot_base + random.uniform(-2, 4), 1)
            night = round(random.uniform(0, 4), 1)
            actual = round(22 * 8.0 + overtime + night, 1)
            cur.execute("SELECT 1 FROM TTIM413 WHERE YM=? AND SABUN=?", (ym, sabun))
            if cur.fetchone(): continue
            cur.execute("""
                INSERT INTO TTIM413 (ENTER_CD, APPLY_YY, YM, SABUN,
                                     MONTH_PLAN_WORK_TIME, MONTH_ACTUAL_WORK_TIME,
                                     REWARD_OVER_TIME, REWARD_NIGHT_TIME)
                VALUES (?, ?, ?, ?, 176.0, ?, ?, ?)
            """, (ENTER_CD, f"{ym[:4]}0301", ym, sabun, actual, overtime, night))

    # 8) TTIM511 (휴가) — 2025, 2026 × 직원
    print(f"== TTIM511 휴가 ({2} 년 × 직원) ==")
    for yy in ["2025", "2026"]:
        for sabun, name, emp_ymd, ret_ymd, org_cd, jikgub, jikgub_n, status in all_emp_data:
            emp_year = int(emp_ymd[:4]) if emp_ymd else 2010
            if int(yy) < emp_year: continue
            if ret_ymd and int(yy) > int(ret_ymd[:4]): continue
            tenure = int(yy) - emp_year
            annual = min(15 + max(0, tenure - 3), 25)
            used = min(int(annual * random.uniform(0.2, 0.9)), annual)
            rest = annual - used
            cur.execute("SELECT 1 FROM TTIM511 WHERE YY=? AND SABUN=?", (yy, sabun))
            if cur.fetchone(): continue
            cur.execute("""
                INSERT INTO TTIM511 (ENTER_CD, YY, SABUN, GNT_CD, USE_S_YMD, USE_E_YMD,
                                     CRE_CNT, USE_CNT, USED_CNT, REST_CNT, CLOSE_YN)
                VALUES (?, ?, ?, 'AL001', ?, ?, ?, ?, ?, ?, 'N')
            """, (ENTER_CD, yy, sabun, f"{yy}0101", f"{yy}1231",
                  annual, annual, used, rest))

    conn.commit()

    # 검증
    print()
    print("=== 증강 후 통계 ===")
    for table in ["TORG101","THRM100","THRM151","TCPN303","TCPN203","TTIM413","TTIM511"]:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        n = cur.fetchone()[0]
        print(f"  {table}: {n} rows")

    cur.execute("SELECT STATUS_NM, COUNT(DISTINCT SABUN) FROM THRM151 WHERE EDATE IS NULL GROUP BY STATUS_NM")
    print(f"  재직 상태별 직원 수: {cur.fetchall()}")

    cur.execute("SELECT COUNT(DISTINCT PAY_ACTION_CD) FROM TCPN303")
    print(f"  급여 월 종류: {cur.fetchone()[0]}")

    conn.close()
    print("\n완료. dev_combined.json 재검증을 권장합니다.")


if __name__ == "__main__":
    main()
