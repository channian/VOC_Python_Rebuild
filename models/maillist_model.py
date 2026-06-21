"""
maillist_model.py — 派送名單與報表類型的 SQLAlchemy ORM 模型

資料表對應（依 legacy/dbVOC.cs + EditMailList.aspx.cs 精讀確認）：
  VocMailList ← VOC_Mail_List   異常通知派送名單
  VocMailType ← VOC_Mail_Type   報表類型主檔（下拉選單來源）

詳見 docs/legacy_source_analysis.md 第二節。
"""

from sqlalchemy import Column, String, Integer, SmallInteger
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class VocMailList(Base):
    """
    VOC_Mail_List — 異常通知派送名單
    複合主鍵 (plantno, rpttype, empno)：同一廠區、同一報表類型、同一員工只能有一筆。

    JOB 的 GetMailList(rpttype, plantno, "TO"/"CC") 從此表取收件人寄送異常 Email。

    欄位語意：
      mailtype — 'TO'=主要收件人 / 'CC'=副本（CC 寄信時額外納入 GMO、環工部）
      mail     — 是否發 Email（1/0）
      SM       — 是否發簡訊（1/0）。新系統不做簡訊，欄位保留以忠實還原
      signgrp  — 是否為簽核群組（1/0）
      notesid  — Lotus Notes 收件識別（存檔格式：底線換空格、去 @aseglobal.com）
      Mail1/SM1 — mail/SM 的備份欄，供「全域暫停寄信」切換用（見 service toggle）
    """
    __tablename__ = 'VOC_Mail_List'

    plantno   = Column(String(50), primary_key=True)   # 廠區代號
    rpttype   = Column(String(50), primary_key=True)   # 報表類型（對應 VOC_Mail_Type.RptType）
    empno     = Column(String(50), primary_key=True)   # 員工工號（可為「群組…」「值班…」字串）

    empname   = Column(String(50))    # 員工姓名
    notesid   = Column(String(200))   # Notes ID（收件地址）
    cellphone = Column(String(20))    # 手機（簡訊用，09 開頭 10 碼）
    mailtype  = Column(String(10))    # 'TO' / 'CC'
    mail      = Column(SmallInteger, default=1)  # 是否發 Email
    SM        = Column(SmallInteger, default=0)  # 是否發簡訊
    signgrp   = Column(SmallInteger, default=0)  # 是否簽核群組
    Mail1     = Column(SmallInteger, default=1)  # mail 備份（暫停切換用）
    SM1       = Column(SmallInteger, default=0)  # SM 備份（暫停切換用）


class VocMailType(Base):
    """
    VOC_Mail_Type — 報表類型主檔
    typeid → RptType 對照，是新增派送名單時「報表類型」下拉的來源。
    已知值：水質異常、水Alert、含「保養」字樣者（保養類型會強制關簡訊、開簽核群組）等。
    """
    __tablename__ = 'VOC_Mail_Type'

    typeid  = Column(Integer, primary_key=True)
    RptType = Column(String(50))
