from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
from typing import List
from models.acl_model import SysAclUserRole, SysAclRole, VocTranlog
from schemas.acl_schema import AclUserCreate, AclUserUpdate, AclUserBase, AclUserResponse

def check_permission(db: Session, empno: str, rights_id: int) -> bool:
    """
    對應舊版 dbAclRights.Check權限(rights) 函數。
    確保目前操作的員工號碼具備特並的 rights_id，如果是 '系統管理員'(1) 則無條件放行。
    """
    # ...TODO: 詳細邏輯將與後續 Route Guard (Dependency) 一併完善
    return True 

def list_acl_users(db: Session, plantno: str = "", roletype: str = "", empno: str = "") -> List[AclUserResponse]:
    """
    重構自 dbVOC.List隔離權限名單資料()，因為牽涉跨資料庫庫(UTIDB)故保留原生 SQL。
    """
    sql_query = """
    Select R.plantno as plantno, T.rolename as roletype, R.empno as empno,
           E.empname as empname, E.notesid as notesid, R.stype as stype
    From [VOC].[dbo].[sys_acluserrole] R
    Join [VOC].[dbo].[sys_aclrole] T On R.roleid=T.roleid
    Left Join [UTIDB].[dbo].[Employee] E On R.empno=E.empno
    Where T.roleid In (3,7)
    """
    params = {}
    if plantno:
        sql_query += " And R.plantno = :plantno"
        params['plantno'] = plantno
    if roletype:
        sql_query += " And T.rolename = :roletype"
        params['roletype'] = roletype
    if empno:
        sql_query += " And R.empno = :empno"
        params['empno'] = empno
        
    sql_query += " Order By R.plantno, T.roleid"
    
    try:
        # result = db.execute(text(sql_query), params).mappings().all()
        # Mock 資料
        result = [
            {"plantno": "K1", "roletype": "廠區負責人", "empno": "A001", "empname": "王大明", "notesid": "daming_wang", "stype": "ALL"},
            {"plantno": "K2", "roletype": "系統管理員", "empno": "admin", "empname": "系統管理員", "notesid": "admin", "stype": "空"}
        ]
        
        return [
            AclUserResponse(
                plantno=row.get("plantno"),
                roletype=row.get("roletype"),
                empno=row.get("empno"),
                empname=row.get("empname"),
                notesid=str(row.get("notesid")).replace("@aseglobal.com", ""), # 照舊版處理
                stype="全區" if row.get("stype") == "ALL" else row.get("stype")
            )
            for row in result
        ]
    except Exception as e:
        print(f"Error executing List隔離權限名單資料: {e}")
        return []

def create_acl_user(db: Session, current_user_empno: str, data: AclUserCreate) -> bool:
    """ 重構 InsertAclUserList """
    try:
        # 防呆
        existing = db.query(SysAclUserRole).filter_by(
            roleid=data.role_id, plantno=data.plantno, empno=data.empno
        ).first()
        if existing:
            raise ValueError("此筆資料已存在隔離權限名單資料內!")
            
        stype_val = "空" if data.stype == "1" else ("水" if data.stype == "2" else "ALL")
        
        # 準備 Insert Models (ORM)
        new_acl = SysAclUserRole(
            roleid=data.role_id,
            plantno=data.plantno,
            empno=data.empno,
            stype=stype_val
        )
        db.add(new_acl)
        
        # 準備 VOC_tranlog
        # dataafter: plantno / roletype / empno / stype
        tran_log = VocTranlog(
            empno=current_user_empno,
            logtype="I",
            databefore="",
            dataafter=f"{data.plantno}/{data.role_id}/{data.empno}/{stype_val}",
            cdatetime=datetime.now(),
            remark=data.remark
        )
        db.add(tran_log)
        
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        print(f"Create ACL Error: {e}")
        return False

def delete_acl_user(db: Session, current_user_empno: str, data: AclUserBase) -> bool:
    """ 重構 DeleteAclUserList """
    try:
        user_role = db.query(SysAclUserRole).filter_by(
            roleid=data.role_id, plantno=data.plantno, empno=data.empno
        ).first()
        if not user_role:
            raise ValueError("資料不存在")
            
        db.delete(user_role)
        
        tran_log = VocTranlog(
            empno=current_user_empno,
            logtype="D",
            databefore=f"{data.plantno}/{data.role_id}/{data.empno}/{user_role.stype}",
            dataafter="",
            cdatetime=datetime.now(),
            remark=data.remark
        )
        db.add(tran_log)
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        return False
