"""
scripts/sync_comments.py — 把 models_b.py 的中文 comment 套用到「已存在」的 PG 資料庫。

為什麼需要這支：create_all_b()（= metadata.create_all，checkfirst=True）只會對「不存在的表」
建立時一併寫 COMMENT，對「已存在的表」會整個跳過、不會更新註解。所以：
  - 如果你的 PG 已經先建過表，之後才在 models_b.py 加/改中文註解，用 create_all_b() 是補不進去的。
  - 這支腳本用 SQLAlchemy 的 SetTableComment/SetColumnComment DDL，逐表逐欄 COMMENT ON，
    只改「註解」這個 metadata、完全不動任何資料列，可安心對有資料的 DB 重複執行（冪等）。

用法：
    python scripts/sync_comments.py
（連線讀 database_b 的 VOC_B_DB_URL；DBA 給的正式庫也適用，只要連得到。）
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import inspect  # noqa: E402
from sqlalchemy.schema import SetColumnComment, SetTableComment  # noqa: E402

from database_b import b_engine  # noqa: E402
from models_b import BaseB  # noqa: E402


def main() -> None:
    existing = set(inspect(b_engine).get_table_names())
    tables = 0
    cols = 0
    skipped_tables = []

    with b_engine.begin() as conn:
        for table in BaseB.metadata.sorted_tables:
            if table.name not in existing:
                # 這張表在 DB 還不存在（可能你只建了部分表）；註解無處可下，記下來提醒。
                skipped_tables.append(table.name)
                continue
            if table.comment:
                conn.execute(SetTableComment(table))
                tables += 1
            for col in table.columns:
                if col.comment:
                    conn.execute(SetColumnComment(col))
                    cols += 1

    print(f"已套用註解：{tables} 張表、{cols} 個欄位")
    if skipped_tables:
        print(f"⚠ 下列表在 DB 尚未建立，已略過（可先跑 create_all_b 建表）：{skipped_tables}")


if __name__ == "__main__":
    main()
