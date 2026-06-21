import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from schemas.maillist_schema import MailListAdd, MailListUpdate, MailListDelete
from services.maillist_service import (
    normalize_notesid, notesid_to_email, is_manual_empno,
    build_maillist_where, _tranlog_str,
)


# ── notesid 雙向轉換（舊系統 Replace 規則）────────────────────────────────
def test_normalize_notesid():
    assert normalize_notesid("John_Doe@aseglobal.com") == "John Doe"
    assert normalize_notesid("Mary_Wang") == "Mary Wang"
    assert normalize_notesid("  Tom_Lee@aseglobal.com ") == "Tom Lee"
    assert normalize_notesid("") == ""
    assert normalize_notesid(None) == ""


def test_notesid_to_email():
    assert notesid_to_email("John Doe") == "John_Doe@aseglobal.com"
    assert notesid_to_email("Mary Wang") == "Mary_Wang@aseglobal.com"
    assert notesid_to_email("") == ""
    # 來回轉換應穩定
    assert notesid_to_email(normalize_notesid("A_B@aseglobal.com")) == "A_B@aseglobal.com"


def test_is_manual_empno():
    assert is_manual_empno("環安群組") is True
    assert is_manual_empno("夜間值班") is True
    assert is_manual_empno("E001234") is False


# ── GetMailList WHERE 組裝（TO 嚴格 / CC 含 GMO、環工部）──────────────────
def test_build_where_to():
    where, params = build_maillist_where("水質異常", "K7", "TO")
    assert "rpttype = :rt0 AND plantno = :plantno" in where
    assert params["rt0"] == "水質異常"
    assert params["plantno"] == "K7"
    assert params["mailtype"] == "TO"
    # TO 不應出現 GMO/環工部
    assert "環工部" not in params.values()


def test_build_where_cc_includes_extra_plants():
    where, params = build_maillist_where("水質異常,水Alert", "K7", "CC")
    plant_vals = [v for k, v in params.items() if k.startswith("pl")]
    assert "K7" in plant_vals
    assert "GMO" in plant_vals
    assert "環工部" in plant_vals
    # 多個 rpttype 以 IN 列出
    assert params["rt0"] == "水質異常"
    assert params["rt1"] == "水Alert"
    assert "rpttype IN" in where


# ── tranlog 斜線串格式 ────────────────────────────────────────────────────
def test_tranlog_str():
    s = _tranlog_str("K7", "水質異常", "E001", "王小明", "Ming Wang", "0912345678",
                     "TO", 1, 0, 1)
    assert s == "K7/水質異常/E001/王小明/Ming Wang/0912345678/TO/要/否/是"


# ── schema 驗證 ───────────────────────────────────────────────────────────
def test_add_valid():
    d = MailListAdd(plantno="K7", rpttype="水質異常", empno="E001",
                    empname="王小明", notesid="Ming_Wang", mailtype="TO", mail=1)
    assert d.plantno == "K7"
    assert d.mailtype == "TO"


def test_add_mail_requires_notesid():
    with pytest.raises(Exception):
        MailListAdd(plantno="K7", rpttype="水質異常", empno="E001", mail=1, notesid="")


def test_add_sm_requires_cellphone():
    with pytest.raises(Exception):
        MailListAdd(plantno="K7", rpttype="水質異常", empno="E001",
                    notesid="A_B", mail=1, SM=1, cellphone="")


def test_add_cellphone_format():
    # 非 09 開頭
    with pytest.raises(Exception):
        MailListAdd(plantno="K7", rpttype="水質異常", empno="E001",
                    notesid="A_B", mail=1, SM=1, cellphone="0812345678")
    # 非 10 碼
    with pytest.raises(Exception):
        MailListAdd(plantno="K7", rpttype="水質異常", empno="E001",
                    notesid="A_B", mail=1, SM=1, cellphone="091234")
    # 正確
    d = MailListAdd(plantno="K7", rpttype="水質異常", empno="E001",
                    notesid="A_B", mail=1, SM=1, cellphone="0912345678")
    assert d.cellphone == "0912345678"


def test_add_invalid_mailtype():
    with pytest.raises(Exception):
        MailListAdd(plantno="K7", rpttype="水質異常", empno="E001",
                    notesid="A_B", mailtype="BCC")


def test_add_empty_required():
    with pytest.raises(Exception):
        MailListAdd(plantno="", rpttype="水質異常", empno="E001", notesid="A_B")
    with pytest.raises(Exception):
        MailListAdd(plantno="K7", rpttype="", empno="E001", notesid="A_B")
    with pytest.raises(Exception):
        MailListAdd(plantno="K7", rpttype="水質異常", empno="", notesid="A_B")


def test_update_requires_old_empno():
    d = MailListUpdate(plantno="K7", rpttype="水質異常", empno="E002",
                       old_empno="E001", notesid="A_B", mail=1)
    assert d.old_empno == "E001"
    with pytest.raises(Exception):
        MailListUpdate(plantno="K7", rpttype="水質異常", empno="E002",
                       old_empno="  ", notesid="A_B", mail=1)


def test_delete_schema():
    d = MailListDelete(plantno="K7", rpttype="水質異常", empno="E001")
    assert d.empno == "E001"


# ── mail=0 時不強制 notesid（純簽核群組成員等情境）─────────────────────────
def test_mail_off_allows_empty_notesid():
    d = MailListAdd(plantno="K7", rpttype="水質異常", empno="E001",
                    mail=0, notesid="", signgrp=1)
    assert d.mail == 0
    assert d.signgrp == 1
