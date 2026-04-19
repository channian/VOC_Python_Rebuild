from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    系統通用環境變數設定
    透過 pydantic_settings 自動從系統環境變數或專案根目錄的 .env 載入
    """
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8')

    # App 相關設定
    APP_NAME: str = "VOC 管理平台"
    DEBUG: bool = False

    # SQL Server 資料庫連線 (預設為範例字串，請在 .env 中抽換為真實連線)
    DB_VOC_URL: str = "mssql+pyodbc://user:pass@localhost/VOC?driver=ODBC+Driver+17+for+SQL+Server"
    DB_SIGNFLOW_URL: str = "mssql+pyodbc://user:pass@localhost/SignFlow?driver=ODBC+Driver+17+for+SQL+Server"
    DB_UTIDB_URL: str = "mssql+pyodbc://user:pass@localhost/UTIDB?driver=ODBC+Driver+17+for+SQL+Server"
    
    # Oracle 資料庫連線 (已帶入自動從 Web.config 轉出之 OraCIMConnStr)
    DB_CIM_URL: str = "oracle+oracledb://fac-cim:faccim@10.10.22.192:1521/?service_name=facpdb"

    # LDAP 認證伺服器
    LDAP_SERVER: str = "ldap://KH"

# 實例化以便在專案各處匯入使用
settings = Settings()
