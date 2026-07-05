"""
models_b.py — Schema B（Phase A 重構版）全部資料表的 SQLAlchemy ORM 模型

依據：docs/schema_B_設計提案.md（v2，DDL 語意規格＋決策紀錄）
      docs/PhaseA執行規格書.md（第四節：tag_mapping 新表 + kepware_sim 模擬 A 端表）

★ 引擎可攜規範（schema_B_設計提案.md 第五節，強制條款，本檔案嚴格遵守）：
  1. 全部使用 SQLAlchemy 2.0 宣告式（DeclarativeBase + Mapped/mapped_column）。
  2. 型別一律用 SQLAlchemy 泛型：JSON（不是 PG 專屬 JSONB）、DateTime(timezone=True)、
     Numeric、Boolean、BigInteger + Identity()（不是手寫 bigserial）。
  3. 禁止任何單邊方言語法（PG 的 ON CONFLICT/DISTINCT ON、MSSQL 的 IIF/TOP 等）。
  4. 所有 CHECK 約束一律用 SQLAlchemy CheckConstraint 表達，不寫方言 DDL。
  5. 建表只透過 database_b.py 的 create_all_b()（呼叫 Base.metadata.create_all()），
     本檔案不含任何 raw SQL / CREATE TABLE 字串。

命名對照：本檔案的 class 名稱、欄位名稱 1:1 對應 docs/schema_B_設計提案.md 第二節 DDL 草案的
表名/欄名（皆為 snake_case），可直接對照該文件閱讀。若與草案有出入，會在對應欄位加註解說明原因。
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Identity,
    Index,
    Integer,
    JSON,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class BaseB(DeclarativeBase):
    """Schema B 所有 ORM 模型共用的宣告式基底類別（與既有 MSSQL 版 database.py 的 Base 分開，
    避免兩套 metadata 互相干擾——B 棧 create_all 時不會誤建 A 棧的表，反之亦然）。"""
    pass


# ============================================================
# 主檔：plant / item / source
# ============================================================

class Plant(BaseB):
    """plant — 廠區主檔（對應舊 VOC_plant）。

    G 項決策：plantid=29=ALL、'GMO'/'環工部' 等虛擬列，改用 kind 欄位明確表達語意，
    不再讓程式硬編 plantid==29 這種魔法值判斷。
    """
    __tablename__ = "plant"

    plant_id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)  # 沿用舊 plantid 值
    plant_no: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)  # 'K7'
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="normal")
    is_show: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        CheckConstraint("kind IN ('normal','virtual_group','all')", name="ck_plant_kind"),
    )


class Item(BaseB):
    """item — 量測項目主檔（對應舊 VOC_item）。

    G 項決策：display_name 吸收舊程式硬編的 pH1→pH、COD2→COD 等別名對照表。
    """
    __tablename__ = "item"

    item_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)  # 'pH1'（原名，資料鍵）
    display_name: Mapped[Optional[str]] = mapped_column(String(50))  # 'pH'
    unit: Mapped[Optional[str]] = mapped_column(String(50))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Source(BaseB):
    """source — 資料來源對照表（對應舊 VOC_source）：1=SCADA 2=CWMS 3=QA。"""
    __tablename__ = "source"

    source_id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)


# ============================================================
# 規格（B 項：門檻字串拆數值欄）
# ============================================================

class Spec(BaseB):
    """spec — 規格值主檔（對應舊 VOC_SPEC）。

    B 項決策：LAW/OOS/OOC/Alert/允收值原本是 varchar（雙邊規格存 '6-9'、無效值存 '-'/'建置中'），
    改拆 low/high numeric + status（valid/na/building）。law_text 因僅顯示用途，保留文字欄位。
    """
    __tablename__ = "spec"

    plant_no: Mapped[str] = mapped_column(String(50), ForeignKey("plant.plant_no"), primary_key=True)
    item: Mapped[str] = mapped_column(String(50), ForeignKey("item.item"), primary_key=True)

    law_text: Mapped[Optional[str]] = mapped_column(Text)

    oos_low: Mapped[Optional[Decimal]] = mapped_column(Numeric)
    oos_high: Mapped[Optional[Decimal]] = mapped_column(Numeric)
    oos_status: Mapped[Optional[str]] = mapped_column(String(20))

    ooc_low: Mapped[Optional[Decimal]] = mapped_column(Numeric)
    ooc_high: Mapped[Optional[Decimal]] = mapped_column(Numeric)
    ooc_status: Mapped[Optional[str]] = mapped_column(String(20))

    alert_low: Mapped[Optional[Decimal]] = mapped_column(Numeric)
    alert_high: Mapped[Optional[Decimal]] = mapped_column(Numeric)
    alert_status: Mapped[Optional[str]] = mapped_column(String(20))

    recv_low: Mapped[Optional[Decimal]] = mapped_column(Numeric)  # 允收值
    recv_high: Mapped[Optional[Decimal]] = mapped_column(Numeric)
    recv_status: Mapped[Optional[str]] = mapped_column(String(20))

    source_id: Mapped[int] = mapped_column(SmallInteger, ForeignKey("source.source_id"), nullable=False)
    tagname: Mapped[Optional[str]] = mapped_column(String(100))
    seqno: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# ============================================================
# 讀值（A 項：value+status 拆欄；C 項：隔離不再覆寫，改由 isolation 區間 JOIN 推導）
# ============================================================

class ReadingCurrent(BaseB):
    """reading_current — 目前讀值（對應舊 VOC_SCADA_WEB，同一 plant_no+item 只留最新一筆）。

    C 項決策：隔離中不再把這裡的讀值/管制值竄改成「保養中」；保養狀態改由 isolation 表的
    有效區間即時 JOIN 推導，本表照實寫入 SCADA 實際讀值。
    comm_ok 對應舊 broken=1（斷訊，JOB 專寫）；隔離的 broken=2（保養中）不再落地於此表。
    """
    __tablename__ = "reading_current"

    plant_no: Mapped[str] = mapped_column(String(50), primary_key=True)
    item: Mapped[str] = mapped_column(String(50), primary_key=True)

    value: Mapped[Optional[Decimal]] = mapped_column(Numeric)  # N.D→NULL、<0.05→0.05
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="normal")
    raw_text: Mapped[Optional[str]] = mapped_column(Text)  # 原始字串備查
    comm_ok: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # SCADA 自設管制值（隔離不再覆寫）
    scada_oos_low: Mapped[Optional[Decimal]] = mapped_column(Numeric)
    scada_oos_high: Mapped[Optional[Decimal]] = mapped_column(Numeric)
    scada_ooc_low: Mapped[Optional[Decimal]] = mapped_column(Numeric)
    scada_ooc_high: Mapped[Optional[Decimal]] = mapped_column(Numeric)
    scada_alert_low: Mapped[Optional[Decimal]] = mapped_column(Numeric)
    scada_alert_high: Mapped[Optional[Decimal]] = mapped_column(Numeric)
    scada_limit_status: Mapped[Optional[str]] = mapped_column(String(20))

    # CWMS 管制值
    cwms_oos_low: Mapped[Optional[Decimal]] = mapped_column(Numeric)
    cwms_oos_high: Mapped[Optional[Decimal]] = mapped_column(Numeric)
    cwms_ooc_low: Mapped[Optional[Decimal]] = mapped_column(Numeric)
    cwms_ooc_high: Mapped[Optional[Decimal]] = mapped_column(Numeric)
    cwms_limit_status: Mapped[Optional[str]] = mapped_column(String(20))

    rain_24h: Mapped[Optional[Decimal]] = mapped_column(Numeric)  # J 項：轉拋 JOB 寫入，取代 PMS 跨庫 JOIN

    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        ForeignKeyConstraint(["plant_no", "item"], ["spec.plant_no", "spec.item"]),
        CheckConstraint(
            "status IN ('normal','nd','below_lod','broken','maintenance','building','error')",
            name="ck_reading_current_status",
        ),
    )


class ReadingHistory(BaseB):
    """reading_history — 讀值歷史（對應舊 VOC_SCADA_HIST），append-only，永不 UPDATE。

    ★稽核決策（2026-07-01）：法規稽核需要「當時管制值」逐時證據，每筆讀值快照當下生效的
    SPEC 三階管制值（沿襲舊 VOC_SCADA_HIST 亦存 OOS/OOC/alert1/recv 的做法）。
    SCADA/CWMS 自設管制值快照放 limits_extra（泛型 JSON，引擎可攜，不用 PG 專屬 JSONB）。
    K1/K9 雨水溝三點連升：直接對本表用 window function，不需另存三欄。
    """
    __tablename__ = "reading_history"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    plant_no: Mapped[str] = mapped_column(String(50), nullable=False)
    item: Mapped[str] = mapped_column(String(50), nullable=False)
    value: Mapped[Optional[Decimal]] = mapped_column(Numeric)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    raw_text: Mapped[Optional[str]] = mapped_column(Text)

    spec_oos_low: Mapped[Optional[Decimal]] = mapped_column(Numeric)
    spec_oos_high: Mapped[Optional[Decimal]] = mapped_column(Numeric)
    spec_ooc_low: Mapped[Optional[Decimal]] = mapped_column(Numeric)
    spec_ooc_high: Mapped[Optional[Decimal]] = mapped_column(Numeric)
    spec_alert_low: Mapped[Optional[Decimal]] = mapped_column(Numeric)
    spec_alert_high: Mapped[Optional[Decimal]] = mapped_column(Numeric)
    spec_recv_low: Mapped[Optional[Decimal]] = mapped_column(Numeric)
    spec_recv_high: Mapped[Optional[Decimal]] = mapped_column(Numeric)
    limits_extra: Mapped[Optional[dict]] = mapped_column(JSON)  # SCADA/CWMS 自設管制值快照

    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("plant_no", "item", "measured_at", name="uq_reading_history_pim"),
        Index("idx_rh_lookup", "plant_no", "item", measured_at.desc()),
    )


# ============================================================
# 派報紀錄（D 項：明細正規化，取代 msg1/msg2 字串比對）
# ============================================================

class MailLog(BaseB):
    """mail_log — 派報信件層級紀錄（對應舊 VOC_MAIL_Log，一封信一列）。"""
    __tablename__ = "mail_log"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)  # 取代 logid
    plant_no: Mapped[str] = mapped_column(String(50), nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)  # cdatetime（對齊 5 分）
    subject: Mapped[Optional[str]] = mapped_column(String(200))
    body_note: Mapped[Optional[str]] = mapped_column(Text)  # 原 msg（人讀全文，回覆頁顯示用）
    reply_empno: Mapped[Optional[str]] = mapped_column(String(50))
    reply_reason: Mapped[Optional[str]] = mapped_column(Text)
    reply_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class MailLogItem(BaseB):
    """mail_log_item — 派報明細（原 msg1/msg2 字串正規化，每項目每條件一列）。"""
    __tablename__ = "mail_log_item"

    mail_log_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("mail_log.id"), primary_key=True)
    item: Mapped[str] = mapped_column(String(50), primary_key=True)
    condition_code: Mapped[str] = mapped_column(String(30), primary_key=True)
    # 'OOS'/'OOC'/'ALERT'/'RECV'/'LIMIT_MISMATCH'/'MAINTENANCE'/'BROKEN'
    detail: Mapped[Optional[str]] = mapped_column(Text)
    escalation_stage: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)  # 0/1/2（原 0/15/30 分）
    is_maintenance: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        Index("idx_mli_dedup", "item", "condition_code"),
    )


# ============================================================
# 隔離與簽核
# ============================================================

class Isolation(BaseB):
    """isolation — 隔離申請單主檔（對應舊 VOC_closectl）。

    C 項決策：隔離核准後不再回改 reading_current/reading_history，維護狀態改由本表
    有效區間（stime~etime）即時 JOIN 推導。
    fstatus 沿用 services/flow_service.py 的 FlowStatus IntEnum 數值（0/1/7/8/12），不在此重複定義。
    """
    __tablename__ = "isolation"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)  # 原 ccid
    ccno: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)  # 顯示編號 yyyymmddNNN
    ttype: Mapped[int] = mapped_column(SmallInteger, nullable=False)  # 1新增/2修改
    org_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("isolation.id"))  # 原 orgccid
    plant_id: Mapped[int] = mapped_column(SmallInteger, ForeignKey("plant.plant_id"), nullable=False)
    mdfdesc: Mapped[Optional[str]] = mapped_column(Text)
    remark: Mapped[Optional[str]] = mapped_column(Text)
    stime: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    etime: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cemp_no: Mapped[str] = mapped_column(String(50), nullable=False)
    cemp_name: Mapped[Optional[str]] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    flow_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    fstatus: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    del_clerk: Mapped[Optional[str]] = mapped_column(String(50))

    __table_args__ = (
        CheckConstraint("ttype IN (1,2)", name="ck_isolation_ttype"),
        CheckConstraint("etime > stime", name="ck_isolation_etime_after_stime"),
    )


class IsolationItem(BaseB):
    """isolation_item — 隔離單涵蓋的廠區/項目明細（對應舊 VOC_closectl_list）。"""
    __tablename__ = "isolation_item"

    isolation_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("isolation.id"), primary_key=True)
    plant_no: Mapped[str] = mapped_column(String(50), primary_key=True)
    item: Mapped[str] = mapped_column(String(50), primary_key=True)  # 存原名 pH1/COD2
    source_id: Mapped[int] = mapped_column(SmallInteger, nullable=False)


class IsolationHistory(BaseB):
    """isolation_history — 隔離單異動快照（對應舊 VOC_closectl_his）。

    H 項精神：整單快照存 JSON 取代逐欄複製；utype：1新增/2送簽/3修改。
    """
    __tablename__ = "isolation_history"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    isolation_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("isolation.id"), nullable=False)
    utype: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    uclerk_no: Mapped[Optional[str]] = mapped_column(String(50))
    uclerk_name: Mapped[Optional[str]] = mapped_column(String(100))
    utime: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SpecApply(BaseB):
    """spec_apply — 規格維護申請單（對應舊 VOC_SPEC_apply）。"""
    __tablename__ = "spec_apply"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    formno: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    ftype: Mapped[str] = mapped_column(String(1), nullable=False)  # I新增/M修改/D刪除
    plant_no: Mapped[str] = mapped_column(String(50), nullable=False)
    item: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)  # 申請的規格新值
    emp_no: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    flow_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    fstatus: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)

    __table_args__ = (
        CheckConstraint("ftype IN ('I','M','D')", name="ck_spec_apply_ftype"),
    )


# J 項測試期方案：SignFlow 同構表（欄位語意 1:1，正式去向另議——見 docs/schema_B_設計提案.md 第四節）

class SignEmp(BaseB):
    """sign_emp — 簽核人員快取（對應公司 SignFlow.base_emp，測試期 B 內建同構表）。"""
    __tablename__ = "sign_emp"

    emp_id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    emp_no: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    emp_name: Mapped[Optional[str]] = mapped_column(String(100))
    email: Mapped[Optional[str]] = mapped_column(String(200))
    pos_id: Mapped[Optional[int]] = mapped_column(Integer)
    dep_no: Mapped[Optional[str]] = mapped_column(String(50))


class SignFlow(BaseB):
    """sign_flow — 簽核流程主檔（對應公司 SignFlow.base_flow）。"""
    __tablename__ = "sign_flow"

    flow_id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    frule_id: Mapped[int] = mapped_column(Integer, nullable=False)
    act_step: Mapped[Optional[int]] = mapped_column(Integer)
    fstatus: Mapped[int] = mapped_column(SmallInteger, nullable=False)  # FlowStatus 數值不變（0/1/7/8/12）
    fid: Mapped[Optional[int]] = mapped_column(BigInteger)
    emp_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("sign_emp.emp_id"))
    fstime: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    fetime: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    show_info: Mapped[Optional[str]] = mapped_column(Text)


class SignFlowStep(BaseB):
    """sign_flow_step — 簽核流程節點明細（對應公司 SignFlow.base_flowd）。"""
    __tablename__ = "sign_flow_step"

    flow_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sign_flow.flow_id"), primary_key=True)
    fstep: Mapped[int] = mapped_column(Integer, primary_key=True)
    emp_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ftype: Mapped[Optional[int]] = mapped_column(Integer)
    pos_id: Mapped[Optional[int]] = mapped_column(Integer)
    sign_emp_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    sign_emp_name: Mapped[Optional[str]] = mapped_column(String(100))
    sign_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    sign_action: Mapped[Optional[int]] = mapped_column(SmallInteger)
    sign_memo: Mapped[Optional[str]] = mapped_column(Text)


# ============================================================
# 名單、權限、其他
# ============================================================

class MailList(BaseB):
    """mail_list — 派報名單（對應舊 VOC_Mail_List）。

    F/I 項決策：去掉 SM/cellphone/Mail1/SM1（簡訊停用＋暫停寄信改用 system_config.mail_paused）。
    """
    __tablename__ = "mail_list"

    plant_no: Mapped[str] = mapped_column(String(50), primary_key=True)
    rpttype: Mapped[str] = mapped_column(String(50), primary_key=True)
    emp_no: Mapped[str] = mapped_column(String(50), primary_key=True)
    emp_name: Mapped[Optional[str]] = mapped_column(String(100))
    notes_id: Mapped[Optional[str]] = mapped_column(String(100))
    mail_type: Mapped[str] = mapped_column(String(10), nullable=False)  # 'TO'/'CC'
    mail_on: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sign_grp: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        CheckConstraint("mail_type IN ('TO','CC')", name="ck_mail_list_mail_type"),
    )


class MailTypeModel(BaseB):
    """mail_type — 報表類型對照（對應舊 VOC_Mail_Type）。

    注意：class 名稱刻意避開 MailType，避免與 Python 內建/其他模組常見命名混淆；
    __tablename__ 仍是 'mail_type'，與 DDL 規格一致。
    """
    __tablename__ = "mail_type"

    type_id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    rpttype: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)


class Dept(BaseB):
    """dept — 部門主檔（對應舊 VOC_dept）。"""
    __tablename__ = "dept"

    plant_id: Mapped[int] = mapped_column(SmallInteger, ForeignKey("plant.plant_id"), primary_key=True)
    dept_no: Mapped[str] = mapped_column(String(50), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AclRole(BaseB):
    """acl_role — 角色主檔（對應舊 sys_aclrole）。"""
    __tablename__ = "acl_role"

    role_id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    role_name: Mapped[str] = mapped_column(String(50), nullable=False)


class AclUserRole(BaseB):
    """acl_user_role — 使用者角色指派（對應舊 sys_acluserrole）。plant_no='ALL' 語意沿用。"""
    __tablename__ = "acl_user_role"

    role_id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    emp_no: Mapped[str] = mapped_column(String(50), primary_key=True)
    plant_no: Mapped[str] = mapped_column(String(50), primary_key=True)
    dept_no: Mapped[Optional[str]] = mapped_column(String(50))
    stype: Mapped[Optional[str]] = mapped_column(String(20))


class AclRoleRights(BaseB):
    """acl_role_rights — 角色權限位元旗標（對應舊 sys_aclrolerights，程式 has_right 判斷邏輯不變）。"""
    __tablename__ = "acl_role_rights"

    role_id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    rights_id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    allow_rights: Mapped[int] = mapped_column(Integer, nullable=False)  # 位元旗標沿用（相容）


class Tranlog(BaseB):
    """tranlog — 操作軌跡（對應舊 VOC_tranlog）。

    H 項決策：'K7/水質異常/E001/…' 斜線串改存 JSON（泛型型別，可攜），可查詢可比對。
    """
    __tablename__ = "tranlog"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    emp_no: Mapped[str] = mapped_column(String(50), nullable=False)
    log_type: Mapped[str] = mapped_column(String(1), nullable=False)
    data_before: Mapped[Optional[dict]] = mapped_column(JSON)
    data_after: Mapped[Optional[dict]] = mapped_column(JSON)
    remark: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Employee(BaseB):
    """employee — 員工資料快取（對應舊 UTIDB.Employee，轉拋/排程同步）。"""
    __tablename__ = "employee"

    emp_no: Mapped[str] = mapped_column(String(50), primary_key=True)
    emp_name: Mapped[Optional[str]] = mapped_column(String(100))
    notes_id: Mapped[Optional[str]] = mapped_column(String(100))
    dept_no: Mapped[Optional[str]] = mapped_column(String(50))
    is_leave: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class SystemConfig(BaseB):
    """system_config — 系統設定鍵值表。

    F 項決策：全域暫停寄信改用 mail_paused 旗標（取代舊 Mail1/SM1 備份欄整表搬移）。
    種子鍵：staleness_minutes=30、sync_interval_minutes=5、dispatch_interval_minutes=15、mail_paused=false。
    """
    __tablename__ = "system_config"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Curve(BaseB):
    """curve — 歷史曲線連結（對應舊 VOC_Curve）。功能去留待 HANDOVER 決議，先保留原樣搬遷。"""
    __tablename__ = "curve"

    plant_no: Mapped[str] = mapped_column(String(50), primary_key=True)
    item: Mapped[str] = mapped_column(String(50), primary_key=True)
    url: Mapped[Optional[str]] = mapped_column(Text)


# ============================================================
# 同步 JOB 專用（PhaseA執行規格書 第四節新增）
# ============================================================

class TagMapping(BaseB):
    """tag_mapping — 同步 JOB 的中央設定表（舊 VOC_SCADA_TagList 正名後代）。

    驅動 WP2 sync_service：A 端 (source_table, tagname) → B 端 (plant_no, item, target_field)。
    target_field 可為 value 或六種 SCADA 自設管制值欄位之一。
    """
    __tablename__ = "tag_mapping"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    source_table: Mapped[str] = mapped_column(String(100), nullable=False)  # A 端表名
    tagname: Mapped[str] = mapped_column(String(200), nullable=False)
    plant_no: Mapped[str] = mapped_column(String(50), nullable=False)
    item: Mapped[str] = mapped_column(String(50), nullable=False)
    target_field: Mapped[str] = mapped_column(String(30), nullable=False, default="value")
    # value / scada_oos_high / scada_oos_low / scada_ooc_high / scada_ooc_low
    #       / scada_alert_high / scada_alert_low
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    remark: Mapped[Optional[str]] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("source_table", "tagname", name="uq_tag_mapping_source_tagname"),
    )


class KepwareSim(BaseB):
    """kepware_sim — 模擬 A 端資料表（datetime, tagname, value, quality 四欄，語意同真實 Kepware 轉拋表）。

    注意：id 為本測試環境新增的代理主鍵（真實 A 端表無此欄，A 端由既有轉拋 JOB 維運、
    我們不擁有其 schema）；四個業務欄位維持規格書指定的 datetime/tagname/value/quality。
    value 存文字（比照真實 A 端可能出現 'N.D'/'<0.05'/空字串等原始字串，由 WP2 分類函式解析）。
    """
    __tablename__ = "kepware_sim"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    datetime_: Mapped[datetime] = mapped_column("datetime", DateTime(timezone=True), nullable=False)
    tagname: Mapped[str] = mapped_column(String(200), nullable=False)
    value: Mapped[Optional[str]] = mapped_column(String(50))
    quality: Mapped[str] = mapped_column(String(20), nullable=False)
