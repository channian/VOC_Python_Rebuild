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
- ⚠️ **仍缺外部排程 JOB 原始碼**：`SendMail_廠務法規許可值標準化管控報表`、`GetMsg1`、`CheckMAILlog`（首發/再發判斷）、`MTFlowBase`（簽核框架，狀態值除否決=8 外未確認）。
  做「異常 Email 通知移植」與「完整簽核流程」前需請使用者補貼。

## 開發 / 測試
```
python -m pytest tests/ -v        # 純邏輯測試，不需 DB
python main.py                    # 本地啟動 → http://localhost:8000/home
```
- 新功能盡量寫**不依賴 DB 的純邏輯測試**（DB 端無 ODBC driver，連線會失敗屬正常）。

## 已知待辦（動相關功能前先看）
> 完整落差清單見 `docs/legacy_source_analysis.md` 第五節。重點：
- **派送名單需重寫**：真實 `VOC_Mail_List` 主鍵 `(plantno,rpttype,empno)`，欄位含 rpttype/empname/notesid/mail/SM/signgrp/Mail1/SM1，先前 commit 的版本錯誤。
- 🔴 **ACL 權限全開**（`acl_service.check_permission` 直接 return True）。
- 🔴 **隔離自動核准** bug（`control_service` 的 `b_pass→fstatusid=3` 應移除，舊系統一律走簽核）。
- 🔴 **隔離時間上限**：Python 用 4hr，舊系統一律 1 小時。
- 🔴 **ccno 流水號寫死 `001`**，同日撞號 → 改查當日 MAX 後 3 碼 +1（交易內）。
- AD/LDAP 登入延後到最後（`docs/ad_integration_guide.md`）。

## Git
- 工作分支：`claude/wizardly-clarke-NRLEK`（push 用 `git push -u origin <branch>`）。
- 未經明確要求**不要開 PR**。
