"""
database_b.py — Schema B（Phase A 重構版）資料庫引擎 / Session 工廠

風格比照既有 database.py（MSSQL 版），但完全獨立：
  - 用獨立的 BaseB.metadata（models_b.py），不會與既有 A 棧的 Base 互相污染。
  - 引擎由 config.settings.VOC_B_DB_URL 決定，預設本機 PostgreSQL
    （見 scripts/dev_pg.sh：postgresql+psycopg2://voc:voc@localhost/voc_b）。
  - 正式環境引擎未定案，因此本檔案不得含任何方言特化邏輯（見 models_b.py 開頭的引擎可攜規範）。
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from config import settings
from models_b import BaseB

# ==========================================
# Schema B 資料庫連線實體
# ==========================================
b_engine = create_engine(settings.VOC_B_DB_URL, echo=settings.DEBUG)
BSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=b_engine)


def get_b_db():
    """FastAPI Dependency: 取得 Schema B 資料庫 session。"""
    db = BSessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_all_b() -> None:
    """建立 Schema B 全部資料表（冪等：表已存在則略過，不會清空既有資料）。

    引擎可攜規範第五條：建表一律走 metadata.create_all()，禁止手寫方言 DDL。
    """
    BaseB.metadata.create_all(bind=b_engine)


def drop_all_b() -> None:
    """刪除 Schema B 全部資料表（僅供測試環境清理使用，正式環境不應呼叫）。"""
    BaseB.metadata.drop_all(bind=b_engine)
