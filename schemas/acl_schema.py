from pydantic import BaseModel, model_validator
from typing import Optional, List

from schemas.field_rules import optional_text, require_text

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


# ══════════════════════════════════════════════════════════════════════════
# B 棧（Schema B / PostgreSQL）專用請求模型
# ══════════════════════════════════════════════════════════════════════════
# 2026-08-01 D5：B 棧 routers_b/ui_router_b.py 原本自訂裸模型（只有型別、零驗證），
# 任意 role_id（例如 99）與任意 stype 字串都寫得進 acl_user_role
# （models_b.AclUserRole.role_id 沒有 FK 到 acl_role，DB 也擋不住）——
# 這正是 docs/標準化與待調整清單.md D4 記載的「後端未真擋其他 role_id，只有前端下拉限制」。
# 下列 B 類別**繼承 A 棧既有模型重用全部規則**（角色只能 3/7、廠區/工號必填、stype 1/2/3），
# 只追加 B 棧需要的長度上限與預設值差異。A 棧既有類別一行未改。
#
# ⚠️ 角色限定 3/7 沿用 A 棧與 legacy EditAclUser 的既有規則（services_b/acl_service.py
#    的 _EDITACLUSER_ROLEIDS、/acl/roles 下拉、list_acl_users 篩選也都只認 3/7），
#    不是本次新發明的業務規則。D4「是否開放管理全部 12 種角色」若日後拍板要放寬，
#    改 _ALLOWED_ROLE_IDS 一處即可。

_PLANTNO_MAX = 50   # models_b.AclUserRole.plant_no = String(50)
_EMPNO_MAX = 50     # models_b.AclUserRole.emp_no  = String(50)
_STYPE_MAX = 20     # models_b.AclUserRole.stype   = String(20)


class AclUserCreateB(AclUserCreate):
    """新增一筆隔離權限（POST /acl/create）。stype 未帶時預設 '3'（全區），與 B 棧前端一致。"""
    stype: str = "3"

    @model_validator(mode="after")
    def validate_lengths_b(self) -> "AclUserCreateB":
        self.plantno = require_text(self.plantno, "廠區代碼", _PLANTNO_MAX)
        self.empno = require_text(self.empno, "工號", _EMPNO_MAX)
        return self


class AclUserUpdateB(AclUserUpdate):
    """修改一筆隔離權限（POST /acl/update）。

    與 A 棧 AclUserUpdate 的差異只有 old_stype：A 棧為必填，B 棧前端不一定帶得出來
    （B 的名單列只顯示轉換後的中文，且 old_stype 僅供 tranlog databefore 記錄用、
    不參與定位查詢），故放寬為選填、預設空字串——這只影響 B 棧自己的端點。
    """
    stype: str = "3"
    old_stype: str = ""

    @model_validator(mode="after")
    def validate_lengths_b(self) -> "AclUserUpdateB":
        self.plantno = require_text(self.plantno, "廠區代碼", _PLANTNO_MAX)
        self.empno = require_text(self.empno, "工號", _EMPNO_MAX)
        self.old_empno = require_text(self.old_empno, "原工號（用於定位要修改的資料）", _EMPNO_MAX)
        self.old_stype = optional_text(self.old_stype, "原授權範圍", _STYPE_MAX)
        return self


class AclUserDeleteB(BaseModel):
    """刪除一筆隔離權限（POST /acl/delete）：只需要複合主鍵三欄，不含 stype。

    A 棧的 /acl/delete 沿用 AclUserBase（stype 必填），B 棧前端刪除時只送
    plantno/role_id/empno（見 templates/b/partials/acl.html 的 aclv2Delete），
    因此另建一個不含 stype 的模型，而不是去放寬 A 棧共用的 AclUserBase。
    """
    role_id: int
    plantno: str
    empno: str
    remark: Optional[str] = ""

    @model_validator(mode="after")
    def validate_delete_b(self) -> "AclUserDeleteB":
        if self.role_id not in _ALLOWED_ROLE_IDS:
            raise ValueError(f"roleid 只能是 {_ALLOWED_ROLE_IDS} 之一（隔離維護/隔離查詢）")
        self.plantno = require_text(self.plantno, "廠區代碼", _PLANTNO_MAX)
        self.empno = require_text(self.empno, "工號", _EMPNO_MAX)
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
