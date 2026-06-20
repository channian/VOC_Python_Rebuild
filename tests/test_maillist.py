import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from schemas.maillist_schema import MailListAdd, MailListDelete
import pytest


def test_add_valid():
    data = MailListAdd(plantno="K1", empno="E001", email="user@company.com", mailtype="TO")
    assert data.plantno == "K1"
    assert data.mailtype == "TO"


def test_add_cc():
    data = MailListAdd(plantno="K3", email="mgr@company.com", mailtype="CC")
    assert data.mailtype == "CC"
    assert data.empno == ""


def test_add_invalid_email():
    with pytest.raises(Exception):
        MailListAdd(plantno="K1", email="not-an-email", mailtype="TO")


def test_add_invalid_mailtype():
    with pytest.raises(Exception):
        MailListAdd(plantno="K1", email="a@b.com", mailtype="BCC")


def test_add_empty_plantno():
    with pytest.raises(Exception):
        MailListAdd(plantno="  ", email="a@b.com", mailtype="TO")


def test_add_empty_email():
    with pytest.raises(Exception):
        MailListAdd(plantno="K1", email="", mailtype="TO")


def test_delete_schema():
    d = MailListDelete(seqno=42)
    assert d.seqno == 42
