from pydantic import BaseModel, field_validator, model_validator

from schemas.field_rules import require_text


class ReasonUpdate(BaseModel):
    logid: int
    reason: str

    @field_validator("reason")
    @classmethod
    def reason_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("原因說明不可為空白")
        return v.strip()


# ══════════════════════════════════════════════════════════════════════════
# B 棧（Schema B / PostgreSQL）專用請求模型
# ══════════════════════════════════════════════════════════════════════════
# 2026-08-01 D5：B 棧 /history/reply 原本吃裸的 {item_id, reason}（只有型別、零驗證），
# 空白原因會被寫進 mail_log_item.reply_reason（等於清空回覆卻仍蓋掉回覆人/回覆時間）。
#
# 形狀與 A 棧 ReasonUpdate 不同、無法直接繼承：2026-07-31 C8 決策把回覆從「信件層級」
# 改成「逐項目層級」，定位鍵由 `logid: int` 換成 `item_id: str`
# （services_b/history_service._make_item_id() 組出的 "mail_log_id||item||condition_code"）。
# 驗證規則刻意與 A 棧同源：原因說明不可為空白（legacy 亦同）。
# item_id 這裡只擋空白，**不重複驗證複合鍵格式**——格式錯誤由
# history_service._parse_item_id() 丟 ValueError → router 轉 400，訊息已足夠明確，
# 在兩個地方各寫一份解析規則反而容易走鐘。

class ReasonUpdateB(BaseModel):
    """異常原因回覆（POST /history/reply，逐項目層級）。"""
    item_id: str
    reason: str

    @model_validator(mode="after")
    def validate_reply_b(self) -> "ReasonUpdateB":
        # item_id 是技術鍵，長度可由 models_b 欄位推得上界（BigInteger + item String(50)
        # + condition_code String(30) + 兩組 '||'），200 是有餘裕的防呆上限。
        self.item_id = require_text(self.item_id, "回覆對象（item_id）", 200)
        # 原因說明**刻意不設長度上限**：mail_log_item.reply_reason 是 Text，
        # 資料庫沒有限制，業務上也沒有約定字數，不自行發明。
        if not (self.reason or "").strip():
            raise ValueError("原因說明不可為空白！")
        self.reason = self.reason.strip()
        return self
