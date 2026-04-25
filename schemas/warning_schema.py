from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class RainGutterItem(BaseModel):
    plantno: str
    item: str
    sum24h: str
    rvalue: str
    status: str # G: 正常, R: 預警, O: 斷訊/異常
    remark: str

class WaterUrgentRequest(BaseModel):
    notify_type: str # 'water_abnormal' (水質異常) or 'water_change' (改排水)
    plantid: Optional[int] = None
    reason: Optional[str] = None
