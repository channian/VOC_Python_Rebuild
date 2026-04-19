from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List, Optional

from models.control_model import VocCloseCtl, VocCloseCtlList
from models.acl_model import VocTranlog
from schemas.control_schema import ControlCreate, ControlResponse

def create_control(db: Session, current_user_empno: str, current_user_name: str, data: ControlCreate, is_commit: bool = True) -> bool:
    """
    對應舊版 `Proc新增隔離廠區項目`
    :param is_commit: False 代表暫存, True 代表送簽
    """
    try:
        # --- 1. 檢查有無重複申請 ---
        # 對於清單中的每一個項目檢查是否有重疊的申請
        for itm in data.items:
            # SQLAlchemy 檢查重疊的條件 (簡化舊版 Check申請隔離廠區項目)
            existing = db.query(VocCloseCtl).join(VocCloseCtlList).filter(
                VocCloseCtl.stime <= data.etime,
                VocCloseCtl.etime >= data.stime,
                VocCloseCtlList.plantno == itm.plantno,
                VocCloseCtlList.item == itm.item,
                VocCloseCtlList.sourceid == itm.sourceid
            ).first()
            if existing:
                raise ValueError("重覆申請隔離廠區項目!")

        # --- 2. 判斷免簽核邏輯 (Check申請隔離免簽核) ---
        b_pass = True
        ts = data.etime - data.stime
        for itm in data.items:
            item_name = itm.item
            # 必須是 pH, Cu, Ni, SS, COD 才能有機會免簽
            isValidItem = any(x in item_name for x in ["pH", "Cu", "Ni", "SS", "COD"])
            if not isValidItem:
                b_pass = False
                break
            
            # pH < 1 小時, 其他 < 4 小時
            if "pH" in item_name and ts.total_seconds() > 3600:
                b_pass = False
                break
            elif "pH" not in item_name and ts.total_seconds() > 14400:
                b_pass = False
                break
                
            # 還要檢查今天是不是已經有核准的紀錄 (只能免簽一次)...此處先縮減以防呆為主
            
        fstatusid = 1 # 1: 待簽核 (預設)
        if is_commit and b_pass:
            fstatusid = 3 # 3: 依舊版 MTFlowBase.FlowStatus.核准 假設對齊 3

        # --- 3. 準備寫入主檔 VocCloseCtl ---
        today_prefix = datetime.today().strftime("%Y%m%d")
        # 假設取得最大號碼
        ccno = f"{today_prefix}001" 
        
        new_cc = VocCloseCtl(
            ttypeid=1,
            ccno=ccno,
            plantid=data.plantid,
            mdfdesc=data.mdfdesc,
            stime=data.stime,
            etime=data.etime,
            remark=data.remark,
            cempname=current_user_name,
            cempno=current_user_empno,
            ctime=datetime.now(),
            fstatusid=fstatusid
        )
        db.add(new_cc)
        db.flush() # 取得 autoincrement ccid
        
        # --- 4. 準備寫入子檔 VocCloseCtlList ---
        for itm in data.items:
            new_list_itm = VocCloseCtlList(
                ccid=new_cc.ccid,
                plantno=itm.plantno,
                item=itm.item,
                sourceid=itm.sourceid
            )
            db.add(new_list_itm)
        
        # --- 5. 寫入 Tranlog ---
        tran_log = VocTranlog(
            empno=current_user_empno,
            logtype="I",
            databefore="",
            dataafter=f"新增隔離: ccno={ccno}, 項目數={len(data.items)}",
            cdatetime=datetime.now(),
            remark=data.remark
        )
        db.add(tran_log)

        db.commit()
        return True
    except Exception as e:
        db.rollback()
        raise e
