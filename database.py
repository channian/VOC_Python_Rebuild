from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from config import settings

# 宣告基礎模型，供系統內的所有 SQLAlchemy ORM 模組繼承使用
Base = declarative_base()

# ==========================================
# 1. VOC 主要業務資料庫連線實體
# ==========================================
voc_engine = create_engine(settings.DB_VOC_URL, echo=settings.DEBUG)
VocSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=voc_engine)

def get_voc_db():
    """ FastAPI Dependency: 取得 VOC 資料庫 session """
    db = VocSessionLocal()
    try:
        yield db
    finally:
        db.close()

# ==========================================
# 2. SignFlow 簽核資料庫連線實體
# ==========================================
signflow_engine = create_engine(settings.DB_SIGNFLOW_URL, echo=settings.DEBUG)
SignFlowSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=signflow_engine)

def get_signflow_db():
    """ FastAPI Dependency: 取得 SignFlow 簽核系統資料庫 session """
    db = SignFlowSessionLocal()
    try:
        yield db
    finally:
        db.close()

# ==========================================
# 3. UTIDB 公用資料庫連線實體
# ==========================================
utidb_engine = create_engine(settings.DB_UTIDB_URL, echo=settings.DEBUG)
UtidbSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=utidb_engine)

def get_utidb_db():
    """ FastAPI Dependency: 取得廠區公用資料庫 session """
    db = UtidbSessionLocal()
    try:
        yield db
    finally:
        db.close()

# ==========================================
# 4. CIM Oracle 資料庫連線實體 (只提供讀取資料功能)
# ==========================================
cim_engine = create_engine(settings.DB_CIM_URL, echo=settings.DEBUG)
CimSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cim_engine)

def get_cim_db():
    """ FastAPI Dependency: 取得廠務 CIM (Oracle) 唯讀 session """
    db = CimSessionLocal()
    try:
        yield db
    finally:
        db.close()
