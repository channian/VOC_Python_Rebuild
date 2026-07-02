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

class ControlModify(ControlCreate):
    """
    對應舊版 ModifyControl.aspx Proc新增隔離廠區項目()。

    legacy 這支頁面把「新增」跟「修改」共用同一個 dbVOC.Insert隔離廠區項目() 方法（差別只在
    hrow["ttypeid"]/hrow["orgccid"] 是否有帶值），時間/項目驗證規則完全相同（開始時間不可小於系統
    時間、不可大於結束時間、區間不得超過 1 小時、至少要選一個項目），因此直接繼承 ControlCreate，
    沿用其 validate_times()，只額外多一個 orgccid 欄位指向被修改的原始隔離單。
    """
    orgccid: int


class ControlTimeUpdate(BaseModel):
    """
    對應舊版 ControlTime.aspx Proc修改隔離廠區項目() —— 隔離時間修改（僅限 roleid=12「隔離時間修改」
    權限使用，見 docs/legacy_source_analysis.md 權限章節 / services/acl_service.py）。

    ⚠️ 依 legacy/dbVOC.cs:1870-1904（Update隔離廠區項目）確認：這支功能**直接改主表 VOC_closectl.etime，
    不建立/不呼叫任何簽核流程**，屬於特定權限者的例外通道，與 create_control/modify_control 一律走
    簽核的規則不同，這裡忠實照舊系統實作（不額外加簽核）。
    """
    ccid: int
    ccno: str
    # 對應 legacy 隱藏欄位 _0etime：使用者選取該筆申請單「當下」的原始結束時間，
    # 用來擋「新結束時間不可小於原結束時間」（只能延長或持平，不能縮短）。
    orig_etime: datetime
    etime: datetime
    remark: Optional[str] = ""

    @model_validator(mode='after')
    def validate_etime(self) -> 'ControlTimeUpdate':
        # 對應 legacy：
        #   if (_0etime.Value.CompareTo(hrow["etime"].ToString()) > 0)
        #       db.MsgBox(Page, "結束時間需大於 " + _0etime.Value + " !");
        # 語意 = 新結束時間不得小於選取當下的原始結束時間。
        # ⚠️ 舊系統這裡沒有再套用 EditControl/ModifyControl 那套「隔離上限 1 小時」的驗證——
        #   ControlTime 是給特定權限者的直接調整功能，刻意沒有這層總時長上限，這裡照舊不加，
        #   屬於與「一律 1 小時上限」規則的刻意例外，非遺漏。
        if self.etime < self.orig_etime:
            raise ValueError(f"結束時間需大於 {self.orig_etime.strftime('%Y/%m/%d %H:%M')} !")
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
