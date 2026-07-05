"""
services_b/dept_service.py — 部門權限維護（Schema B 資料層版本）

對應 services/dept_service.py（A/MSSQL 版）。B 版差異：
  - VOC_dept(plantid, deptno, cdatetime) → dept(plant_id, dept_no, created_at)，FK 到 plant.plant_id。
  - 員工主檔查詢改用 B 內 employee 快取表（models_b.Employee，J 項：轉拋/排程同步），
    取代 A 版直接查 [UTIDB].[dbo].[Employee]。is_leave=false 才視為在職部門。
  - plantid=29=ALL 語意（G 項精神）：B 版理論上應改用 plant.kind='all'，但種子資料與既有
    is_all_plant() 純函式仍以「plantid 數值 29」表達，這裡沿用純函式重用（見下）；
    若 main_b 實際佈署時的全廠 plant_id 不是 29，呼叫端仍可自行改用 `plant.kind=='all'` 查詢，
    is_all_plant() 只是給模板顯示用的輔助判斷，不影響資料寫入正確性。

沿用重用（禁止複製，不依賴 DB 的純函式）：
  - services.dept_service.is_all_plant
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from models_b import Dept, Plant, Employee, Tranlog
from services.dept_service import is_all_plant  # noqa: F401

logger = logging.getLogger(__name__)


# ── 查詢 ──────────────────────────────────────────────────────────────────

def list_plants(db: Session) -> list[dict]:
    """廠區下拉清單（排除虛擬廠區，含全廠 kind='all'）。"""
    rows = db.execute(
        select(Plant.plant_id, Plant.plant_no)
        .where(Plant.kind != "virtual_group")
        .order_by(Plant.sort)
    ).all()
    return [{"plantid": r.plant_id, "plantno": r.plant_no} for r in rows]


def list_dept_options(db: Session) -> list[dict]:
    """部門下拉清單：目前已在 dept 表出現過、且在職的部門。"""
    stmt = (
        select(Employee.dept_no)
        .join(Dept, Dept.dept_no == Employee.dept_no)
        .where(Employee.is_leave.is_(False))
        .distinct()
    )
    rows = db.execute(stmt).scalars().all()
    return [{"deptno": d} for d in rows if d]


def list_dept_data(db: Session, plant_id: int | None = None, dept_no: str = "") -> list[dict]:
    """部門資料清單（可用 plant_id/dept_no 篩選），供表格顯示。"""
    stmt = (
        select(Dept.plant_id, Dept.dept_no, Plant.plant_no, Employee.emp_name)
        .join(Plant, Plant.plant_id == Dept.plant_id)
        .outerjoin(Employee, (Employee.dept_no == Dept.dept_no) & (Employee.is_leave.is_(False)))
    )
    if plant_id:
        stmt = stmt.where(Dept.plant_id == plant_id)
    if dept_no:
        stmt = stmt.where(Dept.dept_no == dept_no)
    stmt = stmt.order_by(Dept.plant_id, Dept.dept_no).distinct()
    rows = db.execute(stmt).all()

    # 部門名稱改由 get_dept_name 統一取得（多個在職員工可能對應同一部門，emp_name 只是任意一筆代表值，
    # 這裡改用 get_dept_name 確保與新增/修改防呆邏輯一致）
    result = []
    for r in rows:
        deptname = get_dept_name(db, r.dept_no) or (r.emp_name or "")
        result.append({"plantid": r.plant_id, "deptno": r.dept_no, "plantno": r.plant_no, "deptname": deptname})
    return result


def get_dept_name(db: Session, dept_no: str) -> str:
    """依部門代碼帶出部門名稱（employee 快取表任一在職員工的姓名？不對——部門本身無名稱欄，
    B 版 employee 快取表也沒有 DeptName 欄位，因此以「該部門在職員工人數 > 0」代表部門代碼有效，
    回傳 dept_no 本身作為顯示名稱（employee 表未提供部門中文名稱時的合理退化，
    ⚠️ 待業務確認：若日後 employee 同步含 DeptName 欄位，這裡應改讀該欄位）。"""
    cnt = db.execute(
        select(Employee.emp_no).where(Employee.dept_no == dept_no, Employee.is_leave.is_(False)).limit(1)
    ).first()
    return dept_no if cnt else ""


def get_dept_row(db: Session, plant_id, dept_no: str) -> dict | None:
    """取得單筆部門資料，供修改/刪除定位與 tranlog 用。"""
    rows = list_dept_data(db, plant_id, dept_no)
    return rows[0] if rows else None


def _get_plant_no(db: Session, plant_id) -> str:
    row = db.execute(select(Plant.plant_no).where(Plant.plant_id == plant_id)).scalar_one_or_none()
    return row or ""


# ── 新增 / 修改 / 刪除 ──────────────────────────────────────────────────────

def add_dept(db: Session, current_user_empno: str, plant_id, dept_no: str, remark: str = "") -> None:
    """新增一筆部門資料。防重複：同 (plant_id, dept_no) 已存在則拒；dept_no 需為有效在職部門代碼。"""
    try:
        plant_no = _get_plant_no(db, plant_id)
        if not plant_no:
            raise ValueError("廠區代碼不存在!")

        deptname = get_dept_name(db, dept_no)
        if not deptname:
            raise ValueError("部門代碼錯誤!")

        existing = db.execute(
            select(Dept).where(Dept.plant_id == plant_id, Dept.dept_no == dept_no)
        ).scalar_one_or_none()
        if existing:
            raise ValueError("此筆資料已存在部門資料內!")

        db.add(Dept(plant_id=plant_id, dept_no=dept_no, created_at=datetime.now(timezone.utc)))
        db.add(Tranlog(
            emp_no=current_user_empno, log_type="I", data_before={},
            data_after={"plant_no": plant_no, "dept_no": dept_no, "dept_name": deptname},
            remark=remark or "",
        ))
        db.commit()
    except ValueError:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"[add_dept] 新增失敗: {e}")
        raise


def update_dept(db: Session, current_user_empno: str, plant_id, old_dept_no: str,
                 new_dept_no: str, remark: str = "") -> None:
    """修改一筆部門資料。plant_id 不可改，只能改 dept_no（比照 A 版鎖定廠區下拉）。"""
    try:
        plant_no = _get_plant_no(db, plant_id)
        if not plant_no:
            raise ValueError("廠區代碼不存在!")

        entry = db.execute(
            select(Dept).where(Dept.plant_id == plant_id, Dept.dept_no == old_dept_no)
        ).scalar_one_or_none()
        if not entry:
            raise ValueError("找不到要修改的部門資料")

        new_deptname = get_dept_name(db, new_dept_no)
        if not new_deptname:
            raise ValueError("部門代碼錯誤!")

        old_deptname = get_dept_name(db, old_dept_no) or old_dept_no

        # dept_no 是複合主鍵一部分，改鍵值用「刪除舊列＋新增新列」
        db.delete(entry)
        db.flush()
        db.add(Dept(plant_id=plant_id, dept_no=new_dept_no, created_at=datetime.now(timezone.utc)))

        db.add(Tranlog(
            emp_no=current_user_empno, log_type="M",
            data_before={"plant_no": plant_no, "dept_no": old_dept_no, "dept_name": old_deptname},
            data_after={"plant_no": plant_no, "dept_no": new_dept_no, "dept_name": new_deptname},
            remark=remark or "",
        ))
        db.commit()
    except ValueError:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"[update_dept] 修改失敗: {e}")
        raise


def delete_dept(db: Session, current_user_empno: str, plant_id, dept_no: str, remark: str = "") -> None:
    """刪除一筆部門資料。"""
    try:
        plant_no = _get_plant_no(db, plant_id)
        if not plant_no:
            raise ValueError("廠區代碼不存在!")

        entry = db.execute(
            select(Dept).where(Dept.plant_id == plant_id, Dept.dept_no == dept_no)
        ).scalar_one_or_none()
        if not entry:
            raise ValueError("找不到要刪除的部門資料")

        deptname = get_dept_name(db, dept_no) or dept_no
        db.delete(entry)
        db.add(Tranlog(
            emp_no=current_user_empno, log_type="D",
            data_before={"plant_no": plant_no, "dept_no": dept_no, "dept_name": deptname},
            data_after={}, remark=remark or "",
        ))
        db.commit()
    except ValueError:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"[delete_dept] 刪除失敗: {e}")
        raise
