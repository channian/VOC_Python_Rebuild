"""
tests/test_dispatch.py — dispatch_service 純邏輯測試（不依賴 DB）

涵蓋 evaluate_row（GetDataRed 移植）的燈號判斷、首發/再發判斷（4 小時重置 +
0/15/30 分鐘 escalation）、msg/msg1/msg2 格式，以及 GetMailList/GetMsg 系列
組字函式、HTML 信件版型純函式。
"""

from datetime import datetime, timedelta
from unittest.mock import patch

from services.dispatch_service import (
    DispatchResult,
    evaluate_row,
    build_plant_msg,
    build_plant_msg1,
    build_plant_msg2,
    plant_is_first,
    _rpttypes_for_plant,
    get_dispatch_maillist,
    build_subject,
    render_dispatch_email,
)


T0 = datetime(2026, 7, 2, 8, 0, 0)


def base_row(**overrides) -> dict:
    """預設一個「完全正常、不會觸發任何條件」的列，測試時只覆寫需要的欄位。"""
    row = {
        "plantno": "K7",
        "item": "COD",
        "rvalue_raw": "5",
        "rvalue": "5",
        "broken": 0,
        "oos": "20",
        "ooc": "15",
        "alert_spec": "50",   # 故意設很高，避免預設值誤觸發黃燈
        "recv": "100",        # 同上
        "scada_oos": "20",
        "scada_ooc": "15",
        "scada_alert": "50",
        "cwms_oos": "20",
        "cwms_ooc": "15",
    }
    row.update(overrides)
    return row


# ── 1. 首發 / 再發基本判斷 ──────────────────────────────────────────────

def test_first_dispatch_no_prev_record():
    """無前筆派報紀錄 → 首發。"""
    row = base_row(rvalue="25", rvalue_raw="25")  # 觸發紅燈 OOS
    result = evaluate_row(row, prev_mail=None, now=T0)
    assert result.is_first is True
    assert "水OOS-K7" in result.codes


def test_repeat_within_4hr_same_content_suppressed():
    """4 小時內、內容完全相同（非 OOC/OOS escalation 類條件）→ 不重發，codes 清空。"""
    row = base_row(rvalue="60", rvalue_raw="60", alert_spec="50", ooc="70", oos="200")  # 觸發 Alert<val<OOC 黃燈
    first_result = evaluate_row(row, prev_mail=None, now=T0)
    assert first_result.codes  # 首發有觸發

    prev_mail = {"cdatetime": T0, "msg1": first_result.msg1}
    repeat_result = evaluate_row(row, prev_mail=prev_mail, now=T0 + timedelta(minutes=5))
    assert repeat_result.codes == []
    assert repeat_result.is_first is False


def test_repeat_within_4hr_content_changed_is_first():
    """4 小時內，但異常內容跟上一筆不同 → 照樣視為首發。"""
    row = base_row(rvalue="60", rvalue_raw="60", alert_spec="50", ooc="70", oos="200")
    # 前一筆紀錄的內容是完全不同的條件（模擬另一種異常訊息）
    prev_mail = {"cdatetime": T0, "msg1": "|COD|：CWMS-OOS(斷訊)；"}
    result = evaluate_row(row, prev_mail=prev_mail, now=T0 + timedelta(minutes=5))
    assert result.is_first is True
    assert result.codes  # 內容變更，視為首發，codes 不清空


def test_repeat_after_4hr_is_first():
    """超過 4 小時 → 視為首發（逾時重置）。"""
    row = base_row(rvalue="25", rvalue_raw="25")  # 紅燈
    prev_mail = {"cdatetime": T0, "msg1": "|COD|：最新讀值＞＝SPEC-OOS"}
    result = evaluate_row(row, prev_mail=prev_mail, now=T0 + timedelta(hours=4, minutes=1))
    assert result.is_first is True
    assert result.codes


def test_exactly_4hr_0min_boundary_not_first():
    """剛好 4 小時整（分鐘=0）不算逾時 → 仍是再發判斷路徑（非「超過4小時」）。"""
    row = base_row(rvalue="25", rvalue_raw="25")
    # msg0 需含跟真實輸出一致的結尾全形分號，escalate() 才能正確比對出「上次是 cnt=0（無後綴）」
    prev_mail = {"cdatetime": T0, "msg1": "|COD|：最新讀值＞＝SPEC-OOS；"}
    result = evaluate_row(row, prev_mail=prev_mail, now=T0 + timedelta(hours=4))
    # 4:00 整剛好落在最終節流閘 "hours<4" 為 False 的邊界 → 不清空，escalation 前進到 15 分鐘代碼
    assert result.codes == ["水OOS15-K7"]
    assert result.is_first is False


# ── 2. 黃燈：兩條件 ──────────────────────────────────────────────────────

def test_yellow_alert_range():
    """Alert < 讀值 < SPEC-OOC → 黃燈。"""
    row = base_row(rvalue="12", rvalue_raw="12", alert_spec="10", scada_alert="10", ooc="15", oos="20")
    result = evaluate_row(row, prev_mail=None, now=T0)
    assert result.light == "Y"
    assert "水Alert-K7" in result.codes
    assert "Alert＜最新讀值＜SPEC-OOC" in result.msg1


def test_yellow_recv_exceed():
    """讀值 > 允收值 → 黃燈（與 Alert 條件共用同一代碼）。"""
    row = base_row(rvalue="9", rvalue_raw="9", alert_spec="50", recv="8", ooc="15", oos="20")
    result = evaluate_row(row, prev_mail=None, now=T0)
    assert result.light == "Y"
    assert "水Alert-K7" in result.codes
    assert "最新讀值＞允收值" in result.msg1


# ── 3. 橙燈：管制值不一致 ─────────────────────────────────────────────────

def test_orange_scada_mismatch():
    """SCADA-OOS 與 SPEC-OOS 不一致 → 橙燈。"""
    row = base_row(scada_oos="18", oos="20")
    result = evaluate_row(row, prev_mail=None, now=T0)
    assert result.light == "O"
    assert "水管制值不-K7" in result.codes
    assert "SCADA-OOS" in result.msg1 and "與SPEC-OOS不一致" in result.msg1


def test_orange_cwms_mismatch():
    """CWMS-OOC 與 SPEC-OOC 不一致 → 橙燈。"""
    row = base_row(cwms_ooc="14", ooc="15")
    result = evaluate_row(row, prev_mail=None, now=T0)
    assert result.light == "O"
    assert "水管制值不-K7" in result.codes
    assert "CWMS-OOC" in result.msg1


def test_maintenance_not_orange_and_excluded_from_msg2():
    """保養中特例：不亮橙燈，且不進 msg2（msg3），但仍記錄 codes 供追蹤。"""
    row = base_row(scada_oos="保養中", oos="20")
    result = evaluate_row(row, prev_mail=None, now=T0)
    assert result.light != "O"        # 不因保養中被判橙燈
    assert "水保養中-K7" in result.codes
    assert "保養中" in result.msg1     # msg1 仍記錄保養中
    assert result.msg2 == ""          # msg2 排除保養中項目，這裡應為空


def test_disconnect_scada_is_orange():
    """斷訊（非保養中）仍要亮橙燈，且要出現在 msg2。"""
    row = base_row(scada_oos="斷訊", oos="20")
    result = evaluate_row(row, prev_mail=None, now=T0)
    assert result.light == "O"
    assert "水斷訊-K7" in result.codes
    assert "斷訊" in result.msg2


def test_voc_exception_scada_stricter_not_mismatch():
    """VOC 項目例外：SCADA 比 SPEC 嚴（更低）時不算不一致，不觸發橙燈。"""
    row = base_row(item="VOC1", scada_oos="9", oos="10", scada_ooc="8", ooc="9",
                    scada_alert="50", cwms_oos="10", cwms_ooc="9", rvalue="1", rvalue_raw="1")
    result = evaluate_row(row, prev_mail=None, now=T0)
    assert result.codes == []
    assert result.light == "G"


def test_voc_no_exception_when_scada_looser():
    """VOC 項目：SCADA 比 SPEC 寬鬆（更高）時，仍要判定不一致（例外只適用「更嚴」的情況）。"""
    row = base_row(item="VOC1", scada_oos="12", oos="10", scada_ooc="9", ooc="9",
                    scada_alert="50", cwms_oos="10", cwms_ooc="9", rvalue="1", rvalue_raw="1")
    result = evaluate_row(row, prev_mail=None, now=T0)
    assert "空管制值不-K7" in result.codes


# ── 4. pH/溫度雙邊規格：取上界 ──────────────────────────────────────────

def test_ph_dual_bound_upper_triggers_red():
    """pH 雙邊規格 '6-9' 取上界(9) 比對；讀值 9.5 >= 9 → 紅燈。"""
    row = base_row(item="pH", oos="6-9", ooc="6-8", alert_spec="6-7", recv="6-20",
                    scada_oos="6-9", scada_ooc="6-8", scada_alert="6-7",
                    cwms_oos="6-9", cwms_ooc="6-8", rvalue="9.5", rvalue_raw="9.5")
    result = evaluate_row(row, prev_mail=None, now=T0)
    assert result.light == "R"
    assert "水OOS-K7" in result.codes


# ── 5. 紅燈 ──────────────────────────────────────────────────────────────

def test_red_rvalue_ge_oos():
    """讀值 >= SPEC-OOS → 紅燈。"""
    row = base_row(rvalue="25", rvalue_raw="25", oos="20")
    result = evaluate_row(row, prev_mail=None, now=T0)
    assert result.light == "R"
    assert "水OOS-K7" in result.codes
    assert "最新讀值＞＝SPEC-OOS" in result.msg1


def test_red_empty_value_and_empty_control():
    """讀值空、管制值也全空 → 紅燈（僅 broken=0 才進 codes）。"""
    row = base_row(rvalue="", rvalue_raw="", scada_oos="", scada_ooc="", scada_alert="", broken=0)
    result = evaluate_row(row, prev_mail=None, now=T0)
    assert result.light == "R"
    assert "水OOS-K7" in result.codes
    assert "水OOC-K7" in result.codes


def test_red_empty_value_broken_excludes_code():
    """讀值空、管制值全空，但 broken!=0（已知斷訊）→ 不重複進 codes。"""
    row = base_row(rvalue="", rvalue_raw="", scada_oos="", scada_ooc="", scada_alert="", broken=1)
    result = evaluate_row(row, prev_mail=None, now=T0)
    assert result.light == "R"
    assert result.codes == []


def test_oos_code_suppressed_when_broken():
    """讀值 >= OOS 但 broken!=0（斷訊中）→ OOS escalation 代碼不進 codes（燈號仍算紅燈）。"""
    row = base_row(rvalue="25", rvalue_raw="25", oos="20", broken=1)
    result = evaluate_row(row, prev_mail=None, now=T0)
    assert result.light == "R"
    assert result.codes == []  # OOS 的代碼因 broken!=0 被排除，且沒有其他條件觸發


# ── 6. OOC / OOS escalation：0 / 15 / 30 分鐘三段 + 滿三次停止 ─────────────

def test_ooc_escalation_sequence_and_stop():
    row = base_row(rvalue="17", rvalue_raw="17", ooc="15", oos="20")  # OOC <= 17 < OOS

    # 第一次（首發）：無 escalation 後綴
    r1 = evaluate_row(row, prev_mail=None, now=T0)
    assert r1.codes == ["水OOC-K7"]
    assert r1.is_first is True

    # 15 分鐘後：內容相同 → escalation 到 "15"
    r2 = evaluate_row(row, prev_mail={"cdatetime": T0, "msg1": r1.msg1}, now=T0 + timedelta(minutes=15))
    assert r2.codes == ["水OOC15-K7"]
    assert r2.is_first is False

    # 再 15 分鐘後：escalation 到 "30"
    t2 = T0 + timedelta(minutes=15)
    r3 = evaluate_row(row, prev_mail={"cdatetime": t2, "msg1": r2.msg1}, now=t2 + timedelta(minutes=15))
    assert r3.codes == ["水OOC30-K7"]
    assert r3.is_first is False

    # 再 15 分鐘後：已發滿 3 次 → 停止，codes 清空
    t3 = t2 + timedelta(minutes=15)
    r4 = evaluate_row(row, prev_mail={"cdatetime": t3, "msg1": r3.msg1}, now=t3 + timedelta(minutes=15))
    assert r4.codes == []
    assert r4.light == "O"  # 燈號仍是橙燈，只是不再派報


def test_ooc_not_at_15min_mark_suppressed():
    """OOC escalation 條件下，非剛好 15 分鐘節點 → codes 清空（等下一個 15 分鐘節點）。"""
    row = base_row(rvalue="17", rvalue_raw="17", ooc="15", oos="20")
    r1 = evaluate_row(row, prev_mail=None, now=T0)
    r2 = evaluate_row(row, prev_mail={"cdatetime": T0, "msg1": r1.msg1}, now=T0 + timedelta(minutes=5))
    assert r2.codes == []


def test_oos_escalation_sequence():
    """讀值 >= OOS 的紅燈 escalation，行為與 OOC 對稱。"""
    row = base_row(rvalue="25", rvalue_raw="25", oos="20")
    r1 = evaluate_row(row, prev_mail=None, now=T0)
    assert r1.codes == ["水OOS-K7"]

    r2 = evaluate_row(row, prev_mail={"cdatetime": T0, "msg1": r1.msg1}, now=T0 + timedelta(minutes=15))
    assert r2.codes == ["水OOS15-K7"]
    assert r2.light == "R"


# ── 7. msg / msg1 / msg2 格式（全形標點）與 K14B 判斷字樣 ──────────────────

def test_msg_format_uses_fullwidth_punctuation():
    row = base_row(rvalue="25", rvalue_raw="25", oos="20")
    result = evaluate_row(row, prev_mail=None, now=T0)
    assert "＞＝" in result.msg
    assert "；" in result.msg
    assert "|COD|" in result.msg1


def test_k14b_marker_appears_in_msg2_via_recv_condition():
    """K14B 跨廠通報依「＞允收值」字樣判斷，需出現在 DispatchResult.msg2。"""
    row = base_row(rvalue="9", rvalue_raw="9", alert_spec="50", recv="8", ooc="15", oos="20")
    result = evaluate_row(row, prev_mail=None, now=T0)
    assert "＞允收值" in result.msg2


def test_non_water_non_voc_item_no_escalation_code_but_light_set():
    """非水質相關、非 VOC 項目（can_escalate=False）：OOC/OOS 範圍仍設定燈號，但不產生派報代碼。"""
    row = base_row(item="導電度", rvalue="17", rvalue_raw="17", ooc="15", oos="20")
    result = evaluate_row(row, prev_mail=None, now=T0)
    assert result.light == "O"
    assert result.codes == []


# ── 8. GetMsg / GetMsg1 / GetMsg2 組字函式（跨列彙整）────────────────────

def test_build_plant_msg_functions_concat_in_order():
    r1 = DispatchResult(codes=["水Alert-K7"], msg="A：異常；", msg1="|A|：異常；", msg2="|A|：異常；", light="Y", is_first=True)
    r2 = DispatchResult(codes=["水OOS-K7"], msg="B：異常；", msg1="|B|：異常；", msg2="", light="R", is_first=False)
    results = [r1, r2]
    assert build_plant_msg(results) == "A：異常；B：異常；"
    assert build_plant_msg1(results) == "|A|：異常；|B|：異常；"
    assert build_plant_msg2(results) == "|A|：異常；"
    assert plant_is_first(results) is True  # 只要有一列是首發即整廠算首發


def test_plant_is_first_false_when_no_row_first():
    r1 = DispatchResult(codes=["水Alert-K7"], is_first=False)
    r2 = DispatchResult(codes=["水OOS-K7"], is_first=False)
    assert plant_is_first([r1, r2]) is False


# ── 9. GetMailList 名單抽取（_rpttypes_for_plant）──────────────────────

def test_rpttypes_for_plant_extracts_only_matching_plant():
    data_red = ["水Alert-K7", "水OOC15-K7", "水OOS-K9"]
    assert _rpttypes_for_plant(data_red, "K7") == "水Alert,水OOC15"
    assert _rpttypes_for_plant(data_red, "K9") == "水OOS"


def test_rpttypes_for_plant_dedup():
    data_red = "水Alert-K7,水Alert-K7,水OOC-K7"
    assert _rpttypes_for_plant(data_red, "K7") == "水Alert,水OOC"


def test_get_dispatch_maillist_empty_when_no_matching_plant():
    """給的 data_red 沒有任何代碼屬於指定廠區 → 回傳空清單，不查 DB。"""
    result = get_dispatch_maillist(db=None, data_red=["水Alert-K9"], plantno="K7", mailtype="TO")
    assert result == []


def test_get_dispatch_maillist_delegates_to_maillist_service():
    """驗證有比對到的情況會呼叫 maillist_service.get_mail_recipients 並回傳其結果。"""
    with patch("services.dispatch_service.get_mail_recipients", return_value=["a@aseglobal.com"]) as mocked:
        result = get_dispatch_maillist(db=None, data_red=["水Alert-K7"], plantno="K7", mailtype="TO")
    assert result == ["a@aseglobal.com"]
    mocked.assert_called_once_with(None, "水Alert", "K7", mailtype="TO")


# ── 10. 主旨 / HTML 信件版型（純函式）──────────────────────────────────

def test_build_subject_first_and_repeat():
    first_subj = build_subject("K7", True, T0)
    repeat_subj = build_subject("K7", False, T0)
    assert first_subj.startswith("【首發】請確認「法遵平台」即時監控狀況 : K7-")
    assert repeat_subj.startswith("【再發】請確認「法遵平台」即時監控狀況 : K7-")
    assert "(Security C)" in first_subj


def test_render_dispatch_email_contains_key_columns_and_no_unc_path():
    rows = [{
        "item": "COD", "unit": "mg/L", "law": "100", "oos": "20", "ooc": "15",
        "alert": "10", "recv": "18", "scada_oos": "20", "scada_ooc": "15",
        "scada_alert": "10", "cwms_oos": "20", "cwms_ooc": "15",
        "rvalue": "25", "light": "R", "remark": "", "source": 1,
    }]
    html = render_dispatch_email("K7", rows)
    assert "廠區" in html and "項目" in html and "法規許可值" in html
    assert "最新讀值" in html and "狀態" in html and "備註" in html
    assert "khfacsv01" not in html  # 不可殘留舊系統內網 UNC 圖片路徑
    assert "COD" in html and "K7" in html
