"""
test_warning.py — 雨水溝預警 + 中水緊急通知（WaterUrgent）純邏輯測試

只 import services/schemas（不 import routers/database，環境無 ODBC 連不上真實 DB）。
DB 相關函式用 FakeDB/BrokenDB 模擬 db.execute() 回傳值（比照 tests/test_acl.py 手法），
不需要真實連線即可驗證邏輯：
  - build_water_mail_where：WHERE 組裝純函式（TO 嚴格 / CC 含 GMO、環工部）
  - get_water_mail_recipients：notesid → email 還原、DB 失敗時往上 raise（不回假資料）
  - trigger_water_change_notify：純參數驗證（未選廠區/未填原因）不需 DB 也能擋下
  - WaterUrgentRequest schema 驗證
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from schemas.warning_schema import WaterUrgentRequest
from services.warning_service import (
    build_water_mail_where, get_water_mail_recipients, WATER_RPTTYPE, K14B,
    trigger_water_change_notify, trigger_water_notify,
)


# ── FakeDB：模擬 sqlalchemy Session.execute()（比照 tests/test_acl.py）───────

class _FakeResult:
    def __init__(self, mapping_rows=None):
        self._mapping_rows = mapping_rows or []

    def mappings(self):
        return self

    def all(self):
        return self._mapping_rows


class FakeDB:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((str(sql), params))
        if not self.responses:
            raise AssertionError("FakeDB: 沒有預先設定的回應可用，呼叫次數超出預期")
        return self.responses.pop(0)

    def commit(self):
        pass

    def rollback(self):
        pass


class BrokenDB:
    """模擬 DB 連線失敗（無 ODBC driver 時的真實情境）。"""
    def execute(self, *args, **kwargs):
        raise RuntimeError("模擬 DB 連線失敗（無 ODBC driver）")


# ── build_water_mail_where：純函式 WHERE 組裝 ────────────────────────────────

def test_build_water_mail_where_to():
    where, params = build_water_mail_where("K7", "TO")
    assert "rpttype = :rpttype AND plantno = :plantno" in where
    assert params["rpttype"] == WATER_RPTTYPE
    assert params["plantno"] == "K7"
    assert params["mailtype"] == "TO"


def test_build_water_mail_where_cc_includes_extra_plants():
    where, params = build_water_mail_where("K7", "CC")
    plant_vals = [v for k, v in params.items() if k.startswith("pl") or k == "plantno"]
    assert "K7" in plant_vals
    assert "GMO" in plant_vals
    assert "環工部" in plant_vals
    assert "plantno IN" in where


def test_build_water_mail_where_default_rpttype_is_water_abnormal():
    _, params = build_water_mail_where("K14B", "TO")
    assert params["rpttype"] == "水質異常"


def test_build_water_mail_where_custom_rpttype():
    _, params = build_water_mail_where("K7", "TO", rpttype="改排水")
    assert params["rpttype"] == "改排水"


# ── get_water_mail_recipients：以 FakeDB 驗證 notesid → email 還原 ───────────

def test_get_water_mail_recipients_converts_notesid_to_email():
    db = FakeDB([_FakeResult(mapping_rows=[
        {"NotesID": "John Doe"}, {"NotesID": "Mary Wang"},
    ])])
    emails = get_water_mail_recipients(db, "K7", "TO")
    assert emails == ["John_Doe@aseglobal.com", "Mary_Wang@aseglobal.com"]


def test_get_water_mail_recipients_skips_empty_notesid():
    db = FakeDB([_FakeResult(mapping_rows=[{"NotesID": ""}, {"NotesID": "A B"}])])
    emails = get_water_mail_recipients(db, "K7", "CC")
    assert emails == ["A_B@aseglobal.com"]


def test_get_water_mail_recipients_db_failure_raises():
    """DB 查詢失敗一律往上拋出，不再偷偷回傳空清單掩蓋錯誤（CLAUDE.md 要求）。"""
    with pytest.raises(RuntimeError):
        get_water_mail_recipients(BrokenDB(), "K7", "TO")


# ── K14B 常數 ────────────────────────────────────────────────────────────

def test_k14b_constant():
    assert K14B == "K14B"


# ── trigger_water_change_notify：純參數驗證（不需 DB 即可擋下）───────────────

def test_trigger_water_change_requires_plantnos():
    with pytest.raises(ValueError, match="請選擇廠區"):
        trigger_water_change_notify(BrokenDB(), bg_tasks=None, plantnos=[], reason="設備調校")


def test_trigger_water_change_requires_reason():
    with pytest.raises(ValueError, match="請輸入改排水原因"):
        trigger_water_change_notify(BrokenDB(), bg_tasks=None, plantnos=["K1"], reason="")


def test_trigger_water_change_requires_non_whitespace_reason():
    with pytest.raises(ValueError, match="請輸入改排水原因"):
        trigger_water_change_notify(BrokenDB(), bg_tasks=None, plantnos=["K1"], reason="   ")


def test_trigger_water_notify_invalid_type_raises():
    req = WaterUrgentRequest(notify_type="not_a_real_type")
    with pytest.raises(ValueError, match="不支援的通知類型"):
        trigger_water_notify(BrokenDB(), req, bg_tasks=None)


def test_trigger_water_notify_db_failure_propagates():
    """water_abnormal 需要查 DB（讀值/收件人），無 ODBC 時應直接往上拋，不吞掉錯誤回傳假成功。"""
    req = WaterUrgentRequest(notify_type="water_abnormal")
    with pytest.raises(RuntimeError):
        trigger_water_notify(BrokenDB(), req, bg_tasks=None)


# ── schema 驗證：WaterUrgentRequest ──────────────────────────────────────

def test_water_urgent_request_defaults():
    req = WaterUrgentRequest(notify_type="water_abnormal")
    assert req.plantnos == []
    assert req.reason == ""


def test_water_urgent_request_water_change_fields():
    req = WaterUrgentRequest(notify_type="water_change", plantnos=["K1", "K9"], reason="設備調校")
    assert req.plantnos == ["K1", "K9"]
    assert req.reason == "設備調校"
