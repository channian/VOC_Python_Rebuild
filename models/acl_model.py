from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, PrimaryKeyConstraint
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class SysAclRole(Base):
    """ 對應舊系統的系統角色定義表 """
    __tablename__ = 'sys_aclrole'
    roleid = Column(Integer, primary_key=True)
    rolename = Column(String(50))

class SysAclUserRole(Base):
    """ 使用者或部門被賦予的各廠區權限 (由 EditAclUser.aspx 管理) """
    __tablename__ = 'sys_acluserrole'
    
    # 根據 dbVOC.cs Insert 邏輯分析，這三個欄位構成唯一複合主鍵
    roleid = Column(Integer, primary_key=True)
    plantno = Column(String(50), primary_key=True)
    empno = Column(String(50), primary_key=True)
    
    stype = Column(String(10)) # 空, 水, ALL
    deptno = Column(String(50), nullable=True)

class SysAclRoleRights(Base):
    """ 定義每一個角色具備什麼權限 (位元運算) """
    __tablename__ = 'sys_aclrolerights'
    roleid = Column(Integer, primary_key=True)
    rightsid = Column(Integer, primary_key=True)
    allowrights = Column(Integer)  # 1查詢, 2修改, 4新增, 8刪除, 16執行

class VocTranlog(Base):
    """ 存放所有權限異動、修改廠區狀態等重要操作軌跡 """
    __tablename__ = 'VOC_tranlog'
    seqno = Column(Integer, primary_key=True, autoincrement=True) # 自增長流水號
    empno = Column(String(50))
    logtype = Column(String(10)) # "I"nsert, "U"pdate, "D"elete
    databefore = Column(String(500))
    dataafter = Column(String(500))
    cdatetime = Column(DateTime)
    remark = Column(String(500))
