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

    # ACL 權限強制模式
    # False（預設）：check_permission 權限不足時只記 log warning，仍然放行。
    #   目的是避免 sys_acluserrole/sys_aclrolerights 權限資料尚未建置完成時，把整個系統鎖死。
    # True：權限不足直接回傳 False，擋下操作。
    # ⚠️ 正式環境上線前必須確認 sys_acluserrole/sys_aclrolerights 資料完整後，將此值設為 True。
    ACL_ENFORCE: bool = False

    # 登入 Mock 模式
    # True（預設，開發用）：允許 admin/admin 假帳密直接登入，方便本機開發不需要真的連 LDAP。
    # False：停用 Mock，一律回「LDAP 尚未實作」訊息（LDAP 串接依專案決策延後）。
    # ⚠️⚠️ 正式環境部署前必須設為 False，否則任何人都能用 admin/admin 登入！
    AUTH_MOCK: bool = True

    # Mock 身分（B 棧閉環測試用）：current_user 尚未接 LDAP（Phase 3），B 棧 router 以
    # 這組設定扮演目前操作者。閉環測試「申請人≠簽核人」時，改 .env 的 MOCK_USER_EMPNO
    # 在 TEST001（申請人）與 TEST999（簽核人）之間切換即可（簽核排除申請人本人是舊系統
    # 原設計，自己不能簽自己的單）。LDAP 完成後此設定廢除。
    MOCK_USER_EMPNO: str = "admin"
    MOCK_USER_NAME: str = "系統管理員"

    # 雙軌並行測試模式 (Test Mode / Dry Run)
    TEST_MODE: bool = True
    TEST_DEV_EMAIL: str = "developer@asegroup.com"
    TEST_DEV_PHONE: str = "0912345678"

    # 測試用「固定副本」：所有寄出的信一律 CC 到這些地址，方便確認信件真的有寄出
    # （非上班時間也能自己收到副本驗證，不必等同事回報）。多個地址用逗號分隔。
    # 留空＝不加固定副本。TEST_MODE=True 時信件已全部改寄 TEST_DEV_EMAIL，此設定僅在
    # 真實寄送（TEST_MODE=False，實際寄給同事）時才有意義。正式上線務必清空。
    ALWAYS_CC_EMAIL: str = ""

    # ==========================================
    # Schema B（Phase A 重構版）資料庫連線
    # ==========================================
    # 測試/沙盒環境預設走本機 PostgreSQL（見 scripts/dev_pg.sh 建立的 voc/voc@voc_b）；
    # 正式環境引擎尚未定案（PG 或 MSSQL 皆有可能），因此 models_b.py 全部使用
    # SQLAlchemy 泛型型別，禁止寫死 PG 專屬方言（見 docs/schema_B_設計提案.md 第五節）。
    VOC_B_DB_URL: str = "postgresql+psycopg2://voc:voc@localhost/voc_b"

# 實例化以便在專案各處匯入使用
settings = Settings()
