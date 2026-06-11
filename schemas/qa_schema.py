from pydantic import BaseModel, model_validator
from typing import Optional
import re


class QAUpdate(BaseModel):
    """ QA 手測值更新（對應舊版 EditQA.aspx 輸入驗證） """
    plantno: str
    item: str
    rvalue: str
    remark: Optional[str] = ""

    @model_validator(mode='after')
    def validate_rvalue(self) -> 'QAUpdate':
        val = self.rvalue.strip()
        if not val:
            raise ValueError("讀值不可為空!")
        # 允許 N.D（未檢出），其餘必須是數字、最多兩位小數
        if val.upper() == "N.D":
            self.rvalue = "N.D"
            return self
        if not re.match(r'^\d+(\.\d{1,2})?$', val):
            raise ValueError(f"讀值({val})錯誤, 請輸入數字(最多兩位小數)或 N.D!")
        self.rvalue = val
        return self
