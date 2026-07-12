"""
routers_b/auth_router_b.py — B 棧登入頁路由（AD/LDAP 串接版）

不再是門面登入：POST /login 會呼叫 `services_b.auth_ldap.authenticate()` 做真正的帳密驗證。
這裡採「平行包」防禦式引用——AD1 負責交付 `services_b/auth_ldap.py`（`authenticate()` /
`provision_user()`），本檔在 import 時包 try/except ImportError；只要 AD1 尚未交付（或
本機環境沒有該模組），就退回 Phase A 的門面語意：AUTH_MOCK=True 時帳密皆非空即放行
（name 直接用 username 頂替，沒有 dept_no/email 可提供）。等 AD1 的檔案就位後，兩邊
會自動接上、不需要再改這支檔案。

`AUTH_MOCK=True` 時（開發環境預設值），即使走到真正的 `authenticate()`，其實作本身也應
放行任意非空帳密（比照 services/auth_service.py 的既有慣例）——這讓登入頁本身變成「切換
測試身分」的入口：想用哪個員編登入就在登入頁打那個帳號，不必再手動改 .env 的
MOCK_USER_EMPNO 重啟服務。AUTH_MOCK=False（正式環境）才會是真正對接 LDAP 的驗證。

登入成功後在 B 棧 session（Starlette `request.session`，由 main_b 掛載的 SessionMiddleware
提供）寫入 `{"empno":..., "name":...}`，並呼叫 `provision_user()` 把使用者資料 upsert 進
Schema B（用獨立的 `BSessionLocal()` session，跟目前其他 router 走 `Depends(get_b_db)`
不同，因為登入 handler 不方便用 FastAPI Depends 包住"是否要開 DB session"這種條件邏輯，
故手動 try/finally 管理生命週期）。
"""

from urllib.parse import parse_qsl

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from database_b import BSessionLocal

router = APIRouter()
templates = Jinja2Templates(directory="templates")

try:
    from services_b.auth_ldap import authenticate, provision_user
except ImportError:
    # AD1 尚未交付 services_b/auth_ldap.py（或本機環境缺依賴）：退回 Phase A 門面語意。
    from config import settings

    class _FallbackUserInfo:
        """防禦式 fallback 用的最小 UserInfo 替身，欄位比照 AD1 介面約定。"""

        def __init__(self, empno: str, name: str):
            self.empno = empno
            self.name = name
            self.dept_no = None
            self.email = None

    def authenticate(username: str, password: str):  # type: ignore[misc]
        """Fallback：AUTH_MOCK=True 時帳密皆非空即放行；AUTH_MOCK=False 一律拒絕。"""
        if not settings.AUTH_MOCK:
            return None
        if not username or not password:
            return None
        return _FallbackUserInfo(empno=username, name=username)

    def provision_user(db, info):  # type: ignore[misc]
        """Fallback：services_b/auth_ldap.py 未就位時無 B 棧使用者表可寫，原樣回傳。"""
        return info


@router.get("/login", name="login_page_b")
def read_login_b(request: Request, error: str | None = None):
    """渲染登入頁。已登入（session 有 user）直接導向 /home，不必重新輸入帳密。

    query `error`：1＝帳號或密碼錯誤、2＝無法連線驗證伺服器（LDAP 連線例外）。
    """
    if request.session.get("user"):
        return RedirectResponse("/home", status_code=303)
    return templates.TemplateResponse(request=request, name="b/login.html", context={"error": error})


@router.post("/login", name="login_submit_b")
async def submit_login_b(request: Request):
    """帳密驗證 → 開 B 棧 session。

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
        return RedirectResponse("/login?error=1", status_code=303)

    try:
        info = authenticate(username, password)
    except Exception:
        # LDAP 連線例外（例如公司網路外連不到驗證伺服器）：不要讓 500 炸出去，導回登入頁。
        return RedirectResponse("/login?error=2", status_code=303)

    if info is None:
        return RedirectResponse("/login?error=1", status_code=303)

    db = BSessionLocal()
    try:
        info = provision_user(db, info)
        db.commit()
    finally:
        db.close()

    request.session["user"] = {"empno": info.empno, "name": info.name}
    return RedirectResponse("/home", status_code=303)


@router.get("/logout", name="logout_b")
def logout_b(request: Request):
    """清除 B 棧 session，導回登入頁。"""
    request.session.clear()
    return RedirectResponse("/login", status_code=303)
