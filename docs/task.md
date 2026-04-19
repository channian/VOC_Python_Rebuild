# VOC_Python_Rebuild 開發任務清單

## Phase 1: 基礎基礎設施構建
- [x] 建立專案骨架 (`main.py`, `pytest.ini`, `requirements.txt`)
- [x] 成功執行第一個通過的單元測試
- [x] 撰寫資料庫連線引擎設定 (`database.py`)，連接三個 SQL Server 與 Oracle
- [x] 將舊的 C# 連線字串移植到 `.env` 環境變數配置
- [x] 實作包含 LDAP 驗證邏輯的 `auth_service.py` 雛形
- [x] 建立 `tests/test_config.py` 進行設定 Mock 單元測試

## Phase 2: 系統設定與讀取端移植
- [x] 實作 Home 儀表板的資料查詢 API
- [x] 導入 Glassmorphism 企業級介面拋光 (`home.html`)
- [x] 實作權限設定與維護的 CRUD (`acl_service.py`)
- [ ] 將 `EditSPEC` 的資料對應到 Pydantic / SQLAlchemy Models

## Phase 3: 核心與防呆移植
- [ ] ... (待 Phase 2 完成後細化)
