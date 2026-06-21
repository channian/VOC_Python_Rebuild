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

public class MasterPage : MTLibrary.Web.MasterPage
{

    public MasterPage()
    {
    }

    public void OpenWindow(string url, string target = "_blank")
    {
        AjaxClientScript(string.Format(
            "window.open('{0}','{1}');"
            , url, target));
    }



}