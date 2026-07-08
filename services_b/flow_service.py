"""
services_b/flow_service.py — Schema B（PostgreSQL）簽核流程資料層

對應舊系統 MTFlowBase.cs / dbSignFlow.cs「一階群組簽核」多載（VOC 平台專用，不牽涉多級主管爬升），
與既有 services/flow_service.py（MSSQL A 棧，串公司 SignFlow..base_flow/base_flowd）語意 1:1，
差別只有資料形狀（B 棧用 models_b.SignFlow/SignFlowStep/SignEmp 內表，A 棧用跨庫 SignFlow..base_*）：

  1. get_signers()：mail_list 裡 sign_grp=1、同廠區、rpttype 符合、排除申請人自己、
     排除離職員工（employee.is_leave）的名單，即為這關的簽核人。
  2. create_sign_flow()：全部簽核人都插在同一個 fstep=1（不分層級），sign_flow.fstatus 初始為「簽核中」。
  3. process_sign()：任一位簽核人核准/否決，流程立即結案（OR 邏輯，非全員會簽）。

★ 純邏輯（FlowStatus/Ttype/Utype enum、build_rtype_list、resolve_new_status 等）一律
  import 既有 services/flow_service.py 重用，本檔不重複定義，確保兩棧數值永遠一致。
★ 引擎可攜規範：全部用 SQLAlchemy 2.0 select()/ORM 物件操作，禁用 raw text()。

未移植（與 A 棧相同的刻意留白）：
  - flowurl（來自 base_flowrule）、show_info 實際填值：本階段不需要，欄位保留但不主動寫入。
  - Email 簽核通知：屬於 notify_service（WP5）範圍，這裡用 notify_callback 參數留 hook，
    預設 no-op，實際寄信邏輯由呼叫端注入。
"""

import logging
from datetime import datetime, timezone
from typing import Callable, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from models_b import Isolation, SignEmp, SignFlow, SignFlowStep, MailList, Employee, Tranlog
from services.flow_service import (
    FlowStatus,
    Ttype,
    Utype,
    SIGN_ACTION_APPROVE,
    SIGN_ACTION_REJECT,
    REVIEWER_TYPE_PERSON,
    FRULEID_ISOLATION,
    build_rtype_list,
    resolve_new_status,
)

logger = logging.getLogger(__name__)


def _noop_notify(**kwargs) -> None:
    """簽核通知信預設 no-op callback；實際寄信函式由 WP5 的 notify_service 注入。"""
    return None


# ── DB 存取：簽核人查詢 ──────────────────────────────────────────────────────

def get_signers(db: Session, plant_no: str, rtype_list: List[str], empno: str) -> List[str]:
    """
    對應 dbSignFlow.Get簽核人員(plantno, rtype, empno) 的 B 棧版本：

        SELECT DISTINCT M.emp_no
        FROM mail_list M
        JOIN employee E ON M.emp_no = E.emp_no AND E.is_leave = false
        WHERE M.plant_no = :plant_no AND M.rpttype IN :rtypes
          AND M.emp_no != :empno AND M.sign_grp = true

    A 棧版本用 SQL Server expanding bindparam 做 IN 子句參數化；B 棧改用 SQLAlchemy 2.0
    select().where(MailList.rpttype.in_(rtype_list)) 表達式，語意相同、無 raw SQL。
    """
    if not rtype_list:
        return []
    stmt = (
        select(MailList.emp_no)
        .join(Employee, (Employee.emp_no == MailList.emp_no) & (Employee.is_leave == False))  # noqa: E712
        .where(
            MailList.plant_no == plant_no,
            MailList.rpttype.in_(rtype_list),
            MailList.emp_no != empno,
            MailList.sign_grp == True,  # noqa: E712
        )
        .distinct()
    )
    rows = db.execute(stmt).scalars().all()
    return list(rows)


def _get_sign_emp(db: Session, empno: str) -> SignEmp:
    """
    查 sign_emp（B 棧 SignFlow 同構表版本，對應 A 棧 dbSignFlow.Get員工id() 查 SignFlow..base_emp）。

    ⚠️ 與 A 棧相同的已知限制：查不到資料時不自動補建（A 棧原本會即時呼叫 AD/LDAP 補建，
    本專案 AD/LDAP 整合延後到 Phase 3，見 HANDOVER.md），查無資料直接 raise。
    """
    emp = db.execute(select(SignEmp).where(SignEmp.emp_no == empno)).scalar_one_or_none()
    if emp is None:
        raise ValueError(
            f"員工 {empno} 尚無簽核系統基本資料（sign_emp），"
            "需先透過 AD/LDAP 整合建檔（Phase 3 待實作，見 HANDOVER.md）"
        )
    return emp


# ── 建立簽核流程 ──────────────────────────────────────────────────────────────

def create_sign_flow(
    db: Session,
    plant_no: str,
    rtype_list: List[str],
    empno: str,
    fid: int,
    notify_callback: Optional[Callable[..., None]] = None,
) -> int:
    """
    對應 dbSignFlow.CreateNewFlow(fruleid, fid, empno, plantno, rtype, hashkey, showinfo) 的
    「一階群組簽核」多載，B 棧版本：

      1. 找簽核人（get_signers）
      2. INSERT sign_flow（fstatus=簽核中(1)，act_step=1）
      3. 每個簽核人都 INSERT sign_flow_step，統一 fstep=1

    找不到任何簽核人時直接 raise——與 A 棧一致的刻意防呆改良（A 棧沿用舊系統會建立一個
    沒人能簽的流程，這裡提前擋下）。

    :param fid: 對應本張隔離單的 isolation.id（B 棧欄位名稱換了，語意同 A 棧的 ccid）。
    :param notify_callback: 送簽通知信 hook，預設 no-op；對應舊系統 Proc送簽() 建立 flow 後立刻呼叫
        SendMail通知(isFinished=false)——送簽當下就主動通知簽核人「有單待簽」，與 process_sign()
        的「簽核結果」通知信是兩個不同時間點的呼叫。成功建立 flow 後以
        (fid=<int>, plant_no=<str>, signer_empnos=<List[str]>, flow_id=<int>) 呼叫。
    """
    notify_callback = notify_callback or _noop_notify

    signer_empnos = get_signers(db, plant_no, rtype_list, empno)
    if not signer_empnos:
        raise ValueError(f"廠區 {plant_no} 尚未設定簽核人員（mail_list.sign_grp=true），無法送簽")

    applicant = _get_sign_emp(db, empno)

    flow = SignFlow(
        frule_id=FRULEID_ISOLATION,
        act_step=1,
        fstatus=int(FlowStatus.簽核中),
        fid=fid,
        emp_id=applicant.emp_id,
        fstime=datetime.now(timezone.utc),
    )
    db.add(flow)
    db.flush()  # 取得 flow.flow_id

    for signer_empno in signer_empnos:
        signer = _get_sign_emp(db, signer_empno)
        db.add(
            SignFlowStep(
                flow_id=flow.flow_id,
                fstep=1,
                ftype=REVIEWER_TYPE_PERSON,
                emp_id=signer.emp_id,
                pos_id=signer.pos_id,
            )
        )
    db.flush()
    notify_callback(fid=fid, plant_no=plant_no, signer_empnos=signer_empnos, flow_id=flow.flow_id)

    return flow.flow_id


# ── 待辦清單 ──────────────────────────────────────────────────────────────────

def get_todo_list(db: Session, empno: str) -> List[Isolation]:
    """
    對應 A 棧 get_todo_applies()：查詢目前輪到某工號簽核、且尚未簽核的隔離申請單。

    VOC 一律「一階群組簽核」（全部簽核人都在 fstep=1，任一人簽即結案），因此待辦條件為：
      - sign_flow.fstatus = 簽核中(1)
      - sign_flow_step.fstep = 1 且 emp_id = 該工號對應的 sign_emp.emp_id
      - sign_flow_step.sign_action IS NULL（自己尚未簽過）
      - isolation.flow_id = sign_flow.flow_id（找出對應的隔離單）

    查無此工號的 sign_emp 資料（例如工號打錯或尚未建檔）時回傳空清單，不 raise
    （待辦清單語意上「找不到人」等同「沒有待辦」，不是錯誤）。
    """
    emp = db.execute(select(SignEmp).where(SignEmp.emp_no == empno)).scalar_one_or_none()
    if emp is None:
        return []

    stmt = (
        select(Isolation)
        .join(SignFlow, SignFlow.flow_id == Isolation.flow_id)
        .join(
            SignFlowStep,
            (SignFlowStep.flow_id == SignFlow.flow_id) & (SignFlowStep.fstep == 1),
        )
        .where(
            SignFlow.fstatus == int(FlowStatus.簽核中),
            SignFlowStep.emp_id == emp.emp_id,
            SignFlowStep.sign_action.is_(None),
        )
        .order_by(Isolation.created_at.desc())
    )
    return list(db.execute(stmt).scalars().all())


# ── 簽核動作 ──────────────────────────────────────────────────────────────────

def process_sign(
    db: Session,
    isolation_id: int,
    flow_id: int,
    action_id: int,
    current_user_empno: str,
    current_user_name: str,
    comment: str = "",
    notify_callback: Optional[Callable[..., None]] = None,
) -> bool:
    """
    對應 dbSignFlow.Sign() + dbVOC.ProcSign()：VOC 平台的「一階群組簽核」，B 棧版本。

    VOC 只有 fstep=1 一關，任一位簽核人核准/否決，流程立即結案（OR 邏輯，非全員會簽）：
      - 更新該簽核人在 sign_flow_step 的簽核紀錄
      - sign_flow.fstatus 依動作改成 核准(7)/否決(8)
      - 同步回寫 isolation.fstatus
      - 核准且是「修改單」（ttype=2）時，把新的 stime/etime 回寫到原單（org_id），
        並寫一筆 isolation_history（utype=修改隔離區間=3），語意與 A 棧 process_sign 一致：
        this history 是掛在「修改單自己（isolation_id）」身上，不是掛在被回寫的原單。

    :param action_id: SIGN_ACTION_APPROVE(1) / SIGN_ACTION_REJECT(9)（services.flow_service 常數）。
    :param notify_callback: 簽核結果通知信 hook，預設 no-op；WP5 的 notify_service 可注入實際寄信函式，
        簽核成功後以 (isolation=<Isolation>, new_status=<FlowStatus>, action_id=<int>) 呼叫。
    """
    # 延後 import，避免 control_service ↔ flow_service 循環 import
    from services_b.control_service import _insert_isolation_history

    notify_callback = notify_callback or _noop_notify

    try:
        signer = _get_sign_emp(db, current_user_empno)

        # 更新該簽核人的簽核紀錄；找不到代表這個人不在 fstep=1 的簽核人清單裡，
        # 或已經簽過了（sign_action 已非 None，下方 WHERE 條件就篩不到）。
        step = db.execute(
            select(SignFlowStep).where(
                SignFlowStep.flow_id == flow_id,
                SignFlowStep.fstep == 1,
                SignFlowStep.emp_id == signer.emp_id,
            )
        ).scalar_one_or_none()
        if step is None:
            raise ValueError("您不具備簽核資格，或此關卡已完成簽核")
        if step.sign_action is not None:
            raise ValueError("您不具備簽核資格，或此關卡已完成簽核")

        step.sign_emp_id = signer.emp_id
        step.sign_emp_name = current_user_name
        step.sign_time = datetime.now(timezone.utc)
        step.sign_action = action_id
        step.sign_memo = comment or ""

        new_status = resolve_new_status(action_id)

        # VOC 全部簽核人都在 fstep=1，不存在 fstep>1，流程必然立即結案
        flow = db.execute(select(SignFlow).where(SignFlow.flow_id == flow_id)).scalar_one_or_none()
        if flow is None:
            raise ValueError("找不到該簽核流程")
        flow.fetime = datetime.now(timezone.utc)
        flow.act_step = None
        flow.fstatus = int(new_status)

        # 回寫隔離單狀態
        record = db.execute(select(Isolation).where(Isolation.id == isolation_id)).scalar_one_or_none()
        if record is None:
            raise ValueError("找不到該申請單")
        record.fstatus = int(new_status)

        # 核准的「修改單」（ttype=2）回寫 org_id 到原單
        if new_status == FlowStatus.核准 and record.ttype == int(Ttype.修改隔離區間) and record.org_id:
            org = db.execute(select(Isolation).where(Isolation.id == record.org_id)).scalar_one_or_none()
            if org is not None:
                org.stime = record.stime
                org.etime = record.etime
                _insert_isolation_history(db, record, Utype.修改隔離區間, current_user_empno, current_user_name)

        db.add(Tranlog(
            emp_no=current_user_empno, log_type="U",
            data_before={"fstatus": int(FlowStatus.簽核中)},
            data_after={"action": "核准" if new_status == FlowStatus.核准 else "否決", "comment": comment or "", "isolation_id": isolation_id},
            remark="",
        ))

        db.flush()
        notify_callback(isolation=record, new_status=new_status, action_id=action_id)

        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
