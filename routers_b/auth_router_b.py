"""
routers_b/auth_router_b.py — B 棧登入頁路由（Phase A 門面登入）

Phase A 階段沒有真正的身分驗證系統：CLAUDE.md 明訂 AD/LDAP 整合延後到 Phase 3
（見 docs/ad_integration_guide.md），現階段 current_user 在各 router 都是寫死 "admin"。
本檔的 POST /login 因此只是「門面」——只要帳號、密碼兩個欄位都有填就視為登入成功，
不做任何密碼驗證，直接導向 /home。等 Phase 3 接上真正的 LDAP 驗證後，這裡要換成
呼叫驗證服務、建立 session/token，並在失敗時導回 /login 顯示錯誤。
"""

from urllib.parse import parse_qsl

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/login", name="login_page_b")
def read_login_b(request: Request):
    """渲染登入頁（無動態資料，純樣板）。"""
    return templates.TemplateResponse(request=request, name="b/login.html", context={})


@router.post("/login", name="login_submit_b")
async def submit_login_b(request: Request):
    """Phase A 門面登入：不驗密碼，帳密皆非空即放行到 /home。

    Phase 3 導入 LDAP 後，這裡應改為呼叫實際的身分驗證服務，
    驗證失敗時導回 /login（可帶錯誤訊息），成功時建立 session 再導向 /home。

    註：這裡故意不用 FastAPI 的 `Form(...)` 參數——它（連同 Starlette 的
    `request.form()`）即使是純 `application/x-www-form-urlencoded` 也一律要求
    安裝 `python-multipart`，而本專案 requirements.txt 目前未收錄該套件。
    改用標準函式庫 `urllib.parse.parse_qsl` 手動解析表單本文，避免引入新依賴。
    """
    body = (await request.body()).decode("utf-8")
    data = dict(parse_qsl(body))
    username = data.get("username", "").strip()
    password = data.get("password", "")
    if not username or not password:
        return RedirectResponse("/login", status_code=303)
    return RedirectResponse("/home", status_code=303)
