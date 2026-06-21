using System;
using System.Collections.Generic;
using System.Linq;
using System.Web;
using System.Web.UI;
using System.Web.UI.WebControls;

public partial class Base_master_ControlSiteMaster : MasterPage
{
    protected void Page_Load(object sender, EventArgs e)
    {
        spanUsername.InnerText = "您好, " + AppConfig.Sess_UserEmpName;
        btnBack.PostBackUrl = "~/Default.aspx";
        lbtnEditControl.PostBackUrl = "~/EditControl.aspx";
        lbtnMyApply.PostBackUrl = "~/MyApply.aspx";
        lbtnPlantApply.PostBackUrl = "~/PlantApply.aspx";

        bool HaveAcl = false;
        using (dbAclRights db = new dbAclRights())
            HaveAcl = db.Check權限(dbAclRights.使用者權限.廠區項目隔離抑制維護, dbAclRights.AclPermit._16執行);
        if (HaveAcl)
        {
            lbtnEditControl.Enabled = true;
            lbtnMyApply.Enabled = true;
            lbtnPlantApply.Enabled = true;
        }
        else
        {
            lbtnEditControl.Enabled = false;
            lbtnMyApply.Enabled = false;
            lbtnPlantApply.Enabled = true;
        }
    }
}
