# 舊系統原始碼分析（legacy/ C# 精讀結果）

> 2026-06-21 取得舊系統 32 個 `.cs` 檔後，用平行 agent 通讀整理。
> 這份文件**取代先前所有「推測」**：凡此處有列的，是從原始碼確認的事實；
> 仍標「待確認」者，是因為原始碼不在 repo 內（見下方「缺失的原始碼」）。

---

## 〇、缺失的原始碼（重構前必須補）

`legacy/` 內是**網頁端**程式（dbVOC.cs + 各 .aspx.cs）。以下屬於**外部排程 JOB / Windows Service**，全檔 grep 確認**不存在**：

| 缺失方法 | 用途 | 影響 |
|---|---|---|
| `SendMail_廠務法規許可值標準化管控報表` | 每 15 分鐘定時派報主流程 | 異常 Email 通知無法忠實移植 |
| `GetDataRed` | JOB 端異常判斷 | （網頁端對應 `GetData()`，可參考）|
| `GetMsg1` / `CheckMAILlog` | **首發 vs 再發判斷**、防當日重複 | 首發/再發邏輯只能推測 |
| `MTFlowBase`（簽核框架）| `Sign`/`GetFlowStatus`/`Proc建立簽核流程` | 簽核狀態值（除否決=8）無法確認 |

➡️ **做「異常 Email 通知移植」與「完整簽核流程」前，需請使用者再貼這幾支。**

---

## 一、完整 DB schema（已確認）

資料庫主要 `[VOC].[dbo]`，跨庫到 `[SignFlow].[dbo]`、`[UTIDB].[dbo]`。

### 規格相關
- **VOC_SPEC**：`plantno, item`(PK)、`LAW, OOS, OOC, alert, recv`(varchar，雙邊存 `6-9`)、`source`(int 1SCADA/2CWMS/3QA)、`status`(int)、`tagname`(varchar=`plantno_item`)、`seqno`(int)。
- **VOC_SPEC_apply**（規格簽核申請，**Python 未移植**）：`formid`(PK identity)、`formno`(char11 `yyyyMMddNNN`)、`ftype`(I/M/D)、規格各欄、`empno, cdatetime, flowid, fstatusid`。

### 隔離相關
- **VOC_closectl**（主表）：`ccid`(PK identity)、`ttypeid`(1新增/2修改)、`ccno`(char11 `yyyyMMddNNN`)、`plantid`(int)、`mdfdesc`、`stime/etime`(datetime)、`remark`、`cempname/cempno`、`ctime`、`flowid`、`fstatusid`、`del`(bit)、`delclerk`、`orgccid`(修改單指向原單)。
- **VOC_closectl_list**（明細）：`ccid`(FK)、`plantno`、`item`(存 pH1/COD2 原值)、`sourceid`。
- **VOC_closectl_his**（歷程）：同主表 + `utypeid`(1新增/2送簽/3修改)、`utime`、`uclerk`(`empno-name`)。
- **VOC_closectl_ttype**：`ttypeid`(PK)、`ttype`。

### 讀值
- **VOC_SCADA_WEB**：`plantno, item`(PK)、`rvalue`(varchar，可 `<0.05`/`N.D`)、`cdatetime`、`broken`(0/1/2)、`light`(R/O/Y/G/-，新系統不讀)、SCADA `OOS_HH/OOC_H/alert`、CWMS `OOS_HH1/OOC_H1`、下限 `OOS_LL/OOC_L/alert_L`、`TwentyFourHours`。

### 派送名單（見第二節）
- **VOC_Mail_List**、**VOC_Mail_Type**

### 異常通知紀錄
- **VOC_MAIL_Log**：`logid`(PK identity)、`plantno`、`cdatetime`(對齊 5 分整點)、`msg`(人看，全形冒號分號)、`msg1`(程式比對，`|item|` 包裹)、`msg2`(MT 旗標)、`empno/reason/rdatetime`(原因回覆回填)。
- **VOC_report**：`plantno, item, qty` — ⚠️ 全域共用實體暫存表，每次報表 `DELETE` 後重填。
- **VOC_SMS_Log**：簡訊紀錄（新系統不做簡訊）。

### 主檔 / 對照
- **VOC_plant**：`plantid`(PK,29=ALL)、`plantno`、`isShow`、`sort`。
- **VOC_item**：`itemid`(PK)、`item`、`unit`、`IsActive`。
- **VOC_source / VOC_status / VOC_tranlog**：來源 / 狀態 / 操作軌跡（`logtype` I/M/D，`databefore/dataafter` 斜線串）。

### 權限（位元）
- **sys_acluserrole**：`roleid, empno, deptno, plantno`(可 'ALL')、`stype`(空/水/ALL)。
- **sys_aclrolerights**：`roleid, rightsid, allowrights`(位元旗標：查詢1/修改2/新增4/刪除8/執行16)。
- **sys_aclrole**：`roleid`(PK)、`rolename`。
- `使用者權限` roleid：1系統管理員 / 2規格維護 / 3隔離維護 / 4派報簡訊啟用 / 5停用 / 6派送名單 / 7隔離查詢 / 8隔離權限 / 9QA / 10部門 / 11中水通知 / 12隔離時間修改。

### 跨庫
- **[SignFlow].[dbo]**：`base_flow / base_flowd / base_flowstatus / base_emp`（簽核框架）。員工查詢 `dbSignFlow.Get員工id/Get員工資訊`。
- **[UTIDB].[dbo].Employee**：`empno, empname, notesid/email, DeptNo, isLeave`。

---

## 二、派送名單維護（EditMailList）— 已確認，需重寫

### VOC_Mail_List 真實欄位（主鍵 `plantno + rpttype + empno`）
`plantno, rpttype, empno, empname, notesid, cellphone, mailtype`(TO/CC)、`mail`(1/0 發信)、`SM`(1/0 簡訊)、`signgrp`(1/0)、`Mail1, SM1`(暫停寄信的備份欄)。

### 關鍵行為
- **VOC_Mail_Type**(`typeid`→`RptType`)：報表類型來源。含「保養」類型 → 強制 SM=0、開啟簽核群組欄。
- **notesid 雙向轉換**：存檔 `_`→空格 + 去 `@aseglobal.com`；寄信時還原 空格→`_` + 加 `@aseglobal.com`。
- **工號帶值**：非「群組/值班」工號 → `dbSignFlow.Get員工資訊()` 自動帶 empname/notesid 並鎖定；群組/值班 → 手動輸入。
- **Mail1/SM1 toggle**（全域暫停）：停用 = `Mail1=Mail, SM1=SM` 後 `Mail=0,SM=0`；啟用 = `Mail=Mail1, SM=SM1`。
- **GetMailList**：`MailType + NotesID!='' + Mail=1`。TO 嚴格綁該廠；CC 額外納入 `'GMO','環工部'`（集團監督）。`rpttype` 支援逗號多值。
- ⚠️ 舊碼字串拼 WHERE，有 SQL injection 風險，Python 須參數化。

### 重構待辦
先前 commit 的 `maillist_*`（email 欄、seqno 主鍵、缺 rpttype/mail/empname…）**需依此重寫**。

---

## 三、異常查詢 / 回覆 / 報表（三頁共用 VOC_MAIL_Log）

### 共用
- 篩選：日期區間 + 廠區 + 項目 + MT checkbox。日期預設當月 1 號~今天。
- **MT 旗標**（易搞反）：**未勾** = 只算 `msg2 LIKE '%|item|%'`（較嚴格）；勾選 = 放寬。
- 件數統計靠 `msg1 LIKE '%|item|%'` 字串比對；員工資料 JOIN 跨庫 `UTIDB..Employee`。

### VOChistory（異常件數查詢）
純查詢/檢視，無寫入。`ListVOClog()` 組母體（SPEC⋈item⋈plant ∪ SCADA_WEB 雨水溝）JOIN MAIL_Log。

### VOCreason（異常原因回覆）⚠️ 有寫入
- 回填流程：取 logid → cdatetime **向下取整 5 分鐘** → `Update異常原因`(寫 reason/rdatetime/empno) → **依 msg 關鍵字分流寄 4 種回覆信**（雨水溝/水質異常/改排水/一般）。
- ⚠️ **無獨立狀態欄位**，靠 reason/rdatetime 是否有值；防重複回覆的鎖定碼被註解 → **目前可重複回覆、重複寄信**（重構應補冪等控制）。

### VOCreport（異常報表）
- 輸出是**畫面**（長條圖 + PIVOT 交叉表 + 排行表），**不是 Excel/CSV 匯出** — 名為 report 實為線上報表。
- ⚠️ `VOC_report` 全域共用暫存表，並發查詢會互蓋 → Python 版改用 CTE / 記憶體，不要用實體暫存表。

---

## 四、異常 Email 派報（網頁端可確認部分）

- **GetData(row, msg, ref sRed)**(dbVOC:3764)：網頁端燈號判斷（= Home.aspx.cs 同源）。回傳 6 格配色，`[5]`=燈號 R/O/Y/G；`sRed` 累加派報類型代碼（`水OOS,水Alert,水管制值不...`）餵給 GetMailList。VOC 例外、pH 雙邊取上界、去尾零比對皆與現有 Python 一致。
- **VOC_MAIL_Log**：msg(人看)/msg1(`|item|`比對)/msg2(MT)三者用途不同不可混用。去重指紋 = `(plantno, cdatetime, msg1)`，時間對齊 5 分整點。
- **K14B 跨廠 CC**：法規報表 — 非 K14B 且 msg 含「＞允收值」→ CC K14B 水Alert 名單；中水水質/改排水 — 非 K14B **無條件** CC K14B。
- 硬寫死項目（IT mail server `10.12.10.31`、BCC `Bermy_Po@aseglobal.com`、內網圖片 UNC 路徑）→ 重構移到設定檔。
- **首發/再發邏輯** = 缺失 JOB（見第〇節）。

---

## 五、⚠️ 已實作模組與舊系統的落差清單（依嚴重度）

> 這是本次最重要的發現：部分「以為已完成」的模組與舊系統行為有出入。

| # | 嚴重度 | 落差 | 位置 |
|---|---|---|---|
| 1 | 🔴 最嚴重 | **ACL 權限全開** — `check_permission` 直接 return True，無任何權限管控 | `acl_service.py` |
| 2 | 🔴 嚴重 | **隔離自動核准** — `b_pass→fstatusid=3` 跳過簽核；舊系統免簽核已停用、一律走簽核 | `control_service.create_control` |
| 3 | 🔴 嚴重 | **隔離時間上限錯** — Python 用 4hr/pH 規則，舊系統**一律 1 小時** | `control_schema.py:25`, `control_service.py:24` |
| 4 | 🔴 嚴重 | **ccno 流水號寫死 001** — 同日撞號。舊系統查當日 MAX 後 3 碼 +1 補零（交易內） | `control_service.py:30` |
| 5 | 🟠 中 | **規格簽核流程缺失** — `VOC_SPEC_apply`+ApplySPEC/SignSPEC/SPEC送簽 整段未移植 | `spec_service.py` |
| 6 | 🟠 中 | **廠區 ACL 過濾缺失** — `get_my_applies` 等未做 `sys_acluserrole` 廠區限制；`statusid==-1` 未排除否決(8) | `control_service.py:65` |
| 7 | 🟠 中 | **SPEC 驗證/QA連動/item別名缺** — EditSPEC 欄位驗證(OOC>Alert 等)、UpdateSPEC 的 QA→SCADA_WEB 連動、pH1/COD2 映射皆缺 | `spec_service.py` |
| 8 | 🟠 中 | **隔離重複防呆語意不同** — Python 用區間重疊、舊系統用完全相等(stime/etime 全等)，需業務定奪 | `control_service.py:13` |
| 9 | 🟡 低-中 | **簽核 his/orgccid 回寫缺、log 取值順序錯** — 未寫 VOC_closectl_his、核准修改單未回寫 orgccid | `flow_service.process_sign` |
| 10 | 🟡 低 | **雨水溝燈號型別比對脆弱**、欄位顯隱(K1/K9/29)未移植、水質通知名單寫死 | `warning_service.py` |

### ccno 修法（已確認舊系統作法）
```sql
Select TOP 1 ccno From VOC_closectl Where ccno like 'yyyyMMdd%' Order by ccno desc
```
取後 3 碼 +1 補零（`yyyyMMdd001`→`002`…），無則 `yyyyMMdd000` 起算。須包在交易內避免併發撞號。

### 簽核狀態值（僅否決=8 為確證，其餘待 MTFlowBase）
待簽核 / 簽核中 / 核准 / 否決(8)。多級簽核流程 Python 未實作（簡化成單關卡核准3/否決8）。

---

## 六、建議的處理順序

1. 先**重寫派送名單**（schema 已完全確認，無外部相依）。
2. 做**異常查詢/回覆/報表**（VOC_MAIL_Log 結構已確認；報表注意別用實體暫存表）。
3. 回頭修**已實作模組落差**第 1~4 項（權限、自動核准、時間上限、ccno）— 屬正確性 bug。
4. **異常 Email 通知** + **完整簽核流程** → 需先向使用者索取缺失的 JOB 與 MTFlowBase 原始碼。
