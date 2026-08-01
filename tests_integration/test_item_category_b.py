"""
tests_integration/test_item_category_b.py — B 棧「項目類型改讀 item.category」的真 PG 整合測試

對應 docs/標準化與待調整清單.md **D7**。純邏輯部分（各共用函式的 category 參數、A 棧
不傳參數時行為不變、NULL 退回名稱比對）已由 tests/test_item_category.py 覆蓋；
本檔專測**「B 棧到底有沒有把 DB 裡的 category 真的取出來、傳進去」**這條接線：

    item.category（DB）
      → services_b/dashboard_page_service.get_item_categories()      → build_dashboard_context()
      → services_b/control_service._get_item_categories()            → build_rtype_list()
      → services_b/dispatch_service.get_data_b()['category']         → evaluate_row()
      → services_b/dashboard_service.get_dashboard_rows()            → _calculate_light()

種子資料（scripts/seed_test_data.py）的 3 個項目 category 皆為 NULL，正好也順帶驗證
「未回填 category 的既有資料完全不受影響」。測試內再自行把 Cu1 標成空汙／雨水溝來驗修正。
"""

from datetime import datetime, timezone

from sqlalchemy import select, update

from models_b import Item
from services.category_util import CATEGORY_AIR, CATEGORY_RAINGUTTER
from services.dispatch_service import evaluate_row
from services.flow_service import build_rtype_list
from services_b.control_service import _get_item_categories
from services_b.dashboard_page_service import get_dashboard_page_data, get_item_categories
from services_b.dashboard_service import get_dashboard_rows
from services_b.dispatch_service import get_data_b

PLANT = "TEST1"
# Cu1（顯示名 Cu）刻意選「名稱完全不含 VOC 字樣」的項目，用來重現本次要修的故障
AIR_LIKE_ITEM = "Cu1"
AIR_LIKE_DISPLAY = "Cu"


def _set_category(db, item: str, category) -> None:
    db.execute(update(Item).where(Item.item == item).values(category=category))
    db.flush()


# ── 種子資料現況：category 全 NULL（驗證舊資料不受影響）────────────────────────

def test_seed_items_have_null_category_and_map_is_empty(b_db):
    cats = get_item_categories(b_db)
    assert cats == {}, f"種子資料的 category 應全為 NULL，實際取到 {cats}"
    assert _get_item_categories(b_db, ["pH1", AIR_LIKE_ITEM, "VOC1"]) == {}


def test_null_category_keeps_name_based_behaviour(b_db):
    """category 全 NULL 時，rtype/派報前綴與改版前的名稱字串比對結果完全相同。"""
    cats = _get_item_categories(b_db, ["VOC1", AIR_LIKE_ITEM])
    assert build_rtype_list(["VOC1", AIR_LIKE_ITEM], cats) == ["空保養中", "水保養中"]


# ── get_item_categories / _get_item_categories：對照表組法 ────────────────────

def test_get_item_categories_includes_both_item_and_display_name(b_db):
    _set_category(b_db, AIR_LIKE_ITEM, CATEGORY_AIR)
    cats = get_item_categories(b_db)
    # 資料鍵與顯示名兩種寫法都要查得到（DashboardRow.item 存的是顯示名）
    assert cats[AIR_LIKE_ITEM] == CATEGORY_AIR
    assert cats[AIR_LIKE_DISPLAY] == CATEGORY_AIR
    # 其他仍為 NULL 的項目不會出現在 dict 內 → 呼叫端自動退回名稱比對
    assert "pH1" not in cats and "VOC1" not in cats


def test_control_service_category_lookup_scoped_to_requested_items(b_db):
    _set_category(b_db, AIR_LIKE_ITEM, CATEGORY_AIR)
    _set_category(b_db, "pH1", "水質")
    cats = _get_item_categories(b_db, [AIR_LIKE_ITEM])
    assert cats[AIR_LIKE_ITEM] == CATEGORY_AIR
    assert "pH1" not in cats            # 沒被要求的項目不會被撈進來
    assert _get_item_categories(b_db, []) == {}


# ── 簽核 rtype：本次核心修正（找對簽核人）────────────────────────────────────

def test_signer_rtype_uses_category_not_name(b_db):
    """★ Cu1 名稱不含 VOC，標成空汙後，簽核 rpttype 應改為「空保養中」。"""
    before = build_rtype_list([AIR_LIKE_ITEM], _get_item_categories(b_db, [AIR_LIKE_ITEM]))
    assert before == ["水保養中"]        # 未回填 category → 舊行為

    _set_category(b_db, AIR_LIKE_ITEM, CATEGORY_AIR)
    after = build_rtype_list([AIR_LIKE_ITEM], _get_item_categories(b_db, [AIR_LIKE_ITEM]))
    assert after == ["空保養中"]


# ── 派報：get_data_b 帶出 category，evaluate_row 用它決定代碼前綴 ─────────────

def test_get_data_b_carries_category_into_evaluate_row(b_db):
    _set_category(b_db, AIR_LIKE_ITEM, CATEGORY_AIR)
    rows = {r["item"]: r for r in get_data_b(b_db)}
    row = rows[AIR_LIKE_DISPLAY]          # get_data_b 也用 display_name 當 item
    assert row["category"] == CATEGORY_AIR

    # 讀值拉到 OOS 以上（同時也超過允收值，故 Alert 與 OOS 兩個代碼都會出現），
    # 觀察的是**代碼前綴**（空/水）有沒有改由 category 決定。
    row = dict(row, rvalue_raw="9.9", rvalue="9.9")
    now = datetime.now(timezone.utc)
    # 不傳 category（＝A 棧行為）：名稱 'Cu' 不含 VOC → 前綴「水」
    assert evaluate_row(row, None, now).codes == ["水Alert-TEST1", "水OOS-TEST1"]
    # ★ 傳入 DB 取回的 category='空汙' → 前綴改為「空」，派報名單才找得對
    assert evaluate_row(row, None, now, category=row["category"]).codes == [
        "空Alert-TEST1", "空OOS-TEST1",
    ]


# ── 儀表板：雨水溝欄位改讀 category ─────────────────────────────────────────

def test_dashboard_page_raingutter_flag_uses_category(b_db):
    """★ Cu 名稱不含「雨水溝」，標成雨水溝後，儀表板 is_rain 應為 True。"""
    def _is_rain(ctx) -> bool:
        for plant in ctx["plants"]:
            for row in plant["rows"]:
                if row["item"] == AIR_LIKE_DISPLAY:
                    return row["is_rain"]
        raise AssertionError(f"儀表板 context 找不到項目 {AIR_LIKE_DISPLAY}")

    assert _is_rain(get_dashboard_page_data(b_db)) is False    # 未回填 → 舊行為
    _set_category(b_db, AIR_LIKE_ITEM, CATEGORY_RAINGUTTER)
    assert _is_rain(get_dashboard_page_data(b_db)) is True


def test_dashboard_rows_still_computed_when_category_present(b_db):
    """回填 category 不影響燈號計算結果（種子資料皆為正常值 → 全綠）。"""
    before = {(r.plantno, r.item): r.light_status for r in get_dashboard_rows(b_db)}
    _set_category(b_db, AIR_LIKE_ITEM, CATEGORY_AIR)
    after = {(r.plantno, r.item): r.light_status for r in get_dashboard_rows(b_db)}
    assert before == after
    assert set(after.values()) == {"G"}


def test_item_category_column_accepts_all_three_values(b_db):
    """三種合法類型都存得進去、讀得回來（欄位本身的健全性）。"""
    for item, category in (("pH1", "水質"), (AIR_LIKE_ITEM, "空汙"), ("VOC1", "雨水溝")):
        _set_category(b_db, item, category)
    stored = dict(b_db.execute(select(Item.item, Item.category)).all())
    assert stored["pH1"] == "水質"
    assert stored[AIR_LIKE_ITEM] == "空汙"
    assert stored["VOC1"] == "雨水溝"
