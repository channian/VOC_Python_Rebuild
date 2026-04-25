from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from schemas.control_schema import ApplyListResponse

class SignAction(BaseModel):
    ccid: int
    flowid: int
    actionid: int # 1: 核准, 2: 否決
    comment: Optional[str] = ""
