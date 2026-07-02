"""
dept_schema.py — 部門權限維護（EditDeptList）的 Pydantic 驗證

對應舊版 EditDeptList.aspx.cs 欄位驗證規則：
  - 廠區（plantid）與部門代碼（deptno）皆不可為空。
  - deptname / 部門代碼是否存在的驗證留給 service 層查 [UTIDB]..Employee（需要 DB）。
"""

from pydantic import BaseModel, model_validator
from typing import Optional


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
