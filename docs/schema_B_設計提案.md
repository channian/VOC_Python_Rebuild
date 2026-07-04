# Schema B 設計提案 — v2（決策已回覆）

> 前提文件：`docs/系統功能與資料架構總覽.md`（As-Is 基準）。執行計畫見 `docs/PM執行路線圖.md`。
> **狀態：v2**——2026-07-01 使用者已回覆決策（見第四節決策紀錄），主要變更：
> (1) **歷史表需逐時管制值快照**（稽核需求）→ `reading_history` 加快照欄位；
> (2) **正式環境引擎未定**（PG 測試、正式可能 MSSQL）→ 全部 SQL 須遵守「引擎可攜規範」（見文末）；
> (3) 其餘決策點（A+B/C/D/J/命名）採建議案，凍結前如有異議請提出。建立 2026-07-01

## 設計原則

1. **邏輯 1:1、實體現代化**：每張舊表都有明確去處（沿用/合併/拆分/淘汰），對照表可追溯；
   但型別、約束、命名全面 PG 化（snake_case、真正的 timestamp、FK、NOT NULL、索引）。
2. **歷史資料 append-only**：任何「事後回改歷史」的舊行為都改為「狀態另外記錄」。
3. **程式已鎖住行為**：256 個純邏輯測試不依賴 DB，改 schema 只動資料層，業務邏輯不重寫。
4. 衍生統計表（VOC_AVG 等）與舊 JOB 專用表**先不搬**，等轉拋 JOB 設計時一併決定。

---

## 一、改善建議比對表（現況 → 問題 → 建議）

### ★A. 讀值混型（本提案影響最大的決策）
- **現況**：`rvalue` varchar 混存數字與狀態文字（`N.D`／`<0.05`／`斷訊`／`保養中`／`建置中`／`異常`）。
- **問題**：每次使用都要先字串清洗（`Replace('N.D',0)`…散在各處）；無法建數值索引；
  `<0.05` 被當 0 計算，語意其實是「低於偵測極限」卻永久遺失原值。
- **建議**：拆三欄——`value numeric NULL`（可算的數字）＋ `status`（enum：normal/nd/below_lod/broken/
  maintenance/building/error）＋ `raw_text`（保留原字串備查）。`<0.05` 存 value=0.05、status=below_lod。
- **影響**：轉拋 JOB 寫入時做一次分類（規則就是現有 `evaluate_row` 的清洗邏輯）；查詢端大幅簡化。

### ★B. 門檻值字串（與 A 連動）
- **現況**：LAW/OOS/OOC/Alert/允收值全是 varchar；雙邊規格存 `'6-9'`；無效值存 `'-'/'N/A'/'建置中'`；
  SCADA/CWMS 管制值欄同樣混存，且**隔離時整欄被覆寫成「保養中」**。
- **問題**：`_parse_bounds` 字串解析散在燈號/派報/規格驗證三處；「只比上界」的舊 bug 部分源自這個存法；
  管制值被覆寫後查不回隔離前的真實設定。
- **建議**：每個門檻拆 `xxx_low / xxx_high numeric NULL`（單邊規格 low=NULL）；「無效/建置中」狀態
  獨立成 `xxx_status`；隔離不再覆寫管制值（見 C）。
- **影響**：規格維護 UI 輸入格式不變（服務層轉換）；未來若業務確認要比下界，schema 已就緒。

### C. 隔離＝竄改資料（我認為 As-Is 最大的設計問題）
- **現況**：隔離核准後，JOB 把 `VOC_SCADA_WEB` **和歷史表 `VOC_SCADA_HIST`** 的讀值+管制值
  UPDATE 成「保養中」、broken=2、light=綠。
- **問題**：真實讀值被毀（隔離期間 SCADA 其實仍在量）；歷史不可信；恢復時要靠下一輪 JOB 覆蓋；
  broken 欄位 Web/JOB 搶寫。
- **建議**：讀值照實寫入不動；「隔離中」由 `isolation` 表的有效區間即時 JOIN 推導
  （或由轉拋 JOB 在寫入時標 `status=maintenance` 於**新增列**，舊列不回改）；
  `broken` 拆成 `comm_ok`（通訊狀態，JOB 寫）與隔離狀態（推導，不落地）。
- **影響**：派報與燈號judgment邏輯不變（保養中不派報），只是資料來源從「被竄改的欄位」變成「JOIN 隔離表」。

### ★D. 派報紀錄字串比對（直接影響派報正確性）
- **現況**：首發/再發、0/15/30 escalation、件數統計全靠 `msg1 LIKE '%|item|%'` 字串比對。
- **問題**：項目名互為子字串會誤中；escalation 進度藏在 `(15)(30)` 字尾；統計查詢全表 LIKE 掃描。
- **建議**：`mail_log`（信件層級：一封信一列，保留 msg 全文）＋ 新增 `mail_log_item` 明細表
  （每項目每條件一列：item、condition_code、escalation_stage）。首發/再發改查明細表精確比對。
- **影響**：`evaluate_row` 的輸入從「上一筆 msg1 字串」變成「上一筆明細列」，介面小改、測試已涵蓋。

### E. 流水號（ccno/formno）
- **現況**：char(11) `yyyyMMddNNN`，程式查當日 MAX+1。
- **建議**：真 PK 用 `bigserial`；顯示編號保留同格式但改用 PG sequence+函式產生（併發安全），
  欄位加 UNIQUE。單號格式對使用者不變。

### F. 全域暫停寄信的 Mail1/SM1 備份欄
- **現況**：暫停＝把每列 Mail/SM 抄到 Mail1/SM1 再歸零；恢復＝倒回來。
- **建議**：`system_config` 表一個 `mail_paused` 旗標，名單資料完全不動。SM/SM1 隨簡訊停用一併淘汰。

### G. 魔法值明確化
- **現況**：plantid=29=ALL；'GMO'/'環工部' 是混在廠區表裡的虛擬列；pH1/COD2 別名寫死在程式。
- **建議**：`plant` 加 `kind`（normal/virtual_group/all）；`item` 加 `display_name`
  （pH1→顯示 pH），程式硬編映射全部移除。

### H. 操作軌跡斜線串
- **現況**：`VOC_tranlog.databefore/dataafter` 存 'K7/水質異常/E001/…' 斜線串。
- **建議**：改 `jsonb`（PG 原生），可查詢可比對；log 寫入函式已集中，改一處即可。

### I. 直接淘汰（不建於 B）
`VOC_report`（暫存表，已用 CTE 取代）、`VOC_SMS_Log`＋所有 SM 欄位（簡訊停用）、
`light` 欄位（燈號不落地，已決策）、`VOC_EmptyCell`（改為 `spec.display_mask` 欄位或前端設定，低優先）。

### ★J. 跨庫依賴的去向（第二個大決策）
| 舊依賴 | 測試期方案（建議） | 正式方案（待決策） |
|---|---|---|
| SignFlow（簽核） | B 內建同構表 `sign_flow`/`sign_flow_step`/`sign_emp`，程式邏輯不變 | 續用公司 MSSQL SignFlow（跨庫雙寫）或 VOC 自管簽核（B 內表轉正）——牽涉公司簽核入口是否要看到 VOC 單據 |
| UTIDB.Employee（員工） | B 建 `employee` 快取表（轉拋 JOB 或手動同步） | 同左，或 Phase 3 LDAP 直查 |
| PMS 雨量 | 轉拋 JOB 把 24hr 累積寫進 `reading_current.rain_24h` | 同左（A→B 轉拋範圍要不要含 PMS＝JOB確認清單待決題） |

---

## 二、Schema B DDL 草案（PostgreSQL）

```sql
-- ============ 主檔 ============
CREATE TABLE plant (
    plant_id    smallint PRIMARY KEY,              -- 沿用舊 plantid 值（29 保留但語意由 kind 表達）
    plant_no    text NOT NULL UNIQUE,              -- 'K7'
    kind        text NOT NULL DEFAULT 'normal'
                CHECK (kind IN ('normal','virtual_group','all')),  -- G 項：GMO/環工部=virtual_group
    is_show     boolean NOT NULL DEFAULT true,
    sort        int NOT NULL DEFAULT 0
);

CREATE TABLE item (
    item_id      int PRIMARY KEY,
    item         text NOT NULL UNIQUE,             -- 'pH1'（原名，資料鍵）
    display_name text,                             -- 'pH'（G 項：取代程式硬編別名）
    unit         text,
    is_active    boolean NOT NULL DEFAULT true
);

CREATE TABLE source (
    source_id smallint PRIMARY KEY,                -- 1=SCADA 2=CWMS 3=QA
    name      text NOT NULL
);

-- ============ 規格（B 項：門檻拆數值欄）============
CREATE TABLE spec (
    plant_no   text NOT NULL REFERENCES plant(plant_no),
    item       text NOT NULL REFERENCES item(item),
    law_text   text,                               -- 法規許可值僅顯示用，保留文字
    oos_low    numeric, oos_high   numeric, oos_status   text,   -- status: valid/na/building
    ooc_low    numeric, ooc_high   numeric, ooc_status   text,
    alert_low  numeric, alert_high numeric, alert_status text,
    recv_low   numeric, recv_high  numeric, recv_status  text,   -- 允收值
    source_id  smallint NOT NULL REFERENCES source(source_id),
    tagname    text,
    seqno      int NOT NULL DEFAULT 0,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (plant_no, item)
);

-- ============ 讀值（A 項：value+status 拆欄；C 項：不再被隔離覆寫）============
CREATE TABLE reading_current (
    plant_no   text NOT NULL,
    item       text NOT NULL,
    value      numeric,                            -- 可計算的數字（N.D→NULL、<0.05→0.05）
    status     text NOT NULL DEFAULT 'normal'
               CHECK (status IN ('normal','nd','below_lod','broken','maintenance','building','error')),
    raw_text   text,                               -- 原始字串備查
    comm_ok    boolean NOT NULL DEFAULT true,      -- C 項：取代 broken=1（JOB 專寫）
    -- SCADA 自設管制值（B 項拆欄；隔離不再覆寫）
    scada_oos_low numeric, scada_oos_high numeric,
    scada_ooc_low numeric, scada_ooc_high numeric,
    scada_alert_low numeric, scada_alert_high numeric,
    scada_limit_status text,                       -- valid/na/building/broken
    -- CWMS 管制值
    cwms_oos_low numeric, cwms_oos_high numeric,
    cwms_ooc_low numeric, cwms_ooc_high numeric,
    cwms_limit_status text,
    rain_24h   numeric,                            -- J 項：由轉拋 JOB 寫入（取代 PMS 跨庫 JOIN）
    measured_at timestamptz NOT NULL,              -- 資料時間（對齊 15 分）
    updated_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (plant_no, item),
    FOREIGN KEY (plant_no, item) REFERENCES spec(plant_no, item)
);

CREATE TABLE reading_history (                     -- C 項：append-only，永不 UPDATE
    id          bigserial PRIMARY KEY,
    plant_no    text NOT NULL,
    item        text NOT NULL,
    value       numeric,
    status      text NOT NULL,
    raw_text    text,
    -- ★稽核決策（2026-07-01）：法規稽核需要「當時管制值」逐時證據 →
    --   每筆讀值快照當下生效的 SPEC 三階管制值（沿襲舊 VOC_SCADA_HIST 亦存 OOS/OOC/alert1/recv 的做法）
    spec_oos_low   numeric, spec_oos_high   numeric,
    spec_ooc_low   numeric, spec_ooc_high   numeric,
    spec_alert_low numeric, spec_alert_high numeric,
    spec_recv_low  numeric, spec_recv_high  numeric,
    limits_extra   json,        -- SCADA/CWMS 自設管制值快照（泛型 JSON，引擎可攜）
    measured_at timestamptz NOT NULL,
    UNIQUE (plant_no, item, measured_at)
);
CREATE INDEX idx_rh_lookup ON reading_history (plant_no, item, measured_at DESC);
-- K1/K9 雨水溝三點連升：直接對本表用 window function，不需另存三欄
-- 容量估算：~200 項目 × 96 筆/日 ≈ 1.9 萬筆/日、700 萬筆/年，加快照欄位仍完全可承受

-- ============ 派報紀錄（D 項：明細正規化）============
CREATE TABLE mail_log (
    id         bigserial PRIMARY KEY,              -- 取代 logid
    plant_no   text NOT NULL,
    sent_at    timestamptz NOT NULL,               -- cdatetime（對齊 5 分）
    subject    text,
    body_note  text,                               -- 原 msg（人讀全文，回覆頁顯示用）
    reply_empno text, reply_reason text, reply_at timestamptz   -- 原因回覆回填
);
CREATE TABLE mail_log_item (                       -- 原 msg1/msg2 字串的正規化
    mail_log_id    bigint NOT NULL REFERENCES mail_log(id),
    item           text NOT NULL,
    condition_code text NOT NULL,   -- 'OOS'/'OOC'/'ALERT'/'RECV'/'LIMIT_MISMATCH'/'MAINTENANCE'/'BROKEN'
    detail         text,            -- 原條件敘述（信件顯示）
    escalation_stage smallint NOT NULL DEFAULT 0,  -- 0/1/2（原 0/15/30 分）
    is_maintenance boolean NOT NULL DEFAULT false, -- true=原僅入 msg1 不入 msg2 的項目
    PRIMARY KEY (mail_log_id, item, condition_code)
);
CREATE INDEX idx_mli_dedup ON mail_log_item (item, condition_code);

-- ============ 隔離與簽核 ============
CREATE TABLE isolation (                           -- 原 VOC_closectl
    id         bigserial PRIMARY KEY,              -- 原 ccid
    ccno       text NOT NULL UNIQUE,               -- E 項：顯示編號 yyyymmddNNN，sequence 產生
    ttype      smallint NOT NULL CHECK (ttype IN (1,2)),   -- 1新增/2修改
    org_id     bigint REFERENCES isolation(id),    -- 原 orgccid
    plant_id   smallint NOT NULL REFERENCES plant(plant_id),
    mdfdesc    text, remark text,
    stime      timestamptz NOT NULL, etime timestamptz NOT NULL,
    cemp_no    text NOT NULL, cemp_name text,
    created_at timestamptz NOT NULL DEFAULT now(),
    flow_id    bigint,
    fstatus    smallint NOT NULL DEFAULT 0,        -- FlowStatus enum 值不變（0/1/7/8/12）
    deleted    boolean NOT NULL DEFAULT false, del_clerk text,
    CHECK (etime > stime)
);
CREATE TABLE isolation_item (
    isolation_id bigint NOT NULL REFERENCES isolation(id),
    plant_no  text NOT NULL,
    item      text NOT NULL,                       -- 存原名 pH1/COD2
    source_id smallint NOT NULL,
    PRIMARY KEY (isolation_id, plant_no, item)
);
CREATE TABLE isolation_history (                   -- 原 VOC_closectl_his：主檔快照+utype
    id bigserial PRIMARY KEY,
    isolation_id bigint NOT NULL REFERENCES isolation(id),
    utype smallint NOT NULL,                       -- 1新增/2送簽/3修改
    snapshot jsonb NOT NULL,                       -- H 項精神：整單快照存 jsonb 取代全欄複製
    uclerk_no text, uclerk_name text,
    utime timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE spec_apply (                          -- 原 VOC_SPEC_apply
    id bigserial PRIMARY KEY,
    formno text NOT NULL UNIQUE,
    ftype  char(1) NOT NULL CHECK (ftype IN ('I','M','D')),
    plant_no text NOT NULL, item text NOT NULL,
    payload jsonb NOT NULL,                        -- 申請的規格新值（I/M 用）
    emp_no text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    flow_id bigint, fstatus smallint NOT NULL DEFAULT 0
);

-- J 項測試期方案：SignFlow 同構表（欄位語意 1:1，正式去向另議）
CREATE TABLE sign_emp  (emp_id bigserial PRIMARY KEY, emp_no text UNIQUE NOT NULL,
                        emp_name text, email text, pos_id int, dep_no text);
CREATE TABLE sign_flow (flow_id bigserial PRIMARY KEY, frule_id int NOT NULL,
                        act_step int, fstatus smallint NOT NULL, fid bigint,
                        emp_id bigint REFERENCES sign_emp(emp_id),
                        fstime timestamptz, fetime timestamptz, show_info text);
CREATE TABLE sign_flow_step (flow_id bigint NOT NULL REFERENCES sign_flow(flow_id),
                        fstep int NOT NULL, ftype int, emp_id bigint, pos_id int,
                        sign_emp_id bigint, sign_emp_name text, sign_time timestamptz,
                        sign_action smallint, sign_memo text,
                        PRIMARY KEY (flow_id, fstep, emp_id));

-- ============ 名單、權限、其他 ============
CREATE TABLE mail_list (                           -- F/I 項：去掉 Mail1/SM1/SM/cellphone
    plant_no text NOT NULL,
    rpttype  text NOT NULL,
    emp_no   text NOT NULL,
    emp_name text, notes_id text,
    mail_type text NOT NULL CHECK (mail_type IN ('TO','CC')),
    mail_on  boolean NOT NULL DEFAULT true,
    sign_grp boolean NOT NULL DEFAULT false,
    PRIMARY KEY (plant_no, rpttype, emp_no)
);
CREATE TABLE mail_type (type_id smallint PRIMARY KEY, rpttype text NOT NULL UNIQUE);

CREATE TABLE dept (
    plant_id smallint NOT NULL REFERENCES plant(plant_id),
    dept_no  text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (plant_id, dept_no)
);

CREATE TABLE acl_role        (role_id smallint PRIMARY KEY, role_name text NOT NULL);
CREATE TABLE acl_user_role   (role_id smallint NOT NULL, emp_no text NOT NULL,
                              dept_no text, plant_no text NOT NULL,   -- 'ALL' 語意沿用
                              stype text, PRIMARY KEY (role_id, emp_no, plant_no));
CREATE TABLE acl_role_rights (role_id smallint NOT NULL, rights_id smallint NOT NULL,
                              allow_rights int NOT NULL,              -- 位元旗標沿用（相容）
                              PRIMARY KEY (role_id, rights_id));

CREATE TABLE tranlog (                             -- H 項
    id bigserial PRIMARY KEY,
    emp_no text NOT NULL, log_type char(1) NOT NULL,
    data_before jsonb, data_after jsonb,
    remark text, created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE employee (                            -- J 項：UTIDB.Employee 快取
    emp_no text PRIMARY KEY, emp_name text, notes_id text,
    dept_no text, is_leave boolean NOT NULL DEFAULT false,
    synced_at timestamptz
);

CREATE TABLE system_config (key text PRIMARY KEY, value text NOT NULL,
                            updated_at timestamptz NOT NULL DEFAULT now());
-- 例：('mail_paused','false')  ← F 項取代 Mail1/SM1

CREATE TABLE curve (plant_no text NOT NULL, item text NOT NULL, url text,
                    PRIMARY KEY (plant_no, item));   -- 歷史曲線去留=HANDOVER 未決，先保留
```

## 三、A ↔ B 對照表

| A（MSSQL 舊表） | B（PG 新表） | 變更摘要 |
|---|---|---|
| VOC_plant | plant | isShow→is_show；29/GMO/環工部→kind 欄位 |
| VOC_item | item | +display_name（吸收 pH1/COD2 程式別名） |
| VOC_source | source | 照搬 |
| VOC_SPEC | spec | 門檻 varchar→low/high numeric+status；LAW 保留文字 |
| VOC_SCADA_WEB | reading_current | rvalue→value+status+raw_text；broken→comm_ok+status；light 淘汰；管制值拆欄；+rain_24h |
| VOC_SCADA_HIST | reading_history | append-only；只留讀值（管制值歷史不搬，如需另議）；三點連升改 window function |
| VOC_MAIL_Log | mail_log + mail_log_item | msg1/msg2 字串→明細表；msg→body_note |
| VOC_report | —（淘汰） | CTE 取代 |
| VOC_SMS_Log | —（淘汰） | 簡訊停用 |
| VOC_closectl / _list / _his | isolation / isolation_item / isolation_history | ccid→id bigserial；ccno UNIQUE+sequence；his 改 jsonb 快照 |
| VOC_SPEC_apply | spec_apply | 規格欄全複製→payload jsonb |
| SignFlow.base_flow/base_flowd/base_emp | sign_flow / sign_flow_step / sign_emp | 測試期同構表；正式去向=決策點 J |
| VOC_Mail_List | mail_list | 去 SM/cellphone/Mail1/SM1；mail/signgrp→boolean |
| VOC_Mail_Type | mail_type | 照搬 |
| VOC_dept | dept | 照搬+FK |
| sys_acl* 三表 | acl_* 三表 | 位元旗標沿用（程式 has_right 不變） |
| VOC_tranlog | tranlog | 斜線串→jsonb |
| UTIDB.Employee | employee（快取） | 轉拋/排程同步 |
| VOC_Curve | curve | 暫保留（功能去留另議） |
| VOC_EmptyCell | —（併入 spec 或前端設定，低優先） | |
| VOC_SCADA_TagList/Tag、VOC_Flow_Sta、VOC_AVG 等 | —（第二階段轉拋 JOB 設計時一併決定） | |

## 四、決策紀錄（2026-07-01 使用者回覆）

| # | 問題 | 決策 |
|---|---|---|
| A+B | 讀值與門檻拆數值欄 | ✅ 採建議案 |
| C | 隔離改推導、歷史 append-only | ✅ 採建議案 |
| D | 派報紀錄正規化（mail_log_item） | ✅ 採建議案 |
| J | SignFlow 測試期 B 內同構表 | ✅ 採建議案，正式去向後議 |
| 命名 | snake_case 新名＋對照表 | ✅ 採建議案（凍結前可反悔） |
| **歷史管制值** | 逐時快照 | ✅ **需要**（環保稽核要「當時管制值」證據）→ DDL 已更新 |
| **DB 引擎** | PG 測試、**正式未定** | → 引擎可攜規範（見下節），正式引擎於 Phase C 前決定 |
| **新廠區時程** | **3 個月內**，可先用轉拋程式沿用舊架構 | → 雙軌道計畫，見 `docs/PM執行路線圖.md` |
| 舊系統退場 | 雙軌並行比對後切換 | → 對帳機制設計，見路線圖 |

## 五、引擎可攜規範（因「正式引擎未定」新增，SQL 移植 agent 必守）

1. 優先用 **SQLAlchemy Core/ORM 表達式**，少寫 raw SQL；必要的 raw SQL 限用兩邊共通語法。
2. 型別用 SQLAlchemy 泛型：`JSON`（不是 PG 專屬 `JSONB`）、`DateTime(timezone=True)`、`Numeric`、`Boolean`。
3. 禁用單邊方言：PG 的 `ON CONFLICT`/`DISTINCT ON`、MSSQL 的 `IIF`/`TOP`——用 `case()`、`limit()` 等可攜寫法。
4. 自增主鍵用 `Identity()`/`BigInteger+autoincrement`（兩邊皆通），不要手寫 `bigserial`/`IDENTITY` DDL——
   **建表一律走 SQLAlchemy `metadata.create_all()` 或 Alembic**，本文件的 DDL 是「語意規格」不是部署腳本。
5. 方言特化（如 window function 細節差異）集中到獨立模組，換引擎只改一處。

---

*v2。已凍結供 Phase A 執行；執行順序與里程碑見 `docs/PM執行路線圖.md`。*
