"""
tests_integration/test_history_report_b.py — 真 PG 整合測試：異常記錄查詢/回覆 + 異常報表彙整

涵蓋 services_b/history_service.py 與 services_b/report_service.py。
直接用 ORM 建立 mail_log/mail_log_item 測試資料（不經過完整 dispatch 流程），
聚焦驗證 B 版查詢（mail_log_item 精確比對取代 A 版 msg1 LIKE）與統計彙整正確性。
"""

from datetime import datetime, timedelta, timezone

from models_b import MailLog, MailLogItem
from scripts.seed_test_data import TEST_PLANT_NO, SIGNER_EMPNO
from services_b import history_service as hs
from services_b import report_service as rs


def _make_log(db, plant_no: str, sent_at: datetime, body: str, items: list[tuple[str, str, bool]]) -> int:
    """建立一筆 mail_log + 對應 mail_log_item 明細（items: [(item, condition_code, is_maintenance)]）。"""
    log = MailLog(plant_no=plant_no, sent_at=sent_at, subject=body[:50], body_note=body)
    db.add(log)
    db.flush()
    for item, code, is_maint in items:
        db.add(MailLogItem(
            mail_log_id=log.id, item=item, condition_code=code,
            detail=f"|{item}|：{code}", escalation_stage=0, is_maintenance=is_maint,
        ))
    db.commit()
    return log.id


# ══════════════════════════════════════════════════════════════════════════
# history_service：查詢 + 回覆
# ══════════════════════════════════════════════════════════════════════════

def test_list_voclog_filters_by_plant_item_date_and_mt(b_db):
    d1 = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
    d2 = datetime(2026, 6, 15, 14, 0, tzinfo=timezone.utc)

    _make_log(b_db, TEST_PLANT_NO, d1, "Cu 超標通知", [("Cu", "OOS", False)])
    _make_log(b_db, TEST_PLANT_NO, d2, "pH 保養中通知", [("pH", "MAINTENANCE", True)])
    _make_log(b_db, "OTHER_PLANT", d1, "別廠通知", [("Cu", "OOS", False)])

    # 全區間查詢，不篩廠區/項目：應該只看到 TEST_PLANT_NO 的兩筆（廠區篩選）
    rows = hs.list_voclog(b_db, plant=TEST_PLANT_NO, sdate="2026/06/01", edate="2026/06/30", mt=True)
    assert len(rows) == 2
    assert {r["item"] for r in rows} == {"Cu", "pH"}

    # 篩項目
    rows_cu = hs.list_voclog(b_db, plant=TEST_PLANT_NO, item="Cu",
                              sdate="2026/06/01", edate="2026/06/30", mt=True)
    assert len(rows_cu) == 1
    assert rows_cu[0]["item"] == "Cu"

    # mt=False（排除保養中）：pH 那筆 is_maintenance=True 應該被排除
    rows_no_maint = hs.list_voclog(b_db, plant=TEST_PLANT_NO, sdate="2026/06/01",
                                    edate="2026/06/30", mt=False)
    assert len(rows_no_maint) == 1
    assert rows_no_maint[0]["item"] == "Cu"

    # 日期區間縮小到只涵蓋 d1
    rows_narrow = hs.list_voclog(b_db, plant=TEST_PLANT_NO, sdate="2026/06/01",
                                  edate="2026/06/01", mt=True)
    assert len(rows_narrow) == 1
    assert rows_narrow[0]["item"] == "Cu"


def test_update_reason_writes_reply_fields(b_db):
    """2026-07-31 C8：回覆改為逐項目，update_reason 改吃 item_id 複合鍵（非 logid）。"""
    d1 = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
    logid = _make_log(b_db, TEST_PLANT_NO, d1, "Cu 超標通知", [("Cu", "OOS", False)])

    item_id = hs._make_item_id(logid, "Cu", "OOS")
    hs.update_reason(b_db, item_id, "已確認為設備校正誤差", current_user_empno=SIGNER_EMPNO)

    rows = hs.list_voclog(b_db, plant=TEST_PLANT_NO, sdate="2026/06/01", edate="2026/06/30", mt=True)
    row = next(r for r in rows if r["logid"] == logid)
    assert row["reason"] == "已確認為設備校正誤差"
    assert row["rdatetime"] != ""
    # emp 欄位應該帶出 employee 快取表的姓名/notesid（見 seed_test_data._seed_identities）
    assert "測試簽核人" in row["emp"]
    assert "TEST_PLACEHOLDER" in row["emp"]


def test_update_reason_raises_for_unknown_item(b_db):
    """查無此項目、或 item_id 格式錯誤，都應 raise ValueError（C8 後改吃複合鍵字串）。"""
    import pytest
    with pytest.raises(ValueError):
        hs.update_reason(b_db, hs._make_item_id(999999, "Cu", "OOS"),
                          "不存在的紀錄", current_user_empno=SIGNER_EMPNO)
    with pytest.raises(ValueError):
        hs.update_reason(b_db, "格式錯誤的鍵", "x", current_user_empno=SIGNER_EMPNO)


# ══════════════════════════════════════════════════════════════════════════
# report_service：查詢明細 + 彙整（summary / pivot / ranking 皆為零修改重用的純函式）
# ══════════════════════════════════════════════════════════════════════════

def test_query_report_data_and_aggregations(b_db):
    d1 = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
    d2 = datetime(2026, 6, 2, 9, 0, tzinfo=timezone.utc)
    d3 = datetime(2026, 6, 3, 9, 0, tzinfo=timezone.utc)

    # TEST1：Cu 兩次、pH 一次；OTHER_PLANT：Cu 一次
    _make_log(b_db, TEST_PLANT_NO, d1, "m1", [("Cu", "OOS", False)])
    _make_log(b_db, TEST_PLANT_NO, d2, "m2", [("Cu", "OOS", False)])
    _make_log(b_db, TEST_PLANT_NO, d3, "m3", [("pH", "OOC", False)])
    _make_log(b_db, "OTHER_PLANT", d1, "m4", [("Cu", "OOS", False)])

    rows = rs.query_report_data(b_db, plant="", item="", sdate="2026/06/01", edate="2026/06/30", mt=True)
    assert len(rows) == 4

    summary = rs.build_summary(rows)
    # TEST1 三件、OTHER_PLANT 一件，按件數由大到小排序
    assert summary[0]["plantno"] == TEST_PLANT_NO
    assert summary[0]["count"] == 3
    assert summary[1]["plantno"] == "OTHER_PLANT"
    assert summary[1]["count"] == 1

    pivot = rs.build_pivot(rows)
    assert "Total" in pivot["columns"]
    total_row = next(r for r in pivot["rows"] if r["item"] == "總計")
    assert total_row["Total"] == 4

    ranking = rs.build_ranking(rows)
    assert ranking["rows"][0]["plantno"] == TEST_PLANT_NO
    assert ranking["rows"][0]["rank"] == 1

    # 篩單一廠區
    rows_test1_only = rs.query_report_data(b_db, plant=TEST_PLANT_NO, item="", sdate="2026/06/01",
                                            edate="2026/06/30", mt=True)
    assert len(rows_test1_only) == 3
    assert {r["item"] for r in rows_test1_only} == {"Cu", "pH"}


def test_default_date_range_and_validation_reused():
    """default_date_range / validate_date_range 是從 services.history_service 零修改重用。"""
    import pytest
    sdate, edate = rs.default_date_range()
    assert sdate <= edate
    with pytest.raises(ValueError):
        rs.validate_date_range("2026/06/30", "2026/06/01")
