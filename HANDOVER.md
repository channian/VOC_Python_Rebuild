# VOC 平台重構交接文件

> 給新 Session 的 Claude：請完整讀完這份文件再開始動手。
> 所有重要決策的「為什麼」都在這裡，不要從零推論。

---

## 一、系統是什麼

**廠務法規許可標準化管控平台**（VOC 平台）  
ASP.NET Web Forms 舊系統的 Python FastAPI 重構版。

功能：監控工廠各廠區的廢水／空污排放數值（pH、VOC、COD、SS 等），
依三層門檻（OOS > OOC > Alert）自動計算燈號，超標時發送 Email 通知。
（通知管道決策 2026-06-11：SMS 已停用不移植、PushPlus 暫不實作，只留 Email）

舊系統：`dbVOC.cs`（4,931 行單一 C# class，全部業務邏輯在裡面）
新系統：本 repo，FastAPI + SQLAlchemy + Jinja2 + HTMX

---

## 二、目前實作進度

### ✅ Phase 1 — 首頁儀表板（完成並測試通過）

| 項目 | 狀態 |
|---|---|
| 從 DB 查詢最新讀值與規格值 | ✅ |
| 燈號計算（R/O/Y/G/-）| ✅ |
| SCADA vs SPEC 管制值比對（橙燈第二條件）| ✅ |
| 廠區 rowspan 合併顯示 | ✅ |
| 讀值欄底色依資料來源（SCADA/CWMS/QA）| ✅ |
| 斷訊/保養中/N.D 斜線紋路 | ✅ |
| 倒數計時器（每 15 分鐘刷新）| ✅ |
| voc.css 設計系統 | ✅ |

### ✅ Phase 2 — Modal 功能面板

| Modal | 狀態 | 說明 |
|---|---|---|
| 廠區隔離 | ✅ 完成 | 有效隔離清單 + 申請表單（廠區下拉 → HTMX 動態載入項目 checkbox → JSON POST `/control/create`）|
| 規格維護 | ✅ 完成 | inline 編輯：每列「編輯」→ 欄位轉 input/select →「儲存」POST `/spec/update` |
| QA 手測值 | ✅ 完成 | Phase 4 提前完成。列出 source=QA 項目，輸入數值或 N.D 寫入 `VOC_SCADA_WEB.rvalue` |
| 預警紀錄 | ✅ 基礎 | 顯示目前紅/橙燈項目 |
| 簽核管理 | ✅ 基礎 | 顯示待簽核清單，核准/退回按鈕已有 HTMX |
| 系統管理 | 🔲 卡片 | AD/LDAP 已決定延後到最後處理 |

### 🔲 Phase 3 — LDAP 登入 + 權限控制（未實作）

- `auth_service.py` 目前是 mock，`check_permission()` 永遠回傳 True
- `home_router.py` 沒有驗證，直接進 `/home`
- `current_user` 沒有傳進 template context（template 已預留位置用 `{# #}` 標記）
- AD / LDAP 整合說明在 `docs/ad_integration_guide.md`

### 🔶 Phase 4 — 其他頁面（進行中）

- ✅ QA 手測值輸入（舊版 EditQA.aspx）— `qa_service.py` / `qa_router.py` / `qa_modal.html`
- 🔲 派送名單維護（舊版 EditMailList.aspx）
- 🔲 異常件數查詢（舊版 VOChistory.aspx）
- 🔲 異常原因回覆（舊版 VOCreason.aspx）
- 🔲 異常報表匯出（舊版 VOCreport.aspx）
- 🔲 廠區 / 項目動態新增管理（`tag_mapping` table Admin UI）
- 🔲 異常 Email 通知（移植 SendMail.cs 的 VOC 報表，詳見 `docs/JOB確認清單.md` 第七節）

### 🔲 Phase 5 — JOB 遷移（暫緩，待架構決策）

見下方「架構層面的未決事項」。
舊 JOB 原始碼（dbVOC.cs / Program.cs / SendMail.cs）已分析完畢，
重點結論都整理在 `docs/JOB確認清單.md`（Q4-Q11/Q13/Q15/Q16 已確認 + 第七節通知流程）。

---

## 已知問題（待修，動相關功能前先看）

> 2026-06-21：取得舊網頁端原始碼後，**完整落差清單見 `docs/legacy_source_analysis.md` 第五節**。下表為摘要。

| # | 問題 | 位置 | 說明 |
|---|---|---|---|
| 1 | ccno 流水號寫死 `001` | `control_service.create_control()` | 同日撞號。舊系統查當日 `MAX(ccno)` 後 3 碼 +1 補零（交易內）|
| 2 | ~~VOC 項目 SCADA 比對例外未實作~~ ✅ 已修 | `dashboard_service._bounds_mismatch()` | 已實作 `voc_exception` 參數。回歸測試 `test_voc_item_scada_exception` |
| 3 | Tag 名稱比對靜默失敗（舊 JOB 行為，新 JOB 要避免） | 舊 dbVOC.cs | 名稱不符直接跳過不報錯 → 讀值空白。新 JOB 必須「比對不到就告警」 |
| 4 | 🔴 **ACL 權限全開** | `acl_service.check_permission` | 直接 return True，無權限管控。須實作 `sys_acluserrole + sys_aclrolerights` 位元檢查 |
| 5 | 🔴 **隔離自動核准** | `control_service.create_control` | `b_pass→fstatusid=3` 跳過簽核；舊系統免簽核已停用、一律走簽核 |
| 6 | 🔴 **隔離時間上限錯** | `control_schema.py` / `control_service.py` | Python 用 4hr，舊系統一律 1 小時 |
| 7 | 🟠 **派送名單需重寫** | `maillist_*` | 真實 schema 主鍵 `(plantno,rpttype,empno)`，欄位差異大 |
| 8 | 🟠 規格簽核流程 / 廠區 ACL 過濾 / SPEC 驗證 / item 別名 缺失 | `spec_service` / `control_service` | 詳見分析文件第五節 #5~#7 |

### 燈號邏輯重構紀錄（2026-06-18，已取得完整 Home.aspx.cs 原始碼後對齊）

逐行核對舊 `Home.aspx.cs` 的 `GetData(gvRow)` 後修正三處與舊系統的落差：

1. **雙邊規格（pH / K21 溫度）**：舊碼 `Split('-')` 取上界 `[1]` 比對。
   新版用 `_parse_bounds()` 格式驅動解析 `'6-9' → (6.0, 9.0)`，單/雙邊自動相容。
   **修正前 pH/溫度因 `_safe_float('6-9')=None` 永遠顯示綠燈（嚴重 bug）。**
2. **SCADA 精度**：舊碼比對前先 `ChangeData(text, 2)` 四捨五入到小數 2 位。
   新版 `_bounds_mismatch` 用 `round(x, 2)`，避免 SCADA `0.4999` vs SPEC `0.5` 誤亮橙。
3. **VOC 例外**：見上方已知問題 #2。

**⚠️ 待用戶確認的舊系統行為**：雙邊規格（pH/溫度）的燈號**只比上界**（`[1]`），
舊碼完全不檢查下界。意即 pH 過低（偏酸）在舊系統也顯示綠燈。
新版忠實沿用此行為。若要改為「過低也示警」需用戶確認後再加（屬功能增強，非 bug 修復）。

---

## 三、關鍵業務邏輯

### 燈號計算規則（`services/dashboard_service.py`）

```
broken != 0  →  '-'（灰）斷訊 / 保養中
rvalue 為非數字文字  →  '-'（灰）

rvalue >= OOS  →  'R'（紅）
OOC <= rvalue < OOS  →  'O'（橙）
SCADA 或 CWMS 的管制值 ≠ SPEC 設定值  →  'O'（橙）← 重要！
Alert < rvalue < OOC  →  'Y'（黃）
rvalue > recv（允收值）→  'Y'（黃）
其他  →  'G'（綠）
```

> 門檻一律經 `_parse_bounds()` 取「高界」，單邊（`1.16`）與雙邊（pH/溫度 `6-9`）皆相容。
> SCADA/SPEC 比對先 `round(x, 2)` 對齊舊系統四捨五入。VOC 項目有 SCADA 更嚴例外。
> 詳見上方「燈號邏輯重構紀錄」。

**SCADA vs SPEC 比對**：
SCADA 系統會把自己設的警報值（OOS_HH / OOC_H / alert）存在 `VOC_SCADA_WEB`。
如果這些值與 `VOC_SPEC` 三階文件的值不一致（代表有人改了其中一邊但忘了同步），
就亮橙燈。只有兩邊都是有效數字時才比對，`-`/`N/A`/`建置中` 等視為無效跳過。

**broken 欄位含義**：
- `0` → 正常
- `1` → 斷訊（SCADA Tag 品質異常，由 JOB 寫入）
- `2` → 保養中 / 隔離中（由 Web 端隔離申請觸發）

### 廠區分組 rowspan

`_annotate_plant_groups()` 在 service 層後處理，
為每列設 `plant_rowspan`、`show_plant`、`plant_has_red`。
Template 只需 `{% if row.show_plant %}` 控制是否渲染 `<td>`。

### 資料來源

`VOC_SPEC.source`（int）：`1=SCADA, 2=CWMS, 3=QA手測`
Template 用 `src-{{ row.source }}` CSS class 決定讀值欄底色。

---

## 四、重要的技術決策（不要改掉）

### 1. 燈號不讀 DB 存的 light 欄位

舊系統的 JOB 和 Web 各計算一次 `light` 存進 DB，是技術債。
新系統在 `_calculate_light()` 從原始讀值重新計算，不讀 `VOC_SCADA_WEB.light`。
（例外：`warning_service.get_current_anomalies()` 仍讀 `light` 欄位做快速篩選，可接受）

### 2. Modal 用原生 `<dialog>`，不用 Bootstrap Modal

`home.html` 用 `<dialog id="voc-modal">` + HTMX 動態載入 partials。
所有 partial 模板的關閉按鈕一律用：
```html
onclick="document.getElementById('voc-modal').close()"
```
**不要用 `data-bs-dismiss="modal"`**，那是 Bootstrap Modal 的語法，在 `<dialog>` 裡無效。

### 3. Jinja2 不會跳過 HTML 注解

`<!-- {% if %} -->` 裡的 `{% %}` 和 `{{ }}` 仍會被 Jinja2 解析。
備忘用的 Jinja2 語法一律用 `{# 說明文字 #}`，不要放進 `<!-- -->`。
這個錯誤在 Phase 1 已經犯過並修掉了。

### 4. SQL Server 中文路徑問題

專案放在含中文字的 Windows 路徑下，Bash 工具有亂碼問題。
一律用 `Read` / `Write` / `Edit` 工具操作檔案，避免 `cat` / `ls` 中文路徑。

---

## 五、架構層面的未決事項（重要，動手前先確認）

### JOB 遷移架構決策（與用戶討論中，尚未定案）

目前：iFIX Historian → JOB → MSSQL（`VOC_SCADA_WEB`）→ 網頁

用戶傾向未來拿掉 iFIX Historian，改成：Kepware（OPC-UA）→ JOB → PostgreSQL → 網頁

**影響評估**（已與用戶討論）：

| 功能 | 影響 |
|---|---|
| 首頁 table 最新讀值 | ✅ 無影響，Kepware 直接輪詢即可 |
| 燈號計算 | ✅ 無影響，邏輯在 service 層 |
| 雨水溝三點連升邏輯（K1/K9）| ⚠️ 需要自存三筆歷史，設計 history 表 |
| 24hr 累積雨量（TwentyFourHours）| ⚠️ 目前來自 PMS.dbo.Water_WindRainHistValue，需確認 PMS 資料源 |
| 歷史曲線圖（VOC_Curve URL）| ❌ 功能消失，需決定是否自建或移除 |

**目前決策**：先照舊 MSSQL schema 完成重構，架構變更後續再討論。
在此之前，`models/spec_model.py` 的 `VocScadaWeb` 對應舊 MSSQL schema，不要改。

18 個 JOB 確認問題見 `docs/JOB確認清單.md`。
2026-06-11 已從舊 JOB 原始碼確認 11 題，剩 7 題（Q1-Q3, Q12, Q14, Q17-Q18）為架構決策。

**舊 JOB 架構速查**（來自 Program.cs）：
- `SCADA_VOC` 指令每 15 分鐘：連 10+ 台 iFIX Historian（K12 有 3 台 IH4/5/6；K11 另有 Oracle WWT 雙來源）
  → `UpdateVOCData()` → `InsertVOCHistValue()` → 00:00 跑日平均
- `GETCWMS` 指令：HTTP JSON API 取 CWMS 值（K14B, K5, K7, K11, K22, K21）
- `VOC` 指令：異常 Email 派報（首發/再發判斷、K14B 跨廠通報，詳見 JOB確認清單第七節）

---

## 六、專案結構速查

```
VOC_Python_Rebuild/
├── main.py                      # 入口：7 個 router + StaticFiles
├── database.py                  # SQLAlchemy Engine（VOC_DB_URL from .env）
├── config.py                    # .env 設定讀取
│
├── models/
│   └── spec_model.py            # ORM：VocSpec, VocScadaWeb, VocPlant, VocItem...
│
├── schemas/
│   ├── dashboard_schema.py      # DashboardRow（燈號計算輸出）
│   ├── control_schema.py        # ControlCreate, ApplyListResponse...
│   └── spec_schema.py           # SpecResponse（LAW/OOS/OOC/alert 欄位）
│
├── services/
│   ├── dashboard_service.py     # 燈號計算核心（_calculate_light, _parse_bounds, _bounds_mismatch）
│   ├── control_service.py       # 廠區隔離（get_active_isolations, get_plant_list）
│   ├── spec_service.py          # 規格維護（list_specs, create_spec, update_spec）
│   ├── qa_service.py            # QA 手測值（list_qa_items, update_qa_value）
│   ├── warning_service.py       # 異常查詢（get_current_anomalies）
│   ├── flow_service.py          # 簽核流程（get_todo_applies）
│   └── notify_service.py        # Email 發送（SMS 已停用移除）
│
├── routers/
│   ├── home_router.py           # GET /home → home.html
│   ├── ui_router.py             # GET /ui/* → partials（HTMX 片段）
│   ├── control_router.py        # POST /control/create 等
│   ├── qa_router.py             # POST /qa/update
│   ├── spec_router.py           # SPEC CRUD API
│   ├── flow_router.py           # 簽核 API
│   ├── warning_router.py        # 預警 API
│   └── acl_router.py            # 權限 API
│
├── templates/
│   ├── home.html                # 首頁：rowspan + 燈號 + 倒數計時
│   ├── partials/
│   │   ├── control_modal.html   # 廠區隔離（有效清單 + 申請表單）
│   │   ├── control_items.html   # 隔離項目 checkbox（HTMX 片段）
│   │   ├── spec_modal.html      # 規格維護（inline 編輯）
│   │   ├── qa_modal.html        # QA 手測值輸入
│   │   ├── warning_modal.html   # 預警（目前紅/橙燈）
│   │   ├── flow_modal.html      # 簽核管理
│   │   └── acl_modal.html       # 系統管理（Phase 3 卡片）
│   └── design/                  # Claude Design 設計稿（靜態參考）
│
├── static/
│   └── css/voc.css              # 設計系統（燈號色/rowspan/底色/斜紋）
│
└── docs/
    ├── 首頁測試流程.md           # 到公司測試的步驟
    ├── 系統架構說明.md           # Mermaid 架構圖
    ├── 重構路線圖.md             # 五階段計畫
    ├── JOB確認清單.md            # 18 個待確認 JOB 問題
    └── ad_integration_guide.md  # LDAP 整合說明（Phase 3 用）
```

---

## 七、DB schema 重點（MSSQL，目前不動）

### 主要查詢涉及的表

| 表 | 用途 |
|---|---|
| `VOC.dbo.VOC_SPEC` | 規格三階文件（LAW/OOS/OOC/alert/recv）|
| `VOC.dbo.VOC_SCADA_WEB` | JOB 寫入的最新讀值（rvalue/broken/light/SCADA管制值）|
| `VOC.dbo.VOC_plant` | 廠區基本資料（plantno/plantid/isShow/sort）|
| `VOC.dbo.VOC_item` | 監控項目（item/unit）|
| `VOC.dbo.VOC_Curve` | 歷史曲線連結 URL |
| `VOC.dbo.VOC_EmptyCell` | 空白分隔列標記（表格視覺分組用）|
| `VOC.dbo.VOC_closectl` | 廠區隔離申請單主表 |
| `VOC.dbo.VOC_closectl_list` | 隔離申請單明細（plantno/item）|
| `SignFlow.dbo.base_flowstatus` | 簽核狀態（跨 DB，連不上時有 mock）|

### VOC_SCADA_WEB 重要欄位

```
rvalue      — 最新讀值（含 N.D / 斷訊 等文字）
broken      — 0=正常, 1=斷訊, 2=保養中
light       — JOB 計算的燈號（新系統不讀，自行計算）
OOS_HH      — SCADA 系統的 OOS 上限（供 SCADA vs SPEC 比對）
OOC_H       — SCADA 系統的 OOC 上限
alert       — SCADA 系統的 Alert 值
OOS_HH1     — CWMS 系統的 OOS 上限
OOC_H1      — CWMS 系統的 OOC 上限
OOS_LL      — SCADA OOS 下限（pH 等雙邊規格）
OOC_L       — SCADA OOC 下限
TwentyFourHours — 24hr 累積雨量（來源：PMS.dbo.Water_WindRainHistValue）
```

---

## 八、環境設定

### .env 必填

```
VOC_DB_URL=mssql+pyodbc://帳號:密碼@DB_IP/VOC?driver=ODBC+Driver+17+for+SQL+Server
TEST_MODE=True                    # 並行測試期間保持 True，避免真實發信
TEST_DEV_EMAIL=你的信箱
```

### 啟動

```powershell
.venv\Scripts\activate
python main.py
# http://localhost:8000/home
```

---

## 九、下一步建議

**已完成（2026-06-11 前）：** 廠區隔離申請接通、規格維護 inline 編輯、QA 手測值輸入。

**接下來的順序（AD/LDAP 已決定延到最後）：**

1. **派送名單維護**（EditMailList.aspx）— 也是異常 Email 通知的前置（GetMailList 的資料來源）
2. **異常件數查詢**（VOChistory.aspx）
3. **異常原因回覆**（VOCreason.aspx）
4. **異常報表匯出**（VOCreport.aspx）
5. **異常 Email 通知移植**（SendMail.cs → Python，只做 Email，SMS/Push 不做）
6. **已知問題修復**：ccno 流水號（VOC 項目 SCADA 例外已於 2026-06-18 修復）
7. **最後：AD/LDAP 登入**
   - `docs/ad_integration_guide.md` 有詳細說明
   - 完成後把 `home_router.py` 加上 user 驗證
   - Template 裡的 `{# Phase 3: if has_perm(user, 'admin') #}` 換成真實 `{% if %}`

**架構決策（需要與用戶確認後才能動）：**
- Historian 是否拿掉 → PostgreSQL schema 如何設計
- 雨水溝歷史邏輯如何處理
- 歷史曲線圖是否保留

---

## 十、Git 資訊

- **Repo**：https://github.com/channian/VOC_Python_Rebuild
- **工作分支**：`20260517`
- **main 分支**：保留舊版（學姊的原始重構，未接 DB）

開發建議在 `20260517` 分支繼續，功能穩定後再考慮合併 main。
