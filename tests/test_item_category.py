"""
test_item_category.py — 項目類型（水質／空汙／雨水溝）改讀 item.category 的純邏輯測試

對應 docs/標準化與待調整清單.md **D7**：原本判斷項目屬於水質／空汙／雨水溝，全靠項目名稱
字串比對（`"VOC" in item`、`"雨水溝" in item`），新廠若有**不叫 VOC 的空汙項目**會被誤判成
水質，連帶找錯簽核人、派報信分錯類、燈號的 VOC 例外沒套用。

本檔驗證三件事（全部不依賴 DB）：
  1. **A 棧保護**：不傳 category 時，每一支改過的函式行為與改版前逐字元相同
     （含「項目名稱叫 VOC1 → 判空汙」這種既有案例）。A 棧（main.py）公司平行測試中，
     行為不可有任何變化。
  2. **B 棧修正生效**：名稱不含 VOC、但 category='空汙' 的項目會被正確判成空汙
     （本次要修的核心故障）；雨水溝同理。
  3. **NULL 退回**：category 為 None／空字串／未知值時退回名稱字串比對，舊資料不會壞掉。

保護模式沿用 C1（`_calculate_light(check_lower_bound=...)`）與 D8（`Item.is_dual_bound`）：
共用純函式一律「加 optional 參數、預設 None＝走舊路徑」，A 棧呼叫端不傳。
"""

from datetime import datetime, timezone

import pytest

from schemas.dashboard_schema import DashboardRow
from services.category_util import (
    CATEGORY_AIR,
    CATEGORY_RAINGUTTER,
    CATEGORY_WATER,
    is_air_item,
    is_raingutter_item,
    is_water_item,
)
from services.dashboard_service import _calculate_light
from services.dispatch_service import evaluate_row, mark_isolated_item
from services.flow_service import build_rtype_list
from services_b.dashboard_page_service import build_dashboard_context

# 名稱不含 "VOC" 字樣的空汙項目——這正是舊字串比對會誤判成水質的案例
AIR_ITEM_NO_VOC_NAME = "非甲烷總烴"
# 名稱不含 "雨水溝" 字樣的雨水溝項目
RAIN_ITEM_NO_NAME = "排水溝A"

T0 = datetime(2026, 8, 1, 10, 0, 0)


# ══════════════════════════════════════════════════════════════════════
# 1. category_util 純函式本身
# ══════════════════════════════════════════════════════════════════════

class TestCategoryUtil:
    def test_a_stack_default_none_uses_name_matching(self):
        """不傳 category → 完全等同舊的 `"VOC" in item` / `"雨水溝" in item`。"""
        assert is_air_item("VOC1") is True
        assert is_air_item("VOC") is True
        assert is_air_item("pH") is False
        assert is_air_item(AIR_ITEM_NO_VOC_NAME) is False   # 舊行為的誤判，刻意保留
        assert is_raingutter_item("雨水溝pH") is True
        assert is_raingutter_item("COD") is False
        assert is_raingutter_item(RAIN_ITEM_NO_NAME) is False  # 舊行為的誤判，刻意保留

    def test_b_stack_category_drives_result(self):
        """category 為合法值 → 以 category 為準，名稱不再有影響力。"""
        assert is_air_item(AIR_ITEM_NO_VOC_NAME, CATEGORY_AIR) is True
        assert is_air_item("pH1", CATEGORY_WATER) is False
        assert is_air_item("VOC1", CATEGORY_WATER) is False   # category 有權推翻名稱
        assert is_raingutter_item(RAIN_ITEM_NO_NAME, CATEGORY_RAINGUTTER) is True
        assert is_raingutter_item("雨水溝pH", CATEGORY_WATER) is False

    def test_raingutter_is_not_air(self):
        """雨水溝屬於「水」側（舊行為：名稱不含 VOC → 水），category 判定結果一致。"""
        assert is_air_item("雨水溝pH", CATEGORY_RAINGUTTER) is False
        assert is_raingutter_item(AIR_ITEM_NO_VOC_NAME, CATEGORY_AIR) is False

    @pytest.mark.parametrize("bad", [None, "", "  ", "空氣汙染", "AIR", "unknown"])
    def test_null_or_unknown_category_falls_back_to_name(self, bad):
        """None／空字串／不在三種合法值內的髒資料 → 一律退回名稱字串比對。"""
        assert is_air_item("VOC1", bad) is True
        assert is_air_item(AIR_ITEM_NO_VOC_NAME, bad) is False
        assert is_raingutter_item("雨水溝1", bad) is True
        assert is_raingutter_item(RAIN_ITEM_NO_NAME, bad) is False


# ══════════════════════════════════════════════════════════════════════
# 2. services/dashboard_service._calculate_light —— VOC 例外
#    （SCADA 管制值比 SPEC 嚴＝更低時，VOC 項目不算管制值不一致，不亮橙燈）
# ══════════════════════════════════════════════════════════════════════

def _scada_stricter_row(item: str) -> dict:
    """SCADA-OOS(8) 比 SPEC-OOS(10) 嚴、讀值正常 → 非 VOC 亮橙(O)，VOC 例外則綠(G)。"""
    return dict(
        item=item, rvalue_raw="1", broken=0,
        oos="10", ooc="9", alert_spec="", recv="",
        scada_oos="8", scada_ooc="", scada_alert="",
        cwms_oos="", cwms_ooc="",
    )


class TestCalculateLightVocException:
    def test_a_stack_unchanged_voc_named_item(self):
        """A 棧（不傳 category）：名稱含 VOC → 套用 VOC 例外 → 綠燈（改版前行為）。"""
        assert _calculate_light(_scada_stricter_row("VOC1"))[0] == "G"

    def test_a_stack_unchanged_non_voc_named_item(self):
        """A 棧（不傳 category）：名稱不含 VOC → 不套例外 → 橙燈（改版前行為）。"""
        assert _calculate_light(_scada_stricter_row("Cu"))[0] == "O"
        # 名稱不含 VOC 的空汙項目，在 A 棧一樣維持舊的（誤判）行為，不可改變
        assert _calculate_light(_scada_stricter_row(AIR_ITEM_NO_VOC_NAME))[0] == "O"

    def test_b_stack_fix_air_category_without_voc_in_name(self):
        """★ 本次核心修正：名稱不含 VOC 但 category='空汙' → 正確套用 VOC 例外 → 綠燈。"""
        light, _ = _calculate_light(
            _scada_stricter_row(AIR_ITEM_NO_VOC_NAME), category=CATEGORY_AIR
        )
        assert light == "G"

    def test_b_stack_water_category_overrides_voc_name(self):
        """category='水質' 有權推翻名稱裡的 VOC 字樣 → 不套例外 → 橙燈。"""
        light, _ = _calculate_light(_scada_stricter_row("VOC1"), category=CATEGORY_WATER)
        assert light == "O"

    @pytest.mark.parametrize("bad", [None, "", "unknown"])
    def test_null_category_falls_back(self, bad):
        """category 為 NULL／髒值 → 退回名稱比對，與 A 棧結果相同。"""
        assert _calculate_light(_scada_stricter_row("VOC1"), category=bad)[0] == "G"
        assert _calculate_light(_scada_stricter_row("Cu"), category=bad)[0] == "O"

    def test_category_does_not_disturb_check_lower_bound(self):
        """category 與 C1 的 check_lower_bound 互不干擾（pH 雙邊下界示警照常）。"""
        ph_row = dict(
            item="pH", rvalue_raw="5.5", broken=0,
            oos="6-9", ooc="6.5-8.5", alert_spec="6.8-8.2", recv="",
            scada_oos="", scada_ooc="", scada_alert="", cwms_oos="", cwms_ooc="",
        )
        assert _calculate_light(ph_row)[0] == "G"                       # A 棧：只比上界
        assert _calculate_light(ph_row, check_lower_bound=True)[0] == "R"
        assert _calculate_light(
            ph_row, check_lower_bound=True, category=CATEGORY_WATER
        )[0] == "R"


# ══════════════════════════════════════════════════════════════════════
# 3. services/dispatch_service.evaluate_row —— 派報代碼前綴（空/水）＋ escalation
# ══════════════════════════════════════════════════════════════════════

def _alert_row(item: str) -> dict:
    """Alert(5) ＜ 讀值(6) ＜ SPEC-OOC(8) → 黃燈，產生 '{空|水}Alert-K1' 代碼。"""
    return dict(
        plantno="K1", item=item, rvalue_raw="6", rvalue="6", broken=0,
        oos="10", ooc="8", alert_spec="5", recv="",
        scada_oos="", scada_ooc="", scada_alert="", cwms_oos="", cwms_ooc="",
    )


def _oos_row(item: str) -> dict:
    """讀值(12) ＞＝ SPEC-OOS(10) → 紅燈；只有水質相關或空汙項目才會產生 OOS 代碼。"""
    return dict(
        plantno="K1", item=item, rvalue_raw="12", rvalue="12", broken=0,
        oos="10", ooc="8", alert_spec="5", recv="",
        scada_oos="", scada_ooc="", scada_alert="", cwms_oos="", cwms_ooc="",
    )


class TestEvaluateRowCategory:
    def test_a_stack_unchanged_prefix(self):
        """A 棧（不傳 category）：VOC 名稱→'空'、其餘→'水'（改版前行為，逐字元不變）。"""
        assert evaluate_row(_alert_row("VOC1"), None, T0).codes == ["空Alert-K1"]
        assert evaluate_row(_alert_row("pH"), None, T0).codes == ["水Alert-K1"]
        assert evaluate_row(_alert_row("雨水溝pH"), None, T0).codes == ["水Alert-K1"]
        # 名稱不含 VOC 的空汙項目：A 棧維持舊的誤判（分到「水」），不可改變
        assert evaluate_row(_alert_row(AIR_ITEM_NO_VOC_NAME), None, T0).codes == ["水Alert-K1"]

    def test_b_stack_fix_prefix(self):
        """★ 本次核心修正：category='空汙' → 代碼前綴改為「空」，派報名單才找得對。"""
        result = evaluate_row(_alert_row(AIR_ITEM_NO_VOC_NAME), None, T0, category=CATEGORY_AIR)
        assert result.codes == ["空Alert-K1"]

    def test_b_stack_water_category_overrides_voc_name(self):
        result = evaluate_row(_alert_row("VOC1"), None, T0, category=CATEGORY_WATER)
        assert result.codes == ["水Alert-K1"]

    def test_b_stack_raingutter_category_goes_to_water_side(self):
        """雨水溝歸「水」側，與舊名稱比對的結果一致。"""
        result = evaluate_row(_alert_row(RAIN_ITEM_NO_NAME), None, T0, category=CATEGORY_RAINGUTTER)
        assert result.codes == ["水Alert-K1"]

    def test_a_stack_unchanged_oos_escalation_gate(self):
        """
        A 棧（不傳 category）：can_escalate = 水質關鍵字 or VOC 名稱。
        名稱不含 VOC 又不含 pH/Cu/Ni/SS/COD 的項目 → 不產生 OOS 代碼（舊行為）。
        """
        assert evaluate_row(_oos_row("VOC1"), None, T0).codes == ["空OOS-K1"]
        assert evaluate_row(_oos_row("COD"), None, T0).codes == ["水OOS-K1"]
        assert evaluate_row(_oos_row(AIR_ITEM_NO_VOC_NAME), None, T0).codes == []
        assert evaluate_row(_oos_row(AIR_ITEM_NO_VOC_NAME), None, T0).light == "R"

    def test_b_stack_fix_oos_escalation_gate(self):
        """
        ★ 這是本次修正最嚴重的一個後果：名稱不含 VOC 的空汙項目讀值超出 OOS，
        舊邏輯下 can_escalate=False，**紅燈卻完全不會派報**（codes 空）。
        category='空汙' 後才會正確產生「空OOS-K1」。
        """
        result = evaluate_row(_oos_row(AIR_ITEM_NO_VOC_NAME), None, T0, category=CATEGORY_AIR)
        assert result.codes == ["空OOS-K1"]
        assert result.light == "R"

    @pytest.mark.parametrize("bad", [None, "", "unknown"])
    def test_null_category_falls_back(self, bad):
        assert evaluate_row(_alert_row("VOC1"), None, T0, category=bad).codes == ["空Alert-K1"]
        assert evaluate_row(_alert_row("pH"), None, T0, category=bad).codes == ["水Alert-K1"]

    def test_b_stack_voc_exception_in_mismatch(self):
        """管制值不一致比對的 VOC 例外，一樣改由 category 決定。"""
        row = dict(
            plantno="K1", item=AIR_ITEM_NO_VOC_NAME, rvalue_raw="1", rvalue="1", broken=0,
            oos="10", ooc="", alert_spec="", recv="",
            scada_oos="8", scada_ooc="", scada_alert="", cwms_oos="", cwms_ooc="",
        )
        # 不傳 category（A 棧）→ 不套 VOC 例外 → 管制值不一致，橙燈 + 代碼
        a_stack = evaluate_row(row, None, T0)
        assert a_stack.codes == ["水管制值不-K1"]
        assert a_stack.light == "O"
        # category='空汙'（B 棧）→ SCADA 比 SPEC 嚴，不算不一致 → 不派報
        b_stack = evaluate_row(row, None, T0, category=CATEGORY_AIR)
        assert b_stack.codes == []
        assert b_stack.light == "G"


# ══════════════════════════════════════════════════════════════════════
# 4. services/flow_service.build_rtype_list —— 簽核人 rpttype（水/空保養中）
# ══════════════════════════════════════════════════════════════════════

class TestBuildRtypeListCategory:
    def test_a_stack_unchanged(self):
        """A 棧（不傳 categories）：與改版前逐字元相同。"""
        assert build_rtype_list(["pH", "COD", "SS"]) == ["水保養中"]
        assert build_rtype_list(["VOC", "VOC2"]) == ["空保養中"]
        assert build_rtype_list(["pH", "VOC", "COD"]) == ["水保養中", "空保養中"]
        assert build_rtype_list(["VOC", "pH"]) == ["空保養中", "水保養中"]
        assert build_rtype_list([]) == []
        assert build_rtype_list([AIR_ITEM_NO_VOC_NAME]) == ["水保養中"]  # 舊誤判，刻意保留

    def test_a_stack_unchanged_with_empty_dict(self):
        """明確傳空 dict 等同不傳（全部退回名稱比對）。"""
        assert build_rtype_list(["VOC", "pH"], {}) == ["空保養中", "水保養中"]

    def test_b_stack_fix(self):
        """★ 本次核心修正：名稱不含 VOC 但 category='空汙' → 找「空保養中」的簽核人。"""
        cats = {AIR_ITEM_NO_VOC_NAME: CATEGORY_AIR}
        assert build_rtype_list([AIR_ITEM_NO_VOC_NAME], cats) == ["空保養中"]

    def test_b_stack_mixed_items_keep_first_seen_order(self):
        cats = {AIR_ITEM_NO_VOC_NAME: CATEGORY_AIR, "pH1": CATEGORY_WATER}
        assert build_rtype_list([AIR_ITEM_NO_VOC_NAME, "pH1"], cats) == ["空保養中", "水保養中"]
        assert build_rtype_list(["pH1", AIR_ITEM_NO_VOC_NAME], cats) == ["水保養中", "空保養中"]

    def test_partial_map_falls_back_per_item(self):
        """dict 裡查不到的項目逐項退回名稱比對（未回填 category 的舊資料不會壞掉）。"""
        cats = {AIR_ITEM_NO_VOC_NAME: CATEGORY_AIR}   # "VOC9" 不在 dict 內
        assert build_rtype_list([AIR_ITEM_NO_VOC_NAME, "VOC9"], cats) == ["空保養中"]
        assert build_rtype_list(["Cu", "VOC9"], cats) == ["水保養中", "空保養中"]

    def test_null_value_in_map_falls_back(self):
        """dict 內值為 None（DB category IS NULL）→ 退回名稱比對。"""
        assert build_rtype_list(["VOC1"], {"VOC1": None}) == ["空保養中"]
        assert build_rtype_list([AIR_ITEM_NO_VOC_NAME], {AIR_ITEM_NO_VOC_NAME: None}) == ["水保養中"]

    def test_raingutter_category_maps_to_water(self):
        cats = {RAIN_ITEM_NO_NAME: CATEGORY_RAINGUTTER}
        assert build_rtype_list([RAIN_ITEM_NO_NAME], cats) == ["水保養中"]


# ══════════════════════════════════════════════════════════════════════
# 5. services/dispatch_service.mark_isolated_item —— 雨水溝不覆寫管制值欄位
#    （只是 A 棧的 UPDATE 組句，用假 db 攔截 SQL 字串驗證，不連 DB）
# ══════════════════════════════════════════════════════════════════════

class _FakeDb:
    """只記錄 execute() 收到的 SQL 文字，不做任何事。"""

    def __init__(self):
        self.statements: list[str] = []

    def execute(self, stmt, params=None):
        self.statements.append(str(stmt))
        return None


def _marks_control_columns(item: str, category=None, source: str = "SCADA") -> bool:
    """執行 mark_isolated_item，回傳「有沒有把管制值欄位一起改成保養中」。"""
    db = _FakeDb()
    mark_isolated_item(db, "K1", item, source, category=category)
    return any("OOS_HH" in s for s in db.statements)


class TestMarkIsolatedItemCategory:
    def test_a_stack_unchanged(self):
        """A 棧（不傳 category）：名稱含「雨水溝」才略過管制值欄位（改版前行為）。"""
        assert _marks_control_columns("雨水溝pH") is False
        assert _marks_control_columns("pH") is True
        assert _marks_control_columns(RAIN_ITEM_NO_NAME) is True   # 舊誤判，刻意保留

    def test_b_stack_fix(self):
        """★ 名稱不含「雨水溝」但 category='雨水溝' → 正確略過管制值欄位。"""
        assert _marks_control_columns(RAIN_ITEM_NO_NAME, CATEGORY_RAINGUTTER) is False

    def test_b_stack_category_overrides_name(self):
        assert _marks_control_columns("雨水溝pH", CATEGORY_WATER) is True

    @pytest.mark.parametrize("bad", [None, "", "unknown"])
    def test_null_category_falls_back(self, bad):
        assert _marks_control_columns("雨水溝pH", bad) is False
        assert _marks_control_columns("pH", bad) is True

    def test_cwms_branch_still_works(self):
        """非雨水溝的 CWMS 來源走另一組欄位，category 不影響這個分支選擇。"""
        db = _FakeDb()
        mark_isolated_item(db, "K1", "pH", "CWMS", category=CATEGORY_WATER)
        assert any("OOS_HH1" in s for s in db.statements)


# ══════════════════════════════════════════════════════════════════════
# 6. services_b/dashboard_page_service.build_dashboard_context（B 棧專屬）
#    —— 雨水溝欄位（is_rain / rain_24h）改讀 category
# ══════════════════════════════════════════════════════════════════════

def _dash_row(**kw) -> DashboardRow:
    defaults = dict(
        plantno="K12", item="COD", unit="mg/L",
        law_spec="120", oos="100", ooc="80", alert_spec="70", recv="60",
        scada_oos="100", scada_ooc="80", scada_alert="70",
        cwms_oos="100", cwms_ooc="80",
        rvalue_raw="50", rvalue="50",
        broken=0, source=1, url="", remark="", emptycell="",
        light_status="G", is_anomaly=False, rain_24h="",
    )
    defaults.update(kw)
    return DashboardRow(**defaults)


def _first_row(ctx: dict) -> dict:
    return ctx["plants"][0]["rows"][0]


class TestDashboardContextRaingutter:
    def test_a_stack_style_default_uses_name_matching(self):
        """不傳 categories → 完全等同改版前的 `"雨水溝" in row.item`。"""
        ctx = build_dashboard_context([_dash_row(item="雨水溝COD")])
        assert _first_row(ctx)["is_rain"] is True
        ctx = build_dashboard_context([_dash_row(item="COD")])
        assert _first_row(ctx)["is_rain"] is False
        # 名稱不含「雨水溝」的雨水溝項目：不傳 categories 時維持舊誤判
        ctx = build_dashboard_context([_dash_row(item=RAIN_ITEM_NO_NAME)])
        assert _first_row(ctx)["is_rain"] is False

    def test_b_stack_fix_raingutter_category(self):
        """★ 名稱不含「雨水溝」但 category='雨水溝' → is_rain 正確為 True，並帶出 24H 雨量。"""
        ctx = build_dashboard_context(
            [_dash_row(item=RAIN_ITEM_NO_NAME)],
            rain_map={("K12", RAIN_ITEM_NO_NAME): "8.1"},
            categories={RAIN_ITEM_NO_NAME: CATEGORY_RAINGUTTER},
        )
        row = _first_row(ctx)
        assert row["is_rain"] is True
        assert row["rain_24h"] == "8.1"

    def test_b_stack_category_overrides_name(self):
        """category='水質' 有權推翻名稱裡的「雨水溝」字樣。"""
        ctx = build_dashboard_context(
            [_dash_row(item="雨水溝COD")],
            rain_map={("K12", "雨水溝COD"): "8.1"},
            categories={"雨水溝COD": CATEGORY_WATER},
        )
        row = _first_row(ctx)
        assert row["is_rain"] is False
        assert row["rain_24h"] == ""

    @pytest.mark.parametrize("cats", [None, {}, {"雨水溝COD": None}])
    def test_null_category_falls_back(self, cats):
        ctx = build_dashboard_context([_dash_row(item="雨水溝COD")], categories=cats)
        assert _first_row(ctx)["is_rain"] is True

    def test_categories_do_not_disturb_light_classification(self):
        """帶 categories 不影響燈號分類（counts/stats 與不帶時一致）。"""
        rows = [
            _dash_row(plantno="K1", item="COD", rvalue_raw="120", rvalue="120", light_status="R"),
            _dash_row(plantno="K1", item=RAIN_ITEM_NO_NAME, light_status="G"),
        ]
        plain = build_dashboard_context(rows)
        with_cats = build_dashboard_context(
            rows, categories={RAIN_ITEM_NO_NAME: CATEGORY_RAINGUTTER}
        )
        assert plain["stats"] == with_cats["stats"]
        assert [p["counts"] for p in plain["plants"]] == [p["counts"] for p in with_cats["plants"]]


# ══════════════════════════════════════════════════════════════════════════
# is_water_item：水質側的 can_escalate 漏報（2026-08-01 主控驗收 D7 時實測發現）
# ══════════════════════════════════════════════════════════════════════════

class TestWaterItemEscalation:
    """
    背景：`evaluate_row()` 的 `can_escalate = is_water or is_voc` 決定 OOC/OOS 超標時
    要不要產生派報代碼。原本 `is_water` 只比對五個名稱關鍵字（pH/Cu/Ni/SS/COD），
    因此像「氨氮」這種名稱不在清單內的水質項目，讀值超過 OOS 亮紅燈時
    **不會產生 OOS 派報代碼**（只剩黃燈 Alert 那條），最嚴重的一級反而漏掉。

    D7 第一輪只把空汙側（is_air_item）改成資料驅動，水質側若不一起改就只修一半，
    而水質項目才是絕大多數——故一併補上 is_water_item()。
    """

    BASE = {"plantno": "K1", "rvalue_raw": "150", "rvalue": "150", "broken": 0,
            "oos": "100", "ooc": "80", "alert_spec": "60", "recv": "80", "source": "SCADA"}
    NOW = datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc)

    def _codes(self, item, category=None):
        return evaluate_row({**self.BASE, "item": item}, None, self.NOW, category=category).codes

    def test_a_stack_keyword_names_still_escalate(self):
        """A 棧保護：名稱含關鍵字的項目不傳 category 時照樣產生 OOS 代碼（行為不變）。"""
        assert "水OOS-K1" in self._codes("COD")

    def test_a_stack_non_keyword_water_item_still_misses_oos(self):
        """
        A 棧保護（刻意鎖住「舊行為就是有漏報」這件事）：不傳 category 時，
        「氨氮」仍然只有 Alert、沒有 OOS——A 棧行為必須逐字元不變，
        修正只在 B 棧（有帶 category）生效。
        """
        codes = self._codes("氨氮")
        assert "水Alert-K1" in codes
        assert "水OOS-K1" not in codes

    def test_b_stack_category_fixes_missing_oos_dispatch(self):
        """B 棧修正生效：標上 category='水質' 後，氨氮的紅燈 OOS 代碼就會產生。"""
        codes = self._codes("氨氮", category="水質")
        assert "水Alert-K1" in codes
        assert "水OOS-K1" in codes

    def test_air_item_by_category_escalates_with_air_prefix(self):
        """名稱不含 VOC 的空汙項目，標上 category 後用「空」前綴且會升級。"""
        codes = self._codes("臭氧", category="空汙")
        assert "空OOS-K1" in codes

    @pytest.mark.parametrize("bad", [None, "", "水", "unknown"])
    def test_dirty_category_falls_back_to_name_matching(self, bad):
        """category 為 None／空／未知髒值 → 退回名稱比對，不會誤判也不會爆。"""
        assert "水OOS-K1" in self._codes("COD", category=bad)
        assert "水OOS-K1" not in self._codes("氨氮", category=bad)

    def test_is_water_item_pure_function(self):
        """純函式本身：category 優先，未指定才看名稱關鍵字。"""
        assert is_water_item("COD") is True
        assert is_water_item("氨氮") is False              # 舊行為：關鍵字比對猜不到
        assert is_water_item("氨氮", "水質") is True        # 資料驅動修正
        assert is_water_item("COD", "空汙") is False       # category 有權推翻名稱
        assert is_water_item("雨水溝1", "雨水溝") is False
