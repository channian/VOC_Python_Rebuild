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

    plant_id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, comment="廠區代碼（主鍵，沿用舊 plantid 值，29 保留但語意改由 kind 表達）")  # 沿用舊 plantid 值
    plant_no: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, comment="廠區編號（唯一，例 'K7'，各表用來 JOIN 的業務鍵）")  # 'K7'
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="normal", comment="廠區種類：normal=實體廠區／virtual_group=虛擬群組(GMO/環工部)／all=全部(舊 29=ALL)")
    is_show: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, comment="是否於首頁顯示（舊 isShow）")
    sort: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="顯示排序（數字小者在前）")

    __table_args__ = (
        CheckConstraint("kind IN ('normal','virtual_group','all')", name="ck_plant_kind"),
        {"comment": "廠區主檔（對應舊 VOC_plant；魔法值 29/GMO/環工部 改以 kind 欄位明確表達）"},
    )


class Item(BaseB):
    """item — 量測項目主檔（對應舊 VOC_item）。

    G 項決策：display_name 吸收舊程式硬編的 pH1→pH、COD2→COD 等別名對照表。
    """
    __tablename__ = "item"

    item_id: Mapped[int] = mapped_column(Integer, primary_key=True, comment="項目代碼（主鍵）")
    item: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, comment="項目原名（唯一，例 'pH1'，各表 JOIN 用的資料鍵）")  # 'pH1'（原名，資料鍵）
    display_name: Mapped[Optional[str]] = mapped_column(String(50), comment="顯示名稱（例 'pH'，吸收舊程式硬編的 pH1→pH/COD2→COD 別名對照）")  # 'pH'
    unit: Mapped[Optional[str]] = mapped_column(String(50), comment="量測單位（例 mg/L）")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, comment="是否啟用中")

    __table_args__ = {"comment": "量測項目主檔（對應舊 VOC_item；display_name 收納舊程式硬編別名對照）"}


class Source(BaseB):
    """source — 資料來源對照表（對應舊 VOC_source）：1=SCADA 2=CWMS 3=QA。"""
    __tablename__ = "source"

    source_id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, comment="來源代碼（主鍵）：1=SCADA／2=CWMS／3=QA")
    name: Mapped[str] = mapped_column(String(50), nullable=False, comment="來源名稱")

    __table_args__ = {"comment": "資料來源對照表（對應舊 VOC_source）：1=SCADA／2=CWMS／3=QA"}


# ============================================================
# 規格（B 項：門檻字串拆數值欄）
# ============================================================

class Spec(BaseB):
    """spec — 規格值主檔（對應舊 VOC_SPEC）。

    B 項決策：LAW/OOS/OOC/Alert/允收值原本是 varchar（雙邊規格存 '6-9'、無效值存 '-'/'建置中'），
    改拆 low/high numeric + status（valid/na/building）。law_text 因僅顯示用途，保留文字欄位。
    """
    __tablename__ = "spec"

    plant_no: Mapped[str] = mapped_column(String(50), ForeignKey("plant.plant_no"), primary_key=True, comment="廠區編號（主鍵之一，FK→plant.plant_no）")
    item: Mapped[str] = mapped_column(String(50), ForeignKey("item.item"), primary_key=True, comment="項目原名（主鍵之一，FK→item.item）")

    law_text: Mapped[Optional[str]] = mapped_column(Text, comment="法規許可值原文（僅顯示用，保留文字不拆數值）")

    oos_low: Mapped[Optional[Decimal]] = mapped_column(Numeric, comment="OOS(超出規格/紅燈門檻) 下界；單邊規格為 NULL")
    oos_high: Mapped[Optional[Decimal]] = mapped_column(Numeric, comment="OOS(超出規格/紅燈門檻) 上界；燈號比對取上界")
    oos_status: Mapped[Optional[str]] = mapped_column(String(20), comment="OOS 門檻狀態：valid=有效／na=無效(舊 '-'/'N/A')／building=建置中")

    ooc_low: Mapped[Optional[Decimal]] = mapped_column(Numeric, comment="OOC(超出管制/橙燈門檻) 下界；單邊規格為 NULL")
    ooc_high: Mapped[Optional[Decimal]] = mapped_column(Numeric, comment="OOC(超出管制/橙燈門檻) 上界")
    ooc_status: Mapped[Optional[str]] = mapped_column(String(20), comment="OOC 門檻狀態：valid／na／building")

    alert_low: Mapped[Optional[Decimal]] = mapped_column(Numeric, comment="Alert(預警/黃燈門檻) 下界；單邊規格為 NULL")
    alert_high: Mapped[Optional[Decimal]] = mapped_column(Numeric, comment="Alert(預警/黃燈門檻) 上界")
    alert_status: Mapped[Optional[str]] = mapped_column(String(20), comment="Alert 門檻狀態：valid／na／building")

    recv_low: Mapped[Optional[Decimal]] = mapped_column(Numeric, comment="允收值下界；單邊規格為 NULL")  # 允收值
    recv_high: Mapped[Optional[Decimal]] = mapped_column(Numeric, comment="允收值上界（rvalue 超過即黃燈）")
    recv_status: Mapped[Optional[str]] = mapped_column(String(20), comment="允收值狀態：valid／na／building")

    source_id: Mapped[int] = mapped_column(SmallInteger, ForeignKey("source.source_id"), nullable=False, comment="資料來源（FK→source.source_id）：1=SCADA／2=CWMS／3=QA")
    seqno: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="同廠區內顯示排序")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), comment="最後更新時間"
    )

    __table_args__ = {"comment": "規格門檻設定（對應舊 VOC_SPEC；門檻字串已拆成 low/high numeric + status 三欄）"}


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

    plant_no: Mapped[str] = mapped_column(String(50), primary_key=True, comment="廠區編號（主鍵之一）")
    item: Mapped[str] = mapped_column(String(50), primary_key=True, comment="項目原名（主鍵之一）")

    value: Mapped[Optional[Decimal]] = mapped_column(Numeric, comment="讀值數值（A 版 rvalue 拆出的純數字；N.D→NULL、<0.05→0.05，非數字狀態另存 status）")  # N.D→NULL、<0.05→0.05
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="normal", comment="讀值狀態：normal/nd/below_lod/broken/maintenance/building/error（取代 rvalue 內混存的狀態文字）")
    raw_text: Mapped[Optional[str]] = mapped_column(Text, comment="原始讀值字串備查（例 'N.D'/'<0.05'）")  # 原始字串備查
    comm_ok: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, comment="通訊是否正常（取代舊 broken=1 斷訊，JOB 專寫；隔離的 broken=2 不再落地於此表）")

    # SCADA 自設管制值（隔離不再覆寫）
    scada_oos_low: Mapped[Optional[Decimal]] = mapped_column(Numeric, comment="SCADA 自設 OOS 下界（隔離不再覆寫）")
    scada_oos_high: Mapped[Optional[Decimal]] = mapped_column(Numeric, comment="SCADA 自設 OOS 上界（與 SPEC 不一致時亮橙燈）")
    scada_ooc_low: Mapped[Optional[Decimal]] = mapped_column(Numeric, comment="SCADA 自設 OOC 下界")
    scada_ooc_high: Mapped[Optional[Decimal]] = mapped_column(Numeric, comment="SCADA 自設 OOC 上界")
    scada_alert_low: Mapped[Optional[Decimal]] = mapped_column(Numeric, comment="SCADA 自設 Alert 下界")
    scada_alert_high: Mapped[Optional[Decimal]] = mapped_column(Numeric, comment="SCADA 自設 Alert 上界")
    scada_limit_status: Mapped[Optional[str]] = mapped_column(String(20), comment="SCADA 管制值狀態：valid/na/building/broken")

    # CWMS 管制值
    cwms_oos_low: Mapped[Optional[Decimal]] = mapped_column(Numeric, comment="CWMS 管制 OOS 下界")
    cwms_oos_high: Mapped[Optional[Decimal]] = mapped_column(Numeric, comment="CWMS 管制 OOS 上界")
    cwms_ooc_low: Mapped[Optional[Decimal]] = mapped_column(Numeric, comment="CWMS 管制 OOC 下界")
    cwms_ooc_high: Mapped[Optional[Decimal]] = mapped_column(Numeric, comment="CWMS 管制 OOC 上界")
    cwms_limit_status: Mapped[Optional[str]] = mapped_column(String(20), comment="CWMS 管制值狀態：valid/na/building/broken")

    rain_24h: Mapped[Optional[Decimal]] = mapped_column(Numeric, comment="24 小時累積雨量（J 項：由轉拋 JOB 寫入，取代舊 PMS 跨庫 JOIN）")  # J 項：轉拋 JOB 寫入，取代 PMS 跨庫 JOIN

    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, comment="資料量測時間（對齊 15 分）")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), comment="本列最後寫入時間"
    )

    __table_args__ = (
        ForeignKeyConstraint(["plant_no", "item"], ["spec.plant_no", "spec.item"]),
        CheckConstraint(
            "status IN ('normal','nd','below_lod','broken','maintenance','building','error')",
            name="ck_reading_current_status",
        ),
        {"comment": "目前讀值（對應舊 VOC_SCADA_WEB，每 plant_no+item 僅存最新一筆；rvalue 拆 value+status+raw_text，隔離不再覆寫）"},
    )


class ReadingHistory(BaseB):
    """reading_history — 讀值歷史（對應舊 VOC_SCADA_HIST），append-only，永不 UPDATE。

    ★稽核決策（2026-07-01）：法規稽核需要「當時管制值」逐時證據，每筆讀值快照當下生效的
    SPEC 三階管制值（沿襲舊 VOC_SCADA_HIST 亦存 OOS/OOC/alert1/recv 的做法）。
    SCADA/CWMS 自設管制值快照放 limits_extra（泛型 JSON，引擎可攜，不用 PG 專屬 JSONB）。
    K1/K9 雨水溝三點連升：直接對本表用 window function，不需另存三欄。
    """
    __tablename__ = "reading_history"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True, comment="流水主鍵（自增）")
    plant_no: Mapped[str] = mapped_column(String(50), nullable=False, comment="廠區編號")
    item: Mapped[str] = mapped_column(String(50), nullable=False, comment="項目原名")
    value: Mapped[Optional[Decimal]] = mapped_column(Numeric, comment="讀值數值（非數字狀態另存 status）")
    status: Mapped[str] = mapped_column(String(20), nullable=False, comment="讀值狀態：normal/nd/below_lod/broken/maintenance/building/error")
    raw_text: Mapped[Optional[str]] = mapped_column(Text, comment="原始讀值字串備查")

    spec_oos_low: Mapped[Optional[Decimal]] = mapped_column(Numeric, comment="當下生效的 SPEC OOS 下界快照（稽核用）")
    spec_oos_high: Mapped[Optional[Decimal]] = mapped_column(Numeric, comment="當下生效的 SPEC OOS 上界快照（稽核用）")
    spec_ooc_low: Mapped[Optional[Decimal]] = mapped_column(Numeric, comment="當下生效的 SPEC OOC 下界快照")
    spec_ooc_high: Mapped[Optional[Decimal]] = mapped_column(Numeric, comment="當下生效的 SPEC OOC 上界快照")
    spec_alert_low: Mapped[Optional[Decimal]] = mapped_column(Numeric, comment="當下生效的 SPEC Alert 下界快照")
    spec_alert_high: Mapped[Optional[Decimal]] = mapped_column(Numeric, comment="當下生效的 SPEC Alert 上界快照")
    spec_recv_low: Mapped[Optional[Decimal]] = mapped_column(Numeric, comment="當下生效的 SPEC 允收值下界快照")
    spec_recv_high: Mapped[Optional[Decimal]] = mapped_column(Numeric, comment="當下生效的 SPEC 允收值上界快照")
    limits_extra: Mapped[Optional[dict]] = mapped_column(JSON, comment="SCADA/CWMS 自設管制值快照（泛型 JSON，引擎可攜）")  # SCADA/CWMS 自設管制值快照

    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, comment="資料量測時間")

    __table_args__ = (
        UniqueConstraint("plant_no", "item", "measured_at", name="uq_reading_history_pim"),
        Index("idx_rh_lookup", "plant_no", "item", measured_at.desc()),
        {"comment": "讀值歷史（對應舊 VOC_SCADA_HIST，append-only 永不 UPDATE；逐時快照當時 SPEC 管制值供法規稽核）"},
    )


# ============================================================
# 派報紀錄（D 項：明細正規化，取代 msg1/msg2 字串比對）
# ============================================================

class MailLog(BaseB):
    """mail_log — 派報信件層級紀錄（對應舊 VOC_MAIL_Log，一封信一列）。"""
    __tablename__ = "mail_log"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True, comment="信件流水主鍵（自增，取代舊 logid）")  # 取代 logid
    plant_no: Mapped[str] = mapped_column(String(50), nullable=False, comment="廠區編號")
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, comment="寄送時間（舊 cdatetime，對齊 5 分）")  # cdatetime（對齊 5 分）
    subject: Mapped[Optional[str]] = mapped_column(String(200), comment="信件主旨")
    body_note: Mapped[Optional[str]] = mapped_column(Text, comment="信件全文備註（舊 msg，人讀全文，回覆頁顯示用）")  # 原 msg（人讀全文，回覆頁顯示用）
    # 2026-07-12 C8 使用者確認：異常回覆改成「逐項目」層級（原本一封信只有一組回覆，
    # 分不清是在回覆信裡的哪個異常項目）。回覆三欄搬到 MailLogItem，此處不再保留。

    __table_args__ = {"comment": "派報信件層級紀錄（對應舊 VOC_MAIL_Log，一封信一列；明細拆到 mail_log_item）"}


class MailLogItem(BaseB):
    """mail_log_item — 派報明細（原 msg1/msg2 字串正規化，每項目每條件一列）。"""
    __tablename__ = "mail_log_item"

    mail_log_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("mail_log.id"), primary_key=True, comment="所屬信件（主鍵之一，FK→mail_log.id）")
    item: Mapped[str] = mapped_column(String(50), primary_key=True, comment="項目原名（主鍵之一）")
    condition_code: Mapped[str] = mapped_column(String(30), primary_key=True, comment="異常條件碼（主鍵之一）：OOS/OOC/ALERT/RECV/LIMIT_MISMATCH/MAINTENANCE/BROKEN")
    # 'OOS'/'OOC'/'ALERT'/'RECV'/'LIMIT_MISMATCH'/'MAINTENANCE'/'BROKEN'
    detail: Mapped[Optional[str]] = mapped_column(Text, comment="原條件敘述（信件顯示用）")
    escalation_stage: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0, comment="派報升級階段：0/1/2（對應舊 0/15/30 分再發）")  # 0/1/2（原 0/15/30 分）
    is_maintenance: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否保養中項目（true=舊系統僅入 msg1 不入 msg2）")
    # 2026-07-12 C8：異常回覆從「信件層級」改成「逐項目層級」，回覆三欄從 MailLog 搬過來
    # （使用者確認：舊系統一封信只有一組回覆，分不清是回覆信裡的哪個項目；新版改成每個
    # 項目各自回覆）。語意不變，只是掛的位置從 mail_log 改成 mail_log_item。
    reply_empno: Mapped[Optional[str]] = mapped_column(String(50), comment="原因回覆人工號（2026-07-12 起改為逐項目回覆，原掛在 mail_log）")
    reply_reason: Mapped[Optional[str]] = mapped_column(Text, comment="異常原因回覆內容（逐項目）")
    reply_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), comment="原因回覆回填時間（逐項目）")

    __table_args__ = (
        Index("idx_mli_dedup", "item", "condition_code"),
        {"comment": "派報明細（D 項：舊 msg1/msg2 字串正規化，每項目每條件一列，供首發/再發精確比對）"},
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

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True, comment="隔離單流水主鍵（自增，原 ccid）")  # 原 ccid
    ccno: Mapped[str] = mapped_column(String(20), nullable=False, unique=True, comment="隔離單顯示編號（唯一，格式 yyyymmddNNN）")  # 顯示編號 yyyymmddNNN
    ttype: Mapped[int] = mapped_column(SmallInteger, nullable=False, comment="單別：1=新增隔離／2=修改隔離")  # 1新增/2修改
    org_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("isolation.id"), comment="來源原單 id（修改單指向被修改的原隔離單，原 orgccid，自我參照）")  # 原 orgccid
    plant_id: Mapped[int] = mapped_column(SmallInteger, ForeignKey("plant.plant_id"), nullable=False, comment="廠區代碼（FK→plant.plant_id）")
    mdfdesc: Mapped[Optional[str]] = mapped_column(Text, comment="修改說明")
    remark: Mapped[Optional[str]] = mapped_column(Text, comment="備註")
    stime: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, comment="隔離起始時間（有效區間起點）")
    etime: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, comment="隔離結束時間（有效區間終點，須大於 stime）")
    cemp_no: Mapped[str] = mapped_column(String(50), nullable=False, comment="申請人工號")
    cemp_name: Mapped[Optional[str]] = mapped_column(String(100), comment="申請人姓名")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), comment="建單時間"
    )
    flow_id: Mapped[Optional[int]] = mapped_column(BigInteger, comment="關聯簽核流程 id（sign_flow.flow_id）")
    fstatus: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0, comment="簽核狀態（FlowStatus 值）：0=待簽核／1=簽核中／7=核准／8=否決／12=取消")
    deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否已刪除（軟刪除旗標）")
    del_clerk: Mapped[Optional[str]] = mapped_column(String(50), comment="刪除人工號")

    __table_args__ = (
        CheckConstraint("ttype IN (1,2)", name="ck_isolation_ttype"),
        CheckConstraint("etime > stime", name="ck_isolation_etime_after_stime"),
        {"comment": "隔離(保養/隔離)申請單主檔（對應舊 VOC_closectl；核准後不再竄改讀值，維護狀態改由有效區間 JOIN 推導）"},
    )


class IsolationItem(BaseB):
    """isolation_item — 隔離單涵蓋的廠區/項目明細（對應舊 VOC_closectl_list）。"""
    __tablename__ = "isolation_item"

    isolation_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("isolation.id"), primary_key=True, comment="所屬隔離單（主鍵之一，FK→isolation.id）")
    plant_no: Mapped[str] = mapped_column(String(50), primary_key=True, comment="廠區編號（主鍵之一）")
    item: Mapped[str] = mapped_column(String(50), primary_key=True, comment="項目原名（主鍵之一，存原名 pH1/COD2）")  # 存原名 pH1/COD2
    source_id: Mapped[int] = mapped_column(SmallInteger, nullable=False, comment="資料來源：1=SCADA／2=CWMS／3=QA")

    __table_args__ = {"comment": "隔離單涵蓋的廠區/項目明細（對應舊 VOC_closectl_list）"}


class IsolationHistory(BaseB):
    """isolation_history — 隔離單異動快照（對應舊 VOC_closectl_his）。

    H 項精神：整單快照存 JSON 取代逐欄複製；utype：1新增/2送簽/3修改。
    """
    __tablename__ = "isolation_history"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True, comment="異動流水主鍵（自增）")
    isolation_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("isolation.id"), nullable=False, comment="所屬隔離單（FK→isolation.id）")
    utype: Mapped[int] = mapped_column(SmallInteger, nullable=False, comment="異動類別：1=新增／2=送簽／3=修改")
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, comment="整單快照（JSON 取代逐欄複製，泛型型別可攜）")
    uclerk_no: Mapped[Optional[str]] = mapped_column(String(50), comment="異動人工號")
    uclerk_name: Mapped[Optional[str]] = mapped_column(String(100), comment="異動人姓名")
    utime: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), comment="異動時間"
    )

    __table_args__ = {"comment": "隔離單異動快照（對應舊 VOC_closectl_his；整單以 JSON 快照，utype 1新增/2送簽/3修改）"}


class SpecApply(BaseB):
    """spec_apply — 規格維護申請單（對應舊 VOC_SPEC_apply）。"""
    __tablename__ = "spec_apply"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True, comment="申請單流水主鍵（自增）")
    formno: Mapped[str] = mapped_column(String(20), nullable=False, unique=True, comment="申請單顯示編號（唯一）")
    ftype: Mapped[str] = mapped_column(String(1), nullable=False, comment="申請類別：I=新增／M=修改／D=刪除")  # I新增/M修改/D刪除
    plant_no: Mapped[str] = mapped_column(String(50), nullable=False, comment="廠區編號")
    item: Mapped[str] = mapped_column(String(50), nullable=False, comment="項目原名")
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, comment="申請的規格新值（I/M 用，JSON 取代逐欄複製）")  # 申請的規格新值
    emp_no: Mapped[str] = mapped_column(String(50), nullable=False, comment="申請人工號")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), comment="建單時間"
    )
    flow_id: Mapped[Optional[int]] = mapped_column(BigInteger, comment="關聯簽核流程 id（sign_flow.flow_id）")
    fstatus: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0, comment="簽核狀態（FlowStatus 值）：0=待簽核／1=簽核中／7=核准／8=否決／12=取消")

    __table_args__ = (
        CheckConstraint("ftype IN ('I','M','D')", name="ck_spec_apply_ftype"),
        {"comment": "規格維護申請單（對應舊 VOC_SPEC_apply；規格新值改存 payload JSON）"},
    )


# J 項測試期方案：SignFlow 同構表（欄位語意 1:1，正式去向另議——見 docs/schema_B_設計提案.md 第四節）

class SignEmp(BaseB):
    """sign_emp — 簽核人員快取（對應公司 SignFlow.base_emp，測試期 B 內建同構表）。"""
    __tablename__ = "sign_emp"

    emp_id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True, comment="簽核人員流水主鍵（自增）")
    emp_no: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, comment="員工工號（唯一）")
    emp_name: Mapped[Optional[str]] = mapped_column(String(100), comment="員工姓名")
    email: Mapped[Optional[str]] = mapped_column(String(200), comment="電子郵件")
    pos_id: Mapped[Optional[int]] = mapped_column(Integer, comment="職位代碼")
    dep_no: Mapped[Optional[str]] = mapped_column(String(50), comment="部門編號")

    __table_args__ = {"comment": "簽核人員快取（對應公司 SignFlow.base_emp；測試期 B 內建同構表，正式去向後議）"}


class SignFlow(BaseB):
    """sign_flow — 簽核流程主檔（對應公司 SignFlow.base_flow）。"""
    __tablename__ = "sign_flow"

    flow_id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True, comment="簽核流程主鍵（自增）")
    frule_id: Mapped[int] = mapped_column(Integer, nullable=False, comment="簽核規則代碼")
    act_step: Mapped[Optional[int]] = mapped_column(Integer, comment="目前進行中的簽核關卡步驟")
    fstatus: Mapped[int] = mapped_column(SmallInteger, nullable=False, comment="流程狀態（FlowStatus 值）：0=待簽核／1=簽核中／7=核准／8=否決／12=取消")  # FlowStatus 數值不變（0/1/7/8/12）
    fid: Mapped[Optional[int]] = mapped_column(BigInteger, comment="來源單據 id（隔離單/規格申請單等業務主鍵）")
    emp_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("sign_emp.emp_id"), comment="送簽人（FK→sign_emp.emp_id）")
    fstime: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), comment="流程開始時間")
    fetime: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), comment="流程結束時間")
    show_info: Mapped[Optional[str]] = mapped_column(Text, comment="流程顯示摘要資訊")

    __table_args__ = {"comment": "簽核流程主檔（對應公司 SignFlow.base_flow；測試期 B 內建同構表）"}


class SignFlowStep(BaseB):
    """sign_flow_step — 簽核流程節點明細（對應公司 SignFlow.base_flowd）。"""
    __tablename__ = "sign_flow_step"

    flow_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sign_flow.flow_id"), primary_key=True, comment="所屬流程（主鍵之一，FK→sign_flow.flow_id）")
    fstep: Mapped[int] = mapped_column(Integer, primary_key=True, comment="簽核關卡步驟序（主鍵之一）")
    emp_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, comment="應簽核人 emp_id（主鍵之一）")
    ftype: Mapped[Optional[int]] = mapped_column(Integer, comment="關卡類型")
    pos_id: Mapped[Optional[int]] = mapped_column(Integer, comment="職位代碼")
    sign_emp_id: Mapped[Optional[int]] = mapped_column(BigInteger, comment="實際簽核人 emp_id")
    sign_emp_name: Mapped[Optional[str]] = mapped_column(String(100), comment="實際簽核人姓名")
    sign_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), comment="簽核時間")
    sign_action: Mapped[Optional[int]] = mapped_column(SmallInteger, comment="簽核動作（核准/否決等）")
    sign_memo: Mapped[Optional[str]] = mapped_column(Text, comment="簽核意見備註")

    __table_args__ = {"comment": "簽核流程節點明細（對應公司 SignFlow.base_flowd；每流程每關卡一列）"}


# ============================================================
# 名單、權限、其他
# ============================================================

class MailList(BaseB):
    """mail_list — 派報名單（對應舊 VOC_Mail_List）。

    F/I 項決策：去掉 SM/cellphone/Mail1/SM1（簡訊停用＋暫停寄信改用 system_config.mail_paused）。
    """
    __tablename__ = "mail_list"

    plant_no: Mapped[str] = mapped_column(String(50), primary_key=True, comment="廠區編號（主鍵之一）")
    rpttype: Mapped[str] = mapped_column(String(50), primary_key=True, comment="報表類型（主鍵之一，對應 mail_type.rpttype）")
    emp_no: Mapped[str] = mapped_column(String(50), primary_key=True, comment="收件人工號（主鍵之一）")
    emp_name: Mapped[Optional[str]] = mapped_column(String(100), comment="收件人姓名")
    notes_id: Mapped[Optional[str]] = mapped_column(String(100), comment="Lotus Notes 郵件帳號")
    mail_type: Mapped[str] = mapped_column(String(10), nullable=False, comment="收件方式：TO=正本／CC=副本")  # 'TO'/'CC'
    mail_on: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, comment="是否啟用寄信（舊 mail 布林化）")
    sign_grp: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否簽核群組成員（舊 signgrp 布林化）")

    __table_args__ = (
        CheckConstraint("mail_type IN ('TO','CC')", name="ck_mail_list_mail_type"),
        {"comment": "派報名單（對應舊 VOC_Mail_List；去掉 SM/cellphone/Mail1/SM1，暫停寄信改用 system_config.mail_paused）"},
    )


class MailTypeModel(BaseB):
    """mail_type — 報表類型對照（對應舊 VOC_Mail_Type）。

    注意：class 名稱刻意避開 MailType，避免與 Python 內建/其他模組常見命名混淆；
    __tablename__ 仍是 'mail_type'，與 DDL 規格一致。
    """
    __tablename__ = "mail_type"

    type_id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, comment="報表類型代碼（主鍵）")
    rpttype: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, comment="報表類型名稱（唯一，例 水質異常/規格維護）")

    __table_args__ = {"comment": "報表類型對照（對應舊 VOC_Mail_Type）"}


class Dept(BaseB):
    """dept — 部門主檔（對應舊 VOC_dept）。"""
    __tablename__ = "dept"

    plant_id: Mapped[int] = mapped_column(SmallInteger, ForeignKey("plant.plant_id"), primary_key=True, comment="廠區代碼（主鍵之一，FK→plant.plant_id）")
    dept_no: Mapped[str] = mapped_column(String(50), primary_key=True, comment="部門編號（主鍵之一）")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), comment="建立時間"
    )

    __table_args__ = {"comment": "部門主檔（對應舊 VOC_dept；以廠區+部門編號為複合主鍵）"}


class AclRole(BaseB):
    """acl_role — 角色主檔（對應舊 sys_aclrole）。"""
    __tablename__ = "acl_role"

    role_id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, comment="角色代碼（主鍵）")
    role_name: Mapped[str] = mapped_column(String(50), nullable=False, comment="角色名稱")

    __table_args__ = {"comment": "角色主檔（對應舊 sys_aclrole）"}


class AclUserRole(BaseB):
    """acl_user_role — 使用者角色指派（對應舊 sys_acluserrole）。plant_no='ALL' 語意沿用。"""
    __tablename__ = "acl_user_role"

    role_id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, comment="角色代碼（主鍵之一，對應 acl_role.role_id）")
    emp_no: Mapped[str] = mapped_column(String(50), primary_key=True, comment="使用者工號（主鍵之一）")
    plant_no: Mapped[str] = mapped_column(String(50), primary_key=True, comment="授權廠區（主鍵之一，'ALL'=全廠區，語意沿用舊系統）")
    dept_no: Mapped[Optional[str]] = mapped_column(String(50), comment="授權部門編號")
    stype: Mapped[Optional[str]] = mapped_column(String(20), comment="授權範圍/種類標記")

    __table_args__ = {"comment": "使用者角色指派（對應舊 sys_acluserrole；plant_no='ALL' 表全廠區）"}


class AclRoleRights(BaseB):
    """acl_role_rights — 角色權限位元旗標（對應舊 sys_aclrolerights，程式 has_right 判斷邏輯不變）。"""
    __tablename__ = "acl_role_rights"

    role_id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, comment="角色代碼（主鍵之一，對應 acl_role.role_id）")
    rights_id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, comment="權限項目代碼（主鍵之一）")
    allow_rights: Mapped[int] = mapped_column(Integer, nullable=False, comment="允許權限位元旗標（沿用舊值，程式 has_right 位元判斷邏輯不變）")  # 位元旗標沿用（相容）

    __table_args__ = {"comment": "角色權限位元旗標（對應舊 sys_aclrolerights；位元旗標沿用相容）"}


class Tranlog(BaseB):
    """tranlog — 操作軌跡（對應舊 VOC_tranlog）。

    H 項決策：'K7/水質異常/E001/…' 斜線串改存 JSON（泛型型別，可攜），可查詢可比對。
    """
    __tablename__ = "tranlog"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True, comment="軌跡流水主鍵（自增）")
    emp_no: Mapped[str] = mapped_column(String(50), nullable=False, comment="操作人工號")
    log_type: Mapped[str] = mapped_column(String(1), nullable=False, comment="操作類別代碼")
    data_before: Mapped[Optional[dict]] = mapped_column(JSON, comment="異動前資料（H 項：舊斜線串改存 JSON，可查詢可比對）")
    data_after: Mapped[Optional[dict]] = mapped_column(JSON, comment="異動後資料（JSON）")
    remark: Mapped[Optional[str]] = mapped_column(Text, comment="備註")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), comment="操作時間"
    )

    __table_args__ = {"comment": "操作軌跡(稽核 log)（對應舊 VOC_tranlog；斜線串改存 JSON）"}


class Employee(BaseB):
    """employee — 員工資料快取（對應舊 UTIDB.Employee，轉拋/排程同步）。"""
    __tablename__ = "employee"

    emp_no: Mapped[str] = mapped_column(String(50), primary_key=True, comment="員工工號（主鍵）")
    emp_name: Mapped[Optional[str]] = mapped_column(String(100), comment="員工姓名")
    notes_id: Mapped[Optional[str]] = mapped_column(String(100), comment="Lotus Notes 郵件帳號")
    dept_no: Mapped[Optional[str]] = mapped_column(String(50), comment="部門編號")
    is_leave: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否已離職")
    synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), comment="最後同步時間")

    __table_args__ = {"comment": "員工資料快取（對應舊 UTIDB.Employee；由轉拋/排程 JOB 同步）"}


class SystemConfig(BaseB):
    """system_config — 系統設定鍵值表。

    F 項決策：全域暫停寄信改用 mail_paused 旗標（取代舊 Mail1/SM1 備份欄整表搬移）。
    種子鍵：staleness_minutes=30、sync_interval_minutes=5、dispatch_interval_minutes=15、mail_paused=false。
    """
    __tablename__ = "system_config"

    key: Mapped[str] = mapped_column(String(100), primary_key=True, comment="設定鍵（主鍵，例 mail_paused/staleness_minutes/sync_interval_minutes/dispatch_interval_minutes）")
    value: Mapped[str] = mapped_column(Text, nullable=False, comment="設定值（一律以文字存放，取用端自行轉型）")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), comment="最後更新時間"
    )

    __table_args__ = {"comment": "系統設定鍵值表（F 項：全域暫停寄信改用 mail_paused 旗標取代舊 Mail1/SM1 備份欄）"}


class Curve(BaseB):
    """curve — 歷史曲線連結（對應舊 VOC_Curve）。功能去留待 HANDOVER 決議，先保留原樣搬遷。"""
    __tablename__ = "curve"

    plant_no: Mapped[str] = mapped_column(String(50), primary_key=True, comment="廠區編號（主鍵之一）")
    item: Mapped[str] = mapped_column(String(50), primary_key=True, comment="項目原名（主鍵之一）")
    url: Mapped[Optional[str]] = mapped_column(Text, comment="外部歷史曲線圖表頁連結")

    __table_args__ = {"comment": "歷史曲線連結（對應舊 VOC_Curve；功能去留待 HANDOVER 決議，先原樣保留）"}


# ============================================================
# 同步 JOB 專用（PhaseA執行規格書 第四節新增）
# ============================================================

class TagMapping(BaseB):
    """tag_mapping — 同步 JOB 的中央設定表（舊 VOC_SCADA_TagList 正名後代）。

    驅動 WP2 sync_service：A 端 (source_table, tagname) → B 端 (plant_no, item, target_field)。
    target_field 可為 value 或六種 SCADA 自設管制值欄位之一。
    """
    __tablename__ = "tag_mapping"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True, comment="對照設定流水主鍵（自增）")
    source_table: Mapped[str] = mapped_column(String(100), nullable=False, comment="A 端來源表名")  # A 端表名
    tagname: Mapped[str] = mapped_column(String(200), nullable=False, comment="A 端 tag 名稱")
    plant_no: Mapped[str] = mapped_column(String(50), nullable=False, comment="對應 B 端廠區編號")
    item: Mapped[str] = mapped_column(String(50), nullable=False, comment="對應 B 端項目原名")
    target_field: Mapped[str] = mapped_column(String(30), nullable=False, default="value", comment="寫入 reading_current 的目標欄位：value 或六種 scada_* 自設管制值欄位之一")
    # value / scada_oos_high / scada_oos_low / scada_ooc_high / scada_ooc_low
    #       / scada_alert_high / scada_alert_low
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, comment="此對照是否啟用")
    remark: Mapped[Optional[str]] = mapped_column(Text, comment="備註")

    __table_args__ = (
        UniqueConstraint("source_table", "tagname", name="uq_tag_mapping_source_tagname"),
        {"comment": "同步 JOB 中央對照設定（舊 VOC_SCADA_TagList 正名；驅動 A 端 tag → B 端 plant_no/item/target_field）"},
    )


class KepwareSim(BaseB):
    """kepware_sim — 模擬 A 端資料表（datetime, tagname, value, quality 四欄，語意同真實 Kepware 轉拋表）。

    注意：id 為本測試環境新增的代理主鍵（真實 A 端表無此欄，A 端由既有轉拋 JOB 維運、
    我們不擁有其 schema）；四個業務欄位維持規格書指定的 datetime/tagname/value/quality。
    value 存文字（比照真實 A 端可能出現 'N.D'/'<0.05'/空字串等原始字串，由 WP2 分類函式解析）。
    """
    __tablename__ = "kepware_sim"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True, comment="測試環境代理主鍵（自增；真實 A 端表無此欄）")
    datetime_: Mapped[datetime] = mapped_column("datetime", DateTime(timezone=True), nullable=False, comment="量測時間（實體欄名為 datetime，同真實 Kepware 轉拋表）")
    tagname: Mapped[str] = mapped_column(String(200), nullable=False, comment="A 端 tag 名稱")
    value: Mapped[Optional[str]] = mapped_column(String(50), comment="原始讀值字串（可能為 'N.D'/'<0.05'/空字串，由 WP2 分類函式解析）")
    quality: Mapped[str] = mapped_column(String(20), nullable=False, comment="品質旗標（同真實 Kepware quality 欄）")

    __table_args__ = {"comment": "模擬 A 端 Kepware 轉拋表（datetime/tagname/value/quality 四欄語意同真實表，供本測試環境驅動同步）"}
