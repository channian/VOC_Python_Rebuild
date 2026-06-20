from pydantic import BaseModel, model_validator
import re


class MailListAdd(BaseModel):
    plantno:  str
    empno:    str = ""
    email:    str
    mailtype: str   # 'TO' or 'CC'

    @model_validator(mode='after')
    def validate_fields(self) -> 'MailListAdd':
        if not self.plantno.strip():
            raise ValueError("廠區代號不可為空!")
        if not self.email.strip():
            raise ValueError("Email 不可為空!")
        if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', self.email.strip()):
            raise ValueError(f"Email 格式不正確: {self.email}")
        if self.mailtype not in ("TO", "CC"):
            raise ValueError("mailtype 只能是 TO 或 CC")
        self.plantno  = self.plantno.strip()
        self.email    = self.email.strip()
        self.empno    = self.empno.strip()
        return self


class MailListDelete(BaseModel):
    seqno: int
