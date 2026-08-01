"""
services_b/control_service.py — Schema B（PostgreSQL）廠區隔離申請資料層

對應舊系統 dbVOC.cs「新增隔離廠區項目清單」region，與既有 services/control_service.py
（MSSQL A 棧）語意 1:1，差別只有資料形狀：
  - A 棧：VOC_closectl / VOC_closectl_list / VOC_closectl_his（逐欄複製 his）
  - B 棧：models_b.Isolation / IsolationItem / IsolationHistory（his 改存 jsonb 整單快照，
    對應 docs/schema_B_設計提案.md C 項決策）

★ C 決策核心（is_item_isolated）：隔離「不竄改讀值」，維護狀態改由本表有效區間
  （fstatus=核准 且 stime<=at<=etime）即時 JOIN 推導，供派報/儀表板判定 maintenance，
  絕不回寫 reading_current/reading_history 任何欄位。

★ 純邏輯（next_ccno、FlowStatus/Ttype/Utype enum、build_rtype_list）一律 import 既有
  services/control_service.py、services/flow_service.py 重用，本檔不重複定義。
★ 時間驗證（1 小時上限、ControlTime 只能延長不能縮短）一律 import 既有
  schemas/control_schema.py 的 pydantic 驗證器（ControlCreate/ControlModify/ControlTimeUpdate），
  B 棧不重寫這套規則。
★ 引擎可攜規範：全部用 SQLAlchemy 2.0 select()/ORM 物件操作，禁用 raw text()。

⚠️ 與 A 棧的刻意差異（見任務回報「行為差異點」）：
  update_isolation_time（ControlTime）在 A 棧會連帶 UPDATE VOC_closectl_his 裡同 ccno 的
  所有歷程列的 etime；B 棧的 isolation_history 是 append-only 的 jsonb 快照設計
  （C 決策精神：歷史不可事後竄改，狀態異動另開新記錄），因此 B 棧刻意不回改舊快照，
  只更新 isolation.etime 本體並寫一筆 tranlog，語意仍是「修改隔離時間」，只是不重寫舊歷史快照。
"""

import logging
from datetime import datetime, timezone
from typing import Callable, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from models_b import (
    Isolation, IsolationItem, IsolationHistory, SystemConfig, Tranlog, Plant, AclUserRole, Item,
)
from schemas.control_schema import ControlCreate, ControlModify, ControlTimeUpdate
from services.control_service import next_ccno, RIGHTSID_CONTROL_TIME  # noqa: F401（供呼叫端引用）
from services.flow_service import FlowStatus, Ttype, Utype, build_rtype_list
from services_b.flow_service import create_sign_flow

logger = logging.getLogger(__name__)


# ── 系統設定 ──────────────────────────────────────────────────────────────────

def _get_control_time_max_hours(db: Session) -> Optional[float]:
    """
    讀 system_config['control_time_max_hours']，做為 ControlTime（隔離時間修改）例外通道的
    隔離總時長上限（小時）。

    仿 services_b/sync_service.py._get_config_int() 的風格，差別是這裡「找不到/格式錯誤/
    非正數」一律視為「無上限」（回傳 None），而不是回傳某個數字預設值——這是刻意設計：
    C5 只是「加開關」，不是「加限制」，維持本例外通道原本不受 1 小時上限限制的行為，
    直到有人主動在 system_config 設定正數才生效。
    """
    row = db.execute(
        select(SystemConfig.value).where(SystemConfig.key == "control_time_max_hours")
    ).scalar_one_or_none()
    if row is None:
        return None
    try:
        hours = float(row)
    except (TypeError, ValueError):
        logger.warning("system_config[control_time_max_hours]=%r 無法轉為數字，視為無上限", row)
        return None
    if hours <= 0:
        return None
    return hours


# ── 項目類型對照（D7：簽核 rtype 改讀 item.category，取代項目名稱字串比對）──────────

def _get_item_categories(db: Session, item_names: List[str]) -> dict:
    """
    查 item.category，組成 build_rtype_list(categories=...) 需要的 {項目名稱: 類型} 對照表。

    D7（2026-08-01）：簽核人是靠 rpttype「水保養中／空保養中」找的，舊做法用
    `"VOC" in item` 猜類型，新廠若有不叫 VOC 的空汙項目會找錯簽核人。改讀 item.category。

    key 同時涵蓋 item.item（資料鍵，isolation_item.item 存的就是這個）與 item.display_name
    （顯示名，pH1→pH；呼叫端若傳的是顯示名也對得上），避免兩種命名對不上而漏查。
    category 為 NULL 的項目**不放進 dict**，讓 build_rtype_list 自動退回名稱字串比對
    （未回填 category 的舊資料行為不變）。
    """
    if not item_names:
        return {}
    names = list({n for n in item_names if n})
    rows = db.execute(
        select(Item.item, Item.display_name, Item.category).where(
            (Item.item.in_(names)) | (Item.display_name.in_(names))
        )
    ).all()
    categories: dict = {}
    for item_key, display_name, category in rows:
        if category is None:
            continue
        categories[item_key] = category
        if display_name:
            categories.setdefault(display_name, category)
    return categories


# ── ccno 流水號（DB 查詢，純邏輯沿用 services.control_service.next_ccno）───────────

def _get_last_ccno_today(db: Session, today: str) -> Optional[str]:
    """對應 A 棧 _get_last_ccno_today()：查當日 isolation 表已存在的最大 ccno。"""
    stmt = (
        select(Isolation.ccno)
        .where(Isolation.ccno.like(f"{today}%"))
        .order_by(Isolation.ccno.desc())
        .limit(1)
    )
    row = db.execute(stmt).first()
    return row[0] if row else None


# ── 隔離單快照（供 isolation_history.snapshot jsonb 使用）──────────────────────

def _snapshot_isolation(db: Session, iso: Isolation) -> dict:
    """
    組出整單快照 dict（H 項精神：取代 A 棧逐欄複製到 his 表）。
    含主檔欄位 + 明細項目清單，供稽核回溯「這個時間點這張單長什麼樣子」。
    """
    items = db.execute(
        select(IsolationItem).where(IsolationItem.isolation_id == iso.id)
    ).scalars().all()
    return {
        "id": iso.id,
        "ccno": iso.ccno,
        "ttype": iso.ttype,
        "org_id": iso.org_id,
        "plant_id": iso.plant_id,
        "mdfdesc": iso.mdfdesc,
        "remark": iso.remark,
        "stime": iso.stime.isoformat() if iso.stime else None,
        "etime": iso.etime.isoformat() if iso.etime else None,
        "cemp_no": iso.cemp_no,
        "cemp_name": iso.cemp_name,
        "flow_id": iso.flow_id,
        "fstatus": iso.fstatus,
        "deleted": iso.deleted,
        "items": [
            {"plant_no": it.plant_no, "item": it.item, "source_id": it.source_id}
            for it in items
        ],
    }


def _insert_isolation_history(db: Session, iso: Isolation, utype: Utype, empno: str, name: str) -> None:
    """
    對應 A 棧 insert_closectl_his()：寫一筆歷程快照（utype：1新增/2送簽/3修改）。
    B 棧改存整單 jsonb 快照（snapshot），取代逐欄複製。
    """
    db.add(
        IsolationHistory(
            isolation_id=iso.id,
            utype=int(utype),
            snapshot=_snapshot_isolation(db, iso),
            uclerk_no=empno,
            uclerk_name=name,
        )
    )
    db.flush()


# ── 重複申請防呆 ──────────────────────────────────────────────────────────────

def _has_overlapping_isolation(
    db: Session, plant_no: str, item: str, source_id: int, stime: datetime, etime: datetime
) -> bool:
    """
    對應 A 棧 create_control() 內的重疊檢查：同 (plant_no, item, source_id) 時間區間重疊即視為重複。

    ⚠️ 與舊系統的差異（與 A 棧一致的既有落差，非本次新增）：legacy 是用 stime/etime「完全相等」
    才視為重複，這裡採較嚴格的「時間區間重疊」判斷，語意差異待業務確認
    （見 docs/legacy_source_analysis.md 落差清單 #8 / CLAUDE.md 已知待辦 #4）。
    """
    stmt = (
        select(Isolation.id)
        .join(IsolationItem, IsolationItem.isolation_id == Isolation.id)
        .where(
            Isolation.stime <= etime,
            Isolation.etime >= stime,
            IsolationItem.plant_no == plant_no,
            IsolationItem.item == item,
            IsolationItem.source_id == source_id,
        )
        .limit(1)
    )
    return db.execute(stmt).first() is not None


# ── 申請 / 送簽 / 修改單 ──────────────────────────────────────────────────────

def create_isolation(
    db: Session,
    current_user_empno: str,
    current_user_name: str,
    data: ControlCreate,
    is_commit: bool = True,
    notify_callback: Optional[Callable[..., None]] = None,
) -> Isolation:
    """
    對應 A 棧 create_control()：新增隔離申請單。data 沿用既有 schemas.control_schema.ControlCreate
    （1 小時上限、開始/結束時間順序等驗證已在 pydantic 建構當下做完，本函式不重複驗證）。

    一律走簽核（免簽核 b_pass 分支舊系統已停用，不移植，與 A 棧一致）：
      - 暫存（is_commit=False）：fstatus=待簽核(0)
      - 送簽（is_commit=True）：建立簽核流程後 fstatus=簽核中(1)

    :param notify_callback: 送簽通知信 hook（is_commit=True 時才會觸發），語意同 submit_isolation。
    """
    try:
        for itm in data.items:
            if _has_overlapping_isolation(db, itm.plantno, itm.item, int(itm.sourceid), data.stime, data.etime):
                raise ValueError("重覆申請隔離廠區項目!")

        today = datetime.now().strftime("%Y%m%d")
        last_ccno = _get_last_ccno_today(db, today)
        ccno = next_ccno(last_ccno, today)

        new_iso = Isolation(
            ccno=ccno,
            ttype=int(Ttype.新增),
            plant_id=data.plantid,
            mdfdesc=data.mdfdesc,
            remark=data.remark,
            stime=data.stime,
            etime=data.etime,
            cemp_no=current_user_empno,
            cemp_name=current_user_name,
            fstatus=int(FlowStatus.待簽核),
        )
        db.add(new_iso)
        db.flush()  # 取得 new_iso.id

        for itm in data.items:
            db.add(
                IsolationItem(
                    isolation_id=new_iso.id, plant_no=itm.plantno, item=itm.item, source_id=int(itm.sourceid)
                )
            )
        db.flush()

        _insert_isolation_history(db, new_iso, Utype.新增, current_user_empno, current_user_name)

        if is_commit:
            item_names = [itm.item for itm in data.items]
            rtype_list = build_rtype_list(item_names, _get_item_categories(db, item_names))
            # 沿用 A 棧既有行為：plantno 取 items 迴圈最後一筆值（legacy 遺留行為，見 services/control_service.py 註解）
            plantno = data.items[-1].plantno

            def _adapt(fid, plant_no, signer_empnos, flow_id):
                if notify_callback is not None:
                    notify_callback(isolation=new_iso, signer_empnos=signer_empnos, flow_id=flow_id)

            flow_id = create_sign_flow(
                db, plantno, rtype_list, current_user_empno, new_iso.id, notify_callback=_adapt
            )
            new_iso.flow_id = flow_id
            new_iso.fstatus = int(FlowStatus.簽核中)

        db.add(
            Tranlog(
                emp_no=current_user_empno,
                log_type="I",
                data_before={},
                data_after={"ccno": ccno, "item_count": len(data.items)},
                remark=data.remark,
            )
        )
        db.commit()
        return new_iso
    except Exception:
        db.rollback()
        raise


def submit_isolation(
    db: Session,
    isolation_id: int,
    current_user_empno: str,
    current_user_name: str,
    notify_callback: Optional[Callable[..., None]] = None,
) -> bool:
    """
    對應 A 棧 submit_control()：把一筆先前「暫存」（fstatus=待簽核）的隔離申請單正式送出簽核。

    :param notify_callback: 送簽通知信 hook，預設 no-op；成功建立簽核流程後以
        (isolation=<Isolation>, signer_empnos=<List[str]>, flow_id=<int>) 呼叫
        （呼叫端可據此寄信通知簽核人「有單待簽」）。
    """
    try:
        record = db.execute(select(Isolation).where(Isolation.id == isolation_id)).scalar_one_or_none()
        if record is None:
            raise ValueError(f"無此筆資料! isolation_id:{isolation_id}")

        items = db.execute(
            select(IsolationItem).where(IsolationItem.isolation_id == isolation_id)
        ).scalars().all()
        if not items:
            raise ValueError("此隔離申請單尚無項目明細!")

        item_names = [it.item for it in items]
        rtype_list = build_rtype_list(item_names, _get_item_categories(db, item_names))
        plantno = items[-1].plant_no  # 沿用 A 棧既有行為

        def _adapt(fid, plant_no, signer_empnos, flow_id):
            if notify_callback is not None:
                notify_callback(isolation=record, signer_empnos=signer_empnos, flow_id=flow_id)

        flow_id = create_sign_flow(
            db, plantno, rtype_list, current_user_empno, isolation_id, notify_callback=_adapt
        )
        record.flow_id = flow_id
        record.fstatus = int(FlowStatus.簽核中)

        _insert_isolation_history(db, record, Utype.送簽, current_user_empno, current_user_name)

        db.add(
            Tranlog(
                emp_no=current_user_empno,
                log_type="U",
                data_before={"fstatus": int(FlowStatus.待簽核)},
                data_after={"ccno": record.ccno, "action": "送簽"},
                remark="",
            )
        )
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise


def modify_isolation(
    db: Session,
    current_user_empno: str,
    current_user_name: str,
    data: ControlModify,
    is_commit: bool = True,
    notify_callback: Optional[Callable[..., None]] = None,
) -> Isolation:
    """
    對應 A 棧 modify_control()：針對「已核准且仍有效」的隔離單建立一張新的修改單
    （ttype=修改隔離區間(2) + org_id=原單 id），不是原地修改。

    his 寫入沿用 A 棧語意：本函式一律寫 utype=新增(1)；utype=修改隔離區間(3) 是核准後才由
    services_b.flow_service.process_sign 寫入（回寫 org_id 那段），這裡不重複寫。

    :param notify_callback: 送簽通知信 hook（is_commit=True 時才會觸發），語意同 submit_isolation。
    """
    try:
        org = db.execute(select(Isolation).where(Isolation.id == data.orgccid)).scalar_one_or_none()
        if org is None:
            raise ValueError(f"找不到原始隔離申請單! orgccid={data.orgccid}")
        if org.fstatus != int(FlowStatus.核准):
            raise ValueError("原始隔離申請單尚未核准，無法建立修改單!")
        # ⚠️ org.etime 從 DB 讀回一律 tz-aware，須用 tz-aware 的 now() 比較（見本檔頂部說明），
        # 不可直接沿用 pydantic 驗證器內那個 naive datetime.now()（schemas/control_schema.py 不可改）。
        if org.etime is not None and org.etime < datetime.now(timezone.utc):
            raise ValueError("隔離廠區項目區間為過去的資料，已不能再修改，請重新申請!")

        today = datetime.now().strftime("%Y%m%d")
        last_ccno = _get_last_ccno_today(db, today)
        ccno = next_ccno(last_ccno, today)

        new_iso = Isolation(
            ccno=ccno,
            ttype=int(Ttype.修改隔離區間),
            org_id=data.orgccid,
            plant_id=data.plantid,
            mdfdesc=data.mdfdesc,
            remark=data.remark,
            stime=data.stime,
            etime=data.etime,
            cemp_no=current_user_empno,
            cemp_name=current_user_name,
            fstatus=int(FlowStatus.待簽核),
        )
        db.add(new_iso)
        db.flush()

        for itm in data.items:
            db.add(
                IsolationItem(
                    isolation_id=new_iso.id, plant_no=itm.plantno, item=itm.item, source_id=int(itm.sourceid)
                )
            )
        db.flush()

        _insert_isolation_history(db, new_iso, Utype.新增, current_user_empno, current_user_name)

        if is_commit:
            item_names = [itm.item for itm in data.items]
            rtype_list = build_rtype_list(item_names, _get_item_categories(db, item_names))
            plantno = data.items[-1].plantno

            def _adapt(fid, plant_no, signer_empnos, flow_id):
                if notify_callback is not None:
                    notify_callback(isolation=new_iso, signer_empnos=signer_empnos, flow_id=flow_id)

            flow_id = create_sign_flow(
                db, plantno, rtype_list, current_user_empno, new_iso.id, notify_callback=_adapt
            )
            new_iso.flow_id = flow_id
            new_iso.fstatus = int(FlowStatus.簽核中)

        db.add(
            Tranlog(
                emp_no=current_user_empno,
                log_type="I",
                data_before={"org_id": data.orgccid, "org_ccno": org.ccno},
                data_after={"ccno": ccno, "item_count": len(data.items)},
                remark=data.remark,
            )
        )
        db.commit()
        return new_iso
    except Exception:
        db.rollback()
        raise


def update_isolation_time(db: Session, current_user_empno: str, data: ControlTimeUpdate) -> bool:
    """
    對應 A 棧 update_control_time()（ControlTime.aspx）：直接修改主表 etime，
    不建立/不呼叫任何簽核流程（特定權限者 roleid=12「隔離時間修改」環工部權限的例外通道）。

    只能延長/持平不能縮短已由 schemas.control_schema.ControlTimeUpdate.validate_etime() 在
    pydantic 建構當下驗證完畢，本函式不重複驗證。

    權限檢查（rightsid=RIGHTSID_CONTROL_TIME）由呼叫端負責，本函式不重複檢查。

    ⚠️ 與 A 棧的刻意差異：A 棧會連帶 UPDATE 同 ccno 底下所有歷程列的 etime；
    B 棧 isolation_history 是 append-only 的 jsonb 快照，不回改舊快照（見本檔頂部說明）。

    ★ C5（2026-07-30）：舊系統這條通道刻意不套用一般申請的「隔離總時長 1 小時上限」，
    這裡維持「不走簽核」的既有行為，但把上限改成可由 system_config['control_time_max_hours']
    設定（見 _get_control_time_max_hours()）。量的是「隔離總時長」= 本次新 etime − 該隔離單的
    stime（與一般申請 ControlCreate/ControlModify 的 1 小時上限同一個量法），未設定/設 0/
    負數/空字串/無法轉數字時一律視為無上限（維持現行行為，不報錯）。
    """
    try:
        record = db.execute(
            select(Isolation).where(Isolation.id == data.ccid, Isolation.ccno == data.ccno)
        ).scalar_one_or_none()
        if record is None:
            raise ValueError(f"找不到隔離申請單! ccno={data.ccno}")

        max_hours = _get_control_time_max_hours(db)
        if max_hours is not None and record.stime is not None:
            new_etime, stime = data.etime, record.stime
            # 兩者 tz-aware 狀態可能不一致（DB 讀回一律 tz-aware，pydantic 輸入未必帶時區），
            # 相減前一律轉成 naive，只取時長差，不受時區標記影響（與 modify_isolation 的
            # tz 處理原則一致，見本檔頂部說明）。
            if new_etime.tzinfo is not None:
                new_etime = new_etime.replace(tzinfo=None)
            if stime.tzinfo is not None:
                stime = stime.replace(tzinfo=None)
            total_hours = (new_etime - stime).total_seconds() / 3600
            if total_hours > max_hours:
                raise ValueError(
                    f"隔離總時長不可超過 {max_hours:g} 小時(目前設定)，本次將達 {total_hours:g} 小時!"
                )

        before_etime = record.etime
        record.etime = data.etime

        before_str = before_etime.strftime("%Y/%m/%d %H:%M:%S") if before_etime else ""
        after_str = data.etime.strftime("%Y/%m/%d %H:%M:%S")
        db.add(
            Tranlog(
                emp_no=current_user_empno,
                log_type="M",
                data_before={"ccno": data.ccno, "etime": before_str},
                data_after={"ccno": data.ccno, "etime": after_str},
                remark=data.remark or "",
            )
        )
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise


# ── 查詢 ──────────────────────────────────────────────────────────────────────

def get_active_isolations(db: Session) -> List[dict]:
    """
    對應 A 棧 get_active_isolations()：目前時間點仍在有效期內的隔離記錄（fstatus=核准(7)）。
    """
    now = datetime.now(timezone.utc)
    stmt = (
        select(Isolation, Plant.plant_no)
        .join(Plant, Plant.plant_id == Isolation.plant_id)
        .where(
            Isolation.fstatus == int(FlowStatus.核准),
            Isolation.stime <= now,
            Isolation.etime >= now,
            Isolation.deleted == False,  # noqa: E712
        )
        .order_by(Isolation.stime)
    )
    rows = db.execute(stmt).all()
    return [
        {
            "id": iso.id,
            "ccno": iso.ccno,
            "plant_id": iso.plant_id,
            "plant_no": plant_no,
            "empstr": f"{iso.cemp_no}-{iso.cemp_name or ''}",
            "mdfdesc": iso.mdfdesc,
            "stime": iso.stime,
            "etime": iso.etime,
            "remark": iso.remark,
        }
        for iso, plant_no in rows
    ]


def get_my_applies(
    db: Session,
    cemp_no: str,
    plant_id: int = -1,
    fstatus: int = -1,
    isolation_id: int = -1,
) -> List[dict]:
    """
    對應 A 棧 get_my_applies()：查詢「我的申請單」，B 棧版本。

    與 A 棧一致的落差修正（見 docs/legacy_source_analysis.md 落差清單 #6）：
      - fstatus=-1（全部）時排除否決(8) 的紀錄，用 FlowStatus enum 比對，禁止寫死數字。
      - 額外納入自己有 ACL 廠區權限（acl_user_role.plant_no = 該廠區 或 'ALL'）的廠區單據
        （不會反而濾掉自己的申請），語意與 A 棧一致：⚠️ 這是「我的申請單」與「廠區的申請單」
        合併簡化，實際業務規則待確認。
    """
    stmt = select(Isolation, Plant.plant_no).join(Plant, Plant.plant_id == Isolation.plant_id)

    if plant_id != -1:
        stmt = stmt.where(Isolation.plant_id == plant_id)

    if fstatus != -1:
        stmt = stmt.where(Isolation.fstatus == fstatus)
    else:
        stmt = stmt.where(Isolation.fstatus != int(FlowStatus.否決))

    if isolation_id != -1:
        stmt = stmt.where(Isolation.id == isolation_id)
    else:
        acl_plant_nos = db.execute(
            select(AclUserRole.plant_no).where(AclUserRole.emp_no == cemp_no)
        ).scalars().all()
        acl_plant_nos_set = set(acl_plant_nos)
        if acl_plant_nos_set:
            if "ALL" in acl_plant_nos_set:
                pass  # 具備全廠區權限，不額外過濾（等同 A 棧 plantno='ALL' 語意）
            else:
                stmt = stmt.where(
                    (Isolation.cemp_no == cemp_no) | (Plant.plant_no.in_(acl_plant_nos_set))
                )
        else:
            stmt = stmt.where(Isolation.cemp_no == cemp_no)

    stmt = stmt.order_by(Isolation.created_at.desc())
    rows = db.execute(stmt).all()
    return [
        {
            "id": iso.id,
            "ccno": iso.ccno,
            "flow_id": iso.flow_id,
            "ttype": iso.ttype,
            "plant_no": plant_no,
            "empstr": f"{iso.cemp_no}-{iso.cemp_name or ''}",
            "mdfdesc": iso.mdfdesc,
            "stime": iso.stime,
            "etime": iso.etime,
            "fstatus": iso.fstatus,
            "created_at": iso.created_at,
        }
        for iso, plant_no in rows
    ]


def is_item_isolated(db: Session, plant_no: str, item: str, at_time: Optional[datetime] = None) -> bool:
    """
    ★ C 決策核心：判斷某廠區/項目在指定時間點是否處於「隔離中」。

    隔離狀態由 isolation/isolation_item 的有效區間 JOIN 推導（fstatus=核准(7) 且
    stime<=at<=etime 且未刪除），供派報/儀表板判定 maintenance 使用。

    ⚠️ 絕不回寫 reading_current/reading_history 任何欄位——這是 C 決策與 A 棧最大的行為差異：
    A 棧（舊系統/legacy）核准後會把 VOC_SCADA_WEB/VOC_SCADA_HIST 的讀值+管制值 UPDATE 成
    「保養中」，B 棧改為本函式即時推導，讀值照實寫入不動。

    :param at_time: 判斷的時間點，預設現在（timezone-aware）。
    """
    if at_time is None:
        at_time = datetime.now(timezone.utc)

    stmt = (
        select(Isolation.id)
        .join(IsolationItem, IsolationItem.isolation_id == Isolation.id)
        .where(
            Isolation.fstatus == int(FlowStatus.核准),
            Isolation.deleted == False,  # noqa: E712
            Isolation.stime <= at_time,
            Isolation.etime >= at_time,
            IsolationItem.plant_no == plant_no,
            IsolationItem.item == item,
        )
        .limit(1)
    )
    return db.execute(stmt).first() is not None
