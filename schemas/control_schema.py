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
    items: List[ControlItemBase] # 被勾選的欲隔離清單 (DataRow[])

    @model_validator(mode='after')
    def validate_times(self) -> 'ControlCreate':
        """ 完全復刻 EditControl.aspx.cs 的時間防呆 """
        now = datetime.now()
        
        # 1. 開始時間不可小於現在系統時間
        if self.stime < now:
            raise ValueError("開始時間不可小於系統時間!")
            
        # 2. 開始時間不可大於結束時間
        if self.stime > self.etime:
            raise ValueError("開始時間不可大於結束時間!")
            
        ts = self.etime - self.stime
        
        # 3. 預設隔離時間不能超過 1 小時 
        # C# 原版: (ts.Days > 0 || ts.Hours > 1 || (ts.Hours == 1 && ts.Minutes != 0))
        # 轉換為秒數: 1 小時 = 3600 秒
        if ts.total_seconds() > 3600:
            raise ValueError("隔離廠區項目時間不得超過1小時!")
            
        if not self.items:
            raise ValueError("尚未選擇要隔離的廠區項目!")

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
