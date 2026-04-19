from pydantic import BaseModel
from typing import Optional, List

class AclUserBase(BaseModel):
    """ 新增/修改權限名單的共用基底欄位 """
    role_id: int
    plantno: str
    empno: str
    stype: str   # '1'->空, '2'->水, '3'->ALL, 會在 Service 層進行邏輯轉換
    remark: Optional[str] = ""

class AclUserCreate(AclUserBase):
    pass

class AclUserUpdate(AclUserBase):
    old_empno: str
    old_stype: str

class AclUserResponse(BaseModel):
    """ 從資料庫提取出來供前端表格呈現的 Schema """
    plantno: str
    roletype: str  # 即 rolename
    empno: str
    empname: Optional[str] = ""
    notesid: Optional[str] = ""
    stype: str  # 空, 水, ALL
    
    class Config:
        from_attributes = True
