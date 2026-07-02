"""
dept_service.py — 部門權限維護（移植舊版 EditDeptList.aspx + dbVOC.cs 部門相關方法）

依 legacy/EditDeptList.aspx.cs + legacy/dbVOC.cs 精讀重寫，相關方法：
  List廠區9()      — 廠區下拉（排除環工部/GMO，含 plantid=29 全廠）
  List部門()       — 部門下拉（VOC_dept 內已出現過、且在職的部門）
  List部門資料()   — 部門資料表格（可用廠區/部門篩選）
  Get部門名稱()    — 依工號帶出部門名稱（部門代碼驗證用）
  InsertDeptList() — 新增（防重複 (plantid,deptno)）
  UpdateDeptList() — 修改（plantid 不可改，只能改 deptno；舊版編輯時鎖定廠區下拉）
  DeleteDeptList() — 刪除

VOC_dept 只有 (plantid, deptno, cdatetime) 三欄，deptno 對應 [UTIDB].[dbo].[Employee].DeptNo，
plantid 對應 [VOC].[dbo].[VOC_plant].plantid（29 = ALL，代表該部門可視全廠資料，不受廠區篩選限制，
語意見 docs/legacy_source_analysis.md「VOC_plant：plantid(PK,29=ALL)」）。

環境無 ODBC driver，DB 查詢一律參數化 sqlalchemy text()（風格參照 services/history_service.py），
查詢/寫入失敗一律 raise + log，不回傳假資料掩蓋錯誤（比照 services/acl_service.py 的既有作法）。
"""

import logging
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)

# VOC_plant.plantid：29 = 全廠（ALL），語意上該部門不受廠區篩選限制
ALL_PLANT_ID = 29


# ── 純邏輯輔助函式（可單獨測試，不依賴 DB）─────────────────────────────────

def is_all_plant(plantid) -> bool:
    """判斷 plantid 是否代表「全廠」（VOC_plant.plantid=29）。非數字一律回 False。"""
    try:
        return int(plantid) == ALL_PLANT_ID
    except (TypeError, ValueError):
        return False


def _tranlog_str(plantno: str, deptno: str, deptname: str) -> str:
    """組 VOC_tranlog 的斜線串（舊版 databefore/dataafter = plantno+"/"+deptno+"/"+deptname）。"""
    return "/".join([plantno or "", deptno or "", deptname or ""])


# ── 查詢 ──────────────────────────────────────────────────────────────────

def list_plants(db: Session) -> list[dict]:
    """廠區下拉清單（舊版 List廠區9，排除環工部/GMO，含 plantid=29 全廠）。"""
    sql = text("""
        SELECT plantid, plantno FROM [VOC].[dbo].[VOC_plant]
        WHERE plantno NOT IN ('環工部', 'GMO')
        ORDER BY sort
    """)
    try:
        rows = db.execute(sql).mappings().all()
    except Exception as e:
        logger.error(f"[list_plants] DB 查詢失敗: {e}")
        raise
    return [dict(r) for r in rows]


def list_dept_options(db: Session) -> list[dict]:
    """部門下拉清單（舊版 List部門，取目前已在 VOC_dept 出現過、且在職的部門）。"""
    sql = text("""
        SELECT DISTINCT E.DeptNo AS deptno, E.DeptName AS deptname
        FROM [VOC].[dbo].[VOC_dept] D
        JOIN [UTIDB].[dbo].[Employee] E ON D.deptno = E.DeptNo AND E.isLeave = 0
        ORDER BY E.DeptNo
    """)
    try:
        rows = db.execute(sql).mappings().all()
    except Exception as e:
        logger.error(f"[list_dept_options] DB 查詢失敗: {e}")
        raise
    return [dict(r) for r in rows]


def list_dept_data(db: Session, plantid: str = "", deptno: str = "") -> list[dict]:
    """部門資料清單（舊版 List部門資料，供表格顯示），可用 plantid/deptno 篩選。"""
    sql = ("SELECT DISTINCT D.plantid, D.deptno, P.plantno, E.deptname "
           "FROM [VOC].[dbo].[VOC_dept] D "
           "JOIN [VOC].[dbo].[VOC_plant] P ON D.plantid = P.plantid "
           "JOIN [UTIDB].[dbo].[Employee] E ON D.deptno = E.DeptNo AND E.isLeave = 0 "
           "WHERE 1=1 ")
    params: dict = {}

    plantid_int = _to_int(plantid)
    if plantid_int and plantid_int > 0:
        sql += "AND D.plantid = :plantid "
        params["plantid"] = plantid_int
    if deptno:
        sql += "AND D.deptno = :deptno "
        params["deptno"] = deptno
    sql += "ORDER BY D.plantid, D.deptno"

    try:
        rows = db.execute(text(sql), params).mappings().all()
    except Exception as e:
        logger.error(f"[list_dept_data] DB 查詢失敗: {e}")
        raise
    return [dict(r) for r in rows]


def get_dept_name(db: Session, deptno: str) -> str:
    """
    依工號帶出部門名稱（舊版 Get部門名稱 / __deptno_TextChanged），查無回傳空字串
    （舊版對應「部門代碼錯誤!」訊息，由呼叫端決定要不要擋）。
    """
    sql = text("""
        SELECT DISTINCT DeptName FROM [UTIDB].[dbo].[Employee]
        WHERE DeptNo = :deptno AND isLeave = 0
    """)
    try:
        row = db.execute(sql, {"deptno": deptno}).mappings().first()
    except Exception as e:
        logger.error(f"[get_dept_name] DB 查詢失敗: {e}")
        raise
    return row["DeptName"] if row else ""


def get_dept_row(db: Session, plantid, deptno: str) -> dict | None:
    """取得單筆部門資料（含 plantno, deptname），供修改/刪除定位與 tranlog 用。"""
    rows = list_dept_data(db, plantid, deptno)
    return rows[0] if rows else None


def _get_plantno(db: Session, plantid) -> str:
    """依 plantid 反查 plantno（舊版 Insert/Update/DeleteDeptList 內固定先查一次）。"""
    try:
        row = db.execute(text(
            "SELECT plantno FROM [VOC].[dbo].[VOC_plant] WHERE plantid = :plantid"
        ), {"plantid": plantid}).first()
    except Exception as e:
        logger.error(f"[_get_plantno] DB 查詢失敗: {e}")
        raise
    return row[0] if row else ""


def _to_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _insert_tranlog(db: Session, empno: str, logtype: str, before: str, after: str, remark: str = "") -> None:
    db.execute(text("""
        INSERT INTO [VOC].[dbo].[VOC_tranlog]
            ([empno],[logtype],[databefore],[dataafter],[cdatetime],[remark])
        VALUES (:empno,:logtype,:databefore,:dataafter,:cdatetime,:remark)
    """), {
        "empno": empno, "logtype": logtype, "databefore": before, "dataafter": after,
        "cdatetime": datetime.now(), "remark": remark or "",
    })


# ── 新增 / 修改 / 刪除 ──────────────────────────────────────────────────────

def add_dept(db: Session, current_user_empno: str, plantid, deptno: str, remark: str = "") -> None:
    """
    新增一筆部門資料（舊版 InsertDeptList）。
    防重複：同 (plantid, deptno) 已存在則拒（舊版「此筆資料已存在部門資料內!」）。
    deptno 需能在 [UTIDB]..Employee 查到在職部門（舊版「部門代碼錯誤!」）。
    """
    try:
        plantno = _get_plantno(db, plantid)
        if not plantno:
            raise ValueError("廠區代碼不存在!")

        deptname = get_dept_name(db, deptno)
        if not deptname:
            raise ValueError("部門代碼錯誤!")

        dup = db.execute(text("""
            SELECT COUNT(*) FROM [VOC].[dbo].[VOC_dept]
            WHERE plantid = :plantid AND deptno = :deptno
        """), {"plantid": plantid, "deptno": deptno}).scalar()
        if (dup or 0) > 0:
            raise ValueError("此筆資料已存在部門資料內!")

        db.execute(text("""
            INSERT INTO [VOC].[dbo].[VOC_dept] ([plantid],[deptno],[cdatetime])
            VALUES (:plantid,:deptno,:cdatetime)
        """), {"plantid": plantid, "deptno": deptno, "cdatetime": datetime.now()})

        _insert_tranlog(db, current_user_empno, "I", "",
                         _tranlog_str(plantno, deptno, deptname), remark)
        db.commit()
    except ValueError:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"[add_dept] 新增失敗: {e}")
        raise


def update_dept(db: Session, current_user_empno: str, plantid, old_deptno: str,
                 new_deptno: str, remark: str = "") -> None:
    """
    修改一筆部門資料（舊版 UpdateDeptList）。
    plantid 不可改（舊版編輯表單廠區下拉鎖定），只能改 deptno。
    """
    try:
        plantno = _get_plantno(db, plantid)
        if not plantno:
            raise ValueError("廠區代碼不存在!")

        old_row = get_dept_row(db, plantid, old_deptno)
        if not old_row:
            raise ValueError("找不到要修改的部門資料")

        new_deptname = get_dept_name(db, new_deptno)
        if not new_deptname:
            raise ValueError("部門代碼錯誤!")

        result = db.execute(text("""
            UPDATE [VOC].[dbo].[VOC_dept] SET deptno = :deptno
            WHERE plantid = :plantid AND deptno = :old_deptno
        """), {"plantid": plantid, "old_deptno": old_deptno, "deptno": new_deptno})
        if result.rowcount == 0:
            raise ValueError("找不到要修改的部門資料")

        before = _tranlog_str(plantno, old_deptno, old_row["deptname"])
        after = _tranlog_str(plantno, new_deptno, new_deptname)
        _insert_tranlog(db, current_user_empno, "M", before, after, remark)
        db.commit()
    except ValueError:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"[update_dept] 修改失敗: {e}")
        raise


def delete_dept(db: Session, current_user_empno: str, plantid, deptno: str, remark: str = "") -> None:
    """刪除一筆部門資料（舊版 DeleteDeptList）。刪除前查一次現值供 tranlog 記錄。"""
    try:
        plantno = _get_plantno(db, plantid)
        if not plantno:
            raise ValueError("廠區代碼不存在!")

        row = get_dept_row(db, plantid, deptno)
        if not row:
            raise ValueError("找不到要刪除的部門資料")

        result = db.execute(text("""
            DELETE FROM [VOC].[dbo].[VOC_dept] WHERE plantid = :plantid AND deptno = :deptno
        """), {"plantid": plantid, "deptno": deptno})
        if result.rowcount == 0:
            raise ValueError("找不到要刪除的部門資料")

        before = _tranlog_str(plantno, deptno, row["deptname"])
        _insert_tranlog(db, current_user_empno, "D", before, "", remark)
        db.commit()
    except ValueError:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"[delete_dept] 刪除失敗: {e}")
        raise
