from fastapi.testclient import TestClient
from fastapi import FastAPI, BackgroundTasks
from services.notify_service import add_notification_task
import pytest

app = FastAPI()

@app.post("/notify")
def trigger_notify(background_tasks: BackgroundTasks):
    add_notification_task(background_tasks, "Test Subj", "Test Message", ["test@example.com"])
    return {"status": "ok"}

client = TestClient(app)

def test_trigger_notify():
    # This just ensures we can enqueue the background tasks without crashing
    response = client.post("/notify")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# ── ALWAYS_CC_EMAIL：測試用固定副本（所有信一律 CC 到自己，確認有寄出）─────────
from unittest import mock  # noqa: E402
from config import settings  # noqa: E402
import services.notify_service as notify  # noqa: E402


def _capture_sent(monkeypatch):
    """攔截 smtplib.SMTP，回傳一個會收集 send_message(msg) 的假 server。"""
    sent = []

    class _FakeSMTP:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def send_message(self, msg): sent.append(msg)

    monkeypatch.setattr(notify.smtplib, "SMTP", _FakeSMTP)
    return sent


def test_always_cc_added_in_real_send(monkeypatch):
    """TEST_MODE=False 真實寄送時，ALWAYS_CC_EMAIL 會被加進 Cc。"""
    monkeypatch.setattr(settings, "TEST_MODE", False)
    monkeypatch.setattr(settings, "ALWAYS_CC_EMAIL", "me@aseglobal.com")
    sent = _capture_sent(monkeypatch)

    notify.send_email_sync("主旨", "內文", ["colleague@aseglobal.com"])

    assert len(sent) == 1
    assert sent[0]["To"] == "colleague@aseglobal.com"
    assert "me@aseglobal.com" in sent[0]["Cc"]


def test_always_cc_supports_multiple_and_dedup(monkeypatch):
    """多個地址（逗號分隔）；已在收件人清單中的地址不重複加。"""
    monkeypatch.setattr(settings, "TEST_MODE", False)
    monkeypatch.setattr(settings, "ALWAYS_CC_EMAIL", "me@aseglobal.com, boss@aseglobal.com")
    sent = _capture_sent(monkeypatch)

    # me 已在 To → 不應再出現在 Cc；boss 應被加入 Cc
    notify.send_email_sync("主旨", "內文", ["me@aseglobal.com"])

    cc = sent[0]["Cc"] or ""
    assert "boss@aseglobal.com" in cc
    assert cc.count("me@aseglobal.com") == 0


def test_always_cc_empty_no_cc(monkeypatch):
    """ALWAYS_CC_EMAIL 留空時不加任何副本（維持原行為）。"""
    monkeypatch.setattr(settings, "TEST_MODE", False)
    monkeypatch.setattr(settings, "ALWAYS_CC_EMAIL", "")
    sent = _capture_sent(monkeypatch)

    notify.send_email_sync("主旨", "內文", ["colleague@aseglobal.com"])

    assert sent[0]["Cc"] is None
