"""
test_dashboard_lower_bound.py — C1：雙邊規格(pH/溫度)下界示警測試

背景（2026-07-12 使用者確認）：
  現行 `_calculate_light()` 對雙邊規格（pH '6-9'、溫度）只比對上界，數值過低不示警
  （忠實還原舊系統）。使用者確認新系統（B 棧）要改成上下界都示警，但 A 棧
  （services/dashboard_service.py，main.py 公司平行測試中）不可受影響，因此新增
  預設 False 的 `check_lower_bound` 參數：不傳 = 完全維持舊行為（A 棧）；
  傳 True = 啟用下界示警（B 棧 services_b/dashboard_service.py 呼叫時使用）。

本檔案只測純函式 `_calculate_light`，不連 DB。
"""

from services.dashboard_service import _calculate_light


# pH 規格：OOS '6-9'、OOC '6.5-8.5'、Alert '6.8-8.2'（皆為雙邊）
def _ph_row(rvalue: str) -> dict:
    return {
        "item": "pH",
        "rvalue_raw": rvalue,
        "broken": 0,
        "oos": "6-9",
        "ooc": "6.5-8.5",
        "alert_spec": "6.8-8.2",
        "recv": "",
        "scada_oos": "6-9",
        "scada_ooc": "6.5-8.5",
        "scada_alert": "6.8-8.2",
        "cwms_oos": "",
        "cwms_ooc": "",
    }


class TestDefaultBehaviorUnchanged:
    """★ 最重要：不傳參數（A 棧預設）時，pH 過低仍是綠燈，證明 A 棧行為未變。"""

    def test_default_no_lower_bound_check_low_ph_is_green(self):
        light, is_anomaly = _calculate_light(_ph_row("5.5"))
        assert light == "G"
        assert is_anomaly is False

    def test_explicit_false_same_as_default(self):
        light, _ = _calculate_light(_ph_row("5.5"), check_lower_bound=False)
        assert light == "G"

    def test_default_upper_bound_still_works(self):
        # 上界原本就有比對，確認預設行為（過高示警）仍正常
        light, _ = _calculate_light(_ph_row("9.5"))
        assert light == "R"
        light, _ = _calculate_light(_ph_row("8.6"))
        assert light == "O"
        light, _ = _calculate_light(_ph_row("8.3"))
        assert light == "Y"


class TestLowerBoundEnabled:
    """check_lower_bound=True：pH 5.5→R、6.2→O、6.7→Y、7.5→G、8.3→Y、8.6→O、9.5→R"""

    def test_5_5_is_red(self):
        light, is_anomaly = _calculate_light(_ph_row("5.5"), check_lower_bound=True)
        assert light == "R"
        assert is_anomaly is False

    def test_6_2_is_orange(self):
        light, _ = _calculate_light(_ph_row("6.2"), check_lower_bound=True)
        assert light == "O"

    def test_6_7_is_yellow(self):
        light, _ = _calculate_light(_ph_row("6.7"), check_lower_bound=True)
        assert light == "Y"

    def test_7_5_is_green(self):
        light, _ = _calculate_light(_ph_row("7.5"), check_lower_bound=True)
        assert light == "G"

    def test_8_3_is_yellow(self):
        light, _ = _calculate_light(_ph_row("8.3"), check_lower_bound=True)
        assert light == "Y"

    def test_8_6_is_orange(self):
        light, _ = _calculate_light(_ph_row("8.6"), check_lower_bound=True)
        assert light == "O"

    def test_9_5_is_red(self):
        light, _ = _calculate_light(_ph_row("9.5"), check_lower_bound=True)
        assert light == "R"

    def test_boundary_exactly_at_oos_lower_is_red(self):
        # rvalue <= OOS 下界 → R
        light, _ = _calculate_light(_ph_row("6.0"), check_lower_bound=True)
        assert light == "R"

    def test_boundary_exactly_at_ooc_lower_is_orange(self):
        light, _ = _calculate_light(_ph_row("6.5"), check_lower_bound=True)
        assert light == "O"

    def test_boundary_exactly_at_alert_lower_is_green(self):
        # rvalue < Alert 下界 才是 Y，等於下界時不算
        light, _ = _calculate_light(_ph_row("6.8"), check_lower_bound=True)
        assert light == "G"


class TestSingleSidedSpecUnaffected:
    """單邊規格（如 COD '100'）在 check_lower_bound=True 時行為完全不變。"""

    def _cod_row(self, rvalue: str) -> dict:
        return {
            "item": "COD",
            "rvalue_raw": rvalue,
            "broken": 0,
            "oos": "100",
            "ooc": "80",
            "alert_spec": "60",
            "recv": "",
            "scada_oos": "100",
            "scada_ooc": "80",
            "scada_alert": "60",
            "cwms_oos": "",
            "cwms_ooc": "",
        }

    def test_low_value_still_green_regardless_of_lower_bound_flag(self):
        # 單邊規格沒有「下界」概念，數值極低（甚至 0）依然是綠燈
        light_false, _ = _calculate_light(self._cod_row("0.1"), check_lower_bound=False)
        light_true, _ = _calculate_light(self._cod_row("0.1"), check_lower_bound=True)
        assert light_false == "G"
        assert light_true == "G"

    def test_upper_bound_results_identical_with_and_without_flag(self):
        for rvalue, expected in [("50", "G"), ("70", "Y"), ("90", "O"), ("100", "R")]:
            light_false, _ = _calculate_light(self._cod_row(rvalue), check_lower_bound=False)
            light_true, _ = _calculate_light(self._cod_row(rvalue), check_lower_bound=True)
            assert light_false == expected
            assert light_true == expected


class TestBrokenAndMismatchUnaffectedByFlag:
    """broken / SCADA 不一致等既有規則不受新參數影響。"""

    def test_broken_returns_dash_regardless_of_flag(self):
        row = _ph_row("5.5")
        row["broken"] = 1
        light_false, anomaly_false = _calculate_light(row, check_lower_bound=False)
        light_true, anomaly_true = _calculate_light(row, check_lower_bound=True)
        assert light_false == "-" and anomaly_false is True
        assert light_true == "-" and anomaly_true is True

    def test_scada_mismatch_still_orange_when_within_normal_range(self):
        row = _ph_row("7.5")  # 正常範圍內
        row["scada_oos"] = "6-9.5"  # SCADA 與 SPEC 不一致
        light_false, _ = _calculate_light(row, check_lower_bound=False)
        light_true, _ = _calculate_light(row, check_lower_bound=True)
        assert light_false == "O"
        assert light_true == "O"

    def test_red_from_upper_not_downgraded_by_mismatch(self):
        row = _ph_row("9.5")
        row["scada_oos"] = "6-9.5"  # 不一致，但讀值已達紅燈，不應被降級
        light, _ = _calculate_light(row, check_lower_bound=True)
        assert light == "R"
