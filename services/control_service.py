"""
control_service.py — 廠區隔離申請（EditControl / MyApply / PlantApply 移植）

對應舊系統 dbVOC.cs「新增隔離廠區項目清單」region（Insert隔離廠區項目 / Update隔離廠區項目 /
Proc送簽 / ProcSign / List我的申請單 / List隔離廠區項目）。

重要決策（見 CLAUDE.md「已知待辦」與 docs/legacy_source_analysis.md 第五節）：
  - 隔離免簽核（b_pass）邏輯已於舊系統停用，一律走簽核，本檔不移植免簽核分支。
  - 隔離時間上限一律 1 小時（見 schemas/control_schema.py），不分 pH / 其他項目。
  - ccno 流水號改查當日 MAX 後 3 碼 +1（見 next_ccno()），不再寫死 001。
"""

import logging
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import text

from models.control_model import VocCloseCtl, VocCloseCtlList
from models.acl_model import VocTranlog
from schemas.control_schema import ControlCreate, ApplyListResponse, ControlTagResponse
from services.flow_service import (
    FlowStatus,
    Ttype,
    Utype,
    build_rtype_list,
    create_sign_flow,
    insert_closectl_his,
)

logger = logging.getLogger(__name__)


# ── 純邏輯函式（不依賴 DB，可單獨測試）────────────────────────────────────────

def next_ccno(last_ccno: Optional[str], today: str) -> str:
    """
    計算下一個隔離申請單號（ccno），格式 yyyyMMddNNN 共 11 碼。

    對應舊系統 Insert隔離廠區項目() 的流水號規則：
        Select TOP 1 ccno From VOC_closectl Where ccno like 'yyyyMMdd%' Order by ccno desc
        （無則以 'yyyyMMdd000' 起算）取後 3 碼 +1 補零。
    ⚠️ 修法前 Python 端把 ccno 寫死成 '{today}001'，同一天第二筆就會撞號，是資料正確性 bug，
    見 docs/legacy_source_analysis.md「ccno 修法」章節。

    :param last_ccno: 當日目前資料庫查到的最大 ccno（同一 SQL 交易內查得，無資料時傳 None）
    :param today: 今天日期字串 yyyyMMdd（8 碼）
    """
    base_seq = 0 if not last_ccno else int(last_ccno[8:11])
    seq = base_seq + 1
    if seq > 999:
        # 舊系統（GetNextNo）沒有處理這個邊界，續號會變成 4 碼破壞 yyyyMMddNNN 11 碼格式；
        # 這裡刻意提前擋下視為溢位錯誤，屬於比舊系統更嚴謹的防呆改良（與舊行為的刻意差異）。
        raise ValueError(f"當日隔離申請單號已滿 999 筆，無法再新增（ccno 前綴={today}）")
    return f"{today}{seq:03d}"


# ── DB 存取 ────────────────────────────────────────────────────────────────

def _get_last_ccno_today(db: Session, today: str) -> Optional[str]:
    row = db.execute(
        text(
            "SELECT TOP 1 ccno FROM [VOC].[dbo].[VOC_closectl] "
            "WHERE ccno LIKE :pattern ORDER BY ccno DESC"
        ),
        {"pattern": f"{today}%"},
    ).first()
    return row[0] if row else None


def create_control(db: Session, current_user_empno: str, current_user_name: str, data: ControlCreate, is_commit: bool = True) -> bool:
    """
    對應舊版 Insert隔離廠區項目(hrow, rows, isCommit)。isCommit=True:送簽 / False:暫存。

    一律走簽核（免簽核 b_pass 分支舊系統已停用，不移植）：
      - 暫存：fstatusid=待簽核(0)
      - 送簽：建立簽核流程（create_sign_flow）後 fstatusid=簽核中(1)
    整個流程（含 ccno 流水號查詢）包在同一個 DB Session 交易內，commit 前不會有其他交易看到這筆 ccno。
    """
    try:
        # 防呆：時間區間重疊檢查
        # ⚠️ 與舊系統的差異：legacy Check申請隔離廠區項目() 是用 stime/etime「完全相等」才視為重複，
        # 這裡採較嚴格的「時間區間重疊」判斷。語意差異待業務確認是否要改回完全相等
        # （見 docs/legacy_source_analysis.md 落差清單 #8）。
        for itm in data.items:
            existing = db.query(VocCloseCtl).join(VocCloseCtlList).filter(
                VocCloseCtl.stime <= data.etime, VocCloseCtl.etime >= data.stime,
                VocCloseCtlList.plantno == itm.plantno, VocCloseCtlList.item == itm.item, VocCloseCtlList.sourceid == itm.sourceid
            ).first()
            if existing:
                raise ValueError("重覆申請隔離廠區項目!")

        today = datetime.today().strftime('%Y%m%d')
        last_ccno = _get_last_ccno_today(db, today)
        ccno = next_ccno(last_ccno, today)

        new_cc = VocCloseCtl(
            ttypeid=int(Ttype.新增), ccno=ccno, plantid=data.plantid, mdfdesc=data.mdfdesc,
            stime=data.stime, etime=data.etime, remark=data.remark,
            cempname=current_user_name, cempno=current_user_empno, ctime=datetime.now(),
            fstatusid=int(FlowStatus.待簽核),
        )
        db.add(new_cc)
        db.flush()

        for itm in data.items:
            db.add(VocCloseCtlList(ccid=new_cc.ccid, plantno=itm.plantno, item=itm.item, sourceid=itm.sourceid))
        db.flush()

        insert_closectl_his(db, new_cc.ccid, Utype.新增, current_user_empno, current_user_name)

        if is_commit:
            rtype_list = build_rtype_list([itm.item for itm in data.items])
            # 與舊碼 Insert隔離廠區項目() 一致的行為：plantno 沿用 foreach 迴圈結束後留下的最後一筆值
            # （legacy 用同一個區域變數，多廠區同時申請時只會用「最後一個項目」的廠區去建簽核流程；
            #  目前前端一次只送單一廠區，這裡忠實沿用舊行為，未做多廠區防呆）。
            plantno = data.items[-1].plantno
            flowid = create_sign_flow(db, plantno, rtype_list, current_user_empno, new_cc.ccid)
            new_cc.flowid = flowid
            new_cc.fstatusid = int(FlowStatus.簽核中)

        db.add(VocTranlog(empno=current_user_empno, logtype="I", databefore="", dataafter=f"新增隔離: ccno={ccno}, 項目數={len(data.items)}", cdatetime=datetime.now(), remark=data.remark))
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        raise e


def submit_control(db: Session, ccid: int, current_user_empno: str, current_user_name: str) -> bool:
    """
    對應舊版 Proc送簽(ccid)：把一筆先前「暫存」（fstatusid=待簽核）的隔離申請單正式送出簽核。

    目前前端（control_modal.html）建立時一律直接送簽（is_commit=True），尚未提供
    「先暫存、之後再送簽」的操作路徑，這裡先補上服務層函式與 utypeid=送簽(2) 的歷程紀錄，
    供未來串接「暫存」功能時使用。
    """
    try:
        record = db.query(VocCloseCtl).filter(VocCloseCtl.ccid == ccid).first()
        if not record:
            raise ValueError(f"無此筆資料! ccid:{ccid}")

        items = db.query(VocCloseCtlList).filter(VocCloseCtlList.ccid == ccid).all()
        if not items:
            raise ValueError("此隔離申請單尚無項目明細!")

        rtype_list = build_rtype_list([itm.item for itm in items])
        plantno = items[-1].plantno  # 沿用 legacy 行為，見 create_control() 註解

        flowid = create_sign_flow(db, plantno, rtype_list, current_user_empno, ccid)
        record.flowid = flowid
        record.fstatusid = int(FlowStatus.簽核中)

        insert_closectl_his(db, ccid, Utype.送簽, current_user_empno, current_user_name)

        db.add(VocTranlog(
            empno=current_user_empno, logtype="U",
            databefore=f"fstatusid={int(FlowStatus.待簽核)}",
            dataafter=f"送簽: ccno={record.ccno}", cdatetime=datetime.now(), remark="",
        ))
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        raise e


def get_my_applies(db: Session, cempno: str, sdate: str = "", edate: str = "", plantid: int = -1, statusid: int = -1, ccid: int = -1) -> List[ApplyListResponse]:
    """
    移植舊版 dbVOC.List我的申請單()。

    與舊版落差修正（見 docs/legacy_source_analysis.md 落差清單 #6）：
      - statusid=-1（全部）時排除否決(8) 的紀錄，比照舊系統。
      - 補上 sys_acluserrole 廠區過濾：查自己申請的單據之外，也納入自己有 ACL 廠區權限
        （sys_acluserrole.plantno = 該廠區 或 'ALL'）的廠區單據，用 EXISTS 子查詢做「額外納入」
        （不會反而濾掉自己的申請）。
        ⚠️ 這是「我的申請單」與「廠區的申請單」語意的合併簡化，實際業務規則待確認。
    """
    sql_base = """
        Select M.ccid, M.ccno, M.flowid, CT.ttype, P.plantno, M.cempno+'-'+M.cempname as empstr,
               M.mdfdesc, M.stime, M.etime, FS.fstatus, M.ctime
        From [VOC].[dbo].[VOC_closectl] M
        Join [VOC].[dbo].[VOC_plant] P On M.plantid=P.plantid
        Join [VOC].[dbo].[VOC_closectl_ttype] CT On M.ttypeid=CT.ttypeid
        Join [SignFlow].[dbo].[base_flowstatus] FS On M.fstatusid=FS.fstatusid
        Where 1=1
    """
    params = {}
    if sdate:
        sql_base += " And convert(varchar(10),M.ctime,111) >= :sdate"
        params['sdate'] = sdate
    if edate:
        sql_base += " And convert(varchar(10),M.ctime,111) <= :edate"
        params['edate'] = edate
    if plantid != -1:
        sql_base += " And M.plantid = :plantid"
        params['plantid'] = plantid
    if statusid != -1:
        sql_base += " And M.fstatusid = :statusid"
        params['statusid'] = statusid
    else:
        # 全部時排除否決(8)，比照舊系統（見 docs/legacy_source_analysis.md 落差清單 #6）
        sql_base += " And M.fstatusid != :rejected_status"
        params['rejected_status'] = int(FlowStatus.否決)

    if ccid == -1:
        # sys_acluserrole 廠區過濾：除了自己申請的單據，額外納入自己有 ACL 廠區權限
        # （該廠區或 'ALL'）的單據。inline 參數化 EXISTS 子查詢，不用字串拼接。
        sql_base += """
            And (
                M.cempno = :cempno
                Or Exists (
                    Select 1 From [VOC].[dbo].[sys_acluserrole] R
                    Where R.empno = :cempno And (R.plantno = 'ALL' Or R.plantno = P.plantno)
                )
            )
        """
        params['cempno'] = cempno
    else:
        sql_base += " And M.ccid = :ccid"
        params['ccid'] = ccid

    sql_base += " Order by M.ctime desc"

    try:
        rows = db.execute(text(sql_base), params).mappings().all()
    except Exception as e:
        logger.error(f"[get_my_applies] DB 查詢失敗 cempno={cempno}: {e}")
        raise

    return [ApplyListResponse(**row) for row in rows]


def get_active_isolations(db: Session) -> list:
    """
    取得目前時間點仍在有效期內的隔離記錄（fstatusid=核准(7)）。
    供 control_modal 首頁區塊顯示「目前有效隔離」。

    ⚠️ 修法前寫死 fstatusid=3，真實核准值是 7，見 docs/legacy_source_analysis.md「簽核狀態值」章節。
    """
    sql = text("""
        SELECT M.ccid, M.ccno, P.plantno,
               M.cempno + '-' + M.cempname AS empstr,
               M.mdfdesc, M.stime, M.etime, M.remark
        FROM  [VOC].[dbo].[VOC_closectl] M
        JOIN  [VOC].[dbo].[VOC_plant]    P ON M.plantid = P.plantid
        WHERE M.fstatusid = :approved_status
          AND M.stime <= GETDATE()
          AND M.etime >= GETDATE()
        ORDER BY M.stime
    """)
    try:
        rows = db.execute(sql, {"approved_status": int(FlowStatus.核准)}).mappings().all()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"[get_active_isolations] DB 查詢失敗: {e}")
        raise


def get_plant_list(db: Session) -> list:
    """
    取得所有顯示中廠區清單，供隔離申請表單的下拉選單使用。
    """
    sql = text("""
        SELECT plantid, plantno
        FROM  [VOC].[dbo].[VOC_plant]
        WHERE isShow = 1
        ORDER BY sort
    """)
    try:
        rows = db.execute(sql).mappings().all()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"[get_plant_list] DB 查詢失敗: {e}")
        raise


def get_plant_items(db: Session, plantno: str) -> list:
    """取得指定廠區的所有監控項目，供隔離申請 checkbox 使用"""
    sql = text("""
        SELECT S.item, S.source AS sourceid, I.unit
        FROM  [VOC].[dbo].[VOC_SPEC] S
        JOIN  [VOC].[dbo].[VOC_item] I ON S.item = I.item
        WHERE S.plantno = :plantno
        ORDER BY S.seqno
    """)
    try:
        rows = db.execute(sql, {"plantno": plantno}).mappings().all()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"[get_plant_items] DB 查詢失敗 plantno={plantno}: {e}")
        raise


def get_control_tags(db: Session, ccid: int) -> List[ControlTagResponse]:
    """ 移植舊版 dbVOC.List隔離廠區項目() """
    sql_base = """
        Select concat(L.plantno,'_',L.item) as oldtagname, L.plantno, L.item, S.source
        From [VOC].[dbo].[VOC_closectl_list] L
        Join [VOC].[dbo].[VOC_source] S On L.sourceid=S.sourceid
        Where ccid = :ccid
    """
    try:
        result = db.execute(text(sql_base), {"ccid": ccid}).mappings().all()
        return [ControlTagResponse(**row) for row in result]
    except Exception as e:
        logger.error(f"[get_control_tags] DB 查詢失敗 ccid={ccid}: {e}")
        raise
