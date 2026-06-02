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
            passed_filter  INTEGER DEFAULT 0,
            business_text  TEXT
        )
    """)
    # 기존 DB에 컬럼이 없는 경우 마이그레이션
    cols = [r[1] for r in conn.execute("PRAGMA table_info(companies)").fetchall()]
    if "business_text" not in cols:
        conn.execute("ALTER TABLE companies ADD COLUMN business_text TEXT")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS analysis_results (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            corp_code           TEXT NOT NULL,
            year                INTEGER,
            product_description TEXT,
            product_category    TEXT,
            rd_score            REAL,
            debt_score          REAL,
            rag_score           REAL,
            total_score         REAL,
            rag_detail          TEXT,
            is_valid            INTEGER DEFAULT 1,
            analyzed_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(corp_code, year, product_description)
        )
    """)
    conn.commit()
    conn.close()
    print("DB 초기화 완료: b2b_finder.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn
