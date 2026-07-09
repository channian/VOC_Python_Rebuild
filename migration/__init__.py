"""
migration — A（舊 MSSQL VOC 資料庫）→ B（Schema B / PostgreSQL）搬遷套件。

用途雙效：
  1. 現在：把公司 A 棧的真實資料轉進 B 棧測試庫，讓功能測試有真資料（人員改綁自己部門同事）。
  2. 將來：即 Phase C 上線切換要用的搬遷腳本雛型（同一套轉換邏輯，來源換成正式 MSSQL）。

三段式設計（source → normalize → sink），彼此以固定介面解耦：
  - 來源 Source：兩種實作——檔案來源（讀 export/*.json，沙盒可測）與 MSSQL 直連（公司跑，
    沙盒無 ODBC 無法測）。兩者都吐「A 形狀 dict（key=A 資料表原始欄位名）」。
  - 轉換 normalize：純函式，A 形狀 dict → B 形狀 ORM 物件（未 save）。可純測、不需 DB。
    重用既有轉換邏輯（services/dashboard_service._parse_bounds 門檻拆解、
    services_b/sync_service 讀值分類精神），不重寫規則。
  - 寫入 sink：migration/io.upsert()，以主鍵 merge（可攜、非方言 ON CONFLICT），冪等可重跑。

編排：migration/runner.py 依 FK 安全順序呼叫各 normalize 模組 + upsert。
人員（employee/sign_emp/mail_list/acl_user_role）不搬 A 真人，改由 migration_personnel.json
產生（見 migration/context.py），A 的申請人/簽核人一律改綁 config 裡的同事。
"""
