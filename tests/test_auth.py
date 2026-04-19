import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.auth_service import authenticate_user, LoginRequest

def test_mock_login_success():
    """ 驗證開發版的 Mock 登入防呆是否成功 """
    req = LoginRequest(emp_no="admin", password="admin")
    resp = authenticate_user(req)
    
    assert resp.success is True
    assert resp.message == "登入成功 (Mock)"
    assert resp.token is not None
    assert resp.emp_no == "admin"

def test_mock_login_failure():
    """ 驗證失敗的帳密組合是否被正確阻擋 """
    req = LoginRequest(emp_no="admin", password="wrong_password")
    resp = authenticate_user(req)
    
    assert resp.success is False
    assert "錯誤" in resp.message
    assert resp.token is None
