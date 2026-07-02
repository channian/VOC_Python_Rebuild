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
        # 隔離時間上限一律 1 小時（3600 秒），不分 pH / 其他項目。
        # 修法前 Python 端誤用 pH=1hr／其他=4hr 分流，舊系統其實不分項目一律 1 小時，
        # 見 legacy/dbVOC.cs Check申請隔離免簽核() 與 docs/legacy_source_analysis.md 落差清單 #3。
        if ts.total_seconds() > 3600: raise ValueError("隔離廠區項目時間不得超過1小時!")
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
    """ MyApply / PlantApply / SignControl 表單列表的通用回傳結構 """
    ccid: int
    ccno: str
    flowid: Optional[int] = None # 簽核流程ID (未送簽/暫存時為 None，供 /flow/sign 呼叫用)
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
