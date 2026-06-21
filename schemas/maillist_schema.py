"""
maillist_schema.py — 派送名單維護的 Pydantic 驗證

對應舊版 EditMailList.aspx.cs 的欄位驗證規則。
notesid 正規化與「群組/值班」特例由 service 層處理。
"""

from pydantic import BaseModel, model_validator
from typing import Optional
import re


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
