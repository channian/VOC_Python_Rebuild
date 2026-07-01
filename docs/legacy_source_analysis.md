# 舊系統原始碼分析（legacy/ C# 精讀結果）

> 2026-06-21 取得舊系統 32 個 `.cs` 檔後，用平行 agent 通讀整理。
> 這份文件**取代先前所有「推測」**：凡此處有列的，是從原始碼確認的事實；
> 仍標「待確認」者，是因為原始碼不在 repo 內（見下方「缺失的原始碼」）。

---

## 〇、缺失的原始碼 → 2026-07-01 已全部補齊 ✅

`legacy/` 內原本只有**網頁端**程式（dbVOC.cs + 各 .aspx.cs）。經過 2026-07-01 一連串補件，
**外部排程 JOB / Windows Service 的所有相關程式碼現已全部取得**：

| 曾缺失方法 | 用途 | 狀態 |
|---|---|---|
| `MTFlowBase`（簽核框架外殼）| enum 定義、方法簽章 | ✅ 已取得 |
| `dbSignFlow`（簽核框架實作本體）| `CreateNewFlow`/`Sign`/`GetFlowStatus`/`SendMail通知` 的實際邏輯 | ✅ 已取得，見「簽核流程完整還原」 |
| `Job.SendMail`（JOB 端寄信類別）| `SendMail_廠務法規許可值標準化管控報表()` 等派報主流程 | ✅ 已取得，見「JOB 派報流程完整還原」 |
| `Job.dbVOC.GetMsg` / `GetMsg1` / `GetMsg2` | 組信件文字、**首發 vs 再發判斷**（`GetMsg1(..., "status")`）| ✅ **2026-07-01 已取得**（`legacy/Job_dbVOC.cs`）|
| `Job.dbVOC.GetDataRed` | 判斷該筆讀值是否要列入派報、決定燈號、寫入 msg/msg1/msg2 | ✅ **2026-07-01 已取得**，完整邏輯見下方「GetDataRed 完整還原」 |
| `Job.dbVOC.GetData()`（無參數）| JOB 撈全廠即時資料 | ✅ **2026-07-01 已取得** |
| `dbVOC.CheckMAILlog` | IH 主機/Tag 斷訊通知的「當天是否已發送」判斷 | ⚠️ 仍未取得本體，但已知契約：回傳 `1`=今天已發過、`0`=尚未發過；**與 VOC 主派報無關**（只用在 IH 斷線通知），不影響核心移植 |

**重要澄清**：先前以為 `GetMsg`/`GetMsg1`/`GetMsg2`/`GetDataRed`/`GetData()` 屬於網頁端 `dbVOC.cs`（namespace 空白，MTLibrary 專案），
所以在該檔案 grep 不到；**實際上這些方法屬於另一個同名但不同 namespace 的類別 `Job.dbVOC`**（JOB 專案自己的 DB 存取類別），
現已存檔在 `legacy/Job_dbVOC.cs`。網頁端 `dbVOC.cs` 與 JOB 端 `Job.dbVOC.cs` 是兩份平行但獨立維護的檔案，均操作同一顆 VOC 資料庫。

➡️ **至此，異常 Email 派報所需的全部程式碼（除了不影響核心的 `CheckMAILlog` 本體）都已到位，
可以開始完整移植 `notify_service.py` 了。**

**2026-07-01 補充 1**：`legacy/SendMail.cs`（`MTLibrary.SendMail.寄送Mail通知()`）——最底層 SMTP 寄送工具，
被 `MTFlowBase.SendMail通知()`／`Job.SendMail` 內部呼叫，非缺失方法本身。

**2026-07-01 補充 2**：`legacy/MTFlowBase.cs` + `legacy/dbSignFlow.cs`——**重大發現：`FlowStatus` enum 真實數值
與目前 Python 程式碼假設的不同**，見「簽核狀態值」章節——`control_service.py`/`flow_service.py` 目前把「核准」
寫死成 `fstatusid=3`，真實值是 **`7`**（否決=8 是巧合猜對，待簽核預設值 1 應為 0）。VOC 簽核流程本身邏輯已完整
還原，見「簽核流程完整還原」節。

**2026-07-01 補充 3**：`legacy/Job_SendMail.cs`（`Job.SendMail` 類別，JOB 端所有系統共用的寄信類別，體積龐大，
只有其中 6 支方法跟 VOC 有關）。完整還原了派報「外層流程」，見下方「JOB 派報流程還原」——包含 HTML 信件版型、
收件名單來源、K14B 跨廠通報規則、SMS 觸發點、`InsertMAIL` 真實呼叫簽章。**但流程內部呼叫的
`GetMsg`/`GetMsg1`/`GetMsg2`/`GetDataRed`/`GetData()` 這幾支決定「文字內容」與「首發/再發」的方法本體仍缺**，
不影響架構設計，但影響「訊息內容」與「防重複寄信」邏輯能否 100% 忠實移植。

---

## JOB 派報流程完整還原（2026-07-01，由 `Job_SendMail.cs` 確認）

JOB 每 15 分鐘執行 `Job.SendMail.SendMail_廠務法規許可值標準化管控報表()`，完整流程：

```
1. List隔離廠區項目() + Update隔離廠區項目(row)  ← 先把隔離中項目的 broken 標成 2（已在 dbVOC.cs 裡確認）
2. dtb = GetData()                              ← 撈全廠即時資料（❌缺，但欄位結構與 Home.aspx GetData() 相近）
3. 對每列資料：清理格式（逗號移除、空值補「異常」、數字四捨五入到小數2位，
   導電度/日累積水量到整數，未四捨五入前的值另存於 col+21 供比對用）
4. sRed = GetDataRed(row, dt2)                  ← ❌缺，回傳逗號分隔的「派報代碼」（如 "水Alert-九號放流口"）
   把每列的 sRed 去重後累加成 DataRed（例："水Alert-九號放流口,水OOS-K7,水保養中-K5"）
5. 若 DataRed 不為空，依廠區分組（同廠區的異常項目合併成一封信）：
   - msg  = GetMsg(dtb, plantno, r)              ← ❌缺，人類可讀的異常描述（存進 VOC_MAIL_Log.msg）
   - msg1 = GetMsg1(dtb, plantno, r, "msg1")      ← ❌缺，"|item|" 包裹格式（存進 VOC_MAIL_Log.msg1，供 LIKE 比對）
   - status = GetMsg1(dtb, plantno, r, "status")  ← ❌缺，回傳含「首發」或「再發」字樣 ← **這就是首發/再發判斷本體**
   - msg2 = GetMsg2(dtb, plantno, r)               ← ❌缺，用於 SMS 內容 + 判斷「＞允收值」觸發 K14B 跨廠通報
   - msg3 = GetMsg1(dtb, plantno, r, "msg2")        ← ❌缺，存進 VOC_MAIL_Log.msg2（不是布林 MT 旗標，是一段文字）
   - 組 HTML 表格信件（含燈號圖示、SCADA/CWMS/QA 三色底、法規許可值/SPEC/Alert/允收值欄）
6. mailto = GetMailList(DataRed, plantno, "TO")   ← ✅已確認（VOC_Mail_List 查詢，見下方 GetMailList 節）
   mailcc = GetMailList(DataRed, plantno, "CC")
   K14B 跨廠通報：若 plantno≠K14B 且 msg2 含「＞允收值」，額外把「水Alert-K14B」的 TO 名單也 CC 進去
   若 mailto 為空 → **直接 return 0，中止整個派報迴圈**（舊系統的既有行為，注意：這代表若某廠沒設收件人，
   會連帶跳過後面所有廠區的信；Python 版建議修正成 continue 而非 return，除非要忠實重現這個「隱藏 bug」）
7. 寄信：主旨 "【{首發/再發}】請確認「法遵平台」即時監控狀況 : {plantno}-{DT} (Security C)"
8. InsertMAIL(plantno, msg, msg1, dt2, msg3)      ← ✅已確認簽章：(plantno, msg, msg1, DateTime cdatetime, msg2)
   對應 VOC_MAIL_Log 欄位：plantno/msg/msg1/cdatetime/msg2（**msg2 存的是 GetMsg1(...,"msg2") 回傳的文字，
   不是我們原本猜測的布林 MT 旗標**——這點需要修正 history_service.py 的既有假設，待 GetMsg1 本體到手後確認）
9. SMS 派送（**已與使用者確認 2026-06-11 停用，不移植**，僅記錄供理解舊行為：
   msg = "【{首發/再發}】{plantno}有異常,請儘速處理,謝謝!{msg2}"，經 GetCellPhoneList() 取號碼、
   SendSMS.SendSMSByCHTProxy() 發送，K14B 跨廠通報同樣邏輯）
10. PushPlus 推播（**已與使用者確認暫不實作**）：if (msg2 != "") CallPushPlus().Notice(...)
```

**雨水溝預警**（`SendMail_廠務雨水溝預警報表()`）結構完全相同，差別：
- 用 `List隔離廠區項目_雨水溝預警()` / `GetData雨水溝預警(dt0)` / `GetDataRed雨水溝預警(row, dt2)`（獨立的一組方法）
- K1/K9 廠區多顯示「三點連升」欄位（`datetime1/value1/datetime2/value2/datetime3/value3`），
  對應 HANDOVER.md 提過的「雨水溝三點連升邏輯」——**證實資料是從 `GetData雨水溝預警()` 回傳列裡直接帶出，
  不是即時查歷史表現算**，代表舊系統應該有另外的地方（可能是 JOB 寫入時）維護這三筆歷史值
- 連結導向 `VOCreason.aspx?...&type=R`（`change` 參數）而非一般監測項目的連結

**中水陸放/放流量管控**（K1/K9/K14B 專用，`SendMail_廠務中水陸放管控()` / `SendMail_廠務中水放流量管控()`）：
- 首發/再發判斷**不是**靠 `GetMsg1(...,"status")`，而是直接比對 `Get前筆派報資料()` 回傳的上次派報時間，
  超過 4 小時算首發——這是**另一套更簡單的判斷邏輯**，只適用這兩個特化通知，不适用一般監測項目派報
- 這兩個通知目前**已停用 SMS 以外沒有 Email 邏輯**（中水陸放管控完全只發簡訊，不寄信）——因 SMS 已確認不移植，
  這兩個功能等同「暫不需要移植」，除非之後改回發信

**IH 主機/Tag 斷訊通知**（`SendMail_IH主機連線異常通知()` / `SendMail_IH_TAG斷訊通知()`）：
- 揭露 `CheckMAILlog(BU, msg)` 契約：回傳 `int`，`1`=今天已發送過（跳過）、`0`=尚未發送（繼續寄信+`InsertMAIL`）
- 這兩支通知對象是 `dbPMS`（另一個系統的 DB class）不是 `dbVOC`，**與 VOC_MAIL_Log 無直接關係**，
  但若新架構拿掉 IH Historian（HANDOVER.md 提到的方向），這兩個通知可能整個不需要了

---

## GetDataRed 完整還原（2026-07-01，由 `legacy/Job_dbVOC.cs` 確認）

`Job.dbVOC.GetDataRed(DataRow row, DateTime dt2)` 是派報主流程「每一筆讀值」的核心判斷函式，
對每個 `(plantno, item)` 組合執行，回傳逗號分隔的派報代碼字串（空字串代表這筆不用派報）。

### 首發/再發判斷（決定 `first` 變數）

1. 查 `Get前筆派報資料(plantno, item)`：找 `VOC_MAIL_Log` 裡同廠區、`msg1 LIKE '%|item|%'` 的最後一筆
2. 無記錄 → `first=1`（首發）
3. 有記錄但距今 **超過 4 小時**（`ts.Days>=1 || ts.Hours>4 || (ts.Hours==4 && ts.Minutes>0)`）→ `first=1`（首發，逾時視為新事件）
4. 有記錄且在 4 小時內 → 先假設 `first=0`（再發），但底下**每一種異常條件**還會各自用
   `msg0.IndexOf(該條件的訊息片段) < 0` 再次檢查——**只要現在的異常內容跟上一筆記錄的內容不同，就會把 first 改回 1**。
   也就是說「4 小時內」不是無腦不重發，而是「4 小時內只要異常內容沒變就不重發，內容變了照樣算首發」。

### 每個燈號條件的判斷（依「一般水/空項目」vs「pH/溫度雙邊規格項目」分兩branch，邏輯對稱）

| 條件 | light | sRed 代碼格式 | 說明 |
|---|---|---|---|
| `Alert < 讀值 < SPEC-OOC` | 2(黃) | `{水/空}Alert-{廠}` | |
| `讀值 > 允收值(Recv)` | 2(黃) | `{水/空}Alert-{廠}` | 與上面共用同一個 sRed 代碼 |
| `CWMS-OOS_HH ≠ SPEC-OOS`（含斷訊/保養中特例）| 4(橙，保養中不算) | `{水/空}管制值不/斷訊/保養中-{廠}` | |
| `CWMS-OOC_H ≠ SPEC-OOC` | 同上 | 同上 | |
| `SCADA-Alert/OOS_HH/OOC_H ≠ SPEC 對應值` | 4(橙) | 同上 | VOC 項目有例外：SCADA 比 SPEC**更嚴格（更低）**時不算不一致（`voc_exception`，Python 已實作） |
| `SPEC-OOC <= 讀值 < SPEC-OOS` | 4(橙，僅水/VOC項目判斷 sRed) | `{水/空}OOC{0/15/30}-{廠}` | 見下方「0/15/30 escalation」 |
| `讀值 >= SPEC-OOS` | 1(紅) | `{水/空}OOS{0/15/30}-{廠}` | 同上 |
| 讀值為空且管制值也都空 | 1(紅，僅 broken=0 才進 sRed) | `{水/空}OOS-{廠}`+`{水/空}OOC-{廠}` | 代表整組資料都缺失 |

pH/溫度雙邊規格項目（`OOS`/`OOC`/`Alert` 等欄位存 `"下限-上限"` 格式，用 `Split('-')` 取 `[1]` 即上限）判斷邏輯完全相同，
只是所有比較值都先取上界——**這證實了 Python 現有的「雙邊規格取上界比對」邏輯是對的**。

### 0/15/30 分鐘 escalation（`ArrOOCS = {"", "15", "30"}`）

OOC 和 OOS 這兩個條件比較特別：在 4 小時的「再發不重複」窗口內，**如果訊息內容完全一樣，仍然會在
第 15 分鐘、第 30 分鐘各再派報一次**（用 `msg0.IndexOf(sData1 + sOOCS)` 檢查是否已經在 0/15/30 分這幾個時間點各發過一次），
發滿 3 次（`cnt==3`）後才真正停止，直到 4 小時整個週期重置。這是舊系統對「持續惡化中的異常」額外加強提醒的機制，
Python 移植時要注意這不是單純的「4 小時內不重發」。

### `row["status"]` 何時等於「首發」

`if (first == 1 && sRed != "") row["status"] = "首發"`——**只有真的判定為首發、且這筆有異常要派報時才寫入**，
否則欄位維持初始值（`GetData()` 建的空白 `space(4)`）。`GetMsg1(dtb, plantno, r, "status")` 後續拿這欄位
做 `IndexOf("首發")>-1` 判斷，找不到就當「再發」——這解釋了為什麼 status 沒特別設也能正常判斷（預設就是「再發」語意）。

### `msg` / `msg1` / `msg2` 三欄位的真實用途（澄清先前的推測）

- **`msg`**：human-readable，格式 `"{item}：{條件敘述}({數值})；"` 逐條累加，供信件內文與 `VOC_MAIL_Log.msg` 存檔
- **`msg1`**：`"|{item}|：{條件敘述}"` 格式，**這是拿來跟下一輪比對「內容有沒有變」的比對鍵**，存進 `VOC_MAIL_Log.msg1`，
  也是 `VOChistory`/`VOCreason` 查詢時 `msg1 LIKE '%|item|%'` 做件數統計的依據
- **`msg2`（Python 端稱 `msg3` 變數）**：`msg1` 的子集合，**排除「(保養中)」相關的項目**，存進 `VOC_MAIL_Log.msg2`。
  這證實了 CLAUDE.md「MT 旗標」的既有理解是對的方向：`msg2 LIKE '%|item|%'` 天然排除了保養中項目，
  所以 MT 未勾選時用 `msg2` 比對「較嚴格」——**msg2 不是布林旗標，而是排除保養中後的訊息文字**，
  但對「MT 勾選與否」的篩選行為結果是一致的，`history_service.py` 現有的查詢邏輯不用改。

### 派報後統一動作

`UpdateData(plantno, item, light)`——不管有沒有觸發派報，**每筆資料每次執行都會把算出來的 `light` 寫回
`VOC_SCADA_WEB`/`VOC_SCADA_HIST`**。這點呼應 CLAUDE.md「不可違反的技術決策 #1」：舊系統會把 JOB 算好的燈號存回 DB，
但 Python 新系統刻意選擇不讀這個存好的 `light` 欄位、每次重新計算——這個決策依然正確，不用改。

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

### 簽核狀態值（2026-07-01 由 `MTFlowBase.cs` 確認，取代先前推測）

```csharp
public enum FlowStatus
{
    待簽核 = 0,
    簽核中 = 1,
    核准   = 7,   // ⚠️ Python 目前寫死用 3，是錯的！
    否決   = 8,   // 之前推測對了
    取消   = 12,
};
```

**🔴 資料正確性 bug（新發現，建議與「已知 4 個 bug」同批修正）**：

| 檔案:行 | 現況（錯） | 應改為 |
|---|---|---|
| `services/control_service.py:27` | `fstatusid = 1`（待簽核預設值）| `fstatusid = 0` |
| `services/control_service.py:28` | `fstatusid = 3`（自動核准，此邏輯本身也該移除，見已知 bug #2）| 若真的要核准應為 `7` |
| `services/control_service.py:102` | `WHERE M.fstatusid = 3`（查詢已核准隔離）| `WHERE M.fstatusid = 7` |
| `services/flow_service.py:54-55` | `# 1: 核准 -> fstatusid = 3` | 核准應為 `7` |
| `services/flow_service.py:66` | `fstatusid == 3` 判斷是否核准 | 應改判斷 `== 7` |

另外 `SignAction`（簽核動作下拉選單，跟 `FlowStatus` 是不同 enum）：`核准=1`／`否決=9`／`分享=10`（`取消=8` 已被舊系統註解停用）。
`MsgType.法遵平台簽核 = 6`（VOC 平台簽核通知對應的訊息類型代碼，供 `SendMail通知()` 使用）。

---

### 簽核流程完整還原（2026-07-01，由 `dbSignFlow.cs` 確認）

`dbSignFlow.cs` 是給**全公司多個系統共用**的簽核引擎（CCTV、AffectManage、PLC…都用同一套），
`CreateNewFlow` 有 3 個多載對應不同系統的簽核模式。**VOC 平台只用其中最簡單的一種**：

```csharp
// dbVOC.cs 呼叫方式（隔離廠區項目維護 / 法規許可值與規格值維護 都走這個多載）：
MTFlowBase.Proc建立簽核流程(fruleid, ccid/formid, empno, plantno, rtype, hashkey, showinfo)
  → dbSignFlow.CreateNewFlow(fruleid, fid, empno, string plantno, string rtype, hashkey, showinfo)
```

**這個多載是「一階群組簽核」（2019/02/27 新增），VOC 完全不牽涉多級主管爬升、不牽涉職稱判斷**：

1. **找簽核人**：`Get簽核人員(plantno, rtype, empno)`：
   ```sql
   Select Distinct M.empno
   From [VOC].[dbo].[VOC_Mail_List] M
   Join [UTIDB].[dbo].[Employee] E On M.empno=E.empno And E.isLeave=0
   Where M.plantno=@plantno And M.RptType in (@rtype) And M.empno!=@empno And M.SignGrp=1
   ```
   **簽核人清單就是 `VOC_Mail_List` 裡 `SignGrp=1` 的人**（同廠區、同 `rpttype`、排除申請人自己、排除離職員工）。
   這證實了先前重寫 `maillist_service.py` 時 `signgrp` 欄位的用途——它不只是「要不要收信」，
   **同時也是「這個人是不是這個廠區/報表類型的簽核人」**。

2. **`rtype` 傳入格式**（`dbVOC.cs` 組字串範例）：
   ```csharp
   string stype = (item.IndexOf("VOC") > -1 ? "空" : "水") + "保養中";
   rtype += (rtype == "" ? "'" : ",'") + stype + "'";
   // → rtype = "'水保養中'" 或 "'水保養中','空保養中'"
   ```
   直接字串拼進 `RptType in (...)`，即帶引號、逗號分隔的 SQL IN 清單（**注意：這是字串拼接，有 SQL injection 風險，
   Python 版必須參數化**）。代表 `VOC_Mail_List.rpttype` 除了「水質異常」「水Alert」等派報類型外，
   **還有「水保養中」「空保養中」這種專門給隔離申請簽核用的類型**，需要在派送名單維護時一併支援。

3. **建立流程**：全部簽核人都插入同一個 `fstep=1`（不分層級），`base_flow.fstatusid` 初始為 `簽核中(1)`。

4. **核准/否決（`Sign()`，VOC 用這支不用 `Sign1()`）**：
   - 檢查身份：`ftype=2`（人員）時只比對 `empid` 是否等於簽核人清單裡的其中一筆
   - 更新該筆 `base_flowd.signactionid/signtime`
   - 查詢 `next fstep = MIN(fstep) WHERE flowid=@flowid AND fstep > 目前fstep`——因為所有人都在 `fstep=1`，
     不存在 `fstep>1` 的資料，**所以 `nextfstep` 一定找不到，流程立刻關閉**
   - ⚠️ **關鍵結論：VOC 是「任一位 `SignGrp=1` 的人先簽，流程就立刻結束」（OR 邏輯），不是要全部簽核人都同意（AND 邏輯）**。
     核准 → `fstatusid=核准(7)`；否決 → `fstatusid=否決(8)`。沒有多級關卡、沒有主管爬升，比原本猜測的簡單很多。

5. **簽核通知信**（`SendMail通知()` → `Send簽核通知()`）：主旨格式
   `"{msgtype}{核准/退件}通知 [{ccno或formno}] (Security C)"`，本文含表單類別/內容摘要/提交時間/提交人，
   附「進行簽核」或「進行查看」連結；最終呼叫 `SendMail.寄送Mail通知()`（已取得，見上方）寄出。
   `MsgType.法遵平台簽核 = 6`。

**結論：`services/flow_service.py`、`services/control_service.py` 現在可以完整移植 VOC 的簽核邏輯了**——
不需要 `dbSignFlow.cs` 裡其他系統專用的部分（`職稱ID`、主管爬升 `Get員工主管id`、CCTV/PLC 相關的 `Get簽核人員` 多載）。
「異常 Email 派報」JOB 本體（`SendMail_廠務法規許可值標準化管控報表`）已於 2026-07-01 取得，外層流程已還原（見「JOB 派報流程完整還原」節）；
仍缺的只剩 `dbVOC.cs` 裡 `GetDataRed`/`GetMsg`/`GetMsg1`/`GetMsg2`/`CheckMAILlog`/`GetData()`（無參數版本）這幾支。

---

## 六、建議的處理順序

1. 先**重寫派送名單**（schema 已完全確認，無外部相依）。
2. 做**異常查詢/回覆/報表**（VOC_MAIL_Log 結構已確認；報表注意別用實體暫存表）。
3. 回頭修**已實作模組落差**第 1~4 項（權限、自動核准、時間上限、ccno），**加上新發現的 fstatusid 核准值 3→7 修正**。
4. **完整簽核流程移植**——`dbSignFlow.cs` 已取得，邏輯已完全還原（見上方「簽核流程完整還原」），現在可以做。
5. **異常 Email 通知**——✅ **2026-07-01 全部程式碼到位，可以完整移植了**。JOB 外層流程（見「JOB 派報流程完整還原」）
   與核心判斷邏輯（見「GetDataRed 完整還原」）都已還原：HTML 信件版型、收件名單、K14B 跨廠通報、`InsertMAIL` 簽章、
   燈號判斷規則、首發/再發判斷（含 4 小時重置 + 0/15/30 分鐘 escalation）、msg/msg1/msg2 欄位真實用途皆已確認。
   唯一不影響核心的缺口是 `CheckMAILlog` 本體（僅用於 IH 主機/Tag 斷訊通知，非 VOC 主派報必要）。
   SMS/PushPlus 派送部分維持先前決策（不移植）。
