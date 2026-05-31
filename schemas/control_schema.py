from pydantic import BaseModel, model_validator
from typing import Optional, List
from datetime import datetime

class ControlItemBase(BaseModel):
    plantno: str
    item: str
    sourceid: str

class ControlCreate(BaseModel):
    """ 對應舊版 EditControl 新增隔離項目區間 """
    plantid: int
    mdfdesc: str
    stime: datetime
    etime: datetime
    remark: Optional[str] = ""
    items: List[ControlItemBase]

    @model_validator(mode='after')
    def validate_times(self) -> 'ControlCreate':
        now = datetime.now()
        if self.stime < now: raise ValueError("開始時間不可小於系統時間!")
        if self.stime > self.etime: raise ValueError("開始時間不可大於結束時間!")
        ts = self.etime - self.stime
        if ts.total_seconds() > 14400: raise ValueError("隔離廠區項目時間不得超過4小時!")
        if not self.items: raise ValueError("尚未選擇要隔離的廠區項目!")
        return self

class ControlResponse(BaseModel):
    ccid: int
    ccno: str
    mdfdesc: str
    stime: datetime
    etime: datetime
    fstatusid: int
    cempname: str
    
    class Config:
        from_attributes = True

class ApplyListResponse(BaseModel):
    """ MyApply / PlantApply 表單列表的通用回傳結構 """
    ccid: int
    ccno: str
    ttype: str # 來自 VOC_closectl_ttype
    plantno: str # 廠區代號
    empstr: str # 申請人 (例如 A001-王大明)
    mdfdesc: str
    stime: datetime
    etime: datetime
    fstatus: str # 簽核狀態 (例如: 待簽核)
    ctime: datetime

class ControlTagResponse(BaseModel):
    """ 對應舊有 List隔離廠區項目() 回傳 """
    oldtagname: str
    plantno: str
    item: str
    source: str
