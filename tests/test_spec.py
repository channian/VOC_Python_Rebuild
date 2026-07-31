import sys
import os
import pytest
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 純邏輯測試：只 import services/schemas，不 import routers/main/database
# （環境無 ODBC driver、亦無 httpx2，DB/TestClient 相關測試不適用於此檔，
#  比照 tests/test_control.py / tests/test_flow.py 的既有慣例）。

from pydantic import ValidationError
from schemas.spec_schema import (
    SpecCreate, SpecApplyCreate, parse_spec_bound, check_ooc_alert_hierarchy,
    guess_dual_bound_by_name,
)
from services.spec_service import (
    to_storage_item, to_display_item, ftype_label, FTYPE_LABELS,
    FRULEID_SPEC, RPTTYPE_SPEC,
)
from services.flow_service import FlowStatus


# ── 欄位格式驗證：parse_spec_bound 純函式 ────────────────────────────────────

def test_parse_spec_bound_empty_or_na_is_none():
    assert parse_spec_bound("", "OOC", False, "VOC") is None
    assert parse_spec_bound("N/A", "OOC", False, "VOC") is None

def test_parse_spec_bound_single_sided_ok():
    assert parse_spec_bound("80", "OOS", False, "VOC") == [80.0]

def test_parse_spec_bound_double_sided_ok():
    assert parse_spec_bound("6-9", "LAW", True, "pH") == [6.0, 9.0]

def test_parse_spec_bound_ph_requires_double_sided():
    with pytest.raises(ValueError, match="pH 必須為雙邊規格"):
        parse_spec_bound("6", "LAW", True, "pH")

def test_parse_spec_bound_non_ph_requires_single_sided():
    with pytest.raises(ValueError, match="VOC 必須為單邊規格"):
        parse_spec_bound("10-100", "LAW", False, "VOC")

def test_parse_spec_bound_rejects_non_numeric():
    with pytest.raises(ValueError, match="請確保皆為數字"):
        parse_spec_bound("abc", "OOC", False, "VOC")

def test_parse_spec_bound_rejects_more_than_two_decimals():
    with pytest.raises(ValueError, match="請確保皆為數字且最多包含兩位小數"):
        parse_spec_bound("1.234", "OOC", False, "VOC")

def test_parse_spec_bound_allows_two_decimals():
    assert parse_spec_bound("1.23", "OOC", False, "VOC") == [1.23]

def test_parse_spec_bound_double_sided_lower_must_be_less_than_upper():
    with pytest.raises(ValueError, match="下限規格不能大於或等於上限規格"):
        parse_spec_bound("9-6", "LAW", True, "pH")

def test_parse_spec_bound_double_sided_equal_bounds_rejected():
    with pytest.raises(ValueError, match="下限規格不能大於或等於上限規格"):
        parse_spec_bound("7-7", "LAW", True, "pH")


# ── OOC / Alert 層遞防呆：check_ooc_alert_hierarchy 純函式 ───────────────────

def test_check_ooc_alert_hierarchy_single_sided_ok():
    check_ooc_alert_hierarchy([60.0], [50.0], is_dual=False)  # 不 raise 即通過

def test_check_ooc_alert_hierarchy_single_sided_violation():
    with pytest.raises(ValueError, match="OOC 上限值不可小於"):
        check_ooc_alert_hierarchy([40.0], [50.0], is_dual=False)

def test_check_ooc_alert_hierarchy_double_sided_ok():
    # OOC(5-10) 比 Alert(6-9) 寬：下限更低、上限更高
    check_ooc_alert_hierarchy([5.0, 10.0], [6.0, 9.0], is_dual=True)

def test_check_ooc_alert_hierarchy_double_sided_violation():
    with pytest.raises(ValueError, match="OOC 範圍不可比 Alert 範圍窄"):
        check_ooc_alert_hierarchy([6.5, 8.5], [6.0, 9.0], is_dual=True)

def test_check_ooc_alert_hierarchy_skips_when_either_missing():
    check_ooc_alert_hierarchy(None, [50.0], is_dual=False)
    check_ooc_alert_hierarchy([60.0], None, is_dual=False)


# ── 貼齊（Alert == OOC）為合法設定（2026-07-31 環工部確認：實際數值因廠區而異）──

def test_check_ooc_alert_hierarchy_single_sided_equal_allowed():
    """ 單邊：部分廠區把 Alert 設得跟 OOC 完全相同（不留黃燈緩衝），應通過 """
    check_ooc_alert_hierarchy([80.0], [80.0], is_dual=False)  # 不 raise 即通過

def test_check_ooc_alert_hierarchy_double_sided_equal_allowed():
    """ pH 雙邊：Alert 與 OOC 上下界完全相同，應通過 """
    check_ooc_alert_hierarchy([6.5, 8.5], [6.5, 8.5], is_dual=True)

def test_check_ooc_alert_hierarchy_double_sided_one_side_equal_allowed():
    """ pH 雙邊：只有下界貼齊（OOC 6.5-8.5 / Alert 6.5-8.2），另一側仍有間距，應通過 """
    check_ooc_alert_hierarchy([6.5, 8.5], [6.5, 8.2], is_dual=True)

def test_check_ooc_alert_hierarchy_double_sided_upper_side_equal_allowed():
    """ pH 雙邊：只有上界貼齊（OOC 6.5-8.5 / Alert 6.8-8.5），應通過 """
    check_ooc_alert_hierarchy([6.5, 8.5], [6.8, 8.5], is_dual=True)

def test_check_ooc_alert_hierarchy_double_sided_lower_inverted_still_rejected():
    """ 放寬成允許相等後，真正的反轉（OOC 下限高於 Alert 下限）仍必須擋下 """
    with pytest.raises(ValueError, match="OOC 範圍不可比 Alert 範圍窄"):
        check_ooc_alert_hierarchy([6.5, 8.5], [6.2, 8.5], is_dual=True)

def test_check_ooc_alert_hierarchy_double_sided_upper_inverted_still_rejected():
    """ 反轉（OOC 上限低於 Alert 上限）仍必須擋下 """
    with pytest.raises(ValueError, match="OOC 範圍不可比 Alert 範圍窄"):
        check_ooc_alert_hierarchy([6.5, 8.5], [6.5, 8.8], is_dual=True)


# ── SpecCreate（Pydantic）整合驗證 ───────────────────────────────────────────

def test_spec_validation_logic_ph_double_sided():
    """ 成功案例：pH 為雙邊且邏輯正確 """
    spec = SpecCreate(
        plantno="K1", item="pH",
        LAW="6-9", OOS="6.5-8.5", OOC="5-10", alert="6.2-8.8",
        source_id=1
    )
    assert spec.item == "pH"

def test_spec_validation_logic_ph_single_sided_rejected():
    """ 失敗案例：pH 輸入單邊範圍 """
    with pytest.raises(ValidationError) as exc_info:
        SpecCreate(
             plantno="K1", item="pH",
             LAW="6", OOS="6.5", OOC="7", alert="7.2",
             source_id=1
        )
    assert "pH 必須為雙邊規格" in str(exc_info.value)

def test_spec_validation_logic_voc_single_sided():
    """ 一般項目 (VOC) 是否攔下被輸入成雙邊 """
    with pytest.raises(ValidationError) as exc_info:
        SpecCreate(
            plantno="K1", item="VOC",
            LAW="10-100", OOS="80", OOC="60", alert="50",
            source_id=1
        )
    assert "VOC 必須為單邊規格" in str(exc_info.value)

def test_spec_validation_logic_hierarchical_limits():
    """ OOC 是否有防呆「不能寫反或超過 Alert」 """
    with pytest.raises(ValidationError) as exc_info:
        SpecCreate(
            plantno="K1", item="VOC",
            LAW="100", OOS="80", OOC="40", alert="50",  # OOC(40) 反而比 Alert(50) 小
            source_id=1
        )
    assert "單邊規格中，OOC 上限值不可小於" in str(exc_info.value)

def test_spec_validation_allows_alert_equal_to_ooc():
    """ 貼齊設定（Alert == OOC）走 Pydantic 整段驗證也要通過（2026-07-31 確認合法） """
    spec = SpecCreate(
        plantno="K1", item="VOC",
        LAW="100", OOS="90", OOC="80", alert="80",   # Alert 與 OOC 貼齊
        source_id=1
    )
    assert spec.alert == spec.OOC

def test_spec_validation_na_fields_skip_checks():
    """ LAW/OOS 可填 N/A 代表未設定，不觸發格式檢查 """
    spec = SpecCreate(
        plantno="K1", item="VOC",
        LAW="N/A", OOS="N/A", OOC="60", alert="50",
        source_id=1
    )
    assert spec.LAW == "N/A"


# ── 雙邊規格判定改資料驅動（2026-07-31，見 models_b.Item.is_dual_bound）────────
#
# 規則：SpecBase.is_dual_bound 有傳值就以它為準；沒傳（None）才退回
# guess_dual_bound_by_name() 名稱推測。A 棧前端不送這個欄位 → 一律走 fallback，行為凍結。

def _spec_kwargs(**over):
    """SpecCreate 的最小合法參數，測試只覆寫關心的欄位。"""
    base = dict(plantno="K1", item="VOC", LAW="100", OOS="90", OOC="80", alert="70", source_id=1)
    base.update(over)
    return base


def test_guess_dual_bound_by_name_frozen_a_stack_behavior():
    """fallback 必須與 A 棧原本第 97 行 `item.lower()=='ph' or item=='pH1'` 完全相同。"""
    assert guess_dual_bound_by_name("pH") is True
    assert guess_dual_bound_by_name("ph") is True
    assert guess_dual_bound_by_name("PH") is True
    assert guess_dual_bound_by_name("pH1") is True
    # ★ 刻意「猜不到」的三種：A 棧行為凍結，不可為了跟載入器的 ^ph\d*$ 統一而放寬
    assert guess_dual_bound_by_name("pH2") is False
    assert guess_dual_bound_by_name("溫度") is False
    assert guess_dual_bound_by_name("COD") is False


def test_dual_bound_true_allows_temperature_double_sided():
    """★ 核心驗收：名稱是「溫度」、is_dual_bound=True、門檻填 20-35 → 必須通過。"""
    spec = SpecCreate(**_spec_kwargs(
        item="溫度", LAW="20-35", OOS="20-35", OOC="22-33", alert="23-32",
        is_dual_bound=True,
    ))
    assert spec.effective_dual_bound() is True
    assert spec.OOS == "20-35"


def test_dual_bound_none_still_rejects_temperature_double_sided():
    """★ 反證 fallback 沒被改壞：同一筆資料不帶 is_dual_bound 時，仍照舊被擋成「必須為單邊」。"""
    with pytest.raises(ValidationError, match="溫度 必須為單邊規格"):
        SpecCreate(**_spec_kwargs(
            item="溫度", LAW="20-35", OOS="20-35", OOC="22-33", alert="23-32",
        ))


def test_dual_bound_true_allows_ph2_double_sided():
    """pH2 的雙邊門檻：帶 is_dual_bound=True 就改得動（原本載入器灌得進、規格頁改不動）。"""
    spec = SpecCreate(**_spec_kwargs(
        item="pH2", LAW="6-9", OOS="6-9", OOC="6.5-8.5", alert="6.8-8.2",
        is_dual_bound=True,
    ))
    assert spec.effective_dual_bound() is True


def test_dual_bound_false_rejects_double_sided_even_for_ph_name():
    """明確指定單邊時，即使名稱叫 pH 也要擋下雙邊門檻（資料勝過名稱推測）。"""
    with pytest.raises(ValidationError, match="pH 必須為單邊規格"):
        SpecCreate(**_spec_kwargs(
            item="pH", LAW="6-9", OOS="6-9", OOC="6.5-8.5", alert="6.8-8.2",
            is_dual_bound=False,
        ))


def test_dual_bound_false_allows_single_sided_for_ph_name():
    """對照組：同樣指定單邊，填單邊值就通過。"""
    spec = SpecCreate(**_spec_kwargs(item="pH", is_dual_bound=False))
    assert spec.effective_dual_bound() is False


def test_dual_bound_none_keeps_ph_fallback_working():
    """不帶 is_dual_bound 時 pH 仍走名稱推測判成雙邊（A 棧既有行為原封不動）。"""
    spec = SpecCreate(**_spec_kwargs(
        item="pH", LAW="6-9", OOS="6-9", OOC="6.5-8.5", alert="6.8-8.2",
    ))
    assert spec.is_dual_bound is None
    assert spec.effective_dual_bound() is True


def test_dual_bound_true_hierarchy_uses_double_sided_rule():
    """雙邊層遞防呆也要跟著 is_dual_bound 走（溫度的 Alert 超出 OOC 範圍要擋）。"""
    with pytest.raises(ValidationError, match="OOC 範圍不可比 Alert 範圍窄"):
        SpecCreate(**_spec_kwargs(
            item="溫度", LAW="20-35", OOS="20-35", OOC="23-32", alert="22-33",
            is_dual_bound=True,
        ))


def test_spec_apply_create_accepts_dual_bound_injection():
    """送簽申請（SpecApplyCreate）繼承同一套注入機制。"""
    apply = SpecApplyCreate(**_spec_kwargs(
        item="溫度", LAW="20-35", OOS="20-35", OOC="22-33", alert="23-32",
        is_dual_bound=True,
    ), ftype="I")
    assert apply.effective_dual_bound() is True


# ── SpecApplyCreate（送簽申請）驗證 ──────────────────────────────────────────

def test_spec_apply_create_valid_ftype():
    for ftype in ("I", "M", "D"):
        apply = SpecApplyCreate(
            plantno="K1", item="VOC", LAW="100", OOS="80", OOC="60", alert="50",
            source_id=1, ftype=ftype,
        )
        assert apply.ftype == ftype

def test_spec_apply_create_invalid_ftype_rejected():
    with pytest.raises(ValidationError, match="ftype 必須為"):
        SpecApplyCreate(
            plantno="K1", item="VOC", LAW="100", OOS="80", OOC="60", alert="50",
            source_id=1, ftype="X",
        )

def test_spec_apply_create_reuses_spec_field_validation():
    """ SpecApplyCreate 繼承 SpecBase，欄位格式驗證應一併套用 """
    with pytest.raises(ValidationError, match="VOC 必須為單邊規格"):
        SpecApplyCreate(
            plantno="K1", item="VOC", LAW="10-100", OOS="80", OOC="60", alert="50",
            source_id=1, ftype="I",
        )


# ── pH1 / COD2 項目別名映射（雙向）───────────────────────────────────────────

def test_to_storage_item_k14b_ph():
    assert to_storage_item("K14B", "pH") == "pH1"

def test_to_storage_item_k22_ph():
    assert to_storage_item("K22", "pH") == "pH1"

def test_to_storage_item_jiuhao_ph():
    assert to_storage_item("九號放流口", "pH") == "pH1"

def test_to_storage_item_k14b_cod():
    assert to_storage_item("K14B", "COD") == "COD2"

def test_to_storage_item_other_plant_ph_unchanged():
    """ 非 K14B/K22/九號放流口 的 pH 不轉換 """
    assert to_storage_item("K1", "pH") == "pH"

def test_to_storage_item_k22_cod_unchanged():
    """ K22 的 COD 不轉換（COD2 別名只給 K14B） """
    assert to_storage_item("K22", "COD") == "COD"

def test_to_storage_item_unrelated_item_unchanged():
    assert to_storage_item("K14B", "VOC") == "VOC"

def test_to_display_item_reverses_ph1():
    assert to_display_item("pH1") == "pH"

def test_to_display_item_reverses_cod2():
    assert to_display_item("COD2") == "COD"

def test_to_display_item_unrelated_item_unchanged():
    assert to_display_item("VOC") == "VOC"

def test_to_display_item_roundtrip_with_to_storage_item():
    for plantno, item in [("K14B", "pH"), ("K22", "pH"), ("九號放流口", "pH"), ("K14B", "COD")]:
        storage = to_storage_item(plantno, item)
        assert to_display_item(storage) == item


# ── ftype 語意 ────────────────────────────────────────────────────────────

def test_ftype_labels_complete():
    assert FTYPE_LABELS == {"I": "新增", "M": "修改", "D": "刪除"}

def test_ftype_label_known_values():
    assert ftype_label("I") == "新增"
    assert ftype_label("M") == "修改"
    assert ftype_label("D") == "刪除"

def test_ftype_label_unknown_value_passthrough():
    assert ftype_label("X") == "X"


# ── fruleid / fstatusid（簽核流程常數與 FlowStatus 對齊）────────────────────

def test_fruleid_spec_matches_legacy_enum():
    """ legacy/dbVOC.cs:1643 簽核流程 enum：法遵平台_法規許可值與規格值維護 = 9 """
    assert FRULEID_SPEC == 9

def test_fruleid_spec_differs_from_isolation():
    """ 規格簽核與隔離簽核必須用不同 fruleid，不能共用同一個簽核流程規則 """
    from services.flow_service import FRULEID_ISOLATION
    assert FRULEID_SPEC != FRULEID_ISOLATION

def test_rpttype_spec_is_nonempty_constant():
    """ RPTTYPE_SPEC 待業務確認實際值，但至少必須是非空字串常數（不可意外變成 falsy） """
    assert isinstance(RPTTYPE_SPEC, str) and RPTTYPE_SPEC != ""

def test_flowstatus_approve_value_used_by_spec_flow():
    """ 規格簽核核准後 fstatusid 應寫入 FlowStatus.核准=7（與隔離簽核共用同一份 FlowStatus enum） """
    assert int(FlowStatus.核准) == 7
    assert int(FlowStatus.否決) == 8
    assert int(FlowStatus.待簽核) == 0
    assert int(FlowStatus.簽核中) == 1


# ── formno 產生（沿用 control_service.next_ccno）─────────────────────────────

def test_spec_service_reuses_control_next_ccno():
    """
    formno 與 ccno 格式完全相同（yyyyMMddNNN 11 碼流水號），spec_service 應直接 import
    control_service.next_ccno 重用，而不是另外複製一份邏輯。
    """
    from services.spec_service import next_ccno as spec_next_ccno
    from services.control_service import next_ccno as control_next_ccno
    assert spec_next_ccno is control_next_ccno

def test_formno_first_of_day():
    from services.spec_service import next_ccno
    assert next_ccno(None, "20260702") == "20260702001"

def test_formno_increment():
    from services.spec_service import next_ccno
    assert next_ccno("20260702003", "20260702") == "20260702004"

def test_formno_format_length():
    from services.spec_service import next_ccno
    formno = next_ccno("20260702099", "20260702")
    assert len(formno) == 11
    assert formno == "20260702100"
