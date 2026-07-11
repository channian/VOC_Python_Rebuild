"""
tests/test_dashboard_page.py — B 棧首頁儀表板頁面組裝的純邏輯測試

不碰 DB：手工組 DashboardRow 餵給 `services_b.dashboard_page_service.build_dashboard_context()`，
驗證顯示狀態 key 分類、O/O2 分辨、廠區分組排序、counts/pills、active_anomalies、雨水溝欄位。

另外用 Jinja2 直接 render `templates/b/dashboard.html` 做一次 smoke test（不啟動 FastAPI/DB），
確保樣板本身語法正確、吃得下 build_dashboard_context() 產生的 context 形狀。
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jinja2 import Environment, FileSystemLoader

from schemas.dashboard_schema import DashboardRow
from services_b.dashboard_page_service import (
    _classify_status,
    build_dashboard_context,
)


def _row(**kw) -> DashboardRow:
    """組一個 DashboardRow，帶合理預設值，測試逐項 override。"""
    defaults = dict(
        plantno="K1", item="COD", unit="mg/L",
        law_spec="120", oos="100", ooc="80", alert_spec="70", recv="60",
        scada_oos="100", scada_ooc="80", scada_alert="70",
        cwms_oos="100", cwms_ooc="80",
        rvalue_raw="50", rvalue="50",
        broken=0, source=1, url="", remark="", emptycell="",
        light_status="G", is_anomaly=False, rain_24h="",
    )
    defaults.update(kw)
    return DashboardRow(**defaults)


# ══════════════════════════════════════════════════════════════════════════
# 測資：R / O(數值) / O2(不同步) / Y / G / 斷訊 / 保養中 / 雨水溝
# ══════════════════════════════════════════════════════════════════════════

ROW_R = _row(
    plantno="K1", item="COD", oos="100", ooc="80", alert_spec="70", recv="60",
    rvalue_raw="120", rvalue="120", light_status="R", broken=0,
)

ROW_O_NUMERIC = _row(
    plantno="K1", item="SS", oos="30", ooc="25", alert_spec="20", recv="18",
    scada_oos="30", scada_ooc="25", scada_alert="20", cwms_oos="30", cwms_ooc="25",
    rvalue_raw="27", rvalue="27", light_status="O", broken=0,
)

# 讀值 7.5 沒有落在 OOC(8.8)~OOS(9) 之間，橙燈是 scada_ooc 與 SPEC ooc 不同步觸發
ROW_O2_MISMATCH = _row(
    plantno="K2", item="pH", oos="9", ooc="8.8", alert_spec="8.5", recv="8.5",
    scada_oos="9", scada_ooc="9.5", scada_alert="8.5", cwms_oos="9", cwms_ooc="8.8",
    rvalue_raw="7.5", rvalue="7.5", light_status="O", broken=0,
)

ROW_Y = _row(
    plantno="K2", item="VOC", oos="50", ooc="40", alert_spec="30", recv="25",
    rvalue_raw="35", rvalue="35", light_status="Y", broken=0,
)

ROW_G = _row(
    plantno="K3", item="Cu", oos="3", ooc="2.5", alert_spec="2", recv="1.8",
    rvalue_raw="0.4", rvalue="0.4", light_status="G", broken=0,
)

ROW_BROKEN = _row(
    plantno="K4", item="氨氮", rvalue_raw="斷訊", rvalue="0",
    light_status="-", broken=1, is_anomaly=True,
)

ROW_MAINTENANCE = _row(
    plantno="K4", item="濁度", rvalue_raw="保養中", rvalue="0",
    light_status="-", broken=2, is_anomaly=True,
)

ROW_RAIN = _row(
    plantno="K12", item="雨水溝pH", oos="9", ooc="8.8", alert_spec="8.5", recv="8.5",
    rvalue_raw="7.0", rvalue="7.0", light_status="G", broken=0, rain_24h="12.5",
)

ALL_ROWS = [
    ROW_R, ROW_O_NUMERIC, ROW_O2_MISMATCH, ROW_Y, ROW_G,
    ROW_BROKEN, ROW_MAINTENANCE, ROW_RAIN,
]


# ══════════════════════════════════════════════════════════════════════════
# _classify_status：狀態 key 分類
# ══════════════════════════════════════════════════════════════════════════

def test_classify_status_basic():
    assert _classify_status(ROW_R) == "R"
    assert _classify_status(ROW_Y) == "Y"
    assert _classify_status(ROW_G) == "G"
    assert _classify_status(ROW_BROKEN) == "B"
    assert _classify_status(ROW_MAINTENANCE) == "M"


def test_classify_status_o_vs_o2():
    """核心分辨：O(數值超標) 與 O2(管制值不同步) 必須分開，不能混在同一個 key。"""
    assert _classify_status(ROW_O_NUMERIC) == "O"
    assert _classify_status(ROW_O2_MISMATCH) == "O2"


def test_classify_status_broken_overrides_light_status():
    """broken 欄位優先於 light_status 判斷（B/M 就算 light_status 不是 '-' 也要照 broken 分類）。"""
    weird = _row(plantno="K9", item="COD", broken=1, light_status="G")
    assert _classify_status(weird) == "B"
    weird2 = _row(plantno="K9", item="COD", broken=2, light_status="G")
    assert _classify_status(weird2) == "M"


def test_classify_status_non_numeric_no_broken_falls_back_to_b():
    """broken==0 但讀值是非數字異常字串（'異常'/'建置中'）→ 併入 B（斷訊／保養統計卡）。"""
    weird = _row(plantno="K9", item="COD", broken=0, light_status="-", rvalue_raw="異常")
    assert _classify_status(weird) == "B"


# ══════════════════════════════════════════════════════════════════════════
# build_dashboard_context：廠區分組、排序、counts/pills、統計卡、異常速覽
# ══════════════════════════════════════════════════════════════════════════

def test_plant_grouping_and_sort_order():
    ctx = build_dashboard_context(ALL_ROWS)
    plant_nos = [p["plantno"] for p in ctx["plants"]]

    # K1（R+O，severity 最高＝最嚴重）必須排最前面
    assert plant_nos[0] == "K1"
    # K3（純 G）與 K12（純 G + 雨水溝）severity 最低，理應排在 K1/K2/K4 之後
    assert plant_nos.index("K3") > plant_nos.index("K1")
    assert plant_nos.index("K12") > plant_nos.index("K1")
    # 同級（K3、K12 都是純綠燈）按 plantno 字母排序
    assert plant_nos.index("K12") < plant_nos.index("K3")


def test_plant_counts_and_pills():
    ctx = build_dashboard_context(ALL_ROWS)
    by_no = {p["plantno"]: p for p in ctx["plants"]}

    k1 = by_no["K1"]
    assert k1["counts"] == {"R": 1, "O": 1, "O2": 0, "Y": 0, "B": 0, "M": 0}
    assert {p["txt"] for p in k1["pills"]} == {"R1", "O1"}
    assert {p["key"] for p in k1["pills"]} == {"R", "O"}
    assert k1["severity"] == 0  # R 最嚴重

    k2 = by_no["K2"]
    assert k2["counts"] == {"R": 0, "O": 0, "O2": 1, "Y": 1, "B": 0, "M": 0}
    assert {p["txt"] for p in k2["pills"]} == {"O≠1", "Y1"}

    k4 = by_no["K4"]
    assert k4["counts"] == {"R": 0, "O": 0, "O2": 0, "Y": 0, "B": 1, "M": 1}
    assert {p["txt"] for p in k4["pills"]} == {"斷1", "保1"}

    k3 = by_no["K3"]
    assert k3["counts"] == {"R": 0, "O": 0, "O2": 0, "Y": 0, "B": 0, "M": 0}
    assert k3["pills"] == []  # 純正常廠區不需要 pill


def test_global_stats_merge_o_and_o2_and_bm():
    ctx = build_dashboard_context(ALL_ROWS)
    stats = ctx["stats"]
    assert stats["R"] == 1
    assert stats["O"] == 2  # O(數值) + O2(不同步) 合併計入摘要卡
    assert stats["Y"] == 1
    assert stats["BM"] == 2  # 斷訊 + 保養中 合併計入摘要卡


def test_active_anomalies_lists_r_o_o2_only():
    ctx = build_dashboard_context(ALL_ROWS)
    anomalies = ctx["active_anomalies"]
    keys = {(a["plantno"], a["item"]): a["key"] for a in anomalies}

    assert keys[("K1", "COD")] == "R"
    assert keys[("K1", "SS")] == "O"
    assert keys[("K2", "pH")] == "O2"
    # Y／G／斷訊／保養中都不該進異常速覽
    assert ("K2", "VOC") not in keys
    assert ("K3", "Cu") not in keys
    assert ("K4", "氨氮") not in keys
    assert ("K4", "濁度") not in keys
    assert len(anomalies) == 3


def test_active_anomalies_sorted_by_severity():
    ctx = build_dashboard_context(ALL_ROWS)
    keys_in_order = [a["key"] for a in ctx["active_anomalies"]]
    assert keys_in_order == sorted(keys_in_order, key=lambda k: ["R", "O", "O2", "Y"].index(k))


# ══════════════════════════════════════════════════════════════════════════
# 雨水溝欄位
# ══════════════════════════════════════════════════════════════════════════

def test_rain_row_flagged_and_rain_24h_from_row():
    ctx = build_dashboard_context(ALL_ROWS)
    k12 = next(p for p in ctx["plants"] if p["plantno"] == "K12")
    rain_row = k12["rows"][0]
    assert rain_row["is_rain"] is True
    assert rain_row["rain_24h"] == "12.5"


def test_rain_row_falls_back_to_rain_map_when_row_field_empty():
    row = _row(plantno="K12", item="雨水溝COD", rvalue_raw="10", rvalue="10", light_status="G", rain_24h="")
    ctx = build_dashboard_context([row], rain_map={("K12", "雨水溝COD"): "8.1"})
    rain_row = ctx["plants"][0]["rows"][0]
    assert rain_row["is_rain"] is True
    assert rain_row["rain_24h"] == "8.1"


def test_non_rain_row_never_gets_rain_24h():
    row = _row(plantno="K12", item="pH", rvalue_raw="7.0", rvalue="7.0", light_status="G", rain_24h="99.9")
    ctx = build_dashboard_context([row])
    plain_row = ctx["plants"][0]["rows"][0]
    assert plain_row["is_rain"] is False
    assert plain_row["rain_24h"] == ""


# ══════════════════════════════════════════════════════════════════════════
# Jinja2 渲染 smoke test（不啟動 FastAPI/DB，templates/ 目錄直接載入）
# ══════════════════════════════════════════════════════════════════════════

def test_dashboard_template_renders_without_error():
    templates_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")
    env = Environment(loader=FileSystemLoader(templates_dir))
    template = env.get_template("b/dashboard.html")
    ctx = build_dashboard_context(ALL_ROWS, rain_map={})
    html = template.render(ctx=ctx)
    assert "VOC" in html
    assert "K1" in html


def test_dashboard_template_renders_with_empty_data():
    """空資料（無廠區）也不能炸——資料庫尚無資料或全部被篩掉時的邊界情形。"""
    templates_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")
    env = Environment(loader=FileSystemLoader(templates_dir))
    template = env.get_template("b/dashboard.html")
    ctx = build_dashboard_context([], rain_map={})
    html = template.render(ctx=ctx)
    assert "<!DOCTYPE html>" in html
    assert "voc-modal" in html
