from sqlalchemy import Column, String, Integer
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class VocSpec(Base):
    """ 廠區法規許可與規格參數表 (VOC_SPEC) """
    __tablename__ = 'VOC_SPEC'
    
    # 複合主鍵: 廠區與項目不能重複
    plantno = Column(String(50), primary_key=True)
    item = Column(String(50), primary_key=True)
    
    LAW = Column(String(50))   # 法規許可值
    OOS = Column(String(50))   # OOS 規格
    OOC = Column(String(50))   # OOC 規格
    alert = Column(String(50)) # Alert 預警值
    
    source = Column(Integer)   # 對應 VOC_source 的來源 ID
    status = Column(Integer)   # 狀態，原系統為 1
    tagname = Column(String(100)) # 對應底層串接的標籤名稱 (格式常為 plantno_item)

class VocPlant(Base):
    """ 廠區對照表 """
    __tablename__ = 'VOC_plant'
    plantid = Column(Integer, primary_key=True)
    plantno = Column(String(50))
    isShow = Column(Integer)

class VocItem(Base):
    """ 檢測項目對照表 """
    __tablename__ = 'VOC_item'
    itemid = Column(Integer, primary_key=True)
    item = Column(String(50))
    unit = Column(String(50))

class VocSource(Base):
    """ 資料來源對照表 (SCADA / CIM / QA手動) """
    __tablename__ = 'VOC_source'
    sourceid = Column(Integer, primary_key=True)
    source = Column(String(50))
