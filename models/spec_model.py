"""
spec_model.py — 規格值與廠區相關資料表的 SQLAlchemy ORM 模型

資料表對應：
  VocSpec     ← VOC_SPEC        規格值主檔（LAW / OOS / OOC / Alert 等門檻）
  VocScadaWeb ← VOC_SCADA_WEB   即時讀值 + SCADA/CWMS 管制值（由 JOB 每 15 分鐘寫入）
  VocPlant    ← VOC_plant       廠區主檔（代號與顯示設定）
  VocItem     ← VOC_item        量測項目主檔（項目名稱與單位）
  VocSource   ← VOC_source      資料來源對照（SCADA / CWMS / QA）
"""

from sqlalchemy import Column, String, Integer, Float, DateTime, SmallInteger
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class VocSpec(Base):
    """
    VOC_SPEC — 規格值主檔
    每一列 = 一個廠區（plantno）× 一個量測項目（item）的標準設定
    """
    __tablename__ = 'VOC_SPEC'

    plantno = Column(String(50), primary_key=True)   # 廠區代號（K1, K3...）
    item    = Column(String(50), primary_key=True)   # 量測項目名稱（COD, pH...）

    LAW    = Column(String(50))    # 法規許可值（政府核准上限）
    OOS    = Column(String(50))    # Out of Spec 上限（內部規格，比法規嚴格）
    OOC    = Column(String(50))    # Out of Control 上限
    alert  = Column(String(50))    # 預警值
    recv   = Column(String(50))    # 允收值

    source  = Column(Integer)      # 對應 VOC_source.sourceid（SCADA=1, CWMS=2, QA=3）
    status  = Column(Integer)      # 1=啟用, 0=停用
    tagname = Column(String(100))  # SCADA/Kepware Tag 名稱（供 JOB mapping 用）
    seqno   = Column(Integer)      # 排序序號（儀表板顯示順序）


class VocScadaWeb(Base):
    """
    VOC_SCADA_WEB — 即時讀值與 SCADA 管制值
    由背景 JOB 每 15 分鐘從 iFIX Historian / Kepware 讀取並更新。
    同一筆 (plantno, item) 只保留最新一筆（覆蓋寫入）。
    歷史資料另存於 VOC_SCADA_HIST。

    broken 欄位說明：
      0 = 正常
      1 = 斷訊（JOB 判斷 Tag 品質異常或超時未更新）
      2 = 保養中 / 隔離中（由 Web 端隔離申請功能寫入）
    """
    __tablename__ = 'VOC_SCADA_WEB'

    plantno = Column(String(50), primary_key=True)   # 廠區代號
    item    = Column(String(50), primary_key=True)   # 量測項目

    rvalue    = Column(String(50))   # 最新讀值（varchar，因為有 N.D / 斷訊 等文字）
    cdatetime = Column(DateTime)     # 資料時間戳

    # SCADA 系統自設的管制值（由 JOB 從 SCADA 讀回，與 SPEC 值比對決定橙燈）
    OOS_HH  = Column(String(50))    # SCADA 設定的上上限（對應 SPEC.OOS）
    OOC_H   = Column(String(50))    # SCADA 設定的上限（對應 SPEC.OOC）
    alert   = Column(String(50))    # SCADA 設定的預警值（對應 SPEC.alert）
    OOS_LL  = Column(String(50))    # SCADA 下限（pH 等雙邊規格用）
    OOC_L   = Column(String(50))    # SCADA 下限 OOC（雙邊規格用）
    alert_L = Column(String(50))    # SCADA 下限預警（雙邊規格用）

    # CWMS 系統管制值（若有接 CWMS）
    OOS_HH1 = Column(String(50))    # CWMS 上上限
    OOC_H1  = Column(String(50))    # CWMS 上限

    broken  = Column(SmallInteger, default=0)  # 0=正常, 1=斷訊, 2=保養中

    # TwentyFourHours: 雨水溝 24 小時累積值
    # 注意：此值來自 PMS.dbo.Water_WindRainHistValue，由雨水溝查詢時 JOIN，
    # 一般儀表板查詢不使用此欄位。
    TwentyFourHours = Column(Float)


class VocPlant(Base):
    """
    VOC_plant — 廠區主檔
    此表由 DB 管理員直接維護，Web 端目前只讀（無 INSERT/UPDATE）。
    TODO: Phase 4 增加 Admin UI 管理此表。
    """
    __tablename__ = 'VOC_plant'

    plantid = Column(Integer, primary_key=True)   # 廠區 ID（29=ALL，可看全部）
    plantno = Column(String(50))                  # 廠區代號（K1, K3...）
    sort    = Column(Integer)                     # 儀表板顯示排序
    isShow  = Column(Integer)                     # 1=顯示, 0=隱藏


class VocItem(Base):
    """
    VOC_item — 量測項目主檔
    此表由 DB 管理員直接維護，Web 端目前只讀。
    TODO: Phase 4 增加 Admin UI 管理此表。
    """
    __tablename__ = 'VOC_item'

    itemid = Column(Integer, primary_key=True)   # 項目 ID
    item   = Column(String(50))                  # 項目名稱（COD, pH, SS...）
    unit   = Column(String(50))                  # 單位（mg/L, pH, %...）
    stype  = Column(String(20))                  # 類型（廢水 / 空汙...）


class VocSource(Base):
    """VOC_source — 資料來源對照表"""
    __tablename__ = 'VOC_source'

    sourceid = Column(Integer, primary_key=True)
    source   = Column(String(50))   # SCADA / CWMS / QA
