"""
dept_schema.py — 部門權限維護（EditDeptList）的 Pydantic 驗證

對應舊版 EditDeptList.aspx.cs 欄位驗證規則：
  - 廠區（plantid）與部門代碼（deptno）皆不可為空。
  - deptname / 部門代碼是否存在的驗證留給 service 層查 [UTIDB]..Employee（需要 DB）。
"""

from pydantic import BaseModel, model_validator
from typing import Optional

from schemas.field_rules import require_text


class DeptAdd(BaseModel):
    plantid: int
    deptno: str
    remark: Optional[str] = ""

    @model_validator(mode="after")
    def validate_all(self) -> "DeptAdd":
        if self.plantid <= 0:
            raise ValueError("請選擇廠區!")
        if not self.deptno.strip():
            raise ValueError("部門代碼不可為空!")
        self.deptno = self.deptno.strip()
        return self


class DeptUpdate(BaseModel):
    plantid: int
    old_deptno: str
    deptno: str
    remark: Optional[str] = ""

    @model_validator(mode="after")
    def validate_all(self) -> "DeptUpdate":
        if self.plantid <= 0:
            raise ValueError("請選擇廠區!")
        if not self.old_deptno.strip():
            raise ValueError("缺少原部門代碼，無法定位要修改的資料")
        if not self.deptno.strip():
            raise ValueError("部門代碼不可為空!")
        self.old_deptno = self.old_deptno.strip()
        self.deptno = self.deptno.strip()
        return self


class DeptDelete(BaseModel):
    plantid: int
    deptno: str

    @model_validator(mode="after")
    def validate_all(self) -> "DeptDelete":
        if self.plantid <= 0:
            raise ValueError("請選擇廠區!")
        if not self.deptno.strip():
            raise ValueError("部門代碼不可為空!")
        self.deptno = self.deptno.strip()
        return self


# ══════════════════════════════════════════════════════════════════════════
# B 棧（Schema B / PostgreSQL）專用請求模型
# ══════════════════════════════════════════════════════════════════════════
# 2026-08-01 D5：部門權限頁的欄位形狀 A/B 完全相同（plantid + deptno + remark），
# 因此 B 版**直接繼承上面的 A 棧模型重用既有驗證**（廠區必選、部門代碼必填、去空白），
# 只在子類別追加 B 棧才需要的長度上限（models_b.Dept.dept_no 為 String(50)）。
#
# ★ 為什麼不把長度上限直接加進 A 棧的 DeptAdd/DeptUpdate/DeptDelete？
#   那會讓 A 棧（公司平行測試中）原本送得進去的超長字串開始收到 422，屬於行為變更；
#   本專案慣例是「新增 optional／子類別，預設走舊路徑」，故一律用繼承加在 B 棧側。
#   Pydantic v2 會依序執行父類別與子類別的 model_validator（名稱不同才不會覆蓋），
#   所以 B 版等於「A 版全部規則 ＋ 長度上限」。

_DEPTNO_MAX = 50   # models_b.Dept.dept_no = String(50)


class DeptAddB(DeptAdd):
    """新增一筆部門資料（POST /dept/add）。"""

    @model_validator(mode="after")
    def validate_lengths_b(self) -> "DeptAddB":
        self.deptno = require_text(self.deptno, "部門代碼", _DEPTNO_MAX)
        return self


class DeptUpdateB(DeptUpdate):
    """修改一筆部門資料（POST /dept/update）：plantid 不可改，只換 deptno。"""

    @model_validator(mode="after")
    def validate_lengths_b(self) -> "DeptUpdateB":
        self.old_deptno = require_text(self.old_deptno, "原部門代碼（用於定位要修改的資料）", _DEPTNO_MAX)
        self.deptno = require_text(self.deptno, "部門代碼", _DEPTNO_MAX)
        return self


class DeptDeleteB(DeptDelete):
    """刪除一筆部門資料（POST /dept/delete）。"""

    @model_validator(mode="after")
    def validate_lengths_b(self) -> "DeptDeleteB":
        self.deptno = require_text(self.deptno, "部門代碼", _DEPTNO_MAX)
        return self
