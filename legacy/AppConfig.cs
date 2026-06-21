using MTLibrary;
using System;
using System.Collections.Generic;
using System.DirectoryServices;
using System.Linq;
using System.Web;
using System.Web.UI;
using MTLibrary.Web;

public class AppConfig
{
    public enum DataBaseCI
    {
        VOC = 1,
        UTIDB = 2,
    };

    public AppConfig()
    {

    }

    public static string Sess_UserEmpNo
    {
        get { return SessState.GetString("$$Sess_UserEmpNo"); }
        set { SessState.Set("$$Sess_UserEmpNo", value); }
    }

    public static string Sess_UserEmpName
    {
        get { return SessState.GetString("$$Sess_UserEmpName"); }
        set { SessState.Set("$$Sess_UserEmpName", value); }
    }

    public static int Sess_User職位ID
    {
        get { return MTDBbase.ToInt32(SessState.GetString("$$Sess_User職位ID")); }
        set { SessState.Set("$$Sess_User職位ID", value); }
    }

    public static int Sess_User員工ID
    {
        get { return MTDBbase.ToInt32(SessState.GetString("$$Sess_User員工ID")); }
        set { SessState.Set("$$Sess_User員工ID", value); }
    }

    public static int Sess_IsAdmin
    {
        get { return SessState.GetInt32("$$Sess_IsAdmin"); }
        set { SessState.Set("$$Sess_IsAdmin", value); }
    }

    public static string Sess_UserDept
    {
        get { return SessState.GetString("$$Sess_UserDept"); }
        set { SessState.Set("$$Sess_UserDept", value); }
    }
}