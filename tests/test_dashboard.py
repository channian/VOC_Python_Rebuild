import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.dashboard_service import _calculate_light, _parse_bounds, _bounds_mismatch


def _light(item="Cu", rvalue="", oos="", ooc="", alert="", recv="",
           scada_oos="", scada_ooc="", scada_alert="",
           cwms_oos="", cwms_ooc="", broken=0):
    """組一個 dashboard row dict 丟給 _calculate_light，回傳 (light, is_anomaly)。"""
    return _calculate_light(dict(
        item=item, rvalue_raw=rvalue, oos=oos, ooc=ooc, alert_spec=alert, recv=recv,
        scada_oos=scada_oos, scada_ooc=scada_ooc, scada_alert=scada_alert,
        cwms_oos=cwms_oos, cwms_ooc=cwms_ooc, broken=broken,
    ))


# ── 門檻解析 ──────────────────────────────────────────────────────────────
def test_parse_bounds():
    assert _parse_bounds("1.16") == (1.16, 1.16)   # 單邊
    assert _parse_bounds("6-9") == (6.0, 9.0)       # 雙邊（pH / K21 溫度）
    assert _parse_bounds("0") == (0.0, 0.0)          # "0" 是有效值（非未建點）
    assert _parse_bounds("-") is None                # 無效
    assert _parse_bounds("建置中") is None
    assert _parse_bounds("") is None
    assert _parse_bounds(None) is None


# ── 管制值不一致比對（含精度與 VOC 例外）─────────────────────────────────
def test_bounds_mismatch_precision():
    # SCADA 浮點精度：0.4999 四捨五入到 0.50，與 SPEC 0.5 視為相同（不亮橙）
    assert _bounds_mismatch("0.4999", "0.5") is False
    # 真實差異
    assert _bounds_mismatch("0.4", "0.5") is True
    # SCADA 存 "0" 而 SPEC 有真實值 → 未建點/設定不一致 → 亮橙（與舊系統一致）
    assert _bounds_mismatch("0", "0.5") is True
    # 任一邊無效 → 不比對
    assert _bounds_mismatch("-", "0.5") is False
    assert _bounds_mismatch("0.5", "建置中") is False


def test_bounds_mismatch_voc_exception():
    # VOC 項目：SCADA 比 SPEC 嚴（更低）→ 不算不一致
    assert _bounds_mismatch("4.0", "5.0", voc_exception=True) is False
    # VOC 項目：SCADA 比 SPEC 鬆（更高）→ 仍算不一致
    assert _bounds_mismatch("6.0", "5.0", voc_exception=True) is True
    # 非 VOC：低於也算不一致
    assert _bounds_mismatch("4.0", "5.0", voc_exception=False) is True


# ── 單邊規格燈號（多數項目，如 Cu）────────────────────────────────────────
def test_single_bound_lights():
    # 紅：讀值 >= OOS
    assert _light(rvalue="2.5", oos="2.0", ooc="1.16", alert="0.5") == ("R", False)
    # 橙（範圍）：OOC <= 讀值 < OOS
    assert _light(rvalue="1.5", oos="2.0", ooc="1.16", alert="0.5") == ("O", False)
    # 黃（alert）：Alert < 讀值 < OOC
    assert _light(rvalue="0.8", oos="2.0", ooc="1.16", alert="0.5") == ("Y", False)
    # 黃（recv）：讀值 > 允收值
    assert _light(rvalue="0.7", oos="2.0", ooc="1.16", alert="0.5", recv="0.6") == ("Y", False)
    # 綠：正常
    assert _light(rvalue="0.3", oos="2.0", ooc="1.16", alert="0.5", recv="0.6") == ("G", False)


def test_cu_regression_scada_precision():
    """本次 bug 回歸：Cu 讀值正常，但 SCADA alert=0.4999 因精度誤亮橙。修正後應為綠。"""
    got = _light(item="Cu", rvalue="0.03424124",
                 oos="2.0", ooc="1.16", alert="0.5", recv="0.6",
                 scada_oos="2.0", scada_ooc="1.16", scada_alert="0.49999")
    assert got == ("G", False)


# ── 雙邊規格燈號（pH、K21 溫度，'low-high' 格式，僅比上界）────────────────
def test_dual_bound_ph_lights():
    spec = dict(item="pH", oos="5-9.5", ooc="5.5-9", alert="6-8.5")
    assert _light(rvalue="7.5", **spec) == ("G", False)   # 正常
    assert _light(rvalue="9.8", **spec) == ("R", False)   # >= 上界 OOS
    assert _light(rvalue="9.2", **spec) == ("O", False)   # OOC上界 ~ OOS上界
    assert _light(rvalue="8.7", **spec) == ("Y", False)   # Alert上界 ~ OOC上界


# ── VOC 項目燈號例外 ──────────────────────────────────────────────────────
def test_voc_item_scada_exception():
    # SCADA OOS 比 SPEC 嚴（更低）→ 不亮橙（綠）
    assert _light(item="VOC", rvalue="0.1", oos="5.0", ooc="3.0",
                  scada_oos="4.0", scada_ooc="3.0") == ("G", False)
    # SCADA OOS 比 SPEC 鬆（更高）→ 仍亮橙
    assert _light(item="VOC", rvalue="0.1", oos="5.0", ooc="3.0",
                  scada_oos="6.0", scada_ooc="3.0") == ("O", False)


# ── 斷訊 / 保養中 / 無資料 ─────────────────────────────────────────────────
def test_anomaly_states():
    assert _light(rvalue="斷訊", oos="2.0") == ("-", True)
    assert _light(rvalue="N.D", oos="2.0") == ("-", True)
    assert _light(rvalue="1.0", oos="2.0", broken=1) == ("-", True)   # 斷訊
    assert _light(rvalue="1.0", oos="2.0", broken=2) == ("-", True)   # 保養中
    assert _light(rvalue="", oos="2.0") == ("-", True)                 # 無資料
