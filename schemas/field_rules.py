"""
schemas/field_rules.py — 共用欄位驗證小工具（2026-08-01，D5「4 頁 schema 驗證未接線」）

目的：讓 B 棧的請求模型（派送名單／部門／ACL／異常回覆）用同一組寫法產生
**繁體中文、指得出是哪個欄位**的錯誤訊息，不必每個檔案各寫一份。

★ 本檔是**新增**檔案，A 棧（main.py，公司平行測試中）沒有任何呼叫端 import 它，
  因此加入本檔不可能改變 A 棧行為。既有的 A 棧模型（MailListBase / DeptAdd /
  AclUserBase / ReasonUpdate）**一行都沒有改**，只在同檔案內新增 B 棧專用類別。

錯誤訊息一律 `raise ValueError`，交給 Pydantic 包成 422，前端 `extractErrorMsg()`
讀 `detail[].msg` 顯示（B 棧四頁模板都已有這個 helper，見各 partial 的 <script>）。
"""

from typing import Sequence


def require_text(value: str | None, label: str, max_len: int) -> str:
    """必填字串欄位：去頭尾空白後不可為空，且不可超過資料表欄位長度上限。

    `label` 請用使用者看得懂的中文欄位名（例：「廠區代碼」），錯誤訊息會直接引用。
    `max_len` 一律填 models_b.py 對應欄位的 String(n)，避免超長字串一路送到 DB 才炸成 500。
    """
    v = (value or "").strip()
    if not v:
        raise ValueError(f"{label}不可為空白！")
    if len(v) > max_len:
        raise ValueError(f"{label}長度不可超過 {max_len} 個字元（目前 {len(v)} 個）！")
    return v


def optional_text(value: str | None, label: str, max_len: int) -> str:
    """選填字串欄位：可以是空字串，但有值時一樣受長度上限限制。"""
    v = (value or "").strip()
    if len(v) > max_len:
        raise ValueError(f"{label}長度不可超過 {max_len} 個字元（目前 {len(v)} 個）！")
    return v


def require_choice(value: str, label: str, allowed: Sequence[str], hint: str = "") -> str:
    """列舉欄位：只能是 `allowed` 之一（例：派送方式只能 TO/CC）。

    `hint` 可補充人看得懂的說明（例：「'1'=空／'2'=水／'3'=全區」），沒帶就只列合法值。
    """
    v = (value or "").strip()
    if v not in allowed:
        desc = hint or "、".join(allowed)
        raise ValueError(f"{label}只能是 {desc}！")
    return v
