"""
maillist_schema.py — 派送名單維護的 Pydantic 驗證

對應舊版 EditMailList.aspx.cs 的欄位驗證規則。
notesid 正規化與「群組/值班」特例由 service 層處理。
"""

from pydantic import BaseModel, model_validator
from typing import Optional
import re

from schemas.field_rules import optional_text, require_choice, require_text

# 派送方式（TO=正本／CC=副本）。models_b.MailList 也有同名 CHECK constraint，
# 這裡先擋在 API 層，避免 DB 層 IntegrityError 變成 500。
MAILTYPES = ("TO", "CC")


def _validate_cellphone(phone: str) -> str:
    """手機驗證（舊版 __cellphone_TextChanged）：09 開頭、10 碼、純數字。空字串允許。"""
    phone = phone.strip()
    if phone == "":
        return ""
    if not phone.startswith("09"):
        raise ValueError("手機號碼應為 09 開頭!")
    if len(phone) != 10:
        raise ValueError("手機號碼應為 10 碼!")
    if not phone.isdigit():
        raise ValueError("手機號碼請輸入數字!")
    return phone


class MailListBase(BaseModel):
    plantno:   str
    rpttype:   str
    empno:     str
    empname:   str = ""
    notesid:   str = ""
    cellphone: str = ""
    mailtype:  str = "TO"        # 'TO' / 'CC'
    mail:      int = 1           # 是否發 Email（1/0）
    SM:        int = 0           # 是否發簡訊（1/0）
    signgrp:   int = 0           # 是否簽核群組（1/0）
    remark:    Optional[str] = ""

    @model_validator(mode='after')
    def validate_all(self) -> 'MailListBase':
        if not self.plantno.strip():
            raise ValueError("廠區不可為空!")
        if not self.rpttype.strip():
            raise ValueError("報表類型不可為空!")
        if not self.empno.strip():
            raise ValueError("工號不可為空!")
        if self.mailtype not in ("TO", "CC"):
            raise ValueError("派送方式只能是 TO 或 CC")
        for fld in ("mail", "SM", "signgrp"):
            if getattr(self, fld) not in (0, 1):
                raise ValueError(f"{fld} 只能是 0 或 1")
        # 郵件要寄 → notesid 不可空（舊版 mail=="要" && notesid=="" 報錯）
        if self.mail == 1 and not self.notesid.strip():
            raise ValueError("勾選發送 Email 時，Notes ID 不可為空!")
        # 簡訊要發 → 手機不可空
        if self.SM == 1 and not self.cellphone.strip():
            raise ValueError("勾選發送簡訊時，手機號碼不可為空!")
        self.cellphone = _validate_cellphone(self.cellphone)
        self.plantno = self.plantno.strip()
        self.rpttype = self.rpttype.strip()
        self.empno   = self.empno.strip()
        return self


class MailListAdd(MailListBase):
    """新增一筆派送名單"""
    pass


class MailListUpdate(MailListBase):
    """
    修改一筆派送名單。
    plantno + rpttype 為定位用（不可改），empno 允許修改 → 需帶舊工號 old_empno 定位。
    """
    old_empno: str

    @model_validator(mode='after')
    def validate_old_empno(self) -> 'MailListUpdate':
        if not self.old_empno.strip():
            raise ValueError("缺少原工號，無法定位要修改的資料")
        self.old_empno = self.old_empno.strip()
        return self


class MailListDelete(BaseModel):
    plantno: str
    rpttype: str
    empno:   str


# ══════════════════════════════════════════════════════════════════════════
# B 棧（Schema B / PostgreSQL）專用請求模型
# ══════════════════════════════════════════════════════════════════════════
# 2026-08-01 D5：B 棧 routers_b/ui_router_b.py 原本自訂裸模型（只有型別、零驗證），
# 這裡補上真正的欄位驗證。**A 棧既有的 MailListBase/Add/Update/Delete 一行未改**，
# 下列 B 類別是新增的，A 棧沒有任何呼叫端 import 它們。
#
# 為什麼不直接沿用 MailListBase 而要另建？B 棧資料層形狀不同（見
# services_b/maillist_service.py 檔頭 F/I 項決策）：
#   1. mail/signgrp 在 B 是 **bool**（models_b.MailList.mail_on/sign_grp 是 Boolean），
#      A 是 0/1 的 int；
#   2. B **沒有** SM/cellphone 欄位（簡訊功能已停用，B 表不建這兩欄），
#      沿用 MailListBase 會讓 API 多出兩個永遠寫不進 DB 的欄位；
#   3. A 棧的「勾選發送 Email 時 Notes ID 不可為空」在 B 棧**刻意不套用**——
#      B 的新增表單根本沒有 Notes ID 輸入框（notesid 只由 /maillist/employee/{empno}
#      自動帶出，見 templates/b/partials/maillist.html），群組／值班工號查不到 notesid
#      是正常情況；若照搬這條規則，這類人員將完全無法加入名單（功能倒退）。
#      這是**維持寬鬆**的刻意決定，已在任務回報列為待業務確認項。

class MailListBaseB(BaseModel):
    """B 棧派送名單共用欄位（長度上限對齊 models_b.MailList 的 String(n)）。"""
    plantno:  str
    rpttype:  str
    empno:    str
    empname:  str = ""
    notesid:  str = ""
    mailtype: str = "TO"
    mail:     bool = True      # B 棧為 bool（對應 mail_on）
    signgrp:  bool = False     # B 棧為 bool（對應 sign_grp）
    remark:   Optional[str] = ""

    @model_validator(mode="after")
    def validate_maillist_b(self) -> "MailListBaseB":
        self.plantno  = require_text(self.plantno, "廠區代碼", 50)
        self.rpttype  = require_text(self.rpttype, "報表類型", 50)
        self.empno    = require_text(self.empno, "工號", 50)
        self.empname  = optional_text(self.empname, "姓名", 100)
        self.notesid  = optional_text(self.notesid, "Notes ID", 100)
        self.mailtype = require_choice(self.mailtype, "派送方式", MAILTYPES, "TO（正本）或 CC（副本）")
        return self


class MailListAddB(MailListBaseB):
    """新增一筆派送名單（POST /maillist/add）。"""
    pass


class MailListUpdateB(MailListBaseB):
    """修改一筆派送名單（POST /maillist/update）。
    plantno + rpttype 為定位用（不可改），empno 允許修改 → 需帶舊工號 old_empno 定位。"""
    old_empno: str

    @model_validator(mode="after")
    def validate_old_empno_b(self) -> "MailListUpdateB":
        self.old_empno = require_text(self.old_empno, "原工號（用於定位要修改的資料）", 50)
        return self


class MailListDeleteB(BaseModel):
    """刪除一筆派送名單（POST /maillist/delete）：只需要複合主鍵三欄。"""
    plantno: str
    rpttype: str
    empno:   str

    @model_validator(mode="after")
    def validate_delete_b(self) -> "MailListDeleteB":
        self.plantno = require_text(self.plantno, "廠區代碼", 50)
        self.rpttype = require_text(self.rpttype, "報表類型", 50)
        self.empno   = require_text(self.empno, "工號", 50)
        return self
