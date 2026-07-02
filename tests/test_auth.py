"""
test_auth.py — 登入邏輯純測試（只 import services/config，不 import routers 或 database）
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings
from services.auth_service import authenticate_user, LoginRequest


def test_mock_login_success():
    """ 驗證開發版的 Mock 登入防呆是否成功（AUTH_MOCK 預設 True）"""
    original = settings.AUTH_MOCK
    settings.AUTH_MOCK = True
    try:
        req = LoginRequest(emp_no="admin", password="admin")
        resp = authenticate_user(req)

        assert resp.success is True
        assert resp.message == "登入成功 (Mock)"
        assert resp.token is not None
        assert resp.emp_no == "admin"
    finally:
        settings.AUTH_MOCK = original


def test_mock_login_failure():
    """ 驗證失敗的帳密組合是否被正確阻擋（AUTH_MOCK=True 時） """
    original = settings.AUTH_MOCK
    settings.AUTH_MOCK = True
    try:
        req = LoginRequest(emp_no="admin", password="wrong_password")
        resp = authenticate_user(req)

        assert resp.success is False
        assert "錯誤" in resp.message
        assert resp.token is None
    finally:
        settings.AUTH_MOCK = original


def test_auth_mock_false_blocks_even_correct_mock_credentials():
    """
    AUTH_MOCK=False（正式環境設定）：即使帳密剛好是 admin/admin 也必須失敗，
    一律回「LDAP 尚未實作」訊息，不可放行 —— 這是避免正式環境誤留 Mock 通道的關鍵防線。
    """
    original = settings.AUTH_MOCK
    settings.AUTH_MOCK = False
    try:
        req = LoginRequest(emp_no="admin", password="admin")
        resp = authenticate_user(req)

        assert resp.success is False
        assert "LDAP" in resp.message
        assert resp.token is None
    finally:
        settings.AUTH_MOCK = original


def test_auth_mock_false_blocks_any_credentials():
    """AUTH_MOCK=False 時，任何帳密組合都應失敗（LDAP 本體尚未實作）。"""
    original = settings.AUTH_MOCK
    settings.AUTH_MOCK = False
    try:
        req = LoginRequest(emp_no="E001", password="whatever")
        resp = authenticate_user(req)
        assert resp.success is False
        assert "LDAP" in resp.message
    finally:
        settings.AUTH_MOCK = original


def test_login_requires_emp_no_and_password_regardless_of_mock():
    """空白員編/密碼應在檢查 AUTH_MOCK 前就被擋下，訊息與 AUTH_MOCK 狀態無關。"""
    original = settings.AUTH_MOCK
    try:
        for mock in (True, False):
            settings.AUTH_MOCK = mock
            resp = authenticate_user(LoginRequest(emp_no="", password=""))
            assert resp.success is False
            assert resp.message == "請輸入員工編號與密碼"
    finally:
        settings.AUTH_MOCK = original
