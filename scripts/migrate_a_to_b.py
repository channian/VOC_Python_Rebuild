"""
scripts/migrate_a_to_b.py — 把 export/*.json 轉換載入 B 棧（Schema B / PostgreSQL）。

三段式搬遷的「轉換+寫入」入口（沙盒即可測；不需連 MSSQL）。搭配：
  1. 先在公司用 scripts/export_mssql.py 匯出 A 表成 export/*.json（唯一需要 MSSQL 的步驟）。
  2. 把 export/ 複製到能連 PG 的機器（或公司同時連得到兩邊時原地即可）。
  3. 填好 scripts/migration_personnel.json（人員改綁自己部門同事，見 .example）。
  4. 跑本腳本載入 B。

用法：
    python scripts/migrate_a_to_b.py --export export --personnel scripts/migration_personnel.json --plants K7,K8
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database_b import BSessionLocal, create_all_b  # noqa: E402
from migration.context import load_personnel  # noqa: E402
from migration.runner import run_migration  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="A→B 搬遷：載入 export/*.json 到 Schema B")
    parser.add_argument("--export", default="export", help="export JSON 資料夾（預設 export/）")
    parser.add_argument("--personnel", default="scripts/migration_personnel.json",
                        help="人員綁定 JSON（見 scripts/migration_personnel.json.example）")
    parser.add_argument("--plants", default="",
                        help="只載入這些廠區（逗號分隔 plantno，例 K7,K8）；留空=全部")
    args = parser.parse_args()

    if not os.path.exists(args.personnel):
        parser.error(
            f"找不到人員綁定檔 {args.personnel}；請複製 scripts/migration_personnel.json.example "
            "為 scripts/migration_personnel.json 並填入你部門同事"
        )

    plant_filter = {p.strip() for p in args.plants.split(",") if p.strip()} or None
    personnel = load_personnel(args.personnel)

    create_all_b()  # 冪等：確保 Schema B 表已存在
    db = BSessionLocal()
    try:
        report = run_migration(db, args.export, personnel, plant_filter=plant_filter)
    finally:
        db.close()

    print("搬遷完成，各表寫入筆數：")
    for table, n in report.counts.items():
        print(f"  {table}: {n}")
    print(f"合計 {report.total()} 筆")


if __name__ == "__main__":
    main()
