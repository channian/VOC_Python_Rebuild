"""
scripts/fix_schema_b.py — 補上 create_all_b() 不會補的欄位（冪等，可重複執行）。

用法（專案根目錄）：
    python scripts/fix_schema_b.py
    python scripts/check_schema_b.py    # 補完再確認一次

★ 背景見 scripts/check_schema_b.py 的說明：`create_all_b()` 只建「不存在的表」，
  已存在的表不會補欄位，必須真的下 ALTER TABLE。

★ 維護方式：**每次 models_b.py 新增欄位，就往 ALTERS 加一行。**
  `ADD COLUMN IF NOT EXISTS` 與 `COMMENT ON COLUMN` 都是冪等的，重跑不會出錯，
  所以清單只加不減、永遠從頭跑到尾即可，不需要記錄「跑到哪一版」。

★ 注意用 `b_engine.begin()`（會自動 commit）；用 `connect()` 不 commit 等於白做工。
"""

import os
import sys

from sqlalchemy import text

# 讓腳本在 repo 根目錄外執行時仍找得到 database_b
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database_b import b_engine  # noqa: E402  ★ 變數名是 b_engine，不是 engine_b

# (SQL, 說明) — 說明只用於畫面輸出，方便看出這一行在補什麼
ALTERS = [
    # ── 2026-07-31 item 主檔新增兩欄（D7 / D8：類型與規格型態改為資料驅動）──
    ("ALTER TABLE item ADD COLUMN IF NOT EXISTS category VARCHAR(20)",
     "item.category — 項目類型（水質／空汙／雨水溝）"),
    ("ALTER TABLE item ADD COLUMN IF NOT EXISTS is_dual_bound BOOLEAN",
     "item.is_dual_bound — 規格型態（雙邊 True／單邊 False／NULL 未指定）"),
]

# 欄位註解（COMMENT ON COLUMN）——手動 ALTER 加的欄位不會自動帶上 models_b.py 裡的
# comment=...（那只有 create_all() 建表時才會寫入），所以在這裡補齊，
# 讓直接用 psql / DB 工具看表結構的人也讀得到欄位用途。
COMMENTS = [
    ("item.category",
     "項目類型：水質／空汙／雨水溝（2026-07-31 新增。現行程式原本靠項目名稱字串比對判斷類型，"
     "新廠若有不叫 VOC 的空汙項目會被誤判成水質，連帶找錯簽核人、派報分錯類；"
     "本欄由基礎資料建置填入正確值，讀取端已於 2026-08-01 改用本欄）"),
    ("item.is_dual_bound",
     "規格型態是否為雙邊（True=雙邊「低-高」如 pH 的 6-9、K21 溫度的 20-35；"
     "False=單邊如 COD 的 100；NULL=未指定，退回舊的「項目名稱像不像 pH」推測）。"
     "2026-07-31 新增，取代原本散在各處且彼此不一致的名稱字串比對。"
     "填入時機／填入者：基礎資料建置時由環工部在主表「規格型態」欄填「單邊/雙邊」；"
     "日後新廠上線亦可由基礎資料維護頁（/ui/basedata 項目分頁）維護。"
     "讀取端僅限 B 棧，A 棧行為凍結不動。"),
]


def main() -> None:
    print(f"連線：{b_engine.url}\n")
    with b_engine.begin() as conn:  # begin() 會自動 commit
        for sql, note in ALTERS:
            conn.execute(text(sql))
            print(f"OK: {note}")
        for column, comment in COMMENTS:
            # 參數化綁不進 COMMENT ON 的字面值，故以單引號逸出後內嵌（內容為本檔常數，非外部輸入）
            escaped = comment.replace("'", "''")
            conn.execute(text(f"COMMENT ON COLUMN {column} IS '{escaped}'"))
        print(f"OK: 已補上 {len(COMMENTS)} 個欄位註解")

    print("\n完成（本腳本冪等，可重複執行）。"
          "\n接著跑 python scripts/check_schema_b.py 確認「【欄位】全部齊全 ✓」。")


if __name__ == "__main__":
    main()
