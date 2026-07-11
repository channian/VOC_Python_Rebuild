"""
services_b/trend_service.py — 歷史曲線頁資料層（Schema B / PostgreSQL）

舊系統從未取得「歷史曲線頁」原始碼（`VOC_Curve.URL` 只是指向外部圖表頁的連結，見
CLAUDE.md「已知待辦」），本頁是全新用 `reading_history` 自建的功能，沒有 A 版可對照移植。

查詢對象：
  - `spec`：決定「哪些廠區有資料可查」「該廠可選哪些指標」（有 SPEC 才代表這廠區/項目
    正式在監測範圍內，沒有 SPEC 的孤兒讀值不出現在下拉選單）。
  - `reading_history`：實際畫圖用的時序資料（append-only，見 models_b.py 該表註解）。
    每一列都快照了「當下生效」的 SPEC 三階門檻，燈號判斷不需要另外反查 spec 表——
    這也是為什麼 oos/ooc 是取「該指標最新一筆 reading_history 的快照」而不是即時查 spec：
    quantity 稽核語意上，趨勢圖右側標的門檻線應該對應「圖上最後一個點當時的門檻」，
    與 spec 表現在的值（可能已被改過）分開。

全部使用 SQLAlchemy 2.0 `select()` 語法，禁止 raw text()（CLAUDE.md 技術棧規範）。
"""

import csv
import io
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from models_b import Item, Plant, ReadingHistory, Spec

# 5 個時間區間 chip（README「畫面 3」時間 RANGE）；'custom' 另外收 from/to。
RANGE_CHOICES = ("24H", "7D", "30D", "90D", "custom")

_RANGE_DELTAS = {
    "24H": timedelta(hours=24),
    "7D": timedelta(days=7),
    "30D": timedelta(days=30),
    "90D": timedelta(days=90),
}


# ── 下拉選單 ──────────────────────────────────────────────────────────────

def list_plants(db: Session) -> List[dict]:
    """有 SPEC 的廠區清單（有 spec 才代表正式在監測範圍內，供廠棟下拉使用）。

    用 EXISTS 子查詢而非 JOIN+DISTINCT：PostgreSQL 的 `SELECT DISTINCT ... ORDER BY`
    要求 ORDER BY 表達式必須出現在 SELECT 清單中，JOIN spec 後 order by Plant.sort
    會違反這條規則（實測發現，非理論推測）；EXISTS 子查詢天生不會有這個限制。
    """
    stmt = (
        select(Plant.plant_no)
        .where(select(Spec.plant_no).where(Spec.plant_no == Plant.plant_no).exists())
        .order_by(Plant.sort, Plant.plant_no)
    )
    rows = db.execute(stmt).scalars().all()
    return [{"plantno": p} for p in rows]


def list_metrics(db: Session, plant_no: str) -> List[dict]:
    """該廠可選指標（spec ⋈ item）。item 為儲存鍵（如 'pH1'，供 /trend/series 的 items 參數使用），
    display_name 為使用者可讀名稱（如 'pH'，供下拉選單顯示），unit 來自 item 主檔。"""
    stmt = (
        select(Item.item, Item.display_name, Item.unit)
        .join(Spec, Spec.item == Item.item)
        .where(Spec.plant_no == plant_no)
        .order_by(Spec.seqno, Item.item)
    )
    rows = db.execute(stmt).all()
    return [
        {"item": r.item, "display_name": r.display_name or r.item, "unit": r.unit or ""}
        for r in rows
    ]


# ── 時間區間解析 ──────────────────────────────────────────────────────────

def _parse_iso(s: str) -> datetime:
    """解析 ISO 日期/時間字串（原生 `<input type="date">` 送出 'YYYY-MM-DD'，
    也接受完整 datetime）。無時區資訊者視為 UTC。"""
    s = s.strip()
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def resolve_range(range_key: str, from_str: Optional[str] = None, to_str: Optional[str] = None) -> tuple[datetime, datetime]:
    """把 range chip 值 + 選填的 from/to 轉成 [start, end) 時間區間（皆為 tz-aware UTC）。

    24H/7D/30D/90D：以「現在」為結束時間往前推。
    custom：需同時提供 from/to；若 to 是純日期字串（無時間部分），視為含當日整天
    （比照 services/history_service._time_bounds 的日界線處理精神）。
    """
    if range_key in _RANGE_DELTAS:
        now = datetime.now(timezone.utc)
        return now - _RANGE_DELTAS[range_key], now

    if range_key == "custom":
        if not from_str or not to_str:
            raise ValueError("自訂區間需同時提供 from 與 to")
        start = _parse_iso(from_str)
        end = _parse_iso(to_str)
        if len(to_str.strip()) <= 10:  # 純日期字串（無時間部分），含當日整天
            end = end + timedelta(days=1)
        if end <= start:
            raise ValueError("結束時間需晚於起始時間")
        return start, end

    raise ValueError(f"不支援的時間區間: {range_key}（可用值: {', '.join(RANGE_CHOICES)}）")


# ── 趨勢資料 ──────────────────────────────────────────────────────────────

def get_series(db: Session, plant_no: str, items: List[str], start: datetime, end: datetime) -> List[dict]:
    """回傳每個指標一組時序資料 + 統計 + 門檻快照。

    points 依 measured_at 升冪；value 為 None（N.D/低於偵測極限等）照傳 null，不補值。
    oos/ooc 取該指標「最新一筆」reading_history 的 spec 快照上界（見檔頭說明）。
    exceed_count：以 oos_high 為門檻，value >= oos_high 才計入（對齊
    services/dashboard_service._calculate_light 的 `rvalue >= OOS → 紅` 規則，取上界比對）。
    """
    unit_map = {
        i.item: (i.unit or "")
        for i in db.execute(select(Item).where(Item.item.in_(items))).scalars().all()
    }

    result = []
    for item in items:
        stmt = (
            select(ReadingHistory)
            .where(
                ReadingHistory.plant_no == plant_no,
                ReadingHistory.item == item,
                ReadingHistory.measured_at >= start,
                ReadingHistory.measured_at < end,
            )
            .order_by(ReadingHistory.measured_at.asc())
        )
        rows = db.execute(stmt).scalars().all()

        points = []
        values = []
        oos_high: Optional[float] = None
        ooc_high: Optional[float] = None
        for r in rows:
            v = float(r.value) if r.value is not None else None
            points.append({"t": r.measured_at.isoformat(), "v": v, "status": r.status})
            if v is not None:
                values.append(v)
            # rows 依時間升冪，最後一筆覆寫掉的就是「最新一筆」的快照
            oos_high = float(r.spec_oos_high) if r.spec_oos_high is not None else None
            ooc_high = float(r.spec_ooc_high) if r.spec_ooc_high is not None else None

        exceed_count = sum(1 for v in values if oos_high is not None and v >= oos_high)

        stats = {
            "latest": values[-1] if values else None,
            "avg": (sum(values) / len(values)) if values else None,
            "max": max(values) if values else None,
            "min": min(values) if values else None,
            "exceed_count": exceed_count,
        }

        result.append({
            "item": item,
            "unit": unit_map.get(item, ""),
            "points": points,
            "oos": oos_high,
            "ooc": ooc_high,
            "stats": stats,
        })
    return result


def build_csv(plant_no: str, series: List[dict]) -> str:
    """UTF-8 BOM CSV（time,plant,metric,value,status），供 /trend/series.csv 匯出。"""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["time", "plant", "metric", "value", "status"])
    for s in series:
        for p in s["points"]:
            writer.writerow([p["t"], plant_no, s["item"], "" if p["v"] is None else p["v"], p["status"]])
    return "﻿" + buf.getvalue()
