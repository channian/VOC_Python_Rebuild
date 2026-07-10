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
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database_b import BSessionLocal, create_all_b  # noqa: E402
from migration.context import load_personnel  # noqa: E402
from migration.runner import run_migration  # noqa: E402

# 搬遷會讀的 A 表檔（與 scripts/export_mssql.py 匯出的檔名一致）
_EXPECTED_FILES = [
    "VOC_source", "VOC_item", "VOC_plant", "VOC_dept", "VOC_Mail_Type", "VOC_Curve",
    "sys_aclrole", "sys_aclrolerights", "VOC_SPEC", "VOC_SCADA_WEB",
    "VOC_closectl", "VOC_closectl_list",
]


def _preflight_export(export_dir: str) -> int:
    """檢查 export 資料夾：逐檔印出筆數或 MISSING/EMPTY，回傳總筆數。

    這是為了避免「找不到檔 → 默默 0 筆 → 看似成功卻沒資料」的困惑（使用者實測踩過）。
    """
    print(f"檢查 export 資料夾：{os.path.abspath(export_dir)}")
    if not os.path.isdir(export_dir):
        print(f"  ✗ 資料夾不存在！請確認 --export 路徑，或先在公司跑 scripts/export_mssql.py")
        return 0
    total = 0
    for name in _EXPECTED_FILES:
        path = os.path.join(export_dir, f"{name}.json")
        if not os.path.exists(path):
            print(f"  ✗ {name}.json  MISSING")
            continue
        try:
            with open(path, encoding="utf-8") as f:
                rows = json.load(f)
            n = len(rows) if isinstance(rows, list) else 0
        except Exception as exc:  # noqa: BLE001
            print(f"  ✗ {name}.json  讀取失敗：{exc}")
            continue
        total += n
        print(f"  {'✓' if n else '·'} {name}.json  {n} 筆" + ("" if n else "  (EMPTY)"))
    return total


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

    # 先檢查 export 檔案，避免「找不到檔 → 默默 0 筆」的困惑
    total_rows = _preflight_export(args.export)
    if total_rows == 0:
        parser.error(
            f"export 資料夾 {os.path.abspath(args.export)} 沒有任何可載入的 A 表資料。\n"
            "請確認：(1) 你在對的目錄執行、(2) --export 指到正確資料夾、"
            "(3) 已在能連 MSSQL 的機器跑過 scripts/export_mssql.py 產生 export/*.json。"
        )
    print()

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
