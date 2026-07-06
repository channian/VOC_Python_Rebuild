# 本機 PostgreSQL 測試環境（Schema B / WP1）

> 對象：在家（或任何非沙盒環境）用 Docker 重現 Phase A 的 Schema B 測試環境。
> 沙盒/公司環境若已有原生 PostgreSQL 16，可改用 `scripts/dev_pg.sh`（見本文件最後一節），
> 兩種方式殊途同歸——最終都是讓 `VOC_B_DB_URL` 指到一個可連線的 PostgreSQL。

## 一、你會得到什麼

- 一個本機 PostgreSQL 16 容器，資料庫 `voc_b`，帳號 `voc`／密碼 `voc`（僅供本機開發測試，非正式密碼）。
- `models_b.py` 定義的全部 27 張 Schema B 資料表（`plant`/`item`/`spec`/`reading_current`/
  `reading_history`/`isolation`/`sign_flow`/`tag_mapping`/`kepware_sim`… 等，詳見
  `docs/schema_B_設計提案.md` 與 `docs/PhaseA執行規格書.md`）。
- 種子資料：測試廠區 `TEST1`（pH1 雙邊 6-9／Cu1 單邊／VOC1 單邊）、雙測試身分
  `TEST001`（申請人）／`TEST999`（簽核人），以及模擬 A 端 SCADA 表 `kepware_sim` 的六種讀值分類案例。

## 二、前置需求

- Docker（Desktop 或 Engine 皆可）——**僅本機/家用情境需要**；公司正式環境若 IT 已提供
  PostgreSQL 服務，跳過 Docker，直接看第九之一節。
- Python 3.11+，專案根目錄跑 `pip install -r requirements.txt`
  （2026-07-06 已修正：此檔案原本是 UTF-16 編碼且缺 `psycopg2-binary`，會導致
  `pip install` 直接報錯或裝不到 PG 驅動——已修好，現在照抄這行指令即可，不需要再手動補裝）。

## 三、步驟 1：用 Docker 起一個 PostgreSQL 16

```bash
docker run -d \
  --name voc-pg \
  -e POSTGRES_USER=voc \
  -e POSTGRES_PASSWORD=voc \
  -e POSTGRES_DB=voc_b \
  -p 5432:5432 \
  postgres:16
```

等待容器就緒（第一次啟動可能要幾秒鐘做初始化）：

```bash
docker exec voc-pg pg_isready -U voc
# 看到 "accepting connections" 就是就緒了
```

驗證可以連線：

```bash
docker exec -it voc-pg psql -U voc -d voc_b -c "SELECT version();"
```

> 若 5432 port 已被其他 PostgreSQL（例如本機原生安裝）佔用，把 `-p 5432:5432` 改成
> 例如 `-p 55432:5432`，並在下一步的 `VOC_B_DB_URL` 把 port 改成 `55432`。

## 四、步驟 2：設定 `VOC_B_DB_URL`

專案根目錄的 `.env`（複製自 `.env.example`）加入或確認這一行：

```
VOC_B_DB_URL=postgresql+psycopg2://voc:voc@localhost/voc_b
```

（`config.py` 的 `VOC_B_DB_URL` 預設值就是這個字串，本機用 Docker 起的容器帳密與資料庫名稱
完全對齊，通常不需要改動；如果你改了 Docker 的 port/帳密，這裡要對應調整。）

## 五、步驟 3：建表 + 灌種子資料

在專案根目錄（`VOC_Python_Rebuild/`）執行：

```bash
# 建表（create_all，冪等，重跑不會清掉既有資料/報錯）
python -c "from database_b import create_all_b; create_all_b()"

# 灌種子資料（先清後灌，可重複執行）
python scripts/seed_test_data.py
```

看到以下輸出代表成功：

```
[seed_test_data] 種子資料寫入完成。
  廠區：TEST1（plant_id=990），項目：pH1/Cu1/VOC1
  申請人：TEST001／簽核人：TEST999（notesid=TEST_PLACEHOLDER）
  kepware_sim：6 筆分類案例 ＋ 對應 tag_mapping
  system_config：staleness_minutes/sync_interval_minutes/dispatch_interval_minutes/mail_paused
```

> `TEST001`/`TEST999` 的 `notesid` 種子值是 `TEST_PLACEHOLDER`——如果你要實際測試派報寄信
> （例如之後 WP2/WP5 交付的同步 JOB／派報功能），要打開 `scripts/seed_test_data.py` 把這兩個
> 常數改成你自己的 Notes ID／收信信箱，再重新執行種子腳本。

## 六、步驟 4：跑 integration 測試

```bash
python -m pytest tests_integration/ -v
```

預期全綠（12 個測試，涵蓋：27 張表建表成功、種子資料存在、每張表可寫可查、
`isolation.etime>stime`／`tag_mapping` UNIQUE／`reading_history` UNIQUE 等關鍵約束生效、
`reading_history` 管制值快照欄位存在）。

> 如果 PostgreSQL 沒啟動或連不上，這個目錄的測試會**自動整批跳過**（`SKIPPED`，不是錯誤），
> 訊息會提示你檢查 `VOC_B_DB_URL`。這是設計上的行為，方便沒有 PG 的環境（例如 CI）
> 不會因為這個目錄而讓整個 pipeline 炸掉。

同時建議也跑一次既有的純邏輯測試，確認沒有動到 A 棧（MSSQL 版）的行為：

```bash
python -m pytest tests/ -v
```

## 七、步驟 5（WP5 交付後）：啟動 `main_b.py`

> ⚠️ 本文件撰寫時（WP1 階段）`main_b.py` 尚未交付，是 WP5 的產出。以下是**預期**指令，
> 供你在 WP5 完成後直接照抄；若屆時檔名/指令有調整，以 WP5 agent 的回報為準。

```bash
python main_b.py
# 預期：本機啟動 → http://localhost:8000/home（沿用既有 UI，只是資料來源換成 Schema B）
```

`main_b.py` 的設計是重用既有 `routers/`／`templates/`，只把 DB dependency 從
`database.py.get_voc_db` 換成 `database_b.py.get_b_db`，因此畫面應該與現行 MSSQL 版一致，
差異只在於資料是 `TEST1`／`TEST001`／`TEST999` 這組測試資料。

## 八、收尾／重來

清掉容器（資料一併清掉，之後要重測請從步驟一重新開始）：

```bash
docker stop voc-pg && docker rm voc-pg
```

只想清資料表但保留容器（回到「有 PG 但沒建過表」的狀態）：

```bash
python -c "from database_b import drop_all_b; drop_all_b()"
```

## 九、（附）沙盒等「本機已裝原生 PostgreSQL 16」環境的替代做法

如果你的環境（例如本專案的開發沙盒）已經裝了 PostgreSQL 16 的 binaries
（`/usr/lib/postgresql/16`），不需要 Docker，直接跑：

```bash
bash scripts/dev_pg.sh
```

這支腳本會冪等地：初始化＋啟動 PostgreSQL 16 的 `main` cluster、建立使用者 `voc`（密碼 `voc`）、
建立資料庫 `voc_b`，最後用 `psql` 驗證連線成功。跑完之後直接接續本文件第五節（建表＋灌種子資料）
即可，不需要再處理 Docker 相關步驟。此腳本已在專案沙盒環境實測可重複執行（冷啟動／已啟動兩種
情境皆驗證過）。

**注意**：`dev_pg.sh` 啟動的 PG cluster 不是常駐服務（沙盒容器重啟、閒置回收都會讓它停掉），
每次回來測試前**先重跑一次 `bash scripts/dev_pg.sh` 再跑測試**——腳本冪等，PG 已在跑的話
會直接略過初始化步驟，不會出錯。

## 九之一、公司正式／測試環境（IT 已提供 PostgreSQL 服務時）

這是「不是你自己起容器/裝 PG binaries，而是 IT 已經給你一顆可連線的 PostgreSQL」的情境。
跟前兩節的差別只在「PG 從哪來」，後續步驟完全一樣：

1. **跟 IT/DBA 要的資訊**：主機位址、port（預設 5432）、資料庫名稱（可以就叫 `voc_b`，
   或用公司命名慣例）、帳號密碼。**資料庫本身通常要請 DBA 先建好空的**
   （`CREATE DATABASE voc_b;`），本專案的程式**只會建表，不會建資料庫**。
2. **設定 `.env`**：
   ```
   VOC_B_DB_URL=postgresql+psycopg2://帳號:密碼@主機位址:5432/voc_b
   ```
3. **建表＋灌種子資料**（與第五節完全相同）：
   ```bash
   python -c "from database_b import create_all_b; create_all_b()"
   python scripts/seed_test_data.py
   ```
4. 若要讓派報信真的寄到你手上，記得同時確認 `.env` 的 `TEST_MODE=True`、
   `TEST_DEV_EMAIL=你的信箱`；種子資料裡 `TEST001`/`TEST999` 的 `notesid` 預設是
   `TEST_PLACEHOLDER`，要收信仍建議照第五節的提示改掉。
5. **`MOCK_USER_EMPNO`／`MOCK_USER_NAME`**（`.env.example` 已列出）：測「申請人核准不了自己
   的單」這種閉環時，在 `TEST001`（申請人）／`TEST999`（簽核人）之間切換。
6. **網路與防火牆**：公司環境常有網段限制，執行 `python main_b.py` 的機器要能連到
   PG 的 port（5432 或 IT 指定的 port）；反過來若你要讓同事也能用瀏覽器連你的
   `main_b.py`（監聽 `0.0.0.0:8000`），也要確認防火牆開放 8000。
7. 跑 `python -m pytest tests_integration/ -v` 驗證——跟前面章節一樣，全綠代表這顆
   PG 上的 Schema B 運作正常。

**結論**：「建好資料庫＋灌種子資料」是核心的兩步沒錯，但完整順序是
`.env 設連線字串 → create_all_b()（建表）→ seed_test_data.py（灌資料）→ 視需要調整
TEST_DEV_EMAIL/MOCK_USER_EMPNO/notesid → 跑 main_b.py 或 tests_integration/ 驗證`，
資料庫「空殼」本身要先請 DBA 建好，程式不會自己建資料庫（只會建表）。
