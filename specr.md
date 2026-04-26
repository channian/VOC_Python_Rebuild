# VOC 系統重構 - 系統開發與需求規格書 (Specr)

## 專案概述
本專案的目標是以 Python 取代舊有巨大且難以維護的 `dbVOC.cs` 與 Web Forms 架構。所有修改與新功能之開發皆須紀錄於此文件中。

## 開發規劃與規格涵蓋率

為確保「所有舊系統細節都有被轉移涵蓋」，開發切分以下主要規格模組：

### 1. 驗證與權限規格 (Auth & ACL Spec)
- [ ] 串接 LDAP 驗證並發放 JWT (取代舊版 Windows 驗證)。
- [ ] 將 `dbAclRights.cs` 權限抽取成 FastAPI Dependency (存取白名單)。

### 2. 核心參數與資料驗證規格 (Spec Validation)
- [ ] 將 `EditSPEC` 內的所有檢核條件寫成 `Pydantic` Schema Validators。
- [ ] 在 `spec_service.py` 實作資料庫的 CRUD。

### 3. 主流程：簽核與申請規格 (Workflow Spec)
- [x] 實做 `SignFlow` 狀態機處理申請單新建、派送、核准與駁回 (`flow_service.py`)。
- [x] 開發網頁端及 API 提供：一般查詢、廠區查詢、待辦清單簽核。

### 4. 異常控制與預警規格 (Exception Spec)
- [x] 將廠區隔離 (`Control`) 機制獨立為可調用的 Service。
- [x] 當隔離發生或水質/雨水溝異常發生時，觸發背景程式發送 SMS 簡訊與 Email (`notify_service.py` & `warning_service.py`)。
- [x] **[重要安全機制]** 內建 `TEST_MODE` 雙軌並行攔截器。當開啟測試模式時，所有背景發送的 Email 與簡訊將被強制重新導向至開發者信箱/手機，防止與舊系統並行測試時發生「二次派報」。

## 修改歷史 (Changelog)
* **v1.0.0** - Phase 5 測試收尾與文件完備。完成 `flow_service` (簽核)、`warning_service` (預警) 與 `notify_service` (通知/簡訊) API 接口與單元測試。全系統架構支援舊版庫平行運行。
* **v0.2.0** - 預備推進 Phase 4 簽核流程與通報開發。完成 `spec` 與 `control` 重構。
* **v0.1.0** - 專案初始化，建立基本規格與開發準則。
