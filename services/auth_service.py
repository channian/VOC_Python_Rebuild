from pydantic import BaseModel
from config import settings

class LoginRequest(BaseModel):
    """ 登入請求參數規格 """
    emp_no: str
    password: str

class LoginResponse(BaseModel):
    """ 登入回傳結果 """
    success: bool
    message: str
    token: str | None = None
    user_name: str | None = None
    emp_no: str | None = None

def authenticate_user(request: LoginRequest) -> LoginResponse:
    """
    商業邏輯：驗證使用者登入
    依照舊有 Global.asax，將連線至 LDAP 伺服器 (LDAP://KH) 進行 Auth
    """
    if not request.emp_no or not request.password:
        return LoginResponse(success=False, message="請輸入員工編號與密碼")
        
    # --- 開發版 Mock 防呆 (不需要真的連線 AD 也能開發推進) ---
    if request.emp_no == "admin" and request.password == "admin":
        return LoginResponse(
            success=True, 
            message="登入成功 (Mock)", 
            token="dummy-jwt-token-abcd", 
            user_name="系統管理員",
            emp_no="admin"
        )
        
    # --- 正式機邏輯 (待正式環境啟用) ---
    # 這裡將取代舊版 MTDBbase.Get員工姓名 ... "LDAP://KH" 的機制
    # server = ldap3.Server(settings.LDAP_SERVER, get_info=ldap3.ALL)
    # conn = ldap3.Connection(server, user=f"{request.emp_no}@YOUR_DOMAIN", password=request.password)
    # if conn.bind():
    #     取得姓名等資訊並發布 JWT Token
    #     ...
    
    return LoginResponse(success=False, message="帳號或密碼錯誤 (Active Directory Authentication Failed)")
