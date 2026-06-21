using System;
using System.Collections.Generic;
using System.Linq;
using System.Web;
using System.Data;
using System.Data.SqlClient;
using System.Web.Configuration;
using MTLibrary;
using System.Collections;

public class dbAclRights : MTDBbase<dbAclRights>
{
    public dbAclRights()
        : base((int)AppConfig.DataBaseCI.VOC)
    {

    }

    public enum AclPermit
    {
        _1查詢 = 1,
        _2修改 = 2,
        _4新增 = 4,
        _8刪除 = 8,
        _16執行 = 16,
    };

    public enum 使用者權限
    {
        系統管理員 = 1,
        法規許可值與規格值維護 = 2,
        廠區項目隔離抑制維護 = 3,
        異常派報簡訊啟用 = 4,
        異常派報簡訊停用 = 5,
        派送名單維護 = 6,
        廠區項目隔離抑制查詢 = 7,
        隔離權限維護 = 8,
        QA手測值更新 = 9,
        部門權限維護 = 10,
        中水緊急通知 = 11,
        隔離時間修改 = 12
    };

    public int GetIsAdmin()
    {
        SqlParameterClear();
        SqlCommandText = "Select Count(*) " +
            "From [VOC].[dbo].[sys_acluserrole] R " +
            "Join [VOC].[dbo].[sys_aclrolerights] AR On R.roleid=AR.roleid " +
            "Where R.empno=@empno And AR.rightsid=@rightsid1 ";
        SqlParameterAdd("@empno", AppConfig.Sess_UserEmpNo);
        SqlParameterAdd("@rightsid1", (int)使用者權限.系統管理員);
        return SqlExecuteScalarInt32() > 0 ? 1 : 0;
    }

    public bool Check權限(使用者權限 rights, params AclPermit[] permits)
    {
        SqlParameterClear();
        SqlCommandText = "Select AR.allowrights " +
            "From [VOC].[dbo].[sys_acluserrole] R " +
            "Join [VOC].[dbo].[sys_aclrolerights] AR On R.roleid=AR.roleid " +
            "Where (R.empno=@empno Or R.deptno=@deptno) And (AR.rightsid=@rightsid Or AR.rightsid=@rightsid1) ";
        SqlParameterAdd("@empno", AppConfig.Sess_UserEmpNo);
        SqlParameterAdd("@deptno", AppConfig.Sess_UserDept);
        SqlParameterAdd("@rightsid", (int)rights);
        SqlParameterAdd("@rightsid1", (int)使用者權限.系統管理員);
        DataTable dtb = SqlFillDT();
        foreach (DataRow row in dtb.Rows)
        {
            if (permits.Contains((AclPermit)MTDBbase.ToInt32(row["allowrights"])))
                return true;
        }
        return false;
    }

    public int Check權限(使用者權限 rights)
    {
        SqlParameterClear();
        SqlCommandText = "Select Max(AR.roleid) " +
            "From [VOC].[dbo].[sys_acluserrole] R " +
            "Join [VOC].[dbo].[sys_aclrolerights] AR On R.roleid=AR.roleid " +
            "Where (R.empno=@empno Or R.deptno=@deptno) And (AR.rightsid=@rightsid Or AR.rightsid=@rightsid1) ";
        SqlParameterAdd("@empno", AppConfig.Sess_UserEmpNo);
        SqlParameterAdd("@deptno", AppConfig.Sess_UserDept);
        SqlParameterAdd("@rightsid", (int)rights);
        SqlParameterAdd("@rightsid1", (int)使用者權限.系統管理員);
        return SqlExecuteScalarInt32(0);
    }
}