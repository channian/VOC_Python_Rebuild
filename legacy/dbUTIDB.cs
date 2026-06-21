using MTLibrary;

/// <summary>
/// dbUTIDB 的摘要描述
/// </summary>
public class dbUTIDB : MTDBbase<dbUTIDB>
{
	public dbUTIDB()
        : base((int)AppConfig.DataBaseCI.UTIDB)
	{

	}

    public void GetUserDept()
    {
        SqlParameterClear();
        SqlCommandText = "Select deptno From [UTIDB].[dbo].[employee] Where empno=@empno";
        SqlParameterAdd("@empno", AppConfig.Sess_UserEmpNo);
        AppConfig.Sess_UserDept = SqlExecuteScalarString();
    }
}