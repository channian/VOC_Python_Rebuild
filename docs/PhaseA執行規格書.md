# Phase A 執行規格書（含 Track 1 同步核心）

> 依據：`docs/schema_B_設計提案.md`（v2）、`docs/PM執行路線圖.md`。
> 本文件是發包給平行 agent 的工作規格；主控（Claude 主線）負責檢驗與整合，不下場實作。
> 建立日期：2026-07-01

---

## 一、本階段新增的決策紀錄（2026-07-01 使用者回覆）

| 項目 | 決策 |
|---|---|
| A 端資料表結構 | `datetime, tagname, value, quality` 四欄（既有 Kepware 轉拋 JOB 寫入，別的專案維運） |
| 斷訊判斷 | 逾時法：staleness 門檻**先設 30 分鐘**，存 `system_config` 可調；來源最快可到每分鐘（Kepware 訂閱） |
| quality 欄陷阱 | 有時 quality=good 但 value 沒取到（原因未排除）→ 分類規則須涵蓋此情境（見第三節） |
| SCADA 自設管制值 | 可從 Kepware 端取得（tag_mapping 對應到管制值欄位即可） |
| CWMS | **完全不動**，維持現行 HTTP API 路徑 |
| PMS 雨量 | 走向待使用者內部討論（現行路線與選項見第二節），本階段 `rain_24h` 欄位保留、來源先缺值 |
| SignFlow | **VOC 自管**（B 內 sign_flow 表轉正）＋ adapter 介面可抽換；已確認目前簽核未串稽核 |

## 二、PMS 雨量現行路線（回覆使用者提問，供內部討論用）

- 來源：PMS 平台（風雨/水情系統）自行採集，寫入 `[PMS].[dbo].[Water_WindRainHistValue]`，
  每 15 分鐘一筆，欄位含 `UpdateTime` 與 `TwentyFourHours`（24 小時累積雨量），**無廠區鍵**（全站一筆）。
- VOC 用法：查雨水溝時 `LEFT JOIN ... ON UpdateTime = @當下對齊15分的時間戳`——
  **時間戳必須完全相等**，PMS 晚寫/漏寫該筆就 JOIN 不到 → 拿不到雨量 →
  K1/K9 紅燈條件（讀值=1 且 24H累積=0）永遠不成立，等於**靜默漏警報**。這是現行架構的脆弱點。
- 新架構選項（待定）：
  1. **（建議）雨量計 tag 若進得了 Kepware→A 表**：我們的同步 JOB 自算 24h 滾動累積
     （`reading_history` window sum），完全去除 PMS 依賴；
  2. 保留讀 PMS，做成 source adapter，並把「完全相等」改「容忍窗內取最近一筆」修掉脆弱點；
  3. PMS 端改寫入 A 表。

## 三、讀值分類規則（同步 JOB 核心，必須做成純函式）

輸入：A 端一筆 `(datetime, tagname, value, quality)` ＋ 該 tag 的 mapping ＋ 現在時間。輸出寫入 B。

| 情境 | status | comm_ok | value |
|---|---|---|---|
| quality=good 且 value 為合法數字 | normal | true | 數字 |
| quality=good 且 value 為 'N.D' | nd | true | NULL |
| quality=good 且 value 為 '<X'（如 <0.05） | below_lod | true | X |
| quality=good 但 value 空/無法解析（**使用者已知陷阱**） | error | true | NULL |
| quality≠good | broken | false | NULL |
| 該 tag 超過 staleness 門檻無新資料（獨立看門狗檢查） | 維持最後 status | **false** | 維持最後值 |

- staleness 門檻讀 `system_config['staleness_minutes']`（預設 30）；同步間隔 `sync_interval_minutes`（預設 5）；
  派報維持 15 分鐘對齊（影子運行期與舊系統行為對齊）。
- 隔離中項目：**不改讀值**（C 決策），派報/燈號端由 isolation 區間 JOIN 判定 maintenance。

## 四、雙棧並存策略（保護使用者進行中的 MSSQL 測試）

現行 `services/` + `main.py`（MSSQL 版）**一律不准動**——使用者仍在公司環境對它做平行測試。
B 棧全部走新檔案：

```
database_b.py          # B 引擎/Session（環境變數 VOC_B_DB_URL，預設本地 PG voc_b）
models_b.py            # Schema B 全部表（SQLAlchemy 2.0 宣告式，引擎可攜型別）
services_b/            # B 版資料層：SQL 全部重寫為可攜 SQLAlchemy；
                       #   純邏輯（evaluate_row、燈號、驗證器…）一律 import 現有 services 重用，禁止複製
sync_service.py        # (services_b 內) 同步 JOB 核心：tag_mapping 驅動 A→B
main_b.py              # B 版應用組裝（router 重用現有、db dependency 換 B）
scripts/dev_pg.sh      # 沙盒/本機啟動 PG + 建庫
scripts/seed_test_data.py   # 種子資料（見第六節）
tests_integration/     # 真 PG 整合測試（獨立目錄，純邏輯 tests/ 不受影響）
docs/本機PG測試環境.md  # 使用者家用 Docker 指南
```

- **引擎可攜規範**（schema 提案第五節）為強制條款：SQLAlchemy 泛型型別、禁單邊方言、
  建表走 `metadata.create_all()`。
- Schema 以 `docs/schema_B_設計提案.md` v2 為準，另加本階段新表：

```sql
CREATE TABLE tag_mapping (            -- 同步 JOB 的中央設定（舊 VOC_SCADA_TagList 正名後代）
    id bigserial PRIMARY KEY,
    source_table text NOT NULL,       -- A 端表名
    tagname     text NOT NULL,
    plant_no    text NOT NULL,
    item        text NOT NULL,
    target_field text NOT NULL DEFAULT 'value',
        -- value / scada_oos_high / scada_oos_low / scada_ooc_high / scada_ooc_low
        --       / scada_alert_high / scada_alert_low
    enabled     boolean NOT NULL DEFAULT true,
    remark      text,
    UNIQUE (source_table, tagname)
);
-- system_config 種子鍵：staleness_minutes=30, sync_interval_minutes=5,
--                       dispatch_interval_minutes=15, mail_paused=false
```

## 五、工作包（WP）與檔案分工

### WP1 — 基盤（先行，單一 agent）
models_b.py、database_b.py、config.py（加 VOC_B_DB_URL）、scripts/dev_pg.sh、
scripts/seed_test_data.py、tests_integration/conftest.py + test_schema.py、docs/本機PG測試環境.md。
驗收：沙盒 PG 上 create_all + seed + smoke 測試全綠；純邏輯測試 256 個不受影響。

### WP2 — 同步 JOB 核心（WP1 後）
services_b/sync_service.py：分類純函式（第三節規則）、tag_mapping 讀取、A 表讀取（含模擬 A 表）、
寫 reading_current + append reading_history（含 SPEC 管制值快照）、staleness 看門狗、
**legacy sink 骨架**（寫舊 VOC_SCADA_WEB 格式，Track 1 用，介面留好、本階段不需連 MSSQL 實測）。
tests_integration/test_sync.py：用 PG 內模擬 A 表全流程驗證。

### WP3 — B 資料層移植（控制/簽核組）（WP1 後）
services_b/control_service.py、flow_service.py：對 isolation/sign_flow 表重寫資料層，
純邏輯與 FlowStatus 從現有 services import。tests_integration/test_control_flow.py：
申請→簽核→核准/否決→his/orgccid 全流程真 DB 驗證。

### WP4 — B 資料層移植（儀表板/規格/QA組）（WP1 後）
services_b/dashboard_service.py、spec_service.py、qa_service.py：
燈號查詢改讀 reading_current（value+status 新形狀）、規格 CRUD+簽核申請、QA 寫值。
tests_integration/test_dashboard_spec.py。

### WP5 — B 資料層移植（名單/查詢/派報組）＋ main_b（WP1 後）
services_b/maillist_service.py、dept_service.py、acl_service.py、history_service.py、
report_service.py、warning_service.py、dispatch_service.py（讀寫 mail_log/mail_log_item 新形狀）＋
main_b.py 組裝。tests_integration/test_dispatch_b.py（派報寫入與首發/再發用明細表判斷）等。

WP2–WP5 檔案互不重疊，可四路平行；共用檔（models_b/database_b/conftest）WP1 定稿後凍結，
後續 agent 只准 import 不准改（缺欄位缺表時回報主控裁決）。

## 六、種子資料規格（scripts/seed_test_data.py）

- 測試廠區 `TEST1`（kind=normal）＋ 3 個項目（pH 雙邊 6-9、Cu 單邊、VOC 單邊）＋ SPEC 門檻
- 雙測試身分：`TEST001`（申請人）／`TEST999`（簽核人，mail_list SignGrp=1、TO），
  notesid 都填 `TEST_PLACEHOLDER`（實際使用時使用者改成自己的）
- acl/dept/sign_emp/mail_type 最小資料
- 模擬 A 端表 `kepware_sim(datetime, tagname, value, quality)` ＋ 對應 tag_mapping：
  含正常值、超標值（觸發派報）、N.D、<0.05、quality=bad、quality=good但value空 六種案例
- reading_current/history 初始一輪

## 七、共同規範（每個 agent 提示詞都會附）

繁體中文註解；禁 git 寫入；禁動現有 services/routers/templates/tests 與 main.py；
引擎可攜規範強制；integration 測試須在沙盒 PG 實跑通過；回報格式同前兩波。

## 八、Phase A 驗收（主控檢驗清單)

1. `pytest tests/`（純邏輯 256+）與 `pytest tests_integration/`（真 PG）全綠
2. main_b.py 可啟動、儀表板讀 B 資料正常渲染
3. 同步 JOB：模擬 A 表 → B，六種分類案例正確、staleness 看門狗生效
4. 閉環腳本演練：seed → 申請隔離（TEST001）→ 簽核（TEST999）→ 改讀值超標 → 派報只寄 TEST_DEV_EMAIL
5. `docs/本機PG測試環境.md` 照著做能在使用者家中 Docker 重現 1–4
