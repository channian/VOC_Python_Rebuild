"""
tests_integration/conftest.py — Schema B 真 PG 整合測試共用 fixture

與 tests/（純邏輯測試，不依賴 DB）是完全獨立的目錄，兩者互不影響：
  - tests/            純邏輯測試，任何環境都能跑（不需要 DB）
  - tests_integration/ 真的連 PostgreSQL（VOC_B_DB_URL），驗證 models_b.py 的 schema 正確性

沒有 PostgreSQL 可連線時（例如 CI 環境、或本機尚未跑過 scripts/dev_pg.sh），
整個目錄用 pytest.skip(allow_module_level=True) 跳過，不會讓其他測試環境炸掉。
"""

import os
import sys

# 讓本目錄的測試可以 import 專案根目錄下的 database_b / models_b / scripts.seed_test_data
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.exc import OperationalError  # noqa: E402

from database_b import b_engine, BSessionLocal, create_all_b  # noqa: E402
from scripts.seed_test_data import seed as seed_test_data  # noqa: E402


def _pg_available() -> bool:
    """嘗試連線 VOC_B_DB_URL 指定的 PostgreSQL，連不上就回傳 False。"""
    try:
        with b_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except OperationalError:
        return False
    except Exception:
        # 例如 psycopg2 未安裝、連線字串格式錯誤等，一律視為「環境不可用」，跳過即可，
        # 不應該讓 collection 階段直接丟未預期例外中斷整個 pytest。
        return False


# 注意：連線檢查刻意「不」放在 conftest.py 的模組層級（import 當下）。
# pytest 載入 conftest.py 屬於「initial conftest」階段，這個階段丟出 Skipped 例外
# 會被視為致命錯誤（exit code 1 + 完整 traceback），而不是乾淨的 skip 報告。
# 正確做法：把檢查延後到 session-scoped autouse fixture 內部，屬於測試執行階段，
# pytest 才能把 skip 顯示為正常的 "skipped"（見 test session 的 s 標記），exit code 維持乾淨。
@pytest.fixture(scope="session", autouse=True)
def _b_schema():
    """整個測試 session 只需要 create_all 一次（create_all 本身是冪等的，重跑不會出錯）。

    沒有 PG 可連線時，整個目錄的測試都會透過這個 autouse fixture 統一被跳過。
    """
    if not _pg_available():
        pytest.skip(
            "找不到可連線的 PostgreSQL（VOC_B_DB_URL={}）。\n"
            "本機測試請先執行：bash scripts/dev_pg.sh\n"
            "或參考 docs/本機PG測試環境.md 用 Docker 起一個。\n"
            "沒有 PG 屬正常情況（例如 CI 環境），tests_integration/ 全目錄會被跳過。".format(
                os.environ.get("VOC_B_DB_URL", "(預設值，見 config.py)")
            )
        )
    create_all_b()
    yield


@pytest.fixture()
def b_db():
    """
    每個測試案例：
      1. 先跑一次 seed_test_data.seed()（先清後灌，把 TEST1/TEST001/TEST999/kepware_sim 重設回基準值，
         seed() 內部自行 commit）。
      2. 開一個新 session 給測試案例使用。
      3. 測試結束後 rollback + close ——只清掉測試案例自己在 session 內「尚未 commit」的異動；
         若測試案例呼叫了 commit()，下一個測試案例開始前的 seed() 會重新覆蓋回基準值，
         因此測試案例之間不會互相污染。
    """
    seed_test_data()
    session = BSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
