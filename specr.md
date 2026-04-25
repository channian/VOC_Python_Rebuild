# VOC 系統重構 - 系統開發與需求規格書 (Specr)

## 專案概述
本專案的目標是以 Python 取代舊有巨大且難以維護的 `dbVOC.cs` 與 Web Forms 架構。所有修改與新功能之開發皆須紀錄於此文件中。

## 開發規劃與規格涵蓋率

為確保「所有舊系統細節都有被轉移涵蓋」，開發切分以下主要規格模組：

### 1. 驗證與權限規格 (Auth & ACL Spec)
- [ ] 串接 LDAP 驗證並發放 JWT (取代舊版 Windows 驗證)。
- [ ] 將 `dbAclRights.cs` 權限抽取成 FastAPI Dependency (存取白名單)。

### 2. 核心參數與資料驗證規格 (Spec Validation)
- [x] 將 `EditSPEC` 內的所有檢核條件寫成 `Pydantic` Schema Validators。
- [x] 在 `spec_service.py` 實作資料庫的 CRUD。

### 3. 主流程：簽核與申請規格 (Workflow Spec)
- [ ] 實做 `SignFlow` 狀態機處理申請單新建、派送、核准與駁回。
- [ ] 開發網頁端 HTMX 畫面給：一般查詢、廠區查詢、待辦清單簽核。

### 4. 異常控制與預警規格 (Exception Spec)
- [x] 將廠區隔離 (`Control`) 機制獨立為可調用的 Service。
- [ ] 當隔離發生或異常超標時，觸發背景發送 SMS 簡訊與 Email。

## 修改歷史 (Changelog)
* **v0.2.0** - 預備推進 Phase 4 簽核流程與通報開發。完成 `spec` 與 `control` 重構。
* **v0.1.0** - 專案初始化，建立基本規格與開發準則。
