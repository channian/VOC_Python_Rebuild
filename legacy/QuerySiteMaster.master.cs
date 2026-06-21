using MTLibrary;
using System;
using System.Collections.Generic;
using System.Drawing;
using System.Linq;
using System.Web;
using System.Web.UI;
using System.Web.UI.WebControls;

public partial class Base_master_QuerySiteMaster : MasterPage
{
    protected void Page_Load(object sender, EventArgs e)
    {
        spanUsername.InnerText = "您好, " + AppConfig.Sess_UserEmpName;
    }
}
