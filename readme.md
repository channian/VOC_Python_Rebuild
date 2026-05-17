# VOC 廠務法規許可標準化管控平台（Python 重構）

ASP.NET Web Forms 舊系統的現代化重構。以 FastAPI + SQLAlchemy + Jinja2 取代原有 `dbVOC.cs` 巨石架構，雙軌並行運作直到驗證穩定。

---

## 技術棧

| 層次 | 技術 |
|---|---|
| Web 框架 | FastAPI + Uvicorn |
| 資料層 | SQLAlchemy 2.0 + pyodbc（連 SQL Server）|
| 資料驗證 | Pydantic v2 |
| 前端渲染 | Jinja2 Server-Side + HTMX（無 React/Vue）|
| 樣式 | 自製 `voc.css` 設計系統 + Bootstrap 5 |
| 通知 | smtplib（Email）、win32com（簡訊）|
| 測試 | Pytest |

---

## 快速啟動

```powershell
# 1. 建立設定檔（首次）
copy .env.example .env
notepad .env          # 填入 VOC_DB_URL 等連線資訊

# 2. 啟動服務
.venv\Scripts\activate
python main.py

# 3. 開啟首頁（用 Edge）
# http://localhost:8000/home

# 4. OpenAPI 文件
# http://localhost:8000/docs
```

> 詳細測試步驟 → [`docs/首頁測試流程.md`](docs/首頁測試流程.md)

---

## 雙軌並行 / 測試模式

新舊系統並行期間，設定 `.env` 防止重複發送通知：

```
TEST_MODE=True
TEST_DEV_EMAIL=你的信箱@asegroup.com
TEST_DEV_PHONE=09xxxxxxxx
```

`TEST_MODE=True` 時，所有 Email / 簡訊導向上面的測試帳號，標題加上 `[TEST MODE 攔截]`。  
**正式上線前**，將 `TEST_MODE=False` 並重啟服務。

---

## 專案結構

```
VOC_Python_Rebuild/
├── main.py                  # FastAPI 入口、路由掛載、靜態資源
├── database.py              # SQLAlchemy Engine / Session
├── config.py                # .env 設定讀取
├── models/                  # ORM 模型（對應 SQL Server 表結構）
│   └── spec_model.py        # VOC_SPEC, VOC_SCADA_WEB, VOC_plant...
├── schemas/                 # Pydantic 資料結構（輸入驗證 + 輸出格式）
│   └── dashboard_schema.py  # DashboardRow（燈號計算結果）
├── services/                # 業務邏輯
│   ├── dashboard_service.py # 燈號計算、SCADA vs SPEC 比對
│   ├── control_service.py   # 廠區隔離邏輯
│   ├── flow_service.py      # 簽核流程
│   ├── notify_service.py    # Email / 簡訊發送
│   └── warning_service.py   # 預警紀錄
├── routers/                 # FastAPI 路由
│   ├── home_router.py       # GET /home（首頁儀表板）
│   ├── control_router.py    # 廠區隔離
│   ├── spec_router.py       # 規格維護
│   ├── flow_router.py       # 簽核管理
│   ├── warning_router.py    # 預警紀錄
│   ├── acl_router.py        # 系統管理
│   └── ui_router.py         # HTMX 片段路由
├── templates/               # Jinja2 模板
│   ├── home.html            # 首頁儀表板（主畫面）
│   └── design/              # Claude Design 設計稿（靜態參考）
├── static/
│   └── css/voc.css          # 設計系統（燈號色、rowspan、來源底色）
└── docs/                    # 開發文件
    ├── 首頁測試流程.md       # Phase 1 測試步驟
    ├── 系統架構說明.md       # 架構圖（Mermaid）
    ├── 重構路線圖.md         # 五階段重構計畫
    └── JOB確認清單.md        # JOB 遷移待確認事項（18 題）
```

---

## 實作進度

| Phase | 內容 | 狀態 |
|---|---|---|
| Phase 1 | 首頁儀表板（燈號計算 + 資料顯示）| ✅ 完成 |
| Phase 2 | 廠區隔離 / 規格維護 / 預警 / 簽核 Modal | 🔲 架構建立，內容待實作 |
| Phase 3 | LDAP 登入 + 權限控制 | 🔲 尚未實作（目前直接進入）|
| Phase 4 | QA手測值 / 派送名單 / 異常查詢 / 報表匯出 | 🔲 尚未實作 |
| Phase 5 | JOB 遷移（Kepware → PostgreSQL）| 🔲 待確認（見 `docs/JOB確認清單.md`）|

---

## 燈號規則（與舊版 Home.aspx.cs 一致）

| 燈號 | 條件 |
|---|---|
| 🔴 紅 | 讀值 ≥ OOS |
| 🟠 橙 | OOC ≤ 讀值 < OOS，**或** SCADA / CWMS 管制值 ≠ SPEC 設定值 |
| 🟡 黃 | Alert < 讀值 < OOC，**或** 讀值 > 允收值 |
| 🟢 綠 | 正常 |
| ⬜ 灰 | 斷訊（broken=1）/ 保養中（broken=2）/ N.D / 無資料 |

> 修改燈號邏輯前，先跑 `pytest` 確認不破壞邊界條件。
