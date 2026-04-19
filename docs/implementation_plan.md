# VOC 廠務法規許可標準化管理平台 - Python 徹底重建計畫書 (Draft)

因應團隊技能樹與未來維護便利性，本專案將由傳統微軟 `ASP.NET Web Forms + C#` 徹底轉換為現代化的 `Python` 網路架構。

本計畫書確保**「每一個舊有環節都有對應的新解法」**，不會遺漏任何核心業務邏輯與介接層。

---

## 一、 技術棧轉換對照表 (Technology Mapping)

所有的微軟依賴將百分之百轉移至成熟穩定的開源 Python 生態系。

| 系統環節 | 舊方案 (ASP.NET) | 新方案推薦 (Python Ecosystem) | 轉換原因與效益 |
| --- | --- | --- | --- |
| **後端框架** | ASP.NET Web Forms (.aspx.cs) | **FastAPI** | 開發極速，原生支援非同步，自帶 OpenAPI 說明文檔，S.O.L.I.D 與依賴注入 (DI) 的實作極為優雅。 |
| **前端呈現** | .aspx + ViewState | **Jinja2 + HTMX + Bootstrap** | 完全無需學習 JS 框架。使用 Python 後端渲染 Jinja2，搭配 HTMX 實現無重整的動態畫面更新。 |
| **資料庫溝通** | 手刻 SQL (`SqlDataReader`) | **SQLAlchemy + Pydantic** | ORM 將資料庫操作物件化，再由 Pydantic 負責法規與輸入資料防呆驗證。 |
| **跨庫連線** | `System.Data.OracleClient`<br>`SqlConnection` | **pyodbc** (SQL Server)<br>**oracledb** (Oracle CIM) | SQLAlchemy 原生支援這兩種底層連線庫。 |
| **身分驗證** | `<authentication mode="Windows"/>`<br>`Global.asax: LDAP` | **ldap3 套件 + JWT Token** | 後端透過 `ldap3` 向 Active Directory 驗證密碼，核發 Session/Token。 |
| **背景通知** | `SmtpMessage.cs`, `SendSMS.cs` | **FastAPI BackgroundTasks** | 將寄信與發簡訊改為背景非同步執行，不卡住使用者畫面。 |
| **單元測試** | 無 / 難以測試 | **Pytest** | 完全符合您「完成前必須有單元測試」的核心要求。 |

---

## 二、 核心商業邏輯解構與模組化對應表

我們將終結龐大的 `dbVOC.cs` 與纏繞的 `.aspx.cs`，依據功能領域拆分為以下 Python Routers (API 介面) 與 Services (商業邏輯層)：

### 1. 權限與身分模組 (取代 `Global.asax` 與 `dbAclRights.cs`)
*   **模組名稱**: `auth_service.py` / `acl_service.py`
*   **涵蓋頁面**: `EditAclUser`, `EditDeptList` 等後台設定頁。
*   **執行細節**: 實作 Active Directory 驗證。撰寫裝飾器或依賴函數 (`Dependency`) 攔截無權限的路由存取 (例如特定畫面僅 Admin 可讀取)。

### 2. 法規參數與資料核心 (取代 `<EditSPEC>`)
*   **模組名稱**: `spec_service.py`
*   **涵蓋頁面**: `EditSPEC`, `EditQA`
*   **執行細節**: 最重要的一環。法規上下限與規格將成為 Pydantic 的資料模型，確保後續任何 API 寫入前都必須自動經過驗證機制。

### 3. 表單送件與簽核系統 (取代 `dbSignFlow.cs`)
*   **模組名稱**: `apply_service.py` / `flow_service.py`
*   **涵蓋頁面**: `ApplySPEC`, `PlantApply`, `MyApply`, `SignSPEC`, `SignControl`
*   **執行細節**: 將舊有的簽核狀態（待簽核、駁回、結案）寫成狀態機 (State Machine)，所有的簽核行為抽離成純邏輯，以便針對各情境撰寫 Pytest 驗證。

### 4. 異常與廠區隔離模組 (取代大量邏輯混合)
*   **模組名稱**: `control_service.py` / `warning_service.py`
*   **涵蓋頁面**: `EditControl`, `ModifyControl`, `ControlTime`, `VOCreason`, `VOChistory`, `WaterUrgent`, `RainGutter`
*   **執行細節**: 此模組處理所有廠區例外。觸發警報條件時，將直接呼叫背景任務 (BackgroundTasks) 發送 Mail 或 SMS。

---

## 三、 五大開發執行階段 (Execution Phases)

重建專案絕對不能停機，我們將採取系統性的階段交付：

### **Phase 1: 基礎設施構建與骨架打造 (Week 1)**
*   使用 GH (GitHub) 建立版本庫，設定 Python 環境 (`requirements.txt` 或 `poetry`)。
*   設定資料庫連線池引擎（SQL Server x3、Oracle x1）。
*   實作 `LDAP3` 登入核心並建立 `Login` 畫面測試。

### **Phase 2: 系統設定與讀取端移植 (Week 2-3)**
*   處理「唯讀」的儀表板頁面：`Home`。
*   建置權限設定後台：`EditDeptList`、`EditAclUser` 的 CRUD (新增修改刪除)。
*   建置站內參數總管：`EditSPEC` (包含建立核心的 SQLAlchemy Models)。

### **Phase 3: 核心申請單與防呆邏輯移植 (Week 4-6)**
*   *最困難的階段*。AI 會在這裡深度解析原本 `dbVOC.cs` 之中關於「廠區管制條件」的 C# 邏輯。
*   用純 Python 重寫與隔離驗證器，並撰寫**大量的 Pytest 單元測試**確保防呆機制與舊版行為 100% 同步。
*   完成各類 `Apply` (申請) 與 `Control` (廠區隔離設定) 網頁的操作。

### **Phase 4: 封閉簽核迴圈與通報對接 (Week 7-8)**
*   建置 `SignFlow` (簽核流) 的 API 與畫面互動。
*   對接 SMTP 與簡訊發送。
*   完成所有預警畫面 (`WaterUrgent`, `RainGutter`) 的資料綁定。

### **Phase 5: 測試覆蓋與平行運行 (Week 9)**
*   使用 Playwright 為 Python 版新網頁撰寫重要的 E2E 網頁點擊測試。
*   新舊系統接上同一個測試資料庫，比對運算結果。

---

## 四、 給團隊的承諾與保障
1.  **無任何 JS 負擔**：使用 HTMX，團隊依然像在寫傳統伺服器渲染網頁，有任何資料變更全在 Python 端處理。
2.  **S.O.L.I.D. 嚴格貫徹**：未來任何一個模組發生異常，我們都可以立刻定位是在哪一個 `service.py`，絕不會出現 230KB 的怪物檔案。
3.  **無痛解譯舊代碼**：舊系統的 C# 到 Python 的解析翻譯，皆由我來承擔處理，直接交由您審閱與測試。

*(請參閱這份 [實作計畫書](file:///C:/Users/sideshowhan/.gemini/antigravity/brain/83bfe73c-f640-4d5d-bcff-8a1c8de4267c/implementation_plan.md) 以作為此次重構的共識起點。)*
