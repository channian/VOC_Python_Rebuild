"""
flow_service.py — 簽核流程（法遵平台_隔離廠區項目維護）

對應舊系統 MTFlowBase.cs / dbSignFlow.cs 的「一階群組簽核」多載
（dbSignFlow.CreateNewFlow(fruleid, fid, empno, plantno, rtype, hashkey, showinfo) 這個版本，
 2019/02/27 新增，VOC 平台專用，不牽涉多級主管爬升）：

  1. Get簽核人員(plantno, rtype, empno)：VOC_Mail_List 裡 SignGrp=1、同廠區、RptType 符合、
     排除申請人自己、排除離職員工的名單，即為這關的簽核人。
  2. 全部簽核人都插在同一個 fstep=1（不分層級），base_flow.fstatusid 初始為「簽核中」。
  3. Sign()：任一位簽核人核准/否決，流程立即結案（OR 邏輯，不是全員會簽）。
     因為所有人都在 fstep=1，找不到 fstep>1 的下一關，流程必然馬上關閉。

參考 docs/legacy_source_analysis.md「簽核狀態值」「簽核流程完整還原」章節（2026-07-01 由
legacy/MTFlowBase.cs + legacy/dbSignFlow.cs 確認）。
"""

import logging
from enum import IntEnum
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import text, bindparam

from models.control_model import VocCloseCtl
from models.acl_model import VocTranlog
from schemas.control_schema import ApplyListResponse
from schemas.flow_schema import SignAction
from services.category_util import is_air_item

logger = logging.getLogger(__name__)


# ── 簽核狀態值（legacy/MTFlowBase.cs FlowStatus enum，真實數值）──────────────
# ⚠️ 2026-07-01 前 Python 端把「核准」誤寫死成 3，真實值是 7；這是資料正確性 bug，
#    見 docs/legacy_source_analysis.md「簽核狀態值」章節。全部改引用此 Enum，禁止再寫死數字。
class FlowStatus(IntEnum):
    待簽核 = 0
    簽核中 = 1
    核准 = 7
    否決 = 8
    取消 = 12


# MTFlowBase.SignAction enum（跟 FlowStatus 是不同的東西：這是「使用者選的動作」，
# FlowStatus 是「流程目前的狀態」）。取消(=8) 舊系統已停用（註解掉），這裡不提供。
SIGN_ACTION_APPROVE = 1  # 核准
SIGN_ACTION_REJECT = 9   # 否決


# dbVOC.cs 內部的 Ttype / Utype enum（隔離申請單類別 / 歷程異動類別）
class Ttype(IntEnum):
    新增 = 1
    修改隔離區間 = 2


class Utype(IntEnum):
    新增 = 1
    送簽 = 2
    修改隔離區間 = 3


# MTFlowBase.ReviewerType.人員（VOC 平台的簽核人一律是「人員」類型，不用職位/部門）
REVIEWER_TYPE_PERSON = 2

# dbVOC.cs 簽核流程 enum：法遵平台_隔離廠區項目維護 = 8
FRULEID_ISOLATION = 8


# ── 純邏輯函式（不依賴 DB，可單獨測試）────────────────────────────────────────

def build_rtype_list(items: List[str],
                     categories: Optional[Dict[str, Optional[str]]] = None) -> List[str]:
    """
    依隔離項目組出簽核用的 rpttype 清單（VOC_Mail_List.rpttype）。
    對應舊系統 dbVOC.cs：
        string stype = (item.IndexOf("VOC") > -1 ? "空" : "水") + "保養中";
        rtype += (rtype.IndexOf(stype) > -1 ? "" : (rtype == "" ? "'" : ",'") + stype + "'");
    含 "VOC" 字樣的項目歸類為「空保養中」，其餘一律「水保養中」，依出現順序去重。
    舊碼是直接把 rtype 字串拼進 SQL IN 子句（injection 風險），這裡改成清單，
    交給 get_signers() 用 SQLAlchemy expanding bindparam 參數化。

    categories（2026-08-01 D7 新增，比照 _calculate_light 的 check_lower_bound 保護模式）：
      {項目名稱: 類型}（類型來源 models_b.Item.category：'水質'/'空汙'/'雨水溝'）。
      **預設 None → 每個項目都完全退回原本的 `"VOC" in item` 名稱字串比對**，
      A 棧（services/control_service.py）不傳此參數，行為一個字元都不變；
      B 棧（services_b/control_service.py）傳入真實對照表，查不到的項目（dict 內沒有這個
      key，或值為 NULL）一樣退回名稱比對，未回填 category 的舊資料不會壞掉。
      用 dict 而非平行 list，避免長度／順序對不上造成的錯配。
    """
    cats = categories or {}
    rtypes: List[str] = []
    for item in items:
        stype = ("空" if is_air_item(item, cats.get(item)) else "水") + "保養中"
        if stype not in rtypes:
            rtypes.append(stype)
    return rtypes


# ── DB 存取：簽核人查詢 / 建立流程 / 簽核 ──────────────────────────────────────

def get_signers(db: Session, plantno: str, rtype_list: List[str], empno: str) -> List[str]:
    """
    對應 dbSignFlow.Get簽核人員(plantno, rtype, empno)：

        Select Distinct M.empno
        From [VOC].[dbo].[VOC_Mail_List] M
        Join [UTIDB].[dbo].[Employee] E On M.empno=E.empno And E.isLeave=0
        Where M.plantno=@plantno And M.RptType in (@rtype) And M.empno!=@empno And M.SignGrp=1

    ⚠️ 舊碼的 @rtype 是直接字串拼接組出的 SQL IN 子句（`"'水保養中','空保養中'"`），
    有 SQL injection 風險。這裡改用 SQLAlchemy expanding bindparam 做真正的參數化。
    """
    if not rtype_list:
        return []
    stmt = text(
        "SELECT DISTINCT M.empno "
        "FROM [VOC].[dbo].[VOC_Mail_List] M "
        "JOIN [UTIDB].[dbo].[Employee] E ON M.empno = E.empno AND E.isLeave = 0 "
        "WHERE M.plantno = :plantno AND M.RptType IN :rtypes "
        "AND M.empno != :empno AND M.SignGrp = 1"
    ).bindparams(bindparam("rtypes", expanding=True))
    rows = db.execute(stmt, {"plantno": plantno, "rtypes": rtype_list, "empno": empno}).fetchall()
    return [r[0] for r in rows]


def _get_emp_id(db: Session, empno: str) -> int:
    """
    查 [SignFlow].[dbo].[base_emp] 的 empid。

    ⚠️ 已知限制：舊系統 dbSignFlow.Get員工id() 查不到資料時，會即時呼叫 AD/LDAP
    （MTDBbase.Get員工資訊）自動補建 base_emp 資料列。本專案 AD/LDAP 整合延後到 Phase 3
    （見 HANDOVER.md），這裡暫不實作自動建檔，查無資料直接 raise，待 LDAP 串接後補齊。
    """
    row = db.execute(
        text("SELECT empid FROM [SignFlow].[dbo].[base_emp] WHERE empno = :empno"),
        {"empno": empno},
    ).first()
    if not row:
        raise ValueError(
            f"員工 {empno} 尚無簽核系統基本資料（SignFlow..base_emp），"
            "需先透過 AD/LDAP 整合建檔（Phase 3 待實作，見 HANDOVER.md）"
        )
    return row[0]


def _get_pos_id(db: Session, empid: int) -> Optional[int]:
    """查 [SignFlow].[dbo].[base_emp].posid（對應 dbSignFlow.Get職稱By員工）。"""
    row = db.execute(
        text("SELECT posid FROM [SignFlow].[dbo].[base_emp] WHERE empid = :empid"),
        {"empid": empid},
    ).first()
    return row[0] if row else None


def create_sign_flow(db: Session, plantno: str, rtype_list: List[str], empno: str, fid: int) -> int:
    """
    對應 dbSignFlow.CreateNewFlow(fruleid, fid, empno, plantno, rtype, hashkey, showinfo)
    的「一階群組簽核」多載：

      1. 找簽核人（Get簽核人員）
      2. INSERT SignFlow..base_flow（fstatusid=簽核中(1)，actstep=1）
      3. 每個簽核人都 INSERT SignFlow..base_flowd，統一 fstep=1

    找不到任何簽核人時直接 raise——舊系統仍會建立一個沒人能簽的流程（形同卡死），
    這裡刻意提前擋下，屬於比舊系統更嚴謹的防呆改良（與舊行為的刻意差異）。

    ⚠️ 未移植：flowurl（來自 base_flowrule）、showinfo、SendMail通知()。
    Email 簽核通知屬於 notify_service.py 範圍，不在本次任務授權可修改的檔案清單內。
    """
    signer_empnos = get_signers(db, plantno, rtype_list, empno)
    if not signer_empnos:
        raise ValueError(f"廠區 {plantno} 尚未設定簽核人員（VOC_Mail_List.SignGrp=1），無法送簽")

    applicant_empid = _get_emp_id(db, empno)

    flow_row = db.execute(
        text(
            "INSERT INTO [SignFlow].[dbo].[base_flow] "
            "([fruleid],[actstep],[fstatusid],[fid],[empid],[fstime]) "
            "OUTPUT INSERTED.flowid "
            "VALUES (:fruleid, 1, :fstatusid, :fid, :empid, :fstime)"
        ),
        {
            "fruleid": FRULEID_ISOLATION,
            "fstatusid": int(FlowStatus.簽核中),
            "fid": fid,
            "empid": applicant_empid,
            "fstime": datetime.now(),
        },
    ).first()
    flowid = flow_row[0]

    for signer_empno in signer_empnos:
        sign_empid = _get_emp_id(db, signer_empno)
        sign_posid = _get_pos_id(db, sign_empid)
        db.execute(
            text(
                "INSERT INTO [SignFlow].[dbo].[base_flowd] "
                "([flowid],[fstep],[ftype],[empid],[posid]) "
                "VALUES (:flowid, 1, :ftype, :empid, :posid)"
            ),
            {
                "flowid": flowid,
                "ftype": REVIEWER_TYPE_PERSON,
                "empid": sign_empid,
                "posid": sign_posid,
            },
        )

    return flowid


def insert_closectl_his(db: Session, ccid: int, utypeid: Utype, current_user_empno: str, current_user_name: str) -> None:
    """
    對應舊系統 InsertHis()：把 VOC_closectl 目前這筆資料完整複製一份到歷程表 VOC_closectl_his，
    並記錄異動類型（utypeid：1新增/2送簽/3修改）與操作人（uclerk = empno-empname）。
    """
    db.execute(
        text(
            "INSERT INTO [VOC].[dbo].[VOC_closectl_his] "
            "([utypeid],[utime],[uclerk],[ccid],[ttypeid],[ccno],[plantid],[mdfdesc],[stime],[etime],"
            "[remark],[cempname],[cempno],[ctime],[flowid],[fstatusid],[del],[delclerk],[orgccid]) "
            "SELECT :utypeid, :utime, :uclerk, ccid, ttypeid, ccno, plantid, mdfdesc, stime, etime, "
            "remark, cempname, cempno, ctime, flowid, fstatusid, del, delclerk, orgccid "
            "FROM [VOC].[dbo].[VOC_closectl] WHERE ccid = :ccid"
        ),
        {
            "utypeid": int(utypeid),
            "utime": datetime.now(),
            "uclerk": f"{current_user_empno}-{current_user_name}",
            "ccid": ccid,
        },
    )


# ── 待辦清單 / 簽核動作 ────────────────────────────────────────────────────────

def get_todo_applies(db: Session, cempno: str, sdate: str = "", edate: str = "", ccid: int = -1) -> List[ApplyListResponse]:
    """ 移植舊版 dbVOC.List我的待辦事項() """
    sql_base = """
        Select M.ccid, M.ccno, M.flowid, CT.ttype, P.plantno, M.cempno+'-'+M.cempname as empstr,
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
    except Exception as e:
        # 不再吐假資料：DB/跨庫查詢失敗一律記 log 後往上拋，由 router 轉成錯誤回應。
        logger.error(f"[get_todo_applies] DB 查詢失敗 cempno={cempno}: {e}")
        raise


def resolve_new_status(actionid: int) -> FlowStatus:
    """
    依 SignAction.actionid 決定簽核結案後的 FlowStatus（純函式，不依賴 DB，供測試用）。
    對應 dbSignFlow.Sign() 裡 `switch (act) { 核准/分享 -> 核准; 否決 -> 否決; }` 的簡化版
    （VOC 平台沒有「分享」動作，只有核准/否決）。
    VOC 是「任一位簽核人先簽，流程就立刻結束」（OR 邏輯），所以呼叫這個函式的當下就代表流程已結案。
    """
    return FlowStatus.核准 if actionid == SIGN_ACTION_APPROVE else FlowStatus.否決


def process_sign(db: Session, action: SignAction, current_user_empno: str, current_user_name: str) -> bool:
    """
    對應 dbSignFlow.Sign() + dbVOC.ProcSign()：VOC 平台的「一階群組簽核」。

    VOC 只有 fstep=1 一關，任一位簽核人核准/否決，流程立即結案（OR 邏輯，非全員會簽）：
      - 更新該簽核人在 base_flowd 的簽核紀錄
      - base_flow.fstatusid 依動作改成 核准(7)/否決(8)
      - 同步回寫 VOC_closectl.fstatusid
      - 核准且是「修改單」（ttypeid=2）時，把新的 stime/etime 回寫到原單（orgccid），
        並寫一筆 VOC_closectl_his（utypeid=修改隔離區間=3）

    action.actionid：1=核准（SIGN_ACTION_APPROVE），9=否決（SIGN_ACTION_REJECT）。
    """
    try:
        empid = _get_emp_id(db, current_user_empno)

        # 更新該簽核人的簽核紀錄；rowcount=0 代表這個人不在 fstep=1 的簽核人清單裡
        # （對應舊碼 idpass 檢查），或已經簽過了。
        result = db.execute(
            text(
                "UPDATE [SignFlow].[dbo].[base_flowd] "
                "SET signempid=:empid, signempname=:empname, signtime=:signtime, "
                "signactionid=:actionid, signmemo=:comment "
                "WHERE flowid=:flowid AND fstep=1 AND empid=:empid"
            ),
            {
                "empid": empid,
                "empname": current_user_name,
                "signtime": datetime.now(),
                "actionid": action.actionid,
                "comment": action.comment or "",
                "flowid": action.flowid,
            },
        )
        if result.rowcount == 0:
            raise ValueError("您不具備簽核資格，或此關卡已完成簽核")

        new_status = resolve_new_status(action.actionid)

        # VOC 全部簽核人都在 fstep=1，不存在 fstep>1，流程必然立即結案（對齊 dbSignFlow.Sign() 的 nextfstep<0 分支）
        db.execute(
            text(
                "UPDATE [SignFlow].[dbo].[base_flow] "
                "SET fetime=:fetime, actstep=NULL, fstatusid=:fstatusid WHERE flowid=:flowid"
            ),
            {"fetime": datetime.now(), "fstatusid": int(new_status), "flowid": action.flowid},
        )

        # 回寫 VOC 主表狀態
        control_record = db.query(VocCloseCtl).filter(VocCloseCtl.ccid == action.ccid).first()
        if not control_record:
            raise ValueError("找不到該申請單")
        before_status = control_record.fstatusid
        control_record.fstatusid = int(new_status)

        # 核准的「修改單」（ttypeid=2）回寫 orgccid 到原單
        if new_status == FlowStatus.核准 and control_record.ttypeid == int(Ttype.修改隔離區間) and control_record.orgccid:
            org = db.query(VocCloseCtl).filter(VocCloseCtl.ccid == control_record.orgccid).first()
            if org:
                org.stime = control_record.stime
                org.etime = control_record.etime
                insert_closectl_his(db, action.ccid, Utype.修改隔離區間, current_user_empno, current_user_name)

        db.add(VocTranlog(
            empno=current_user_empno,
            logtype="U",
            databefore=str(before_status),
            dataafter=f"簽核動作: {'核准' if new_status == FlowStatus.核准 else '否決'} / 意見: {action.comment}",
            cdatetime=datetime.now(),
            remark="",
        ))
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        raise e
