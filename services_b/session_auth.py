"""
services_b/session_auth.py — Session 與 current_user 基礎設施（AD 串接前置作業）

背景（詳見 CLAUDE.md「已知待辦」與 docs/ad_integration_guide.md）：
    目前所有 router 的身分來自 settings.MOCK_USER_EMPNO/MOCK_USER_NAME（各 router 自己的
    _user()/寫死 "admin"）。本檔提供「單一真相」：一個 ContextVar 存放目前請求的
    (empno, name)，由 SessionAuthMiddleware 每請求從 Starlette session 填入；
    往後 router 的 _user() 改呼叫本檔 get_current_user() 即可（由主控收線時改，不在本檔範圍）。

掛載順序注意（給主控）：
    FastAPI/Starlette 的 add_middleware 是「洋蔥由後往前」——後 add 的先執行。
    SessionMiddleware 必須「比 SessionAuthMiddleware 晚 add」，才能讓 SessionMiddleware
    先執行、把 request.session 準備好，SessionAuthMiddleware 才讀得到 session：

        app.add_middleware(SessionAuthMiddleware)          # 先 add → 後執行
        app.add_middleware(SessionMiddleware, secret_key=getattr(settings, "SESSION_SECRET", "dev"))
                                                             # 後 add → 先執行

    （若順序顛倒，SessionAuthMiddleware 執行時 request.session 尚未被 SessionMiddleware
    的 ASGI 包裝設好，會直接 AttributeError / session 永遠是空的。）
"""
from contextvars import ContextVar, Token
from typing import Optional

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, RedirectResponse

from config import settings

# 目前請求的操作者 (empno, name)；None 代表尚未由 middleware 填入（例如純測試環境
# 直接呼叫 service 函式、沒有經過 request pipeline）。
_current_user: ContextVar[Optional[tuple]] = ContextVar("_current_user", default=None)

# 允許免登入直接放行的路徑前綴（AUTH_MOCK=False 時的守門白名單）。
_ALLOWED_PREFIXES = ("/login", "/logout", "/static", "/docs", "/openapi.json", "/redoc")


def get_current_user() -> tuple:
    """回傳 (empno, name)。

    優先順序：
      1. ContextVar 有值（SessionAuthMiddleware 已從 session 填入）→ 直接回傳。
      2. 沒有值時：
         - AUTH_MOCK=True → 回 (settings.MOCK_USER_EMPNO, settings.MOCK_USER_NAME)
           （沙盒/測試相容：所有既有測試不登入、不經過 middleware 也要能跑）。
         - AUTH_MOCK=False → raise HTTPException(401)（理論上到不了這裡，
           SessionAuthMiddleware 的守門會在更早之前就擋下未登入請求）。
    """
    user = _current_user.get()
    if user is not None:
        return user

    if settings.AUTH_MOCK:
        return (settings.MOCK_USER_EMPNO, settings.MOCK_USER_NAME)

    raise HTTPException(status_code=401, detail="未登入或連線階段已過期")


def _is_allowed_path(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in _ALLOWED_PREFIXES)


class SessionAuthMiddleware(BaseHTTPMiddleware):
    """每請求：從 request.session 讀 "user"，填入 ContextVar 給 get_current_user() 使用。

    守門（僅 AUTH_MOCK=False 時強制擋未登入請求；AUTH_MOCK=True 不擋任何請求，
    但 session 有 user 仍會填入 ContextVar，讓登入頁登入的身分能覆蓋 MOCK 預設值，
    使使用者能在登入頁切換 TEST001/TEST999 等測試帳號）：
      - 路徑在允許清單（/login /logout /static /docs /openapi.json /redoc）→ 一律放行。
      - 未登入且 Accept 含 text/html 且為 GET → 302 RedirectResponse("/login")。
      - 未登入其餘情形（API / POST 等）→ 401 JSONResponse({"detail": "未登入或連線階段已過期"})。
    """

    async def dispatch(self, request: Request, call_next):
        session_user = None
        try:
            session_user = request.session.get("user")
        except AssertionError:
            # SessionMiddleware 未掛載（例如某些測試直接繞過）時 request.session 會炸，
            # 視同未登入，交由下方邏輯處理。
            session_user = None

        path = request.url.path
        allowed = _is_allowed_path(path)

        if not settings.AUTH_MOCK and session_user is None and not allowed:
            accept = request.headers.get("accept", "")
            if request.method == "GET" and "text/html" in accept:
                return RedirectResponse(url="/login", status_code=302)
            return JSONResponse(status_code=401, content={"detail": "未登入或連線階段已過期"})

        token: Optional[Token] = None
        if session_user is not None:
            empno = session_user.get("empno") if isinstance(session_user, dict) else session_user[0]
            name = session_user.get("name") if isinstance(session_user, dict) else session_user[1]
            token = _current_user.set((empno, name))

        try:
            response = await call_next(request)
        finally:
            if token is not None:
                _current_user.reset(token)

        return response
