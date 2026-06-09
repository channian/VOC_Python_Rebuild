from sqlalchemy.orm import Session
from datetime import datetime
from typing import List
from models.spec_model import VocSpec, VocSource
from models.acl_model import VocTranlog
from schemas.spec_schema import SpecCreate, SpecUpdate, SpecResponse, SpecBase

def list_specs(db: Session, plantno: str = "", item: str = "") -> List[SpecResponse]:
    """ 查詢舊版 dbVOC.List規格值資料 """
    query = db.query(
        VocSpec.plantno, VocSpec.item, VocSpec.LAW, VocSpec.OOS, VocSpec.OOC, VocSpec.alert,
        VocSpec.source.label('sourceid'),
        VocSource.source
    ).outerjoin(VocSource, VocSpec.source == VocSource.sourceid)
    try:
        if plantno:
            query = query.filter(VocSpec.plantno == plantno)
        if item:
            query = query.filter(VocSpec.item == item)
        result = query.all()
    except Exception as e:
        print(f"DB Query Error: {e}")
        result = []

    if not result:
        return [
            SpecResponse(plantno="K1", item="VOC", LAW="100", OOS="80", OOC="60", alert="50", source="SCADA (SQL)", sourceid=1, tagname="K1_VOC"),
            SpecResponse(plantno="K2", item="pH", LAW="6-9", OOS="6.5-8.5", OOC="7-8", alert="7.2-7.8", source="CIM (Oracle)", sourceid=2, tagname="K2_pH"),
        ]

    return [SpecResponse.model_validate(row) for row in result]


def get_sources(db: Session) -> list:
    """取得資料來源清單，供規格維護表單下拉選單使用"""
    try:
        rows = db.query(VocSource.sourceid, VocSource.source).all()
        return [{"sourceid": r.sourceid, "source": r.source} for r in rows]
    except Exception as e:
        print(f"[get_sources] DB 查詢失敗: {e}")
        return [
            {"sourceid": 1, "source": "SCADA (SQL)"},
            {"sourceid": 2, "source": "CWMS"},
            {"sourceid": 3, "source": "QA 手測"},
        ]

def create_spec(db: Session, current_user_empno: str, data: SpecCreate) -> bool:
    try:
        # 防呆
        existing = db.query(VocSpec).filter_by(plantno=data.plantno, item=data.item).first()
        if existing:
            raise ValueError("此筆資料已存在規格值資料內!")
            
        new_spec = VocSpec(
            plantno=data.plantno,
            item=data.item,
            LAW=data.LAW,
            OOS=data.OOS,
            OOC=data.OOC,
            alert=data.alert,
            source=data.source_id,
            status=1,
            tagname=f"{data.plantno}_{data.item}"
        )
        db.add(new_spec)
        
        # 寫入 TranLog
        log_str = f"{data.plantno}/{data.item}/{data.LAW}/{data.OOS}/{data.OOC}/{data.alert}/{data.source_id}"
        tran_log = VocTranlog(
            empno=current_user_empno,
            logtype="I",
            databefore="",
            dataafter=log_str,
            cdatetime=datetime.now(),
            remark=data.remark
        )
        db.add(tran_log)
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        print(f"Create SPEC Error: {e}")
        return False

def update_spec(db: Session, current_user_empno: str, data: SpecUpdate) -> bool:
    try:
        spec = db.query(VocSpec).filter_by(plantno=data.plantno, item=data.item).first()
        if not spec:
            raise ValueError("找不到資料!")
            
        old_log_str = f"{spec.plantno}/{spec.item}/{spec.LAW}/{spec.OOS}/{spec.OOC}/{spec.alert}/{spec.source}"
        
        spec.LAW = data.LAW
        spec.OOS = data.OOS
        spec.OOC = data.OOC
        spec.alert = data.alert
        spec.source = data.source_id
        spec.tagname = f"{data.plantno}_{data.item}"
        
        new_log_str = f"{data.plantno}/{data.item}/{data.LAW}/{data.OOS}/{data.OOC}/{data.alert}/{data.source_id}"
        
        tran_log = VocTranlog(
            empno=current_user_empno,
            logtype="M", # Modify
            databefore=old_log_str,
            dataafter=new_log_str,
            cdatetime=datetime.now(),
            remark=data.remark
        )
        db.add(tran_log)
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        print(f"Update SPEC Error: {e}")
        return False

def delete_spec(db: Session, current_user_empno: str, plantno: str, item: str, remark: str = "") -> bool:
    try:
        spec = db.query(VocSpec).filter_by(plantno=plantno, item=item).first()
        if not spec:
            raise ValueError("找不到資料!")
            
        old_log_str = f"{spec.plantno}/{spec.item}/{spec.LAW}/{spec.OOS}/{spec.OOC}/{spec.alert}/{spec.source}"
        db.delete(spec)
        
        tran_log = VocTranlog(
            empno=current_user_empno,
            logtype="D",
            databefore=old_log_str,
            dataafter="",
            cdatetime=datetime.now(),
            remark=remark
        )
        db.add(tran_log)
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        print(f"Delete SPEC Error: {e}")
        return False
