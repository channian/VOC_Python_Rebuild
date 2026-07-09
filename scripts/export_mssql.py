"""
scripts/export_mssql.py — 從 A 棧（公司舊 MSSQL VOC 資料庫）匯出搬遷需要的表成 JSON。

★ 這是三段式搬遷「來源」的第一種實作：只負責把 A 表原封不動 SELECT * dump 成
  export/<表名>.json（key = 原始 DB 欄位名），不做任何轉換。轉換交給 migration/ 的
  normalize 模組（沙盒可測）。因此本腳本**只有在能連到 MSSQL 的環境（公司）才跑得動**。

用法（在公司、能連 MSSQL 的機器上）：
    # 連線字串沿用 A 棧的 VOC_DB_URL（.env），或用 --db 指定
    python scripts/export_mssql.py --out export --plants K7,K8
    # 不給 --plants 則全廠匯出（資料量可能很大，建議先小範圍）

產出：export/VOC_SPEC.json、export/VOC_SCADA_WEB.json … 等，複製到能連 PG 的機器後，
用 scripts/migrate_a_to_b.py 載入 B 棧（或公司同時連得到兩邊時直接原地載入）。
"""

import argparse
import json
import os
import sys
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text  # noqa: E402


# 要匯出的表 → 廠區過濾欄位（None=全表匯出，不受 --plants 影響的全域設定檔）。
# 依「現行功能測試需要的欄位都搬」定案（reading_history 對應的 VOC_SCADA_HIST 先不搬）。
_EXPORT_TABLES = {
    # 設定類（全域，全表匯出）
    "VOC_source": None,
    "VOC_item": None,
    "VOC_plant": None,
    "VOC_dept": None,
    "VOC_Mail_Type": None,
    "sys_aclrole": None,
    "sys_aclrolerights": None,
    # 廠區相關（有 --plants 時依欄位過濾）
    "VOC_SPEC": "plantno",
    "VOC_SCADA_WEB": "plantno",
    "VOC_Curve": "plantno",
    "VOC_closectl": "plantid",       # 註：VOC_closectl 用 plantid（數字），見下方 plantid 轉換
    "VOC_closectl_list": "plantno",
}


def _json_default(o):
    """JSON 無法直接序列化 Decimal/datetime，統一轉字串（normalize 端會再解析回來）。"""
    if isinstance(o, Decimal):
        return str(o)
    if hasattr(o, "isoformat"):
        return o.isoformat()
    return str(o)


def _plantno_to_plantid(conn, plant_nos):
    """VOC_closectl 用 plantid 過濾，需先把 --plants 的 plantno 轉成 plantid。"""
    rows = conn.execute(
        text("SELECT plantid, plantno FROM VOC_plant WHERE plantno IN :ps").bindparams(
            __import__("sqlalchemy").bindparam("ps", expanding=True)
        ),
        {"ps": list(plant_nos)},
    ).all()
    return [r[0] for r in rows]


def export_table(conn, table: str, filter_col, plant_nos, out_dir: str) -> int:
    """匯出單一表成 export/<table>.json，回傳筆數。"""
    if filter_col and plant_nos:
        if filter_col == "plantid":
            ids = _plantno_to_plantid(conn, plant_nos)
            if not ids:
                rows = []
            else:
                stmt = text(f"SELECT * FROM {table} WHERE plantid IN :ps").bindparams(
                    __import__("sqlalchemy").bindparam("ps", expanding=True)
                )
                rows = conn.execute(stmt, {"ps": ids}).mappings().all()
        else:
            stmt = text(f"SELECT * FROM {table} WHERE {filter_col} IN :ps").bindparams(
                __import__("sqlalchemy").bindparam("ps", expanding=True)
            )
            rows = conn.execute(stmt, {"ps": list(plant_nos)}).mappings().all()
    else:
        rows = conn.execute(text(f"SELECT * FROM {table}")).mappings().all()

    data = [dict(r) for r in rows]
    path = os.path.join(out_dir, f"{table}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, default=_json_default, indent=2)
    return len(data)


def main() -> None:
    parser = argparse.ArgumentParser(description="匯出 A 棧 MSSQL 表成 JSON，供 B 棧搬遷載入")
    parser.add_argument("--db", default=os.environ.get("VOC_DB_URL"),
                        help="A 棧 MSSQL 連線字串（預設讀環境變數 VOC_DB_URL）")
    parser.add_argument("--out", default="export", help="輸出資料夾（預設 export/）")
    parser.add_argument("--plants", default="",
                        help="只匯出這些廠區（逗號分隔 plantno，例 K7,K8）；留空=全廠")
    args = parser.parse_args()

    if not args.db:
        parser.error("未提供資料庫連線字串（--db 或環境變數 VOC_DB_URL）")

    plant_nos = [p.strip() for p in args.plants.split(",") if p.strip()]
    os.makedirs(args.out, exist_ok=True)

    engine = create_engine(args.db)
    total = 0
    with engine.connect() as conn:
        for table, filter_col in _EXPORT_TABLES.items():
            try:
                n = export_table(conn, table, filter_col, plant_nos, args.out)
                scope = f"（過濾廠區 {plant_nos}）" if (filter_col and plant_nos) else "（全表）"
                print(f"  匯出 {table}: {n} 筆 {scope}")
                total += n
            except Exception as exc:  # noqa: BLE001 — 單表失敗不中斷其餘表
                print(f"  ⚠ 匯出 {table} 失敗：{exc}")
    print(f"完成，共 {total} 筆，輸出至 {args.out}/")


if __name__ == "__main__":
    main()
