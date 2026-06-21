using System;
using System.Collections.Generic;
using System.Linq;
using System.Web;
using System.Web.UI;
using System.Web.UI.WebControls;

public partial class Base_master_SpecSiteMaster : MasterPage
{
    protected void Page_Load(object sender, EventArgs e)
    {
        spanUsername.InnerText = "您好, " + AppConfig.Sess_UserEmpName;
        btnBack.PostBackUrl = "~/Default.aspx";
        lbtnEditSPEC.PostBackUrl = "~/EditSPEC.aspx";
        lbtnApplySPEC.PostBackUrl = "~/ApplySPEC.aspx";

        bool HaveAcl = false;
        using (dbAclRights db = new dbAclRights())
            HaveAcl = db.Check權限(dbAclRights.使用者權限.法規許可值與規格值維護, dbAclRights.AclPermit._16執行);
        if (HaveAcl)
        {
            //lbtnEditSPEC.Enabled = true;
            //lbtnApplySPEC.Enabled = true;
            lbtnEditSPEC.Enabled = false;
            lbtnApplySPEC.Enabled = false;
        }
        else
        {
            lbtnEditSPEC.Enabled = false;
            lbtnApplySPEC.Enabled = false;
        }
    }
}
