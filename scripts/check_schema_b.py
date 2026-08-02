"""
scripts/check_schema_b.py — 比對 models_b.py 的定義 vs B 棧資料庫實際狀況。

用法（專案根目錄）：
    python scripts/check_schema_b.py

★ 為什麼需要這支：`create_all_b()`（SQLAlchemy `metadata.create_all()`）**只建立
  「資料庫裡不存在的表」**，對已經存在的表**不會補新欄位**——PostgreSQL 沒有
  「建表順便改表」的語法，create_all() 設計上只做 CREATE、不做 ALTER。
  所以拉到新版程式、models_b.py 多了欄位時，跑 create_all_b() 看起來成功、
  實際上舊表仍缺欄位，直到開頁面才爆 SQL 錯誤（2026-08-02 實測踩到：
  item 表缺 category / is_dual_bound，首頁一開就錯）。

  本腳本就是用來在「開頁面爆炸」之前先把落差找出來。
  找到缺欄位後用 `python scripts/fix_schema_b.py` 補，詳見 docs/測試操作手冊.md 第 3 節。

什麼時候跑：每次 git pull 之後、以及任何「頁面一開就 SQL 錯誤」的時候。
"""

import os
import sys

from sqlalchemy import inspect

# 讓腳本在 repo 根目錄外執行時仍找得到 database_b / models_b
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database_b import b_engine  # noqa: E402  ★ 變數名是 b_engine，不是 engine_b
from models_b import BaseB  # noqa: E402


def main() -> int:
    insp = inspect(b_engine)
    db_tables = set(insp.get_table_names())

    missing_tables = []
    missing_columns = []

    for table_name, table in sorted(BaseB.metadata.tables.items()):
        if table_name not in db_tables:
            missing_tables.append(table_name)
            continue
        actual = {c["name"] for c in insp.get_columns(table_name)}
        for col in table.columns:
            if col.name not in actual:
                missing_columns.append((table_name, col.name, str(col.type)))

    print(f"連線：{b_engine.url}")
    print(f"模型定義 {len(BaseB.metadata.tables)} 張表，資料庫實際 {len(db_tables)} 張表\n")

    if missing_tables:
        print("【缺少的表】（跑 create_all_b() 就會補上）：")
        for t in missing_tables:
            print(f"  - {t}")
    else:
        print("【表】全部齊全 ✓")

    print()
    if missing_columns:
        print("【缺少的欄位】（create_all_b() 不會補！請跑 scripts/fix_schema_b.py）：")
        for t, c, ty in missing_columns:
            print(f"  - {t}.{c}    型別：{ty}")
    else:
        print("【欄位】全部齊全 ✓")

    # 「資料庫實際」比「模型定義」多一兩張表是正常的（測試過程可能建過相容表），
    # 只有「缺少」才是問題 → 用離開碼讓 CI/腳本也能判斷。
    return 1 if (missing_tables or missing_columns) else 0


if __name__ == "__main__":
    sys.exit(main())
