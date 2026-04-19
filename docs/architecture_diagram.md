# 廠務法規許可標準化管理平台 (VOC) - 網站架構圖

本網站基於目錄結構與配置內容 (`Web.config`、`Global.asax` 與 `App_Code`) 所繪製之系統架構圖分析如下：

## 系統架構圖

```mermaid
graph TD
    User([系統使用者]) -->|HTTP/HTTPS Request\n(Windows Authentication)| WebApp(網頁系統前端 ASP.NET Web Forms)
    
    subgraph "Application Server (IIS)"
        WebApp --> WebBackend("後端商業邏輯 (Code-behind .cs)")
        WebBackend --> CoreLogic("核心共用模組 (App_Code)")
        
        CoreLogic --> ModuleAuth[權限模組 dbAclRights]
        CoreLogic --> ModuleVoc[VOC業務模組 dbVOC]
        CoreLogic --> ModuleSign[簽核流程模組 dbSignFlow]
        CoreLogic --> ModuleUti[共用設施模組 dbUTIDB]
    end

    subgraph "第三方程式與整合服務"
        CoreLogic -.->|LDAP 查詢員工資訊| AD[Windows Active Directory]
        CoreLogic -.->|SmtpMessage 發送郵件| MailServer[SMTP Email Server]
        CoreLogic -.->|SendSMS 發送簡訊| SMSServer[SMS Gateway / 簡訊閘道]
    end

    subgraph "Database Layer (資料庫層)"
        CoreLogic -->|fac-cim / facpdb| CIM_DB[("Oracle DB (CIM)")]
        CoreLogic -->|VOC 資料連線| VOC_DB[("SQL Server (VOC)")]
        CoreLogic -->|SignFlow 簽核資料庫| SIGN_DB[("SQL Server (SignFlow)")]
        CoreLogic -->|UTIDB 公用資料庫| UTI_DB[("SQL Server (UTIDB)")]
    end
```

## 架構說明：
1. **前端與呈現層**：採用 **ASP.NET Web Forms** 開發 (`.aspx`)，搭配 `theme1` 佈景主題。
2. **驗證機制**：使用 **Windows 驗證** (Intranet 環境常見)，且會在 `Session_Start` 時串接 **LDAP (Active Directory)** 進行員工姓名與單位資料之查詢與綁定。
3. **核心服務與邏輯** (`App_Code`)：包含網站底層的資料流邏輯與流程設計：
   - `dbAclRights.cs`: 處理權限管控 (如 `GetIsAdmin`)。
   - `dbVOC.cs`, `dbUTIDB.cs`: 處理業務核心資料進出。
   - `dbSignFlow`: 建立與簽核處理機制有關的邏輯。
   - `SendSMS.cs`, `SmtpMessage.cs`: 封裝簡訊發送與電子信件通知功能。
4. **資料庫連線**：
   - 核心系統主要使用 **SQL Server**，對應業務分為 `VOC`, `SignFlow`, `UTIDB` 資料庫。
   - 另透過設定檔 (`Web.config`) 內的 `OraCIMConnStr` 連接 **Oracle 資料庫** (`facpdb`)，做為廠務 CIM 相關資料存取。
