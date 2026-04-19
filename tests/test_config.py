from config import settings

def test_settings_loaded():
    """
    單位測試：驗證 config.py 是否能正確抓取預設或 .env 內的環境變數。
    確認重要的 Oracle 連線字串與 pyodbc 協定能正確被配置。
    """
    assert "mssql+pyodbc" in settings.DB_VOC_URL
    assert "oracle+oracledb" in settings.DB_CIM_URL
    assert "10.10.22.192" in settings.DB_CIM_URL
    assert settings.LDAP_SERVER == "ldap://KH"
