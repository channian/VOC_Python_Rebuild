using MTLibrary;
using NPOI.HSSF.UserModel;
using System;
using System.Collections;
using System.Collections.Generic;
using System.Data;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Web;
using System.Web.UI;
using System.Web.UI.HtmlControls;
using System.Web.UI.WebControls;

public class BasePage : MTLibrary.Web.BasePage
{

    public BasePage()
    {
        Page.Load += Page_Load;
    }

    void Page_Load(object sender, EventArgs e)
    {
        if (!Page.IsPostBack)
        {
            string btname = this.GetType().BaseType.Name.ToUpper();
            bool haveLic = false;
            using (dbAclRights db = new dbAclRights())
            {
                switch (btname)
                {
                    case "ADMINCONTROL":
                        haveLic = db.Check權限(dbAclRights.使用者權限.系統管理員, dbAclRights.AclPermit._16執行);
                        break;
                    default:
                        //尚未管控權限的網頁
                        haveLic = true;
                        break;
                }
            }
            if (!haveLic)
                Response.Redirect(@"~/Lock.html");
        }
    }

    public void OpenWindow(string url, string target = "_blank")
    {
        AjaxClientScript(string.Format(
            "window.open('{0}','{1}');"
            , url, target));
    }

}

