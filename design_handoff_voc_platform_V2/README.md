# Handoff: VOC 監測平台（儀表板 / 歷史曲線 / 登入）

## Overview
一套廢水／VOC 放流水質監測操作平台的三個畫面：登入頁、首頁儀表板（廠區異常總覽 + 手風琴明細）、歷史曲線查詢頁（依廠棟 + 指標 + 時間區間畫趨勢圖）。目標使用者是廠務/環安操作員，需要在深色、高資訊密度的 SCADA 風格介面下快速辨識異常燈號並下鑽查看細節。

## About the Design Files
本資料夾內的 `.dc.html` 檔案是**用 HTML 做的設計參考／原型**，用來展示畫面外觀與互動行為，並不是要直接搬進正式專案的程式碼。請在目標專案既有的技術環境（既有框架、元件庫、狀態管理方式）中，依這些設計重新實作；若專案尚未決定技術棧，請選擇最適合的框架來實作。

檔案內的假資料（廠區代號、監測項目、門檻值、時間序列數值）全部是隨機產生的示意資料，正式串接時請換成真實 API。

## Fidelity
**High-fidelity（高保真）**：顏色、字體、間距、圓角、陰影、燈號規則、hover/active 狀態都已定案，請依照這些視覺細節pixel-level 還原。版面結構（grid 欄寬、header 高度等）也應精確對齊。

## Files
- `VOC 登入.dc.html` — 登入頁
- `VOC Dashboard.dc.html` — 首頁儀表板（廠區導覽 + 異常摘要 + 手風琴明細 + 完整功能 modal）
- `VOC 歷史曲線.dc.html` — 歷史曲線查詢頁
- `VOC 規格維護.dc.html` — 規格維護（清單 / 送簽申請 / 我的申請 / 待簽核，新增）
- `VOC 異常報表.dc.html` — 異常報表（長條圖 / 交叉統計 / 排行榜，新增）
- `_ds/` — 綁定的設計系統（Kepware Monitor Design System）原始資料夾，含 `colors_and_type.css`（全部設計 token）與元件庫
- `assets/` — 設計系統的 logo / icon 參考檔
- `support.js` — 本專案的 DC 執行期腳本，**開發時不需要**，僅用於讓 `.dc.html` 在此設計工具內可預覽；請忽略，勿搬進正式專案

> 直接用瀏覽器打開任一 `.dc.html` 即可看到即時可互動的畫面。

---

## Design Tokens
完整 token 定義在 `_ds/.../colors_and_type.css`，重點如下：

**Surfaces（深色堆疊）**
- `--bg-0` `#05070d`（頁面最底層，登入頁背景）
- `--bg-1` `#0a0f1a`（容器背景，儀表板頁面背景）
- `--bg-2` `#0f172a`（卡片背景）
- `--bg-3` `#172033`（輸入框／hover 元素背景）
- `--bg-4` `#1e293b`（更深一層 hover）

**Accent / Action**
- `--accent` 青色 `#22d3ee` — focus 環、即時資料指示、連結
- `--blue` `#3b82f6`（hover `--blue-hover`）— 主要按鈕
- 登入頁與側欄 Logo 使用漸層文字：`linear-gradient(90deg, #eab308, #22c55e, #22d3ee)`（黃 → 綠 → 藍），`-webkit-background-clip: text` 實現

**狀態色（Status）**
- OK `--ok` `#22c55e`　WARN `--warn` `#f59e0b`　ERR `--err` `#ef4444`　INFO `--info` `#60a5fa`　MUTED `--muted` `#475569`
- 每個狀態都有對應的 10% 透明背景版（`-bg`）與 35–45% 透明發光版（`-glow`，搭配 `box-shadow` 做脈動光暈）
- 特殊「Y 預警」色不在標準色階中，直接使用 `#eab308`（黃）

**文字**
- Sans：Inter（fallback Noto Sans TC / Microsoft JhengHei / PingFang TC）
- Mono：JetBrains Mono — 所有數值、代號、時間戳、IP、座標一律使用等寬字體
- 微標籤（如 `PLANTS`、`LEGEND`）：11px、全大寫、`letter-spacing: .08–.12em`、顏色 `--fg-2` 或 `--fg-3`

**間距 / 圓角 / 陰影**
- 間距基準 4px，常用 4/8/12/14/16/18/20/24/28/32/36/48
- 圓角：卡片 10–14px；按鈕/輸入框 6px；狀態 pill 999px（膠囊）
- 陰影分級 `--shadow-1`（卡片）/ `--shadow-2`（懸浮面板、modal）/ `--shadow-3`
- Focus 環一律 `box-shadow: 0 0 0 3px var(--accent-soft)` + 邊框轉 `--accent`

**動效**
- 過場 120–320ms，`cubic-bezier(0.4,0,0.2,1)`（即 `var(--ease)`）
- 即時資料綠燈 dot：`opacity 1→0.5` 1.5s 無限循環（`@keyframes pulse`）
- 按鈕 hover：`translateY(-1px)` + 陰影加深；無 scale/rotate 花俏動效

---

## 畫面 1：登入頁（`VOC 登入.dc.html`）

**Purpose**：操作員輸入帳密或走企業 SSO 進入平台。

**Layout**
- 全螢幕置中卡片，`400px` 寬（`max-width: 92vw`），背景為 `--bg-0` + 兩個角落的低透明度放射狀光暈（青色右上角 8%、藍色左下角 6%）+ 32px 網格線疊加（`rgba` 極淡，不可搶視覺）
- 卡片：`--bg-2` 背景、1px `--border-1` 邊框、14px 圓角、`--shadow-2`，內距 `36px 34px 30px`，內部 flex-column，`gap: 22px`

**Components（由上到下）**
1. **Logo 區塊**：置中。「VOC」漸層文字，目前使用者已手動調整為 **40px**、`font-weight: 800`，漸層 `linear-gradient(90deg,#eab308,#22c55e,#22d3ee)` 文字裁切；右下角疊加 5×7px 青色脈動圓點。下方兩行：「VOC 監測平台」（15px/700/`--fg-1`）與副標「WASTE / VOC MONITOR」（mono、10.5px、`--fg-3`、大寫、letter-spacing .1em）
2. 1px 分隔線（`--border-1`）
3. **帳號欄位**：label「帳號 ACCOUNT」（10.5px/600/大寫/`--fg-2`），input placeholder 現為「AD帳號」，深色輸入框樣式（`--bg-3` 背景、1.5px `--border-3` 邊框、6px 圓角、13.5px 文字），focus 時邊框轉 `--accent` + accent-soft 光環
4. **密碼欄位**：label「密碼 PASSWORD」（忘記密碼連結已依需求移除）。輸入框右側有顯示/隱藏密碼切換按鈕（眼睛 icon，Lucide 風格 SVG，2px stroke）
5. **記住此裝置** checkbox：16×16px 自訂方框，勾選時背景 `--accent`
6. **錯誤訊息**（條件顯示）：紅色系提示條，`--err-bg` 背景 + `--err` 文字 + 驚嘆號 icon，文案「帳號或密碼錯誤，請重新輸入」
7. **登入按鈕**：全寬、`--blue` 背景、白字、700 字重、`--glow-blue` 陰影，loading 狀態顯示白色旋轉圈 + 文案「登入中…」
8. 底部 footer 文字：「KEPWARE PROCESS MONITOR ・ v2.4.0」，mono、10.5px、`--fg-3`

**（已移除）SSO 登入按鈕與「忘記密碼？」連結** — 依最新需求拿掉，勿再加回。

**Interactions**
- 送出表單：若帳號或密碼為空 → 顯示錯誤條；否則進入 700ms loading，之後導向 `VOC Dashboard.dc.html`
- 眼睛 icon 切換 input type text/password
- checkbox 點擊切換勾選狀態

**State**
- `user`, `pass`（文字）
- `pwHidden`（bool，控制密碼顯示）
- `remember`（bool）
- `loading`（bool，送出中）
- `hasError`（bool，帳密驗證失敗）

---

## 畫面 2：首頁儀表板（`VOC Dashboard.dc.html`）

**Purpose**：跨廠區監看放流水質/VOC 燈號異常，可篩選、搜尋、下鑽到單一監測項目細節，並連到歷史曲線。

**Layout**
- 左側固定側欄 `236px` 寬（`--bg-2`，右邊框 `--border-1`，`position: sticky`，隨頁面高度捲動）+ 右側主內容 `flex:1`
- 主內容 header 高 `64px`，`--bg-2` 背景，sticky top
- 內容區 `max-width: 1440px`，`padding: 20px 28px 48px`

**側欄結構（上到下）**
1. Logo 區：與登入頁一致的漸層「VOC」文字（22px）+ 平台名稱「VOC 監測平台」+ 副標「WASTE / VOC MONITOR」
2. 「廠區 PLANTS — 異常置頂」分區標籤，下方為依嚴重度排序（R > O > O2 > Y > 斷訊 > 正常）的廠區清單，每列：左側 3px 色條（依最高嚴重度上色，R 級加發光陰影）+ 廠區代號（mono, 13px, 700）+ 右側狀態 pill（如 `R1`、`O≠2`）
3. 底部「燈號 LEGEND」說明區：列出 6 種燈號圖示語意（R 圓點脈動 / O 三角 / O≠ 虛線菱形 / Y 黃色菱形 / G 空心圓 / 斷訊斜紋方塊）— **這組視覺語意是本設計的核心，勿更改圖形或配色**

**主內容**
1. **異常摘要橫條**：4 張固定寬（128px）的統計卡（紅燈 R / 橙燈 O / 黃燈 Y / 斷訊／保養），每張顯示大字級數字（mono, 30px），R>0 時卡片邊框與陰影轉紅並發光；右側一張彈性寬卡片「異常速覽 ACTIVE ANOMALIES」，把所有 R/O/O2 異常列成可點擊的膠囊 chip（廠區・項目 數值）
2. **篩選列**：狀態 chip（全部/只看異常/R/O/Y/斷訊）+ 分隔線 + 資料來源 chip（SCADA/CWMS/QA手測）+ 右側搜尋框（icon-left input，可搜廠區或項目）
3. **廠區手風琴列表**：每個廠區一張卡片，header 列可點擊展開/收合（chevron 旋轉動畫），顯示代號、描述、狀態 pill 們、項目數；R 級廠區卡片邊框/陰影轉紅高亮。展開後是一張 8 欄 grid 表格（狀態 / 監測項目 / 最新讀值 / 單位 / 來源 / 備註 / 歷史 / 展開箭頭），列可再點擊展開子面板，顯示 SPEC 門檻（OOS/OOC/Alert/允收/法規）、系統管制值比對（SCADA vs CWMS 是否與 SPEC 一致）、以及雨水溝廠區特有的 24H 累積雨量欄位
4. 每列右側「曲線 ↗」連結（僅部分項目有 `url`）導向 `VOC 歷史曲線.dc.html`
5. 右上角工具列：「派送名單」「規格維護」「隔離申請」3 個常駐按鈕 + 「更多工具」下拉選單（分 4 群組：派送與簽核／資料與量測／異常紀錄／系統管理，共 11 個功能入口，新加入的項目標「已改版」pill）。「規格維護」「異常報表」直接連到獨立頁面；其餘（派送名單維護、隔離申請、簽核管理、QA 手測值、異常查詢、異常回覆、中水緊急通知、部門權限、ACL 使用者權限）都在同一組 modal 內完整實作了新增/刪除/驗證/確認流程與 toast 提示，不再是佔位說明。落地時建議改為 `<dialog>` + 局部載入掛回既有表單，**不要用 Bootstrap Modal**

**Interactions**
- 點擊統計卡／chip／篩選 chip → 套用對應的狀態/來源篩選（同 key 再點一次會清除篩選）
- 搜尋框即時過濾（廠區代號或項目名稱，忽略大小寫）
- 廠區卡片、監測項目列可各自獨立展開/收合（`expanded` map by 廠區代號、`openRow` 記錄目前展開的單一項目 id）
- 每 `refreshMinutes`（tweak，預設 15 分鐘）觸發一次「資料更新」倒數重置，header 右側顯示 mm:ss 倒數與最後更新時間

**State**
- `fStatus`（狀態篩選 key）、`fSource`（來源篩選）、`search`（字串）
- `expanded`（`{ [廠區代號]: bool }`）、`openRow`（目前展開的項目 id 或 null）
- `modal`（目前開啟的工具 modal 標題或 null）、`moreOpen`（更多工具下拉是否展開）
- `secs` / `updatedAt`（倒數計時器狀態，`componentDidMount` 啟動 `setInterval`）
- 各 modal 各自的資料／表單 state（派送名單 `mlRows`/`mlForm`、隔離申請 `ctlRows`/`ctlForm`、簽核 `flowRows`、QA 手測 `qaRows`、異常查詢回覆 `histRows`、中水通知 `waterSelected` 等）與全域 `toast`

**Tweaks（本設計已開放的參數化開關）**
- `refreshMinutes`（int, 1–60，預設 15）— 資料刷新週期
- `distinguishSyncOrange`（bool，預設 true）— 是否把「管制值不同步」的 O 燈以虛線菱形（`O≠`）與一般 O 燈區分
- `compactRows`（bool，預設 false）— 表格列是否使用更緊湊的內距

---

## 畫面 3：歷史曲線頁（`VOC 歷史曲線.dc.html`）

**Purpose**：選擇廠棟＋一或多個放流指標＋時間區間，畫出對應的歷史趨勢折線圖，並可匯出 CSV。

**Layout**
- Header 同儀表板風格（64px, `--bg-2`），左側「← 儀表板」返回連結、標題「歷史曲線」，右側顯示目前查詢摘要（廠棟・日期區間・點數）與「匯出 CSV」按鈕
- 內容區 `max-width: 1440px`，`padding: 20px 28px 48px`

**查詢條件卡片**（`--bg-2` 卡片，12px 圓角）
1. **廠棟 PLANT**：原生 `<select>` 下拉選單（單選，12 個廠棟選項），深色樣式（`--bg-3` 背景、自訂右側 chevron icon）
2. **指標 METRIC**：自訂多選下拉（按鈕顯示目前已選摘要，如「pH、COD、VOC」或「pH、COD、VOC 等 5 項」）。點開後彈出面板：每個指標一列（16×16px 勾選框 + 名稱 + 右側單位），底部「清除」／「完成」兩個按鈕
3. **時間 RANGE**：5 個按鈕 chip（24H / 7D / 30D / 90D / 自訂區間）；選「自訂區間」時右側出現兩個原生 `<input type="date">`（`color-scheme: dark`）

**趨勢圖區**（每個已選指標各一張卡片，依序垂直排列）
- 卡頭：指標名稱（15px/700）+ 廠棟・單位（mono, `--fg-3`）+ 若有超標則顯示「超標 N 次」紅色 pill；右側統計列：最新／平均／最大／最小（mono 數字，最新值依是否超標上色）
- SVG 折線圖（`viewBox 0 0 1000 240`）：
  - 5 條水平網格線 + 左側對應數值刻度
  - OOS 門檻線（紅色虛線）與 OOC 門檻線（橙色虛線，`showOoc` tweak 控制是否顯示），線右側標註數值
  - 面積漸層填色（`--accent` 極低透明度）+ 主線（`--accent` 實線）
  - 超出 OOS 的資料點以紅點標記、OOC~OOS 之間以橙點標記（`markExceed` tweak 控制是否標記）
  - 下方 7 個時間刻度標籤（依所選區間格式化為 HH:00 / M/D / M/D HH:00）
- 無任何指標被選取時顯示空狀態卡片（icon + 提示文字「請至少選擇一個指標」）

**Interactions**
- 廠棟切換／指標勾選／時間區間切換都會即時重算所有已選指標的趨勢圖（目前資料是以廠棟+指標字串做 seed 產生的模擬時間序列，正式串接時請替換為真實歷史資料 API：`GET /history?plant=&metric=&from=&to=`）
- 「匯出 CSV」：把目前所有面板的時間序列匯出成 UTF-8 BOM CSV（欄位：time, plant, metric, value）

**State**
- `plant`（字串，選中廠棟）
- `inds`（字串陣列，選中指標）
- `range`（'24H'/'7D'/'30D'/'90D'/'自訂'）
- `customFrom` / `customTo`（自訂區間日期字串）
- `indOpen`（bool，指標下拉是否展開）

**Tweaks**
- `defaultRange`（enum: 24H/7D/30D/90D，預設 7D）
- `showOoc`（bool，預設 true）— 是否畫出 OOC 管制虛線
- `markExceed`（bool，預設 true）— 是否標記超標資料點

---

---

## 畫面 4：規格維護（`VOC 規格維護.dc.html`）

**Purpose**：維護各廠區監測項目的 SPEC 門檻（法規許可值／OOS／OOC／Alert），區分「立即生效的就地編輯」與「需簽核的送簽申請」兩種途徑。

**Layout**：Header 同其他頁（64px），右側為廠區／項目篩選下拉；內容區為 4 個頁籤：規格清單、送簽申請、我的申請、待簽核（有未結案件數時顯示黃色 badge）。頁面上方有可關閉的「現況落差說明」提示條（`showLegacyGapNotice` tweak 控制）。

**規格清單**：表格列出每筆 SPEC（廠區/項目/來源/法規值/OOS/OOC/Alert/備註），列上「編輯」按鈕切換成就地編輯列，輸入格式驗證（pH 須雙邊範圍、其餘單邊、最多 2 位小數、OOC 須比 Alert 寬），存檔立即生效並跳 toast。

**送簽申請**：類別（新增/修改/刪除）+ 來源 + 廠區 + 項目 + LAW/OOS/OOC/Alert + 備註表單，送出前驗證同規格清單規則，並擋同廠區/項目已有待簽案件的重複申請。

**我的申請** / **待簽核**：申請紀錄列表（狀態：待簽核/簽核中/核准/否決/取消）；待簽核頁籤可核准或否決（否決需填原因），動作後更新對應申請狀態並跳 toast。

**Tweaks**：`showLegacyGapNotice`（bool，預設 true）、`defaultTab`（enum: list/apply/mine/todo，預設 list）

---

## 畫面 5：異常報表（`VOC 異常報表.dc.html`）

**Purpose**：跨廠區異常件數的統計總覽，供管理者掌握熱點廠區與項目。

**Layout**：Header 同其他頁，右上角連到「異常查詢／回覆」（在 Dashboard modal 內）。內容區由上到下：現況落差提示條（統計母集合是否含雨水溝廠區 K12）、篩選列（廠區/項目/日期區間/MT 廠全部）、各廠區異常件數長條圖、項目 × 廠區交叉統計表、廠區排行榜（前三名標紅、後三名標綠，`highlightTopBottom` tweak 控制）。長條圖／交叉表儲存格／排行榜列點擊皆彈出 toast 示意「將下鑽至異常查詢頁」。

**Tweaks**：`includeStormDrain`（bool，預設 true）— 統計是否納入雨水溝廠區 K12、`highlightTopBottom`（bool，預設 true）— 排行榜是否標示前三/後三名

---

## Screenshots
`screenshots/` 內附三張現況截圖（01-login / 02-dashboard / 03-history），供快速對照；正式實作仍以 `.dc.html` 即時互動與本文件描述為準。

## Assets
- Logo 使用純 CSS 文字漸層實作，無外部圖片資源
- Icon 全部使用內嵌 Lucide 風格 SVG（stroke-width 2, round cap/join），未使用圖示字型
- `_ds/` 內含設計系統的 `colors_and_type.css`（token 來源）與 `ui_kits/dashboard/`（可參考的既有元件寫法）

## 尚未包含 / 待確認
- `VOC Wireframes.dc.html`（探索階段的手繪風線框稿）**未包含在本次交付**，已被上述五個高保真畫面取代，可忽略
- 所有頁面目前都是前端模擬資料，需與後端資料表（廠棟、監測項目、門檻值、歷史時序、派送名單、隔離申請、規格申請、部門/ACL 權限）對接
- 規格維護頁面「就地編輯」與「送簽申請」的角色權限區分、待簽核頁籤的可見範圍，皆為既有系統落差，非本次改版範圍（詳見頁面內現況說明提示條）
- 規格維護 OOC/Alert 雙邊寬窄方向判斷邏輯待業務確認正確性
- 異常報表統計母集合是否納入雨水溝廠區（K12）需與舊系統口徑對齊確認
