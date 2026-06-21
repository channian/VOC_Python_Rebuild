using System;
using System.Collections.Generic;
using System.Linq;
using System.Web;
using System.Web.UI;
using System.Web.UI.WebControls;

public partial class _Default : System.Web.UI.Page
{
    protected void Page_Load(object sender, EventArgs e)
    {
        using (dbUTIDB db = new dbUTIDB())
            db.GetUserDept();

        using (dbVOC db = new dbVOC())
        {
            if (db.Check登入權限() > 0)
                Response.Redirect("Home.aspx");
            else
                lbMsg.Text = "你沒有系統使用權限!";
        }
    }
}