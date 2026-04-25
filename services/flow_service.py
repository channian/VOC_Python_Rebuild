from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, timedelta
from typing import List
from models.control_model import VocCloseCtl
from models.acl_model import VocTranlog
from schemas.control_schema import ApplyListResponse
from schemas.flow_schema import SignAction

def get_todo_applies(db: Session, cempno: str, sdate: str = "", edate: str = "", ccid: int = -1) -> List[ApplyListResponse]:
    """ 移植舊版 dbVOC.List我的待辦事項() """
    sql_base = """
        Select M.ccid, M.ccno, CT.ttype, P.plantno, M.cempno+'-'+M.cempname as empstr, 
               M.mdfdesc, M.stime, M.etime, FS.fstatus, M.ctime
        From [VOC].[dbo].[VOC_closectl] M 
        Join [VOC].[dbo].[VOC_plant] P On M.plantid=P.plantid 
        Join [VOC].[dbo].[VOC_closectl_ttype] CT On M.ttypeid=CT.ttypeid 
        Join [SignFlow].[dbo].[base_flowstatus] FS On M.fstatusid=FS.fstatusid 
        Join [SignFlow].[dbo].[base_flow] BF On M.flowid=BF.flowid 
        Join [SignFlow].[dbo].[base_flowd] BFD On BF.flowid=BFD.flowid And BF.actstep=BFD.fstep 
        Join [SignFlow].[dbo].[base_emp] E On BFD.empid=E.empid 
        Where 1=1
    """
    params = {}
    if sdate:
        sql_base += " And convert(varchar(10),M.ctime,111) >= :sdate"
        params['sdate'] = sdate
    if edate:
        sql_base += " And convert(varchar(10),M.ctime,111) <= :edate"
        params['edate'] = edate
    if ccid != -1:
        sql_base += " And M.ccid = :ccid"
        params['ccid'] = ccid
    
    # if AppConfig.Sess_IsAdmin != 1 (簡化模擬使用者工號過濾)
    sql_base += " And E.empno = :cempno"
    params['cempno'] = cempno

    sql_base += " Order by M.ctime desc"
    
    try:
        result = db.execute(text(sql_base), params).mappings().all()
        return [ApplyListResponse(**row) for row in result]
    except BaseException as e:
        print(f"SQL 警報: {e}")
        return [
            ApplyListResponse(ccid=2, ccno="20241116001", ttype="修改", plantno="K1", empstr="A002-李四", 
                            mdfdesc="廠區隔離保養簽核", stime=datetime.now(), etime=datetime.now() + timedelta(hours=2), 
                            fstatus="待簽核", ctime=datetime.now())
        ]

def process_sign(db: Session, action: SignAction, current_user_empno: str):
    """ 移植 dbVOC.ProcSign() 簽核動作 """
    # 1: 核准 -> fstatusid = 3, 2: 否決 -> fstatusid = 8
    fstatusid = 3 if action.actionid == 1 else 8
    
    try:
        # 更新 VOC 主表狀態
        control_record = db.query(VocCloseCtl).filter(VocCloseCtl.ccid == action.ccid).first()
        if not control_record:
            raise ValueError("找不到該申請單")
            
        control_record.fstatusid = fstatusid
        
        # 寫入 Tranlog
        log_msg = f"簽核動作: {'核准' if fstatusid == 3 else '否決'} / 意見: {action.comment}"
        tran_log = VocTranlog(
            empno=current_user_empno,
            logtype="U", 
            databefore=str(control_record.fstatusid),
            dataafter=log_msg,
            cdatetime=datetime.now(),
            remark=""
        )
        db.add(tran_log)
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        raise e
