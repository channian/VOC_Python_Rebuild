from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from schemas.control_schema import ApplyListResponse

class SignAction(BaseModel):
    ccid: int
    flowid: int
    # 對應 legacy/MTFlowBase.cs MTFlowBase.SignAction enum：核准=1, 否決=9
    # （取消=8 舊系統已停用/註解掉，這裡不提供）。見 services/flow_service.py
    # SIGN_ACTION_APPROVE / SIGN_ACTION_REJECT。
    actionid: int
    comment: Optional[str] = ""
