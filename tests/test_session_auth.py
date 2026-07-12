"""
test_session_auth.py — session 與 current_user 基礎設施純測試

自建一個最小 FastAPI app（不碰 main_b.py），掛上 SessionMiddleware +
services_b.session_auth.SessionAuthMiddleware，驗證：
  1. AUTH_MOCK=True 未登入 → 回 mock 身分（既有測試/沙盒相容）。
  2. AUTH_MOCK=True 已登入 → session 身分覆蓋 mock 身分。
  3. AUTH_MOCK=False 未登入 → GET html 302 /login；POST/API 401。
  4. AUTH_MOCK=False 已登入 → 正常放行、回真實身分。
  5. 允許清單（/login）未登入也可 200。

注意掛載順序（見 session_auth.py 檔頭註解）：SessionMiddleware 要「後 add」，
因為 add_middleware 是洋蔥由後往前，後 add 的先執行，SessionAuthMiddleware
才讀得到 SessionMiddleware 準備好的 request.session。
"""
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

from config import settings
from services_b.session_auth import SessionAuthMiddleware, get_current_user


def build_app() -> FastAPI:
    app = FastAPI()

    @app.get("/whoami")
    def whoami():
        empno, name = get_current_user()
        return {"empno": empno, "name": name}

    @app.post("/fake-login")
    async def fake_login(request: Request):
        body = await request.json()
        request.session["user"] = {"empno": body["empno"], "name": body.get("name", "")}
        return {"ok": True}

    @app.get("/login")
    def login_page():
        return {"page": "login"}

    # add_middleware 是洋蔥由後往前：後 add 的先執行。
    # 先 add SessionAuthMiddleware（後執行），再 add SessionMiddleware（先執行），
    # 這樣 SessionAuthMiddleware 執行時 request.session 才已經備妥。
    app.add_middleware(SessionAuthMiddleware)
    app.add_middleware(SessionMiddleware, secret_key="test-secret")

    return app


@pytest.fixture
def client():
    app = build_app()
    return TestClient(app)


def test_mock_true_no_login_returns_mock_user(client):
    """AUTH_MOCK=True 且未登入：/whoami 回 MOCK_USER_EMPNO（不擋、沙盒相容）。"""
    original = settings.AUTH_MOCK
    settings.AUTH_MOCK = True
    try:
        resp = client.get("/whoami")
        assert resp.status_code == 200
        assert resp.json()["empno"] == settings.MOCK_USER_EMPNO
    finally:
        settings.AUTH_MOCK = original


def test_mock_true_logged_in_overrides_mock(client):
    """AUTH_MOCK=True 但 session 已登入 TEST999：/whoami 應回 TEST999，session 蓋過 mock 預設值。"""
    original = settings.AUTH_MOCK
    settings.AUTH_MOCK = True
    try:
        login_resp = client.post("/fake-login", json={"empno": "TEST999", "name": "簽核人"})
        assert login_resp.status_code == 200

        resp = client.get("/whoami")
        assert resp.status_code == 200
        assert resp.json()["empno"] == "TEST999"
        assert resp.json()["name"] == "簽核人"
    finally:
        settings.AUTH_MOCK = original


def test_mock_false_not_logged_in_get_html_redirects_to_login(client):
    """AUTH_MOCK=False 且未登入：GET 且 Accept 含 text/html → 302 /login。"""
    original = settings.AUTH_MOCK
    settings.AUTH_MOCK = False
    try:
        resp = client.get("/whoami", headers={"accept": "text/html"}, follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers["location"] == "/login"
    finally:
        settings.AUTH_MOCK = original


def test_mock_false_not_logged_in_api_post_returns_401(client):
    """AUTH_MOCK=False 且未登入：POST/API（Accept json）→ 401。"""
    original = settings.AUTH_MOCK
    settings.AUTH_MOCK = False
    try:
        resp = client.post(
            "/fake-login",
            json={"empno": "TEST001"},
            headers={"accept": "application/json"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "未登入或連線階段已過期"
    finally:
        settings.AUTH_MOCK = original


def test_mock_false_logged_in_works_normally(client):
    """AUTH_MOCK=False 且已登入：/whoami 正常回真實身分。"""
    original = settings.AUTH_MOCK
    settings.AUTH_MOCK = True  # 先用 mock 模式登入，避免登入端點本身被守門擋下
    try:
        login_resp = client.post("/fake-login", json={"empno": "TEST001", "name": "申請人"})
        assert login_resp.status_code == 200

        settings.AUTH_MOCK = False
        resp = client.get("/whoami", headers={"accept": "application/json"})
        assert resp.status_code == 200
        assert resp.json()["empno"] == "TEST001"
        assert resp.json()["name"] == "申請人"
    finally:
        settings.AUTH_MOCK = original


def test_allowlist_login_path_accessible_without_login(client):
    """允許清單：/login 未登入也應 200（即使 AUTH_MOCK=False）。"""
    original = settings.AUTH_MOCK
    settings.AUTH_MOCK = False
    try:
        resp = client.get("/login", headers={"accept": "text/html"})
        assert resp.status_code == 200
        assert resp.json() == {"page": "login"}
    finally:
        settings.AUTH_MOCK = original
