from pydantic import BaseModel, model_validator
from typing import Optional, List

# EditAclUser.aspx 舊版只開放管理這兩種角色（見 acl_service.py 檔頭說明）
_ALLOWED_ROLE_IDS = (3, 7)


class AclUserBase(BaseModel):
    """ 新增/修改權限名單的共用基底欄位 """
    role_id: int
    plantno: str
    empno: str
    stype: str   # '1'->空, '2'->水, '3'->ALL, 會在 Service 層進行邏輯轉換
    remark: Optional[str] = ""

    @model_validator(mode='after')
    def validate_base(self) -> 'AclUserBase':
        if self.role_id not in _ALLOWED_ROLE_IDS:
            raise ValueError(f"roleid 只能是 {_ALLOWED_ROLE_IDS} 之一（隔離維護/隔離查詢）")
        if not self.plantno.strip():
            raise ValueError("廠區不可為空!")
        if not self.empno.strip():
            raise ValueError("工號不可為空!")
        if self.stype not in ("1", "2", "3"):
            raise ValueError("stype 只能是 '1'(空)/'2'(水)/'3'(ALL)")
        self.plantno = self.plantno.strip()
        self.empno = self.empno.strip()
        return self


class AclUserCreate(AclUserBase):
    pass


class AclUserUpdate(AclUserBase):
    old_empno: str
    old_stype: str  # DB 原值（空/水/ALL），僅供 VOC_tranlog databefore 記錄用，不參與定位查詢

    @model_validator(mode='after')
    def validate_old_empno(self) -> 'AclUserUpdate':
        if not self.old_empno.strip():
            raise ValueError("缺少原工號，無法定位要修改的資料")
        self.old_empno = self.old_empno.strip()
        return self


class AclUserResponse(BaseModel):
    """ 從資料庫提取出來供前端表格呈現的 Schema """
    plantno: str
    roletype: str  # 即 rolename
    empno: str
    empname: Optional[str] = ""
    notesid: Optional[str] = ""
    stype: str  # 空, 水, ALL（DB 原值，前端顯示「全區」由 template 負責轉換）

    class Config:
        from_attributes = True
