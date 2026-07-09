"""
migration/io.py — 檔案來源讀取 + 冪等寫入（sink）。

檔案來源：export/<A表名>.json，內容為 list[dict]，每個 dict 的 key = A 資料表的
「原始 DB 欄位名」（因為匯出腳本用 SELECT *）。normalize 各模組吃的就是這種 dict。

sink：upsert() 用 SQLAlchemy Session.merge 以主鍵合併——存在則更新、不存在則插入，
可攜（不用 PG 專屬 ON CONFLICT）、冪等（重跑不會爆主鍵），符合引擎可攜規範。
"""

import json
import os
from typing import Any, Dict, Iterable, List

from sqlalchemy.orm import Session


def read_table(export_dir: str, table_name: str) -> List[Dict[str, Any]]:
    """讀 export_dir/<table_name>.json（不存在回空 list，讓缺某張表不會中斷整批）。"""
    path = os.path.join(export_dir, f"{table_name}.json")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        rows = json.load(f)
    return rows if isinstance(rows, list) else []


def upsert(db: Session, objs: Iterable[Any]) -> int:
    """以主鍵 merge 一批 B 棧 ORM 物件（每個物件的主鍵屬性須已設好），回傳處理筆數。

    用 Session.merge：SQLAlchemy 會依主鍵查是否已存在，存在則 UPDATE、不存在則 INSERT，
    不依賴任一資料庫方言。呼叫端負責 commit。
    """
    n = 0
    for obj in objs:
        db.merge(obj)
        n += 1
    db.flush()
    return n
