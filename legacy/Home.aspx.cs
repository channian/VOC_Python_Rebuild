using MTLibrary;
using System;
using System.Collections;
using System.Collections.Generic;
using System.Data;
using System.Linq;
using System.Web;
using System.Web.UI;
using System.Web.UI.WebControls;
using System.Drawing;

public partial class Home : BasePage
{
    public DataTable _View_VOCDT
    {
        get { return ViewState["VOCDT"] as DataTable; }
        set { ViewState["VOCDT"] = value; }
    }

    protected void Page_Load(object sender, EventArgs e)
    {
        if (!Page.IsPostBack)
        {
            btnEditSPEC.PostBackUrl = "~/EditSPEC.aspx";
            btnEditControl.PostBackUrl = "~/PlantApply.aspx";
            btnEditMailList.PostBackUrl = "~/EditMailList.aspx";
            btnEditAclUser.PostBackUrl = "~/EditAclUser.aspx";
            btnQuery.PostBackUrl = "~/VOChistory.aspx";
            btnReport.PostBackUrl = "~/VOCreport.aspx";
            btnEditQA.PostBackUrl = "~/EditQA.aspx";
            btnEditDeptList.PostBackUrl = "~/EditDeptList.aspx";
            btnReason.PostBackUrl = "~/VOCreason.aspx";
            btnRainGutter.PostBackUrl = "~/RainGutter.aspx";
            btnWaterUrgent.PostBackUrl = "~/WaterUrgent.aspx";
            btnControlTime.PostBackUrl = "~/ControlTime.aspx";

            //using (dbUTIDB db = new dbUTIDB())
            //    db.GetUserDept(AppConfig.Sess_UserEmpNo);

            bool HaveAcl = false;

            using (dbAclRights db = new dbAclRights())
                HaveAcl = db.Check權限(dbAclRights.使用者權限.法規許可值與規格值維護, dbAclRights.AclPermit._16執行);
            SetCtrlVisible(new Control[] { btnEditSPEC }, HaveAcl);

            HaveAcl = false;

            using (dbAclRights db = new dbAclRights())
            {
                HaveAcl = db.Check權限(dbAclRights.使用者權限.廠區項目隔離抑制維護, dbAclRights.AclPermit._16執行);
                SetCtrlVisible(new Control[] { btnEditControl }, HaveAcl);

                if (!HaveAcl)
                {
                    HaveAcl = db.Check權限(dbAclRights.使用者權限.廠區項目隔離抑制查詢, dbAclRights.AclPermit._1查詢);
                    SetCtrlVisible(new Control[] { btnEditControl }, HaveAcl);
                }
            }

            HaveAcl = false;

            using (dbVOC db = new dbVOC())
            {
                if (db.CheckStatus())
                {
                    using (dbAclRights db1 = new dbAclRights())
                        HaveAcl = db1.Check權限(dbAclRights.使用者權限.異常派報簡訊啟用, dbAclRights.AclPermit._16執行);
                    SetCtrlVisible(new Control[] { btnMail啟用 }, HaveAcl);
                    SetCtrlVisible(new Control[] { btnMail停用 }, false);
                }
                else
                {
                    using (dbAclRights db1 = new dbAclRights())
                        HaveAcl = db1.Check權限(dbAclRights.使用者權限.異常派報簡訊停用, dbAclRights.AclPermit._16執行);
                    SetCtrlVisible(new Control[] { btnMail停用 }, HaveAcl);
                    SetCtrlVisible(new Control[] { btnMail啟用 }, false);
                }
            }

            HaveAcl = false;

            using (dbAclRights db = new dbAclRights())
                HaveAcl = db.Check權限(dbAclRights.使用者權限.派送名單維護, dbAclRights.AclPermit._16執行);
            SetCtrlVisible(new Control[] { btnEditMailList }, HaveAcl);

            HaveAcl = false;

            using (dbAclRights db = new dbAclRights())
                HaveAcl = db.Check權限(dbAclRights.使用者權限.隔離權限維護, dbAclRights.AclPermit._16執行);
            SetCtrlVisible(new Control[] { btnEditAclUser }, HaveAcl);

            SetCtrlVisible(new Control[] { btnQuery, btnReport, btnReason }, true);

            HaveAcl = false;

            using (dbAclRights db = new dbAclRights())
                HaveAcl = db.Check權限(dbAclRights.使用者權限.QA手測值更新, dbAclRights.AclPermit._16執行);
            SetCtrlVisible(new Control[] { btnEditQA }, HaveAcl);

            HaveAcl = false;

            using (dbAclRights db = new dbAclRights())
                HaveAcl = db.Check權限(dbAclRights.使用者權限.部門權限維護, dbAclRights.AclPermit._16執行);
            SetCtrlVisible(new Control[] { btnEditDeptList }, HaveAcl);

            HaveAcl = false;

            string PlantID;
            using (dbVOC db = new dbVOC()) PlantID = db.GetPlantID();
            if (PlantID.IndexOf("29") > -1) HaveAcl = true;
            else
            {
                int flg = 0;
                string[] ArrPlantID = PlantID.Split(',');
                for (int i = 0; i < ArrPlantID.Length; i++)
                {
                    //K1/K5/K7/K9/K11/K16
                    if (ArrPlantID[i] == "31" || ArrPlantID[i] == "3" || ArrPlantID[i] == "4" || ArrPlantID[i] == "6" ||
                        ArrPlantID[i] == "8" || ArrPlantID[i] == "16") flg = 1;
                }
                if (flg == 1) HaveAcl = true;
            }

            SetCtrlVisible(new Control[] { btnRainGutter }, HaveAcl);

            HaveAcl = false;

            using (dbAclRights db = new dbAclRights())
                HaveAcl = db.Check權限(dbAclRights.使用者權限.中水緊急通知, dbAclRights.AclPermit._16執行);
            SetCtrlVisible(new Control[] { btnWaterUrgent }, HaveAcl);

            HaveAcl = false;

            using (dbAclRights db = new dbAclRights())
                HaveAcl = db.Check權限(dbAclRights.使用者權限.隔離時間修改, dbAclRights.AclPermit._16執行);
            SetCtrlVisible(new Control[] { btnControlTime }, HaveAcl);

            GetUpdateTime(sender, e);
            BindGrid();
        }
    }

    protected void btnMail啟用_Click(object sender, EventArgs e)
    {
        bool HaveAcl = false;

        using (dbVOC db = new dbVOC())
        {
            db.Mail啟用();
            if (db.CheckStatus())   //停用
            {
                using (dbAclRights db1 = new dbAclRights())
                    HaveAcl = db1.Check權限(dbAclRights.使用者權限.異常派報簡訊啟用, dbAclRights.AclPermit._16執行);
                SetCtrlVisible(new Control[] { btnMail啟用 }, HaveAcl);
                SetCtrlVisible(new Control[] { btnMail停用 }, false);
            }
            else
            {
                using (dbAclRights db1 = new dbAclRights())
                    HaveAcl = db1.Check權限(dbAclRights.使用者權限.異常派報簡訊停用, dbAclRights.AclPermit._16執行);
                SetCtrlVisible(new Control[] { btnMail停用 }, HaveAcl);
                SetCtrlVisible(new Control[] { btnMail啟用 }, false);
            }
        }

        Response.Redirect(ResolveClientUrl("~/Default.aspx"));
    }

    protected void btnMail停用_Click(object sender, EventArgs e)
    {
        bool HaveAcl = false;

        using (dbVOC db = new dbVOC())
        {
            db.Mail停用();
            if (db.CheckStatus())   //停用
            {
                using (dbAclRights db1 = new dbAclRights())
                    HaveAcl = db1.Check權限(dbAclRights.使用者權限.異常派報簡訊啟用, dbAclRights.AclPermit._16執行);
                SetCtrlVisible(new Control[] { btnMail啟用 }, HaveAcl);
                SetCtrlVisible(new Control[] { btnMail停用 }, false);
            }
            else
            {
                using (dbAclRights db1 = new dbAclRights())
                    HaveAcl = db1.Check權限(dbAclRights.使用者權限.異常派報簡訊停用, dbAclRights.AclPermit._16執行);
                SetCtrlVisible(new Control[] { btnMail停用 }, HaveAcl);
                SetCtrlVisible(new Control[] { btnMail啟用 }, false);
            }
        }

        Response.Redirect(ResolveClientUrl("~/Default.aspx"));
    }

    private void GetUpdateTime(object sender, EventArgs e)
    {
        using (dbVOC db = new dbVOC())
            lbNowtime.Text = string.Format("資料更新時間：{0:yyyy/MM/dd HH:mm}", db.Get資料更新時間());
    }

    private DataTable GetData()
    {
        DataTable dtb0, dtb;
        using (dbVOC db = new dbVOC())
        {
            dtb0 = db.List隔離廠區項目();
            if (dtb0.Rows.Count > 0)
            {
                for (int i = 0; i < dtb0.Rows.Count; i++)
                {
                    db.Update隔離廠區項目(dtb0.Rows[i]);
                }
            }
            dtb = db.ListVOC();
        }
        return dtb;
    }

    protected void BindGrid()
    {
        if (_View_VOCDT == null)
            _View_VOCDT = GetData();
        gvVOCList.SetDataSource(_View_VOCDT);
    }

    protected void gvVOCList_PageIndexChanging(object sender, GridViewPageEventArgs e)
    {
        gvVOCList.PageIndex = e.NewPageIndex;
        BindGrid();
    }

    protected void gvVOCList_RowCreated(object sender, GridViewRowEventArgs e)
    {
        //判断是否為表頭行
        if (e.Row.RowType == DataControlRowType.Header)
        {
            //取表頭行的所有欄位
            TableCellCollection Header = e.Row.Cells;
            //清除表頭
            Header.Clear();

            //新增第一行表頭欄位並合併
            Header.Add(new TableHeaderCell());
            Header[0].RowSpan = 2;
            Header[0].Text = "廠區";
            Header[0].Width = Unit.Pixel(100);

            Header.Add(new TableHeaderCell());
            Header[1].RowSpan = 2;
            Header[1].Text = "項目";
            Header[1].Width = Unit.Pixel(80);

            Header.Add(new TableHeaderCell());
            Header[2].RowSpan = 2;
            Header[2].Text = "單位";
            Header[2].Width = Unit.Pixel(80);

            Header.Add(new TableHeaderCell());
            Header[3].RowSpan = 2;
            Header[3].BorderWidth = 2;
            Header[3].Text = "法規許可值";
            Header[3].Width = Unit.Pixel(110);

            Header.Add(new TableHeaderCell());
            Header[4].ColumnSpan = 2;
            Header[4].BorderWidth = 2;
            Header[4].Text = "SPEC(三階文件)";

            Header.Add(new TableHeaderCell());
            Header[5].RowSpan = 2;
            Header[5].BorderWidth = 2;
            Header[5].Text = "Alert";
            Header[5].Width = Unit.Pixel(100);

            Header.Add(new TableHeaderCell());
            Header[6].ColumnSpan = 3;
            Header[6].BorderWidth = 2;
            Header[6].Text = "SCADA";

            Header.Add(new TableHeaderCell());
            Header[7].ColumnSpan = 2;
            Header[7].BorderWidth = 2;
            Header[7].Text = "CWMS";

            Header.Add(new TableHeaderCell());
            Header[8].ColumnSpan = 2;
            Header[8].Text = "Web";

            Header.Add(new TableHeaderCell());
            Header[9].RowSpan = 3;
            Header[9].Text = "歷史曲線";
            Header[9].Width = Unit.Pixel(110);

            Header.Add(new TableHeaderCell());
            Header[10].RowSpan = 3;
            Header[10].Text = "備註</th></tr><tr>";
            Header[10].Width = Unit.Pixel(80);

            //新增第二行表頭欄位
            Header.Add(new TableHeaderCell());
            Header[11].BorderWidth = 2;
            Header[11].Text = "OOS";
            Header[11].Width = Unit.Pixel(100);
            Header[11].BackColor = Color.LightSkyBlue;
            Header[11].ForeColor = Color.DarkBlue;

            Header.Add(new TableHeaderCell());
            Header[12].BorderWidth = 2;
            Header[12].Text = "OOC";
            Header[12].Width = Unit.Pixel(100);
            Header[12].BackColor = Color.LightSkyBlue;
            Header[12].ForeColor = Color.DarkBlue;

            Header.Add(new TableHeaderCell());
            Header[13].BorderWidth = 2;
            Header[13].Text = "OOS-HH";
            Header[13].Width = Unit.Pixel(100);
            Header[13].BackColor = Color.LightSkyBlue;
            Header[13].ForeColor = Color.DarkBlue;

            Header.Add(new TableHeaderCell());
            Header[14].BorderWidth = 2;
            Header[14].Text = "OOC-H";
            Header[14].Width = Unit.Pixel(100);
            Header[14].BackColor = Color.LightSkyBlue;
            Header[14].ForeColor = Color.DarkBlue;

            Header.Add(new TableHeaderCell());
            Header[15].BorderWidth = 2;
            Header[15].Text = "Alert";
            Header[15].Width = Unit.Pixel(100);
            Header[15].BackColor = Color.LightSkyBlue;
            Header[15].ForeColor = Color.DarkBlue;

            Header.Add(new TableHeaderCell());
            Header[16].BorderWidth = 2;
            Header[16].Text = "OOS-HH";
            Header[16].Width = Unit.Pixel(100);
            Header[16].BackColor = Color.LightSkyBlue;
            Header[16].ForeColor = Color.DarkBlue;

            Header.Add(new TableHeaderCell());
            Header[17].BorderWidth = 2;
            Header[17].Text = "OOC-H";
            Header[17].Width = Unit.Pixel(100);
            Header[17].BackColor = Color.LightSkyBlue;
            Header[17].ForeColor = Color.DarkBlue;

            Header.Add(new TableHeaderCell());
            Header[18].Text = "最新讀值";
            Header[18].Width = Unit.Pixel(135);
            Header[18].BackColor = Color.LightSkyBlue;
            Header[18].ForeColor = Color.DarkBlue;

            Header.Add(new TableHeaderCell());
            Header[19].RowSpan = 2;
            Header[19].Text = "狀態</th></tr><tr>";
            Header[19].Width = Unit.Pixel(5);
            Header[19].BackColor = Color.LightSkyBlue;
            Header[19].ForeColor = Color.DarkBlue;

            //新增第三行表頭欄位
            Header.Add(new TableHeaderCell());
            Header[20].ColumnSpan = 3;
            Header[20].Text = "管理權責";
            Header[20].Width = Unit.Pixel(75);
            Header[20].BackColor = Color.AliceBlue;

            Header.Add(new TableHeaderCell());
            Header[21].ColumnSpan = 4;
            Header[21].Text = "4K30";
            Header[21].Width = Unit.Pixel(75);
            Header[21].BackColor = Color.LightSalmon;

            Header.Add(new TableHeaderCell());
            Header[22].ColumnSpan = 6;
            Header[22].Text = "Site FAC";
            Header[22].Width = Unit.Pixel(75);
            Header[22].BackColor = Color.LightSalmon;
        }
    }

    protected void gvVOCList_PreRender(object sender, EventArgs e)
    {
        GridViewRow gvRow;
        GridViewRow gvNextRow;

        gvVOCList.Columns[17].Visible = true;

        gvRow = gvVOCList.Rows[gvVOCList.Rows.Count - 1];
        GetData(gvRow);

        for (int i = 3; i < 13; i++)
        {
            if (i == 3)
                gvRow.Cells[i].CssClass = gvRow.Cells[i].CssClass + " border-left border-bottom";
            else if (i == 7 || i == 10 || i == 12)
                gvRow.Cells[i].CssClass = gvRow.Cells[i].CssClass + " border-right border-bottom";
            else
                gvRow.Cells[i].CssClass = gvRow.Cells[i].CssClass + " border-bottom";
        }

        for (int i = gvVOCList.Rows.Count - 2; i >= 0; i--)
        {
            gvRow = gvVOCList.Rows[i];
            gvNextRow = gvVOCList.Rows[i + 1];

            if (gvRow.Cells[0].Text == gvNextRow.Cells[0].Text)
            {
                if (gvNextRow.Cells[0].RowSpan < 2)
                {
                    gvRow.Cells[0].RowSpan = 2;
                    gvNextRow.Cells[0].Visible = false;
                    gvRow.Cells[0].BackColor = Color.White;
                }
                else
                {
                    gvRow.Cells[0].RowSpan = gvNextRow.Cells[0].RowSpan + 1;
                    gvNextRow.Cells[0].Visible = false;
                    gvRow.Cells[0].BackColor = Color.White;
                }
            }

            GetData(gvRow);
        }

        gvVOCList.Columns[17].Visible = false;
    }

    private string ChangeData(string V, int D)
    {
        string S = (D == 0 ? "#0" : "#0.00");
        string X = "";
        string[] N = V.Split('-');

        if (N.Length < 2 || N[0] == "")
            return MTDBbase.ToDecimal(V).ToString(S);
        else
        {
            for (int i = 0; i < N.Length; i++)
            {
                X = X + (i == 0 ? "" : "-") + MTDBbase.ToDecimal(N[i]).ToString(S);
            }
            return X;
        }
    }

    private string CheckData(string[] V)
    {
        string X = "";
        if (V.Length == 2)
        {
            for (int i = 0; i < V.Length; i++)
            {
                int idx = V[i].IndexOf('.');
                if (idx > 0)
                {
                    int j = V[i].Length - 1;
                    for (; j >= 0; j--)
                    {
                        string S = V[i].Substring(j, 1);
                        if ((S != "0" && S != ".") || j < idx) break;
                    }

                    V[i] = V[i].Substring(0, j + 1);
                }
                X = X + (i == 0 ? "" : "-") + V[i];
            }
            return X;
        }
        else
            return V[0];
    }

    private void GetData(GridViewRow gvRow)
    {
        System.Web.UI.WebControls.Image light;
        string sImg;
        string sDate = "";
        string remark = gvRow.Cells[16].Text.Substring(0, gvRow.Cells[16].Text.IndexOf("|"));
        string source = gvRow.Cells[16].Text.Substring(gvRow.Cells[16].Text.IndexOf("|") + 1, 1);
        string emptycell = gvRow.Cells[17].Text;

        gvRow.Cells[0].Width = Unit.Pixel(90);  //廠區
        gvRow.Cells[1].Width = Unit.Pixel(118); //項目
        gvRow.Cells[2].Width = Unit.Pixel(80);  //單位
        gvRow.Cells[3].Width = Unit.Pixel(85);  //法規許可值
        gvRow.Cells[4].Width = Unit.Pixel(80);  //SPEC_OOS
        gvRow.Cells[5].Width = Unit.Pixel(80);  //SPEC_OOC
        gvRow.Cells[6].Width = Unit.Pixel(78);  //Alert
        gvRow.Cells[7].Width = Unit.Pixel(78);  //Recv
        gvRow.Cells[8].Width = Unit.Pixel(80);  //SCADA_OOS-HH
        gvRow.Cells[9].Width = Unit.Pixel(80);  //SCADA_OOC-H
        gvRow.Cells[10].Width = Unit.Pixel(80);  //SCADA_Alert
        gvRow.Cells[11].Width = Unit.Pixel(77); //CWMS_OOS-HH
        gvRow.Cells[12].Width = Unit.Pixel(75); //CWMS_OOC-H
        gvRow.Cells[13].Width = Unit.Pixel(57); //最新讀值
        gvRow.Cells[14].Width = Unit.Pixel(32); //狀態
        gvRow.Cells[15].Width = Unit.Pixel(60); //歷史曲線
        gvRow.Cells[16].Text = remark;
        if (gvRow.Cells[8].Text == "保養中" || gvRow.Cells[11].Text == "保養中" || gvRow.Cells[8].Text == "-")
        {
            using (dbVOC db = new dbVOC())
                sDate = db.Get隔離廠區項目區間(gvRow.Cells[0].Text, gvRow.Cells[1].Text);
        }
        if (sDate != "")
        {
            gvRow.Cells[16].Text = gvRow.Cells[16].Text.Replace("斷訊", "");
            gvRow.Cells[16].Text += (remark.Replace("斷訊", "") == "" ? "" : ";") + sDate;
        }
        gvRow.Cells[16].Width = Unit.Pixel(47); //備註
        gvRow.Cells[16].Wrap = true;

        //項目欄位底色
        if (gvRow.Cells[1].Text.IndexOf("VOC") > -1)
        {
            gvRow.Cells[1].BackColor = Color.YellowGreen;
            gvRow.Cells[2].BackColor = Color.YellowGreen;
        }
        else if (source == "2") //CWMS
        {
            gvRow.Cells[1].BackColor = Color.Orange;
            gvRow.Cells[2].BackColor = Color.Orange;
        }
        else
        {
            gvRow.Cells[1].BackColor = Color.DodgerBlue;
            gvRow.Cells[1].ForeColor = Color.White;
            gvRow.Cells[2].BackColor = Color.DodgerBlue;
            gvRow.Cells[2].ForeColor = Color.White;
        }

        gvRow.Cells[3].BackColor = Color.LightYellow;

        sImg = "G";

        for (int i = 3; i < 14; i++)
        {
            gvRow.Cells[i].Text = gvRow.Cells[i].Text.Replace("&nbsp;", "").Replace(",", "");

            //if (gvRow.Cells[15].Text.IndexOf("斷訊") > -1 && (gvRow.Cells[i].Text == "" || gvRow.Cells[i].Text == "-") && i > 6 && i < 10)
            //    gvRow.Cells[i].Text = "斷訊";

            //統一數字欄位到小數二位, 第三位四捨五入; 導電度 & 日累積水量 四捨五入到整數
            if (gvRow.Cells[i].Text != "" && gvRow.Cells[i].Text != "-" &&
                gvRow.Cells[i].Text != "N/A" && gvRow.Cells[i].Text != "建置中" &&
                gvRow.Cells[i].Text != "斷訊" && gvRow.Cells[i].Text != "異常" && gvRow.Cells[i].Text != "保養中")
            {
                if (gvRow.Cells[1].Text == "導電度" || gvRow.Cells[1].Text.IndexOf("日累積水量") > -1)
                    gvRow.Cells[i].Text = ChangeData(gvRow.Cells[i].Text, 0);
                else gvRow.Cells[i].Text = ChangeData(gvRow.Cells[i].Text, 2);
            }

            if (gvRow.Cells[i].Text == "-" || gvRow.Cells[i].Text == "" ||
                gvRow.Cells[i].Text == "N/A" || gvRow.Cells[i].Text == "建置中" ||
                gvRow.Cells[i].Text == "斷訊" || gvRow.Cells[i].Text == "異常")
            {
                ////將數字欄位'-', 改為'N/A'; 空白欄位改為'建置中'
                //if (source == "1" && i > 6 && i < 10 && gvRow.Cells[i].Text == "-")
                //{
                //    gvRow.Cells[i].Text = "建置中";
                //}
                //else
                //{
                //    if (gvRow.Cells[i].Text == "-") gvRow.Cells[i].Text = "N/A";
                //}

                if (i > 3 && i < 13)
                {
                    if (gvRow.Cells[i].Text == "")
                    {
                        if (emptycell.IndexOf(i + ";") > -1)
                        {
                            if (i == 7 || i == 10 || i == 12)
                                gvRow.Cells[i].CssClass = "border-slash border-right";
                            else
                                gvRow.Cells[i].CssClass = "border-slash";
                        }
                        else
                        {
                            gvRow.Cells[i].Text = "異常";
                            gvRow.Cells[i].ForeColor = Color.Red;
                            gvRow.Cells[i].BorderColor = Color.Black;
                        }
                    }
                    else if (gvRow.Cells[i].Text == "斷訊" || gvRow.Cells[i].Text == "異常")
                    {
                        gvRow.Cells[i].ForeColor = Color.Red;
                        gvRow.Cells[i].BorderColor = Color.Black;
                    }
                    else
                    {
                        gvRow.Cells[i].BackColor = Color.Gray;
                        gvRow.Cells[i].ForeColor = Color.White;
                    }
                }

                if (i == 13 && gvRow.Cells[i].Text == "斷訊")
                {
                    gvRow.Cells[i].ForeColor = Color.Red;
                    gvRow.Cells[i].BorderColor = Color.Black;
                }
            }
        }

        //即時值欄位底色
        if (source == "1")  //SCADA
            gvRow.Cells[13].BackColor = Color.Cornsilk;
        else if (source == "2") //CWMS
            gvRow.Cells[13].BackColor = Color.Orange;
        else //QA
            gvRow.Cells[13].BackColor = Color.LightGray;

        if (gvRow.Cells[8].Text != "" || gvRow.Cells[9].Text != "" || gvRow.Cells[10].Text != "" ||
            gvRow.Cells[11].Text != "" || gvRow.Cells[12].Text != "" || gvRow.Cells[13].Text != "")
        {
            //紅燈條件：最新讀值>=OOS
            //橘燈條件：OOC<=最新讀值<OOS 或 SCADA與CWMS之管制值<>SPEC
            //黃燈條件：Alert<最新讀值<OOC 或 最新讀值＞允收值
            //綠燈條件：正常狀態
            if ((gvRow.Cells[1].Text.IndexOf("pH") < 0 && gvRow.Cells[1].Text != "溫度") || 
                (gvRow.Cells[1].Text == "溫度" && gvRow.Cells[0].Text != "K21"))
            {
                string sOOS = gvRow.Cells[4].Text;
                string sOOC = gvRow.Cells[5].Text;
                string sAlert = gvRow.Cells[6].Text;
                string sRecv = gvRow.Cells[7].Text;
                string sOOS_HH = gvRow.Cells[8].Text;
                string sOOC_H = gvRow.Cells[9].Text;
                string sAlert1 = gvRow.Cells[10].Text;
                string sOOS_HH1 = gvRow.Cells[11].Text;
                string sOOC_H1 = gvRow.Cells[12].Text;
                string sWEB = gvRow.Cells[13].Text;

                //if ((sOOS_HH == "-" || sOOS_HH == "N/A" || sOOS_HH == "建置中" || sOOS_HH == "斷訊" || sOOS_HH == "異常") &&
                //    (sOOC_H == "-" || sOOC_H == "N/A" || sOOC_H == "建置中" || sOOC_H == "斷訊" || sOOC_H == "異常") &&
                //    (sAlert1 == "-" || sAlert1 == "N/A" || sAlert1 == "建置中" || sAlert1 == "斷訊" || sAlert1 == "異常") && sWEB != "")
                if ((sOOS_HH == "-" || sOOS_HH == "N/A" || sOOS_HH == "建置中" || sOOS_HH == "異常") &&
                    (sOOC_H == "-" || sOOC_H == "N/A" || sOOC_H == "建置中" || sOOC_H == "異常") &&
                    (sAlert1 == "-" || sAlert1 == "N/A" || sAlert1 == "建置中" || sAlert1 == "異常") && sWEB != "")
                {
                    if (sAlert != "" && sAlert != "-" && sAlert != "N/A" && MTDBbase.ToDecimal(sWEB) > MTDBbase.ToDecimal(sAlert) &&
                        MTDBbase.ToDecimal(sWEB) < MTDBbase.ToDecimal(sOOC) && sOOC != "-" && sOOC != "N/A")
                    {
                        sImg = "Y";
                    }

                    if (sRecv != "" && sRecv != "-" && sRecv != "N/A" && MTDBbase.ToDecimal(sWEB) > MTDBbase.ToDecimal(sRecv))
                    {
                        sImg = "Y";
                    }

                    //CWMS OOS_HH
                    if (MTDBbase.ToDecimal(sOOS_HH1) != MTDBbase.ToDecimal(sOOS) && sOOS_HH1 != "" && sOOS_HH1 != "-" &&
                        //sOOS_HH1 != "N/A" && sOOS_HH1 != "建置中" && sOOS_HH1 != "斷訊" && sOOS_HH1 != "異常")
                        sOOS_HH1 != "N/A" && sOOS_HH1 != "建置中" && sOOS_HH1 != "異常" && sOOS_HH1 != "保養中")
                    {
                        gvRow.Cells[11].BackColor = Color.LightPink;
                        sImg = "O";
                    }

                    //CWMS OOC_H
                    if (MTDBbase.ToDecimal(sOOC_H1) != MTDBbase.ToDecimal(sOOC) && sOOC_H1 != "" && sOOC_H1 != "-" &&
                        //sOOC_H1 != "N/A" && sOOC_H1 != "建置中" && sOOC_H1 != "斷訊" && sOOC_H1 != "異常")
                        sOOC_H1 != "N/A" && sOOC_H1 != "建置中" && sOOC_H1 != "異常" && sOOC_H1 != "保養中")
                    {
                        gvRow.Cells[12].BackColor = Color.LightPink;
                        sImg = "O";
                    }

                    if (MTDBbase.ToDecimal(sWEB) >= MTDBbase.ToDecimal(sOOC) && sOOC != "" && sOOC != "-" && sOOC != "N/A" &&
                        MTDBbase.ToDecimal(sWEB) < MTDBbase.ToDecimal(sOOS) && sOOS != "" && sOOS != "-" && sOOS != "N/A")
                    {
                        sImg = "O";
                    }

                    if (MTDBbase.ToDecimal(sWEB) >= MTDBbase.ToDecimal(sOOS) && sOOS != "" && sOOS != "-" && sOOS != "N/A")
                    {
                        sImg = "R";
                    }
                }
                else
                {
                    if (sAlert != "" && sAlert != "-" && sAlert != "N/A" && MTDBbase.ToDecimal(sWEB) > MTDBbase.ToDecimal(sAlert) &&
                        MTDBbase.ToDecimal(sWEB) < MTDBbase.ToDecimal(sOOC) && sOOC != "-" && sOOC != "N/A")
                    {
                        sImg = "Y";
                    }

                    if (sRecv != "" && sRecv != "-" && sRecv != "N/A" && MTDBbase.ToDecimal(sWEB) > MTDBbase.ToDecimal(sRecv))
                    {
                        sImg = "Y";
                    }

                    if (MTDBbase.ToDecimal(sAlert1) != MTDBbase.ToDecimal(sAlert) && sAlert1 != "" && sAlert1 != "-" &&
                        //sAlert1 != "N/A" && sAlert1 != "建置中" && sAlert1 != "斷訊" && sAlert1 != "異常")
                        sAlert1 != "N/A" && sAlert1 != "建置中" && sAlert1 != "異常" && sAlert1 != "保養中")
                    {
                        if (sAlert1 != "斷訊") gvRow.Cells[10].BackColor = Color.LightPink;
                        sImg = "O";
                    }

                    //SCADA OOS_HH
                    if (MTDBbase.ToDecimal(sOOS_HH) != MTDBbase.ToDecimal(sOOS) && sOOS_HH != "" && sOOS_HH != "-" &&
                        //sOOS_HH != "N/A" && sOOS_HH != "建置中" && sOOS_HH != "斷訊" && sOOS_HH != "異常")
                        sOOS_HH != "N/A" && sOOS_HH != "建置中" && sOOS_HH != "異常" && sOOS_HH != "保養中")
                    {
                        if (gvRow.Cells[1].Text.IndexOf("VOC") > -1 && MTDBbase.ToDecimal(sOOS_HH) < MTDBbase.ToDecimal(sOOS))
                        {

                        }
                        else
                        {
                            if (sOOS_HH != "斷訊") gvRow.Cells[8].BackColor = Color.LightPink;
                            sImg = "O";
                        }
                    }

                    //SCADA OOC_H
                    if (MTDBbase.ToDecimal(sOOC_H) != MTDBbase.ToDecimal(sOOC) && sOOC_H != "" && sOOC_H != "-" &&
                        //sOOC_H != "N/A" && sOOC_H != "建置中" && sOOC_H != "斷訊" && sOOC_H != "異常")
                        sOOC_H != "N/A" && sOOC_H != "建置中" && sOOC_H != "異常" && sOOC_H != "保養中")
                    {
                        if (gvRow.Cells[1].Text.IndexOf("VOC") > -1 && MTDBbase.ToDecimal(sOOC_H) < MTDBbase.ToDecimal(sOOC))
                        {

                        }
                        else
                        {
                            if (sOOC_H != "斷訊") gvRow.Cells[9].BackColor = Color.LightPink;
                            sImg = "O";
                        }
                    }

                    //CWMS OOS_HH
                    if (MTDBbase.ToDecimal(sOOS_HH1) != MTDBbase.ToDecimal(sOOS) && sOOS_HH1 != "" && sOOS_HH1 != "-" &&
                        sOOS_HH1 != "N/A" && sOOS_HH1 != "建置中" && sOOS_HH1 != "異常" && sOOS_HH1 != "保養中")
                    {
                        if (sOOS_HH1 != "斷訊") gvRow.Cells[11].BackColor = Color.LightPink;
                        sImg = "O";
                    }

                    //CWMS OOC_H
                    if (MTDBbase.ToDecimal(sOOC_H1) != MTDBbase.ToDecimal(sOOC) && sOOC_H1 != "" && sOOC_H1 != "-" &&
                        sOOC_H1 != "N/A" && sOOC_H1 != "建置中" && sOOC_H1 != "異常" && sOOC_H1 != "保養中")
                    {
                        if (sOOC_H1 != "斷訊") gvRow.Cells[12].BackColor = Color.LightPink;
                        sImg = "O";
                    }

                    if (sWEB == "")
                    {
                        if (sOOS_HH == "" && sOOC_H == "" && sAlert1 == "")
                        {
                            gvRow.Cells[8].BackColor = Color.LightPink;
                            gvRow.Cells[9].BackColor = Color.LightPink;
                            gvRow.Cells[10].BackColor = Color.LightPink;
                            sImg = "R";
                        }
                    }
                    else
                    {
                        if (MTDBbase.ToDecimal(sWEB) >= MTDBbase.ToDecimal(sOOC) && sOOC != "" && sOOC != "-" && sOOC != "N/A" &&
                            MTDBbase.ToDecimal(sWEB) < MTDBbase.ToDecimal(sOOS) && sOOS != "" && sOOS != "-" && sOOS != "N/A")
                        {
                            sImg = "O";
                        }

                        if (MTDBbase.ToDecimal(sWEB) >= MTDBbase.ToDecimal(sOOS) && sOOS != "" && sOOS != "-" && sOOS != "N/A")
                        {
                            sImg = "R";
                        }
                    }
                }
            }
            else
            {
                string sOOS = gvRow.Cells[4].Text;
                string sOOC = gvRow.Cells[5].Text;
                string sAlert = gvRow.Cells[6].Text;
                string sRecv = gvRow.Cells[7].Text;
                string sOOS_HH = gvRow.Cells[8].Text;
                string sOOC_H = gvRow.Cells[9].Text;
                string sAlert1 = gvRow.Cells[10].Text;
                string sOOS_HH1 = gvRow.Cells[11].Text;
                string sOOC_H1 = gvRow.Cells[12].Text;
                string[] OOS = sOOS.Split('-');
                string[] OOC = sOOC.Split('-');
                string[] Alert = sAlert.Split('-');
                string[] Recv = sRecv.Split('-');
                string[] OOS_HH = sOOS_HH.Split('-');
                string[] OOC_H = sOOC_H.Split('-');
                string[] Alert1 = sAlert1.Split('-');
                string[] OOS_HH1 = sOOS_HH1.Split('-');
                string[] OOC_H1 = sOOC_H1.Split('-');
                string WEB = gvRow.Cells[13].Text;

                //if ((sOOS_HH == "-" || sOOS_HH == "N/A" || sOOS_HH == "建置中" || sOOS_HH == "斷訊" || sOOS_HH == "異常") &&
                //    (sOOC_H == "-" || sOOC_H == "N/A" || sOOC_H == "建置中" || sOOC_H == "斷訊" || sOOC_H == "異常") &&
                //    (sAlert1 == "-" || sAlert1 == "N/A" || sAlert1 == "建置中" || sAlert1 == "斷訊" || sAlert1 == "異常") && WEB != "")
                if ((sOOS_HH == "-" || sOOS_HH == "N/A" || sOOS_HH == "建置中" || sOOS_HH == "異常") &&
                    (sOOC_H == "-" || sOOC_H == "N/A" || sOOC_H == "建置中" || sOOC_H == "異常") &&
                    (sAlert1 == "-" || sAlert1 == "N/A" || sAlert1 == "建置中" || sAlert1 == "異常") && WEB != "")
                {
                    if (sAlert != "-" && Alert.Length == 2 && OOC.Length == 2)
                    {
                        if (MTDBbase.ToDecimal(WEB) > MTDBbase.ToDecimal(Alert[1]) &&
                            MTDBbase.ToDecimal(WEB) < MTDBbase.ToDecimal(OOC[1]))
                        {
                            sImg = "Y";
                        }
                    }

                    if (sRecv != "-" && Recv.Length == 2)
                    {
                        if (MTDBbase.ToDecimal(WEB) > MTDBbase.ToDecimal(Recv[1]))
                        {
                            sImg = "Y";
                        }
                    }

                    //CWMS OOS_HH
                    if (CheckData(OOS_HH1) != CheckData(OOS) && sOOS_HH1 != "" && sOOS_HH1 != "-" &&
                        sOOS_HH1 != "N/A" && sOOS_HH1 != "建置中" && sOOS_HH1 != "異常" && sOOS_HH1 != "保養中")
                    {
                        gvRow.Cells[11].BackColor = Color.LightPink;
                        sImg = "O";
                    }

                    //CWMS OOC_H
                    if (CheckData(OOC_H1) != CheckData(OOC) && sOOC_H1 != "" && sOOC_H1 != "-" &&
                        sOOC_H1 != "N/A" && sOOC_H1 != "建置中" && sOOC_H1 != "異常" && sOOC_H1 != "保養中")
                    {
                        gvRow.Cells[12].BackColor = Color.LightPink;
                        sImg = "O";
                    }

                    if (OOC.Length == 2 && OOS.Length == 2)
                    {
                        if (MTDBbase.ToDecimal(WEB) >= MTDBbase.ToDecimal(OOC[1]) && sOOC != "-" &&
                            MTDBbase.ToDecimal(WEB) < MTDBbase.ToDecimal(OOS[1]) && sOOS != "-")
                        {
                            sImg = "O";
                        }
                    }

                    if (OOS.Length == 2)
                    {
                        if (MTDBbase.ToDecimal(WEB) >= MTDBbase.ToDecimal(OOS[1]) && sOOS != "-")
                        {
                            sImg = "R";
                        }
                    }
                }
                else
                {
                    if (CheckData(Alert1) != CheckData(Alert) && sAlert1 != "" && sAlert1 != "-" &&
                        //sAlert1 != "N/A" && sAlert1 != "建置中" && sAlert1 != "斷訊" && sAlert1 != "異常")
                        sAlert1 != "N/A" && sAlert1 != "建置中" && sAlert1 != "異常" && sAlert1 != "保養中")
                    {
                        if (sAlert1 != "斷訊") gvRow.Cells[10].BackColor = Color.LightPink;
                        sImg = "O";
                    }

                    //SCADA OOS_HH
                    if (CheckData(OOS_HH) != CheckData(OOS) && sOOS_HH != "" && sOOS_HH != "-" &&
                        //sOOS_HH != "N/A" && sOOS_HH != "建置中" && sOOS_HH != "斷訊" && sOOS_HH != "異常")
                        sOOS_HH != "N/A" && sOOS_HH != "建置中" && sOOS_HH != "異常" && sOOS_HH != "保養中")
                    {
                        if (sOOS_HH != "斷訊") gvRow.Cells[8].BackColor = Color.LightPink;
                        sImg = "O";
                    }

                    //SCADA OOC_H
                    if (CheckData(OOC_H) != CheckData(OOC) && sOOC_H != "" && sOOC_H != "-" &&
                        //sOOC_H != "N/A" && sOOC_H != "建置中" && sOOC_H != "斷訊" && sOOC_H != "異常")
                        sOOC_H != "N/A" && sOOC_H != "建置中" && sOOC_H != "異常" && sOOC_H != "保養中")
                    {
                        if (sOOC_H != "斷訊") gvRow.Cells[9].BackColor = Color.LightPink;
                        sImg = "O";
                    }

                    //CWMS OOS_HH
                    if (CheckData(OOS_HH1) != CheckData(OOS) && sOOS_HH1 != "" && sOOS_HH1 != "-" &&
                        sOOS_HH1 != "N/A" && sOOS_HH1 != "建置中" && sOOS_HH1 != "異常" && sOOS_HH1 != "保養中")
                    {
                        if (sOOS_HH1 != "斷訊") gvRow.Cells[11].BackColor = Color.LightPink;
                        sImg = "O";
                    }

                    //CWMS OOC_H
                    if (CheckData(OOC_H1) != CheckData(OOC) && sOOC_H1 != "" && sOOC_H1 != "-" &&
                        sOOC_H1 != "N/A" && sOOC_H1 != "建置中" && sOOC_H1 != "異常" && sOOC_H1 != "保養中")
                    {
                        if (sOOC_H1 != "斷訊") gvRow.Cells[12].BackColor = Color.LightPink;
                        sImg = "O";
                    }

                    if (WEB == "")
                    {
                        if (sOOS_HH == "" && sOOC_H == "" && sAlert1 == "")
                        {
                            gvRow.Cells[8].BackColor = Color.LightPink;
                            gvRow.Cells[9].BackColor = Color.LightPink;
                            gvRow.Cells[10].BackColor = Color.LightPink;
                            sImg = "R";
                        }
                    }
                    else
                    {
                        if (sAlert != "-" && Alert.Length == 2 && OOC.Length == 2)
                        {
                            if (MTDBbase.ToDecimal(WEB) > MTDBbase.ToDecimal(Alert[1]) &&
                                MTDBbase.ToDecimal(WEB) < MTDBbase.ToDecimal(OOC[1]))
                            {
                                sImg = "Y";
                            }
                        }

                        if (sRecv != "-" && Recv.Length == 2)
                        {
                            if (MTDBbase.ToDecimal(WEB) > MTDBbase.ToDecimal(Recv[1]))
                            {
                                sImg = "Y";
                            }
                        }

                        if (OOC.Length == 2 && OOS.Length == 2)
                        {
                            if (MTDBbase.ToDecimal(WEB) >= MTDBbase.ToDecimal(OOC[1]) && sOOC != "-" &&
                                MTDBbase.ToDecimal(WEB) < MTDBbase.ToDecimal(OOS[1]) && sOOS != "-")
                            {
                                sImg = "O";
                            }
                        }

                        if (OOS.Length == 2)
                        {
                            if (MTDBbase.ToDecimal(WEB) >= MTDBbase.ToDecimal(OOS[1]) && sOOS != "-")
                            {
                                sImg = "R";
                            }
                        }
                    }
                }
            }
        }

        //燈號顏色
        light = (System.Web.UI.WebControls.Image)gvRow.FindControl("light");
        light.ImageUrl = (sImg == "G" ? "images/CircleGreen.jpg" : (sImg == "Y" ? "images/CircleYellow.jpg" :
            (sImg == "O" ? "images/CircleOrange.jpg" : "images/CircleRed.jpg")));

        //備註欄位顏色
        if (gvRow.Cells[16].Text.IndexOf("斷訊") > -1) gvRow.Cells[16].ForeColor = Color.White;
        gvRow.Cells[16].BorderColor = Color.Black;
    }
}