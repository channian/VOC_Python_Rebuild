from sqlalchemy import Column, String, Integer, DateTime, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class VocCloseCtl(Base):
    """ 廠區隔離申請主檔 """
    __tablename__ = 'VOC_closectl'
    
    ccid = Column(Integer, primary_key=True, autoincrement=True)
    ttypeid = Column(Integer)     # 申請類別 (1: 新增, 2: 修改等)
    ccno = Column(String(50))     # 申請單號 (yyyyMMdd + 流水號)
    plantid = Column(Integer)     # 申請廠區ID
    
    mdfdesc = Column(String(500)) # 申請原因/描述
    stime = Column(DateTime)      # 隔離開始時間
    etime = Column(DateTime)      # 隔離結束時間
    remark = Column(String(500))  # 備註
    
    cempname = Column(String(50)) # 申請人姓名
    cempno = Column(String(50))   # 申請人工號
    ctime = Column(DateTime)      # 建立時間
    
    flowid = Column(Integer, nullable=True) # 簽核流程ID
    fstatusid = Column(Integer)             # 簽核狀態 (例如待簽核/已核准)
    
    del_flag = Column('del', Integer, default=0) # 軟刪除註記
    delclerk = Column(String(50), nullable=True) 
    orgccid = Column(Integer, nullable=True)     # 原申請單號 (供展延/修改對照參考)

class VocCloseCtlList(Base):
    """ 廠區隔離申請明細檔 (包含需要隔離哪些 Tag) """
    __tablename__ = 'VOC_closectl_list'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    ccid = Column(Integer, ForeignKey('VOC_closectl.ccid'))
    plantno = Column(String(50))
    item = Column(String(50))
    sourceid = Column(String(50)) # CIM / WebSCADA 來源
