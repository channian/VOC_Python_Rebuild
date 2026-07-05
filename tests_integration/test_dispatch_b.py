"""
tests_integration/test_dispatch_b.py — 真 PG 整合測試：異常派報（services_b/dispatch_service.py）

涵蓋任務要求的四個情境：
  1. 首發（無 prev_mail）
  2. 4 小時內、內容不變 → 不重發（codes 清空）
  3. 內容變更（觸發不同條件）→ 即使在 4 小時內也立即算首發
  4. OOC/OOS escalation 遞進（0 → 15 分鐘 → 30 分鐘節點）

★ 測試策略：evaluate_row() 本身是從 services/dispatch_service.py 零修改重用的純函式，
其首發/再發/escalation 判斷邏輯已經在 tests/test_dispatch.py 用純邏輯測試覆蓋過，
本檔案的重點是驗證 **B 棧新寫的資料層轉接是否正確**：
  - get_data_b()：B 新形狀（spec 數值欄 + reading_current）→ evaluate_row 輸入形狀。
  - get_prev_mail() / insert_mail_log_b()：mail_log_item.detail 的寫入/讀回是否
    忠實還原 evaluate_row 需要的 prev_mail 形狀（★ 核心轉接設計）。

因此測試採「注入固定 now 時間點」而非依賴 datetime.now() 的真實時間流逝（run_dispatch_b()
本身用 datetime.now()，直接測試會受限於測試執行當下的實際時鐘，難以穩定驗證 15/30 分鐘節點），
改為直接呼叫 evaluate_row() + get_prev_mail() + insert_mail_log_b() 組合驗證整條資料流程，
這三個函式都是本 WP 實際交付的程式碼，並未繞過任何未經測試的邏輯。
"""

from datetime import datetime, timedelta, timezone

from services.dispatch_service import evaluate_row
from scripts.seed_test_data import TEST_PLANT_NO
from services_b import dispatch_service as ds


def _cu1_row(b_db) -> dict:
    """從 get_data_b() 抓一列真實的 Cu1 資料（B 資料層轉接後的 evaluate_row 輸入形狀）。"""
    rows = ds.get_data_b(b_db)
    cu1 = next(r for r in rows if r["plantno"] == TEST_PLANT_NO and r["item"] == "Cu")
    return cu1


def _with_value(row: dict, raw: str) -> dict:
    """複製一份 row，覆寫讀值（模擬不同時間點的即時讀值，不需要真的改 DB）。"""
    new_row = dict(row)
    new_row["rvalue_raw"] = raw
    new_row["rvalue"] = raw
    return new_row


def test_get_data_b_shape_matches_evaluate_row_expectations(b_db):
    """get_data_b() 轉接出來的欄位形狀應包含 evaluate_row 需要的全部鍵，且門檻已轉成字串形狀。"""
    row = _cu1_row(b_db)
    for key in ("plantno", "item", "rvalue_raw", "rvalue", "broken",
                "oos", "ooc", "alert_spec", "recv",
                "scada_oos", "scada_ooc", "scada_alert", "cwms_oos", "cwms_ooc"):
        assert key in row
    # Cu1 是單邊規格，oos_high=3.0 → 轉接後字串應為純數字（非 'low-high' 雙邊格式）
    assert row["oos"] == "3.0" or row["oos"] == "3"
    assert row["broken"] == 0


def test_first_dispatch_no_prev_mail(b_db):
    """情境 1：無 prev_mail → 首發。"""
    base = _cu1_row(b_db)
    row = _with_value(base, "2.80")  # OOC(2.5) <= 2.80 < OOS(3.0)

    prev = ds.get_prev_mail(b_db, TEST_PLANT_NO, "Cu")
    assert prev is None  # 尚未派報過

    t0 = datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc)
    result = evaluate_row(row, prev, t0)
    assert result.is_first is True
    assert result.codes  # 非空，OOC escalate 觸發
    assert "SPEC-OOC＜＝最新讀值＜SPEC-OOS" in result.msg1


def test_same_content_within_4h_not_redispatched(b_db):
    """情境 2：4 小時內、內容不變 → codes 清空，不重發。"""
    base = _cu1_row(b_db)
    row = _with_value(base, "2.80")
    t0 = datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc)

    first_result = evaluate_row(row, None, t0)
    log_id = ds.insert_mail_log_b(
        b_db, TEST_PLANT_NO, msg=first_result.msg, sent_at=t0, subject="首發測試",
        item_results=[("Cu", first_result)],
    )
    assert log_id is not None

    # 寫入後，get_prev_mail 應該能忠實撈回剛才 evaluate_row 產生的 msg1（★ 核心轉接設計）
    prev = ds.get_prev_mail(b_db, TEST_PLANT_NO, "Cu")
    assert prev is not None
    assert prev["msg1"] == first_result.msg1
    assert prev["cdatetime"] == t0

    # 1 分鐘後，同樣讀值（同內容）→ 不重發
    result2 = evaluate_row(row, prev, t0 + timedelta(minutes=1))
    assert result2.codes == []


def test_content_change_forces_first_even_within_4h(b_db):
    """情境 3：內容變更（OOC 條件 → OOS 條件）→ 即使在 4 小時內也立即算首發。"""
    base = _cu1_row(b_db)
    ooc_row = _with_value(base, "2.80")
    t0 = datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc)

    first_result = evaluate_row(ooc_row, None, t0)
    ds.insert_mail_log_b(b_db, TEST_PLANT_NO, msg=first_result.msg, sent_at=t0,
                         subject="首發測試", item_results=[("Cu", first_result)])
    prev = ds.get_prev_mail(b_db, TEST_PLANT_NO, "Cu")

    # 10 分鐘後讀值飆到 OOS 範圍（>=3.0），觸發的條件文字與先前的 OOC 文字不同
    oos_row = _with_value(base, "6.50")
    result2 = evaluate_row(oos_row, prev, t0 + timedelta(minutes=10))
    assert result2.is_first is True
    assert result2.codes
    assert "最新讀值＞＝SPEC-OOS" in result2.msg1


def test_escalation_progression_15_and_30_minutes(b_db):
    """情境 4：OOS escalation 遞進（0 分鐘首發 → 15 分鐘節點 → 30 分鐘節點）。"""
    base = _cu1_row(b_db)
    row = _with_value(base, "6.50")  # 明確超標（OOS=3.0）
    t0 = datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc)

    # 0 分鐘：首發
    r0 = evaluate_row(row, None, t0)
    assert r0.is_first is True
    ds.insert_mail_log_b(b_db, TEST_PLANT_NO, msg=r0.msg, sent_at=t0, subject="首發",
                         item_results=[("Cu", r0)])
    prev0 = ds.get_prev_mail(b_db, TEST_PLANT_NO, "Cu")

    # 5 分鐘：未到 15 分鐘節點、內容不變 → 不重發
    r_mid = evaluate_row(row, prev0, t0 + timedelta(minutes=5))
    assert r_mid.codes == []

    # 15 分鐘整：escalate 到第一階
    r15 = evaluate_row(row, prev0, t0 + timedelta(minutes=15))
    assert r15.codes
    assert "(15)" in r15.msg1
    ds.insert_mail_log_b(b_db, TEST_PLANT_NO, msg=r15.msg, sent_at=t0 + timedelta(minutes=15),
                         subject="再發15分", item_results=[("Cu", r15)])
    prev15 = ds.get_prev_mail(b_db, TEST_PLANT_NO, "Cu")
    assert prev15["msg1"] == r15.msg1  # get_prev_mail 應該撈到「最新」一筆（15分鐘那筆）

    # 30 分鐘整：escalate 到第二階
    r30 = evaluate_row(row, prev15, t0 + timedelta(minutes=30))
    assert r30.codes
    assert "(30)" in r30.msg1

    # mail_log_item.escalation_stage 應該對應存到 1（15 分鐘那筆）
    log_item_stage = ds._escalation_stage(r15.msg1)
    assert log_item_stage == 1
    assert ds._escalation_stage(r30.msg1) == 2


def test_condition_code_and_maintenance_flag_classification():
    """_primary_condition_code / _escalation_stage 純函式分類（不依賴 DB）。"""
    assert ds._primary_condition_code(["水OOS-K7"]) == "OOS"
    assert ds._primary_condition_code(["水OOC15-K7"]) == "OOC"
    assert ds._primary_condition_code(["水斷訊-K7"]) == "BROKEN"
    assert ds._primary_condition_code(["水保養中-K7"]) == "MAINTENANCE"
    assert ds._primary_condition_code(["水管制值不-K7"]) == "LIMIT_MISMATCH"
    assert ds._primary_condition_code(["水Alert-K7"]) == "ALERT"
    assert ds._escalation_stage("") == 0
    assert ds._escalation_stage("...(15)；") == 1
    assert ds._escalation_stage("...(30)；") == 2


def test_run_dispatch_b_end_to_end_sends_and_writes_mail_log(b_db):
    """
    run_dispatch_b() 端到端：Cu1 超標時應該產生 mail_log + mail_log_item，且收件人清單非空
    （測試內自建 mail_list 收件人，種子資料未提供 dispatch 專用 rpttype，見任務提示）。
    """
    from decimal import Decimal
    from models_b import ReadingCurrent, MailList, MailLog, MailLogItem

    rc = b_db.query(ReadingCurrent).filter_by(plant_no=TEST_PLANT_NO, item="Cu1").first()
    rc.value = Decimal("6.50")
    rc.raw_text = "6.50"
    rc.status = "normal"
    rc.comm_ok = True

    b_db.add(MailList(plant_no=TEST_PLANT_NO, rpttype="水OOS", emp_no="E_DISPATCH_TO",
                       emp_name="收件人", notes_id="dispatch_to", mail_type="TO",
                       mail_on=True, sign_grp=False))
    b_db.commit()

    captured = []
    original_send = ds.send_email_sync

    def _capture(subject, body, to_addresses, cc_addresses=None):
        captured.append((subject, to_addresses, cc_addresses))
        return original_send(subject, body, to_addresses, cc_addresses=cc_addresses)

    ds.send_email_sync = _capture
    try:
        summary = ds.run_dispatch_b(b_db)
    finally:
        ds.send_email_sync = original_send

    assert TEST_PLANT_NO in summary["sent"]
    assert captured, "應該至少寄出一封信（TEST_MODE 由 send_email_sync 內部攔截，不影響這裡的參數擷取）"
    subject, to_addrs, _cc = captured[0]
    assert "dispatch_to@aseglobal.com" in to_addrs

    log = b_db.query(MailLog).filter_by(plant_no=TEST_PLANT_NO).order_by(MailLog.sent_at.desc()).first()
    assert log is not None
    items = b_db.query(MailLogItem).filter_by(mail_log_id=log.id).all()
    assert any(i.item == "Cu" for i in items)
