"""
tests/test_light_ooc_priority.py — 「OOC 燈號優先於 Alert」業務規則的迴歸鎖

2026-07-31 使用者向環工部確認兩件事：
  1. Alert 與 OOC 的實際數值**因廠區而異**——有些廠區把 Alert 設得跟 OOC 完全相同（貼齊），
     有些會留間距，兩種都是合法設定（輸入驗證已於 schemas/spec_schema.py 放寬）。
  2. **讀值同時碰到 Alert 與 OOC 時，以 OOC 的燈號（橙）優先。**

第 2 點在 `services/dashboard_service._calculate_light()` 現行邏輯**已經正確**
（OOC 分支 `ooc <= rvalue < oos` 含等號且排在前面，Alert 分支 `alert < rvalue < ooc` 不含等號），
因此本檔**不改任何 runtime 邏輯，只把規則鎖住**——日後若有人重構燈號判定順序或把等號挪動，
這些測試會立刻紅燈。

純邏輯測試，不依賴 DB（只呼叫 _calculate_light 純函式），比照 tests/test_spec.py 慣例。
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.dashboard_service import _calculate_light


def _row(**kw) -> dict:
    """
    建構 _calculate_light() 需要的 row dict。

    刻意讓 scada_*/cwms_* 全部留空（None）——`_bounds_mismatch()` 任一邊解析不出來就回 False，
    所以本檔所有橙燈都**只可能來自 OOC 門檻**，不會是「SCADA/SPEC 設定不同步」那條橙燈，
    測試意圖不會被混淆。
    """
    row = {
        "rvalue_raw": "",
        "broken": 0,
        "item": "COD",
        "oos": None,
        "ooc": None,
        "alert_spec": None,
        "recv": None,
    }
    row.update(kw)
    return row


# ── 單邊規格：Alert 與 OOC 貼齊（部分廠區的合法設定）─────────────────────────

def test_single_sided_alert_equal_ooc_hits_orange_not_yellow():
    """ alert==ooc==80、讀值剛好 80 → 橙燈（OOC 優先），不可是黃燈 """
    light, is_anomaly = _calculate_light(
        _row(rvalue_raw="80", oos="100", ooc="80", alert_spec="80"))
    assert light == "O"
    assert is_anomaly is False


def test_single_sided_alert_equal_ooc_below_threshold_is_green():
    """ 貼齊設定下讀值未達門檻 → 綠燈（貼齊等於「沒有黃燈區間」，這是使用者要的效果） """
    light, _ = _calculate_light(
        _row(rvalue_raw="79", oos="100", ooc="80", alert_spec="80"))
    assert light == "G"


# ── 單邊規格：Alert < OOC（有間距）時三層門檻各自的邊界 ──────────────────────

def test_single_sided_value_equal_ooc_is_orange():
    """ 讀值剛好等於 OOC → 橙燈（OOC 分支含等號，rvalue >= ooc 即觸發） """
    light, _ = _calculate_light(
        _row(rvalue_raw="80", oos="100", ooc="80", alert_spec="60"))
    assert light == "O"


def test_single_sided_value_between_alert_and_ooc_is_yellow():
    """ 讀值落在 Alert 與 OOC 之間 → 黃燈 """
    light, _ = _calculate_light(
        _row(rvalue_raw="70", oos="100", ooc="80", alert_spec="60"))
    assert light == "Y"


def test_single_sided_value_equal_oos_is_red():
    """ 紅燈仍優先於橙燈（順序 R → O → Y 不可被本次規則影響） """
    light, _ = _calculate_light(
        _row(rvalue_raw="100", oos="100", ooc="80", alert_spec="60"))
    assert light == "R"


# ── pH 雙邊：check_lower_bound=True 的下界情境 ───────────────────────────────
# （B 棧呼叫端固定傳 True；A 棧預設 False 維持舊行為，見 _calculate_light docstring）

def test_ph_lower_bound_alert_equal_ooc_hits_orange_not_yellow():
    """ pH 下界貼齊（OOC 下限 == Alert 下限 == 6.5），讀值 6.5 → 橙燈，不可是黃燈 """
    light, is_anomaly = _calculate_light(
        _row(rvalue_raw="6.5", item="pH1", oos="6-9", ooc="6.5-8.5", alert_spec="6.5-8.2"),
        check_lower_bound=True,
    )
    assert light == "O"
    assert is_anomaly is False


def test_ph_lower_bound_value_below_alert_only_is_yellow():
    """ 下界有間距時，讀值低於 Alert 下限但高於 OOC 下限 → 黃燈（確認橙燈不是誤判來的） """
    light, _ = _calculate_light(
        _row(rvalue_raw="6.7", item="pH1", oos="6-9", ooc="6.5-8.5", alert_spec="6.8-8.2"),
        check_lower_bound=True,
    )
    assert light == "Y"


def test_ph_upper_bound_alert_equal_ooc_hits_orange_not_yellow():
    """ pH 上界貼齊（OOC 上限 == Alert 上限 == 8.5），讀值 8.5 → 橙燈 """
    light, _ = _calculate_light(
        _row(rvalue_raw="8.5", item="pH1", oos="6-9", ooc="6.5-8.5", alert_spec="6.8-8.5"),
        check_lower_bound=True,
    )
    assert light == "O"


def test_ph_lower_bound_ignored_when_flag_off():
    """
    A 棧保護：check_lower_bound 預設 False 時，同一筆下界讀值不看下界（維持舊行為）。
    這裡讀值 6.5 上界判定為 G（未超上界門檻），故整體綠燈。
    """
    light, _ = _calculate_light(
        _row(rvalue_raw="6.5", item="pH1", oos="6-9", ooc="6.5-8.5", alert_spec="6.5-8.2"))
    assert light == "G"


# ── 反向確認：橙燈確實來自 OOC，而非「SCADA/SPEC 設定不同步」那條橙燈 ──────────

def test_orange_here_comes_from_ooc_not_config_mismatch():
    """
    把 scada_* 填成與 SPEC 完全一致（不會觸發不同步橙燈），讀值仍在 OOC 區間 → 依然橙燈。
    反證：同樣的 scada_* 設定下讀值降到門檻以下就是綠燈，代表上面的橙燈確實由 OOC 判定而來。
    """
    common = dict(item="COD", oos="100", ooc="80", alert_spec="80",
                  scada_oos="100", scada_ooc="80", scada_alert="80")
    assert _calculate_light(_row(rvalue_raw="80", **common))[0] == "O"
    assert _calculate_light(_row(rvalue_raw="10", **common))[0] == "G"
