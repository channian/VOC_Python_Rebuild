"""
tests_integration/test_history_reply.py — 真 PG 整合測試：異常回覆改成「逐項目層級」（C8）

2026-07-31 使用者確認的行為變更：舊系統（A 版）一封派報信（mail_log）只有一組回覆欄位，
一封信可能包含多個異常項目（mail_log_item 多筆），使用者回覆一次分不清是在回覆哪個項目。
新版把回覆三欄（reply_empno/reply_reason/reply_at）從 mail_log 搬到 mail_log_item，
改成每個異常項目各自回覆。

本檔涵蓋：
  - 一封信多個項目時，list_voclog() 回傳「以項目為單位」的列（每個 mail_log_item 一列）。
  - 對其中一個項目回覆後，只有該項目有回覆內容，同一封信的其他項目仍為空（本次改動核心價值）。
  - 重複回覆會覆蓋（同一項目再回覆一次，內容以最後一次為準）。
  - 重複呼叫 update_reason() 對不存在的 item_id 會丟 ValueError。
  - /ui/history（唯讀）與 /ui/reason（可回覆）兩個頁面都仍能正常渲染（走 FastAPI TestClient）。
"""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from models_b import MailLog, MailLogItem
from scripts.seed_test_data import TEST_PLANT_NO, SIGNER_EMPNO
from services_b import history_service as hs


def _make_log(db, plant_no: str, sent_at: datetime, body: str,
              items: list[tuple[str, str, bool]]) -> int:
    """建立一筆 mail_log + 對應 mail_log_item 明細（items: [(item, condition_code, is_maintenance)]）。
    對應 test_history_report_b.py 的同名 helper（禁止改該檔案，這裡另外複製一份，範圍不重疊）。"""
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
# list_voclog()：以項目為單位回傳
# ══════════════════════════════════════════════════════════════════════════

def test_list_voclog_returns_one_row_per_item_in_same_mail(b_db):
    d1 = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
    logid = _make_log(
        b_db, TEST_PLANT_NO, d1, "Cu/pH 同時超標通知",
        [("Cu", "OOS", False), ("pH", "OOC", False)],
    )

    rows = hs.list_voclog(b_db, plant=TEST_PLANT_NO, sdate="2026/06/01", edate="2026/06/30", mt=True)
    same_mail_rows = [r for r in rows if r["logid"] == logid]
    assert len(same_mail_rows) == 2
    assert {r["item"] for r in same_mail_rows} == {"Cu", "pH"}

    # 每一列都帶自己的 item_id（逐項目複合鍵字串），且互不相同
    item_ids = {r["item_id"] for r in same_mail_rows}
    assert len(item_ids) == 2
    for iid in item_ids:
        assert iid  # 非空字串
        assert str(logid) in iid


# ══════════════════════════════════════════════════════════════════════════
# update_reason()：逐項目回覆，互不影響
# ══════════════════════════════════════════════════════════════════════════

def test_reply_one_item_does_not_affect_other_items_in_same_mail(b_db):
    """本次改動的核心價值：同一封信裡回覆其中一個項目，另一個項目仍是空的。"""
    d1 = datetime(2026, 6, 2, 9, 0, tzinfo=timezone.utc)
    logid = _make_log(
        b_db, TEST_PLANT_NO, d1, "Cu/pH 同時超標通知",
        [("Cu", "OOS", False), ("pH", "OOC", False)],
    )

    rows = hs.list_voclog(b_db, plant=TEST_PLANT_NO, sdate="2026/06/01", edate="2026/06/30", mt=True)
    cu_row = next(r for r in rows if r["logid"] == logid and r["item"] == "Cu")
    ph_row = next(r for r in rows if r["logid"] == logid and r["item"] == "pH")

    hs.update_reason(b_db, cu_row["item_id"], "Cu 已確認為設備校正誤差", current_user_empno=SIGNER_EMPNO)

    rows2 = hs.list_voclog(b_db, plant=TEST_PLANT_NO, sdate="2026/06/01", edate="2026/06/30", mt=True)
    cu_row2 = next(r for r in rows2 if r["logid"] == logid and r["item"] == "Cu")
    ph_row2 = next(r for r in rows2 if r["logid"] == logid and r["item"] == "pH")

    # 只有 Cu 這個項目有回覆內容
    assert cu_row2["reason"] == "Cu 已確認為設備校正誤差"
    assert cu_row2["rdatetime"] != ""
    assert "測試簽核人" in cu_row2["emp"]

    # pH 項目完全沒有被動到
    assert ph_row2["reason"] == ""
    assert ph_row2["rdatetime"] == ""
    assert ph_row2["emp"] == ""


def test_reply_same_item_twice_overwrites(b_db):
    d1 = datetime(2026, 6, 3, 9, 0, tzinfo=timezone.utc)
    logid = _make_log(b_db, TEST_PLANT_NO, d1, "Cu 超標通知", [("Cu", "OOS", False)])

    rows = hs.list_voclog(b_db, plant=TEST_PLANT_NO, sdate="2026/06/01", edate="2026/06/30", mt=True)
    item_id = next(r for r in rows if r["logid"] == logid)["item_id"]

    hs.update_reason(b_db, item_id, "第一次回覆", current_user_empno=SIGNER_EMPNO)
    hs.update_reason(b_db, item_id, "第二次回覆（覆蓋）", current_user_empno=SIGNER_EMPNO)

    rows2 = hs.list_voclog(b_db, plant=TEST_PLANT_NO, sdate="2026/06/01", edate="2026/06/30", mt=True)
    row2 = next(r for r in rows2 if r["logid"] == logid)
    assert row2["reason"] == "第二次回覆（覆蓋）"


def test_update_reason_raises_for_unknown_item_id(b_db):
    with pytest.raises(ValueError):
        hs.update_reason(b_db, "999999||NoSuchItem||OOS", "不存在的紀錄", current_user_empno=SIGNER_EMPNO)


def test_update_reason_raises_for_malformed_item_id(b_db):
    with pytest.raises(ValueError):
        hs.update_reason(b_db, "not-a-valid-item-id", "格式錯誤", current_user_empno=SIGNER_EMPNO)


# ══════════════════════════════════════════════════════════════════════════
# /ui/history、/ui/reason 兩個頁面仍能正常渲染
# ══════════════════════════════════════════════════════════════════════════

def test_ui_history_and_reason_pages_render(b_db, monkeypatch):
    d1 = datetime(2026, 6, 4, 9, 0, tzinfo=timezone.utc)
    _make_log(b_db, TEST_PLANT_NO, d1, "Cu/pH 同時超標通知",
              [("Cu", "OOS", False), ("pH", "OOC", False)])

    from database_b import get_b_db
    import main_b

    def _override_get_b_db():
        yield b_db

    main_b.app.dependency_overrides[get_b_db] = _override_get_b_db
    try:
        client = TestClient(main_b.app)

        r_hist = client.get("/ui/history", params={
            "plant": TEST_PLANT_NO, "sdate": "2026/06/01", "edate": "2026/06/30", "mt": True,
        })
        assert r_hist.status_code == 200
        assert "異常查詢" in r_hist.text

        r_reason = client.get("/ui/reason", params={
            "plant": TEST_PLANT_NO, "sdate": "2026/06/01", "edate": "2026/06/30", "mt": True,
        })
        assert r_reason.status_code == 200
        assert "異常回覆" in r_reason.text
        # 逐項目回覆按鈕存在（item_id 透過 data-item-id 帶出）
        assert "data-item-id=" in r_reason.text
    finally:
        main_b.app.dependency_overrides.pop(get_b_db, None)


def test_history_reply_endpoint_updates_single_item(b_db, monkeypatch):
    d1 = datetime(2026, 6, 5, 9, 0, tzinfo=timezone.utc)
    logid = _make_log(b_db, TEST_PLANT_NO, d1, "Cu/pH 同時超標通知",
                       [("Cu", "OOS", False), ("pH", "OOC", False)])

    from database_b import get_b_db
    import main_b

    def _override_get_b_db():
        yield b_db

    main_b.app.dependency_overrides[get_b_db] = _override_get_b_db
    try:
        client = TestClient(main_b.app)
        rows = hs.list_voclog(b_db, plant=TEST_PLANT_NO, sdate="2026/06/01", edate="2026/06/30", mt=True)
        cu_item_id = next(r for r in rows if r["logid"] == logid and r["item"] == "Cu")["item_id"]

        resp = client.post("/history/reply", json={"item_id": cu_item_id, "reason": "端點測試回覆"})
        assert resp.status_code == 200

        rows2 = hs.list_voclog(b_db, plant=TEST_PLANT_NO, sdate="2026/06/01", edate="2026/06/30", mt=True)
        cu_row2 = next(r for r in rows2 if r["logid"] == logid and r["item"] == "Cu")
        ph_row2 = next(r for r in rows2 if r["logid"] == logid and r["item"] == "pH")
        assert cu_row2["reason"] == "端點測試回覆"
        assert ph_row2["reason"] == ""
    finally:
        main_b.app.dependency_overrides.pop(get_b_db, None)
