import sqlite3

DB_PATH = "b2b_finder.db"

def init_db():
    """DB 및 테이블 초기화 (최초 1회만 실행)"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS companies (
            corp_code      TEXT PRIMARY KEY,
            corp_name      TEXT,
            industry       TEXT,
            market_type    TEXT,
            revenue        INTEGER,
            rd_expense     INTEGER,
            debt_ratio     REAL,
            employees      INTEGER,
            year           INTEGER,
            passed_filter  INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()
    print("DB 초기화 완료: b2b_finder.db")

def get_connection():
    return sqlite3.connect(DB_PATH)
