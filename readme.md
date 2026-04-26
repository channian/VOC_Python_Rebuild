# VOC 廠務法規許可標準化管理平台 (Python 重構現代化專案)

這是一個極為乾淨、依循 S.O.L.I.D. 原則，且大量配備自動化單元測試的現代化 FastAPI 核心系統。
專門為了汰換或雙軌並行舊版 ASP.NET (.aspx.cs) 巨石架構所打造。

## 一、 架構與技術棧

*   **框架**: FastAPI (極速建立現代化 API，內建非同步排程防護與依賴注入)
*   **資料層**: SQLAlchemy 2.0 (透過 `pyodbc` 對接 SQL Server，處理跨庫連線)
*   **防呆驗證**: Pydantic v2 (極度嚴謹的型別檢查，確保例外不進入資料庫)
*   **後端通訊**: Python `smtplib` (取代舊版 SmtpMessage)、`win32com.client` (串接舊版 SendSMS 簡訊機)
*   **單元測試**: Pytest (徹底保證系統能安心推進與重構)

## 二、 如何啟動

本系統可在 Windows 環境完美運行 (兼容內網 AD/SMTP 配置)：

1.  啟動獨立的 Python 虛擬環境：
    ```powershell
    .\venv\Scripts\Activate.ps1
    ```
2.  啟動後端整合測試伺服器：
    ```powershell
    uvicorn main:app --reload --host 0.0.0.0 --port 8000
    ```
3.  打開測試與除錯工具：
    瀏覽器直連 `http://127.0.0.1:8000/docs` 即可操作全套的自動生成 OpenAPI 操作指南，直接對內核發送修改指令或申請表單。

## 三、 雙軌並行測試模式 (Dry Run / Test Mode)

為了讓新舊系統並行測試時不會產生重複派送通知 (二次派報) 的問題，本系統內建了防呆攔截機制。

### 如何設定與調整
1. 請開啟專案根目錄下的 `.env` 檔案 (若無請複製 `.env.example` 建立)。
2. 確認並修改以下變數：
   - `TEST_MODE=True` (啟動測試攔截模式)
   - `TEST_DEV_EMAIL=developer@asegroup.com` (您的開發測試信箱)
   - `TEST_DEV_PHONE=0912345678` (您的開發測試手機號碼)
3. 當 `TEST_MODE=True` 時：
   - 所有的警報 Email 與簡訊**皆不會**發送給原本設定的廠區主管。
   - 所有的通知會被強制重新導向到您設定的 `TEST_DEV_EMAIL` 與 `TEST_DEV_PHONE`。
   - 信件標題將自動加上 `[TEST MODE 攔截]`，以供辨識。
4. **正式上線時**，請務必將 `.env` 中的 `TEST_MODE` 設為 `False`，並重啟 FastAPI 伺服器，系統即會切換為正式發信模式。

## 四、 專案核心解構 (Phase 1 ~ 5 v1.0 完備版)

我們把過去 230KB 極度耦合的 `dbVOC.cs`，依據現代微服務思維抽離成以下架構：

- `models/`：純宣告層。與舊有 SQL Server `VOC`、`SignFlow` 資料庫結構 1:1 對應。
- `schemas/`：安全護城河。例如 `control_schema.py` 直接擋下「開始時間大於一小時」的錯誤隔離申請。
- `services/`：業務邏輯大腦。
  - `control_service.py`: 管理廠區隔離邏輯與紀錄。
  - `flow_service.py`: 管理跨庫簽核流程的申請清單以及核准核退。
  - `notify_service.py` / `warning_service.py`: 取代舊版 `.aspx.cs` 直接綁定按鈕發信的惡夢，改由 FastAPI `BackgroundTasks` 以背後非同步寄送。
- `routers/`：介面層。把 Services 組裝起來，提供整齊劃一的 REST API。

> 任何功能變更前，請優先以 `.\venv\Scripts\pytest` 確保所有邊界條件不被破壞！
3. **測試驅動開發**: 任何小任務或單一路由開發完成前，必須撰寫並且通過單元測試。
