# JOB 重構確認清單

> 狀態說明：⬜ 待確認 ／ ✅ 已確認 ／ ❌ 不適用
>
> 2026-06-11 更新：已分析舊 JOB 原始碼（dbVOC.cs、Program.cs、SendMail.cs），
> Q4～Q11、Q13、Q15、Q16 已從程式碼確認。剩餘 7 題為架構決策，需與業務端確認。

---

## 一、Tag 命名與廠區對應

| # | 問題 | 為什麼重要 | 狀態 |
|---|------|-----------|------|
| 1 | Kepware Tag 的命名格式是什麼？（例如 `K1.COD`、`Plant_K1/COD`、還是其他？） | 決定如何從 Tag path 解析出 `plantno` + `item` | ⬜ 架構決策 |
| 2 | 新舊 Tag 命名有無對應表？（iFIX Tag name vs Kepware Tag name） | 確認是 1:1 對應還是需要 mapping 表 | ⬜ 架構決策 |
| 3 | 新系統的 `tag_mapping` 表要由誰來維護（手動填、還是 Kepware 可以匯出）？ | 影響 Admin UI 的設計 | ⬜ 架構決策 |

**已知（舊系統）**：Tag 對應靠 `VOC_SCADA_TagList.Name` 與 Historian 的 tagname **完全相符**做順序比對
（`while (TagsDT["Name"] != iHDT["tagname"]) iCount++`），名稱不符會**靜默跳過**，不會報錯。
這就是 pH tag 改名後出現空值的根本原因 — 新系統必須改為明確的 mapping + 不符時告警。

---

## 二、讀值與寫入邏輯

| # | 問題 | 為什麼重要 | 狀態 |
|---|------|-----------|------|
| 4 | JOB 除了讀「即時讀值 rvalue」，有沒有也讀「SCADA 自設的管制值」（OOS_HH / OOC_H / alert）？ | 橙燈「設定不一致」比對來源 | ✅ 有。從 Historian 讀回寫入 `VOC_SCADA_WEB` |
| 5 | CWMS 的管制值（OOS_HH1 / OOC_H1）有沒有對應的來源？ | CWMS 是另一套系統 | ✅ 有。`GETCWMS` 指令呼叫 HTTP JSON API：`http://khfsijob/CWMSDataRelayAPI/api/WebApi/{plant}TrueValue`，涵蓋廠區：K14B, K5, K7, K11, K22, K21 |
| 6 | 雙邊規格的下限值（OOS_LL / OOC_L / alert_L，pH 專用）有處理嗎？ | pH 有上下限 | ✅ 有。pH 每個項目處理 **7 個 tag**（讀值 + 上下限管制值），雙邊規格存成 `low-high` 格式（如 `6-9`） |
| 7 | JOB 寫入頻率是多少？ | 影響儀表板更新頻率 | ✅ `SCADA_VOC` 指令每 **15 分鐘**一輪 |
| 8 | JOB 有沒有同時寫「歷史資料表」？ | 雨水溝預警需要歷史值 | ✅ 有。`InsertVOCHistValue()` + `Insert法遵VOC歷史讀值A5()`；每天 00:00 另跑日平均計算 |

**已知（Program.cs）**：`SCADA_VOC` 連 10+ 台 iFIX Historian —
K11=IH、K22=IH2、K21=IH3、**K12=IH4+IH5+IH6（3台）**、K24=IH7、K26=IH8、K25=IH10、K16=IH11、K27=IH15、K18=IH18。
K11 另有 INSQL/Oracle WWT 第二來源（`UpdateVOCData2()`）。新 JOB 必須保留多連線與雙來源邏輯。

---

## 三、斷訊（broken）判斷

| # | 問題 | 為什麼重要 | 狀態 |
|---|------|-----------|------|
| 9 | JOB 怎麼判斷斷訊？ | 斷訊判斷邏輯要在新系統重現 | ✅ Historian Tag **品質碼（quality）= 0** 即視為斷訊，寫入 `broken = 1` |
| 10 | broken 的狀態值怎麼定義？ | Web 端和 JOB 端不可互相覆蓋 | ✅ `0`=正常、`1`=斷訊（JOB 寫）、`2`=保養中/隔離中（Web 寫）。Mail JOB 發報前會先跑 `List隔離廠區項目()` → `Update隔離廠區項目()` 把隔離中的項目更新為 broken=2，避免誤報 |

---

## 四、雨水溝 24 小時累積值（TwentyFourHours）

| # | 問題 | 為什麼重要 | 狀態 |
|---|------|-----------|------|
| 11 | `TwentyFourHours` 從哪裡來？ | 雨水溝紅燈條件依賴此值 | ✅ 確認自 `PMS.dbo.Water_WindRainHistValue` JOIN，**不是 JOB 算的** |
| 12 | PMS 系統會一起遷移到 PostgreSQL 嗎？ | 決定新系統怎麼取這個值 | ⬜ 架構決策 |
| 13 | K1 / K9 的「連續三點上升」邏輯有沒有保留？ | 邏輯複雜易漏 | ✅ 確認存在。雨水溝預警 Mail 對 K1/K9 有特殊欄位（datetime1-3 / value1-3 三點明細），其餘廠區只看最新值 |

---

## 五、PostgreSQL Schema（新 DB）

| # | 問題 | 為什麼重要 | 狀態 |
|---|------|-----------|------|
| 14 | 新 JOB 寫入的 PostgreSQL 資料表與欄位？ | Web 改讀 PG 時需要對應 | ⬜ 架構決策 |
| 15 | `light` 欄位（燈號）新 JOB 要不要繼續寫？ | 避免雙重計算不一致 | ✅ 已決策：**新系統不存 light**，Web 端 `_calculate_light()` 自行計算（舊 JOB 確實有寫 light，屬技術債不移植） |
| 16 | `rvalue` 的型別？ | 有 N.D / 斷訊 等文字 | ✅ 確認舊系統用 VARCHAR 是因為要存 `N.D`、`斷訊`、`建置中`、`保養中` 等文字。新系統維持字串型別（或值欄+狀態欄拆開，PG schema 定案時一併決定） |

---

## 六、過渡期（雙軌並行）

| # | 問題 | 為什麼重要 | 狀態 |
|---|------|-----------|------|
| 17 | 新 Python Web 過渡期間讀 MSSQL 還是 PostgreSQL？ | 決定 Web 重構優先序 | ⬜ 架構決策（目前先接 MSSQL） |
| 18 | 舊 JOB 和新 JOB 會同時跑嗎？ | 資料一致性 | ⬜ 架構決策 |

---

## 七、異常通知（SendMail.cs 分析後新增）

舊 JOB 的 `VOC` 指令每 15 分鐘執行 `SendMail_廠務法規許可值標準化管控報表()`，流程：

```
1. List隔離廠區項目() → Update隔離廠區項目()   ← 先把隔離中項目標成 broken=2
2. GetData()                                  ← 撈全廠即時資料
3. GetDataRed(row, dt2)                       ← 判斷異常廠區（R/O/Y）
4. 組 HTML 表格信件
5. GetMailList(DataRed, plantno, "TO"/"CC")   ← 從 DB 取收件名單
6. 寄信（首發/再發判斷：GetMsg1(..., "status")，依 VOC_MAIL 歷史）
7. InsertMAIL()                               ← 寫通知紀錄
```

**通知管道決策（2026-06-11 與用戶確認）**：
- ✅ Email（SMTP）— 唯一需移植的管道
- ❌ SMS（`SendSMS.SendSMSByCHTProxy`）— 已停用，不移植，Python 端程式碼已移除
- ❌ PushPlus 推播（`CallPushPlus().Notice`）— 暫不實作，日後有需要再新增

**特殊規則**：
- K14B 跨廠通報：任一廠的讀值「＞允收值」時，K14B 的名單也會被 CC
- 雨水溝預警另有獨立方法 `SendMail_廠務雨水溝預警報表()`，邏輯結構相同
- IH 主機連線異常 / IH Tag 斷訊有獨立通知（`CheckMAILlog` 防當天重複發送）

**Python 端尚未實作**：`GetDataRed()` 判斷、`GetMailList()` 名單查詢、
`InsertMAIL()` + 首發/再發、組 HTML 信件 — 目前 `warning_service.py` 只有撈資料。

---

*清單建立日期：2026-05-16　最後更新：2026-06-11*
