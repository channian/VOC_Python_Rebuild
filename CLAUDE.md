# CLAUDE.md

> 廠務法規許可標準化管控平台（VOC 平台）— ASP.NET Web Forms 舊系統的 Python/FastAPI 重構版。
> **動手前先讀 `HANDOVER.md`**（完整決策脈絡）。本檔只放每個 session 都要遵守的操作慣例。

## 語言
- **一律使用繁體中文回答使用者。** 程式碼註解、commit message 也用繁體中文。

## 技術棧
FastAPI + SQLAlchemy + Jinja2 + HTMX。DB 目前接 MSSQL（`VOC` database）。

## 專案結構（速查）
```
main.py              # 入口：註冊所有 router + StaticFiles
database.py          # SQLAlchemy Engine（VOC_DB_URL from .env）
models/              # ORM（spec_model, acl_model, maillist_model...）
schemas/             # Pydantic 驗證
services/            # 業務邏輯（dashboard/control/spec/qa/maillist/notify...）
routers/             # API + ui_router（HTMX partial 片段）
templates/           # home.html + partials/*.html（modal）
static/css/voc.css   # 設計系統（燈號色/rowspan/底色/斜紋）
tests/               # pytest，純邏輯為主（不依賴 DB）
docs/                # 分析文件（注意：皆為「推測/摘要」，非舊原始碼）
```

## 不可違反的技術決策
1. **燈號不讀 DB 的 `light` 欄位**，一律在 `dashboard_service._calculate_light()` 從原始讀值重算。
   - 例外：`warning_service.get_current_anomalies()` 可讀 `light` 做快速篩選。
2. **Modal 用原生 `<dialog>`，不用 Bootstrap Modal**。關閉一律：
   `onclick="document.getElementById('voc-modal').close()"`。**禁用** `data-bs-dismiss`。
3. **Jinja2 備忘用 `{# ... #}`，不要放進 `<!-- -->`**（HTML 注解裡的 `{% %}`/`{{ }}` 仍會被解析）。
4. **檔案操作一律用 Read/Write/Edit 工具**，不要用 `cat`/`ls`（專案原本在含中文的 Windows 路徑，Bash 中文易亂碼）。
5. `models/spec_model.py` 對應舊 MSSQL schema，**架構未定案前不要改**。

## 燈號計算規則（`services/dashboard_service.py`）
```
broken != 0 或 rvalue 非數字  → '-'（灰）
rvalue >= OOS                 → 'R'（紅）
OOC <= rvalue < OOS           → 'O'（橙）
SCADA/CWMS 管制值 ≠ SPEC 設定值 → 'O'（橙）← 設定不同步提醒
Alert < rvalue < OOC          → 'Y'（黃）
rvalue > recv（允收值）        → 'Y'（黃）
其他                          → 'G'（綠）
```
- 門檻一律經 `_parse_bounds()`：單邊 `'1.16'→(1.16,1.16)`、雙邊 `'6-9'→(6.0,9.0)`（pH/溫度），取**上界**比對。
- SCADA/SPEC 比對先 `round(x, 2)` 對齊舊系統 `ChangeData(text,2)` 四捨五入，避免 `0.4999` vs `0.5` 誤亮橙。
- VOC 項目例外：SCADA 比 SPEC 嚴（更低）時不算不一致（`_bounds_mismatch(..., voc_exception=True)`）。
- **待確認**：雙邊規格（pH/溫度）舊系統**只比上界**，過低不示警。是否加下界示警等業務確認。

## broken 欄位
`0`=正常、`1`=斷訊（JOB 寫）、`2`=保養中/隔離中（Web 寫）。Web 與 JOB 不可互蓋。

## 舊原始碼（2026-06-21 已取得網頁端）
- `legacy/` 內有 32 個舊 `.cs`（dbVOC.cs + 各 .aspx.cs），精讀結果見 **`docs/legacy_source_analysis.md`**。
- 要還原舊行為時**先查 `legacy/` 與該分析文件**，不要再憑 `docs/` 的舊推測當定論。
- ✅ **2026-07-01 JOB 原始碼已全部補齊**（`legacy/Job_SendMail.cs`、`legacy/Job_dbVOC.cs`、
  `legacy/MTFlowBase.cs`、`legacy/dbSignFlow.cs`），異常派報與簽核流程皆已依此移植完成。
  唯一未取得：`CheckMAILlog` 本體（僅用於 IH 斷訊通知，不影響核心）。
- **簽核狀態值（已確認）**：待簽核=0、簽核中=1、核准=7、否決=8、取消=12
  （`flow_service.FlowStatus` IntEnum，**不要**再寫死數字）。

## 開發 / 測試
```
python -m pytest tests/ -v        # 純邏輯測試，不需 DB
python main.py                    # 本地啟動 → http://localhost:8000/home
```
- 新功能盡量寫**不依賴 DB 的純邏輯測試**（DB 端無 ODBC driver，連線會失敗屬正常）。

## 已知待辦（2026-07-01 大更新：第一階段模組移植全部完成）
> 先前列的 4 個 🔴 bug（ACL 全開/隔離自動核准/時間上限/ccno 寫死）**皆已修復**，
> 派送名單也已重寫完成。所有舊系統頁面（含派報/報表/規格簽核/部門權限/中水通知/
> 隔離修改與時間修改）皆已移植，全套純邏輯測試 256 個通過。

**尚未完成／待決事項：**
- **check_permission 尚未掛到各 router 當守門**（acl_service 已有真實實作 + `ACL_ENFORCE`
  開關，但除了 ControlTime 外其他端點還沒呼叫）——等 Phase 3 LDAP 有真實 current_user
  後一併接上，現在 current_user 都是寫死 "admin" 接了也沒意義。
- **正式上線前必改設定**：`ACL_ENFORCE=True`、`AUTH_MOCK=False`（見 .env.example）。
- **AD/LDAP 登入**延後到最後（`docs/ad_integration_guide.md`）。
- **歷史曲線頁原始碼未提供**（`VOC_Curve.URL` 指向的外部圖表頁）：目前只移植了連結；
  待補件後決定忠實移植或用 Schema B 的 reading_history 自建（見 PM執行路線圖第七節）。
- **待業務確認清單**（各 agent 移植時發現，已在對應程式碼註解標記）：
  1. 異常報表母集合現含雨水溝（舊報表不含），統計數字會比舊系統多
  2. 水質異常通知固定查 K14B 資料（舊系統原始行為，疑似 bug，已忠實還原）
  3. EditAclUser 只管 roleid 3/7（照舊系統），是否開放管理全部 12 種角色
  4. 隔離重複防呆：新版「區間重疊」擋 vs 舊系統「完全相等」才擋
  5. 規格簽核 RPTTYPE_SPEC="規格維護" 為新設常數（legacy 該段是死碼無從考證）
  6. ControlTime 無 1 小時上限且不走簽核（舊系統後門通道，上線前應評估）
- **第二階段**：資料流與 JOB 重寫——Kepware(A，既有) → 新 VOC 資料庫(B，schema 未定案)
  轉拋 JOB 由本專案撰寫，見 `docs/JOB確認清單.md` 第六節。

## Git
- 工作分支：`claude/wizardly-clarke-NRLEK`（push 用 `git push -u origin <branch>`）。
- 未經明確要求**不要開 PR**。
