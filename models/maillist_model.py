from sqlalchemy import Column, String, Integer, SmallInteger
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class VocMailList(Base):
    """
    VOC_Mail_List — 異常通知派送名單
    JOB 的 GetMailList(plantno, "TO"/"CC") 從此表取收件人，寄送異常 Email。
    mailtype: 'TO'=主要收件人, 'CC'=副本收件人
    """
    __tablename__ = 'VOC_Mail_List'

    seqno    = Column(Integer, primary_key=True, autoincrement=True)
    plantno  = Column(String(50))
    empno    = Column(String(50))
    email    = Column(String(200))
    mailtype = Column(String(10))    # 'TO' or 'CC'
    isEnable = Column(SmallInteger, default=1)
