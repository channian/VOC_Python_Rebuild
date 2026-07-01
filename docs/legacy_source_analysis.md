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
| `MTFlowBase`（簽核框架外殼）| enum 定義、方法簽章 | ✅ **2026-07-01 已取得** |
| `dbSignFlow`（簽核框架實作本體）| `CreateNewFlow`/`Sign`/`GetFlowStatus`/`SendMail通知` 的**實際邏輯** | ✅ **2026-07-01 已取得**，見下方「簽核流程完整還原」 |

➡️ **簽核框架已完整還原（見下方）。剩下真正卡住的只有異常 Email 派報 JOB 本體：
`SendMail_廠務法規許可值標準化管控報表`、`GetDataRed`、`GetMsg1`/`CheckMAILlog` 這 3 支。**

**2026-07-01 補充 1**：使用者已提供 `legacy/SendMail.cs`（`MTLibrary.SendMail.寄送Mail通知()`）。
這是**最底層的 SMTP 寄送工具函式**（subject/body/收件人清單 → 呼叫 `SmtpMessage` 寄出），
被 `MTFlowBase.SendMail通知()` 等上層方法呼叫。這不是缺失方法本身，只是底層工具。

**2026-07-01 補充 2**：使用者已提供 `legacy/MTFlowBase.cs`。**重大發現：`FlowStatus` enum 真實數值與目前
Python 程式碼假設的不同**，見下方「簽核狀態值」章節——`control_service.py`/`flow_service.py`
目前把「核准」寫死成 `fstatusid=3`，但真實值是 **`7`**，這是一個需要立即修正的資料正確性 bug
（否決=8 是巧合猜對，待簽核目前預設用 1 但真實是 0）。
但 `MTFlowBase` 本身只是薄殼，實際簽核邏輯（`CreateNewFlow` 如何決定關卡、`Sign` 如何推進流程）
在 `dbSignFlow.cs`，這支還沒拿到，多級簽核流程的細節仍無法完整移植。

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
唯一還缺的是「異常 Email 派報」JOB 本體（`SendMail_廠務法規許可值標準化管控報表`/`GetDataRed`/`GetMsg1`/`CheckMAILlog`），
這是完全不同的另一套邏輯，不在 `dbSignFlow.cs` 裡。

---

## 六、建議的處理順序

1. 先**重寫派送名單**（schema 已完全確認，無外部相依）。
2. 做**異常查詢/回覆/報表**（VOC_MAIL_Log 結構已確認；報表注意別用實體暫存表）。
3. 回頭修**已實作模組落差**第 1~4 項（權限、自動核准、時間上限、ccno），**加上新發現的 fstatusid 核准值 3→7 修正**。
4. **完整簽核流程移植**——`dbSignFlow.cs` 已取得，邏輯已完全還原（見上方「簽核流程完整還原」），現在可以做。
5. **異常 Email 通知**——仍卡住，需先向使用者索取 JOB 本體：
   `SendMail_廠務法規許可值標準化管控報表`、`GetDataRed`、`GetMsg1`/`CheckMAILlog`。
