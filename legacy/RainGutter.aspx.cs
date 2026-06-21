using MTLibrary;
using System;
using System.Collections.Generic;
using System.Data;
using System.Linq;
using System.Web;
using System.Web.UI;
using System.Web.UI.WebControls;
using System.Drawing;

public partial class RainGutter : BasePage
{
    public DataTable _View_RainGutterDT
    {
        get { return ViewState["RainGutterDT"] as DataTable; }
        set { ViewState["RainGutterDT"] = value; }
    }

    protected void Page_Load(object sender, EventArgs e)
    {
        if (!Page.IsPostBack)
        {
            btnBack.PostBackUrl = "~/Default.aspx";
            GetUpdateTime(sender, e);
            BindGrid();
        }
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
            //dtb0 = db.List隔離廠區項目_雨水溝預警();
            //if (dtb0.Rows.Count > 0)
            //{
            //    for (int i = 0; i < dtb0.Rows.Count; i++)
            //    {
            //        db.Update隔離廠區項目(dtb0.Rows[i]);
            //    }
            //}
            for (int i = 6; i < 12; i++) gvRainGutterList.Columns[i].Visible = true;
            dtb = db.List雨水溝預警();
            string PlantID = db.GetPlantID();
            if (PlantID.IndexOf("29") < 0)
            {
                int flg = 0;
                string[] ArrPlantID = PlantID.Split(',');
                for (int i = 0; i < ArrPlantID.Length; i++)
                {
                    if (ArrPlantID[i] == "31" || ArrPlantID[i] == "6") flg = 1;   //K1/K9
                }
                if (flg == 0)
                {
                    for (int i = 6; i < 12; i++) gvRainGutterList.Columns[i].Visible = false;
                }
            }
        }
        return dtb;
    }

    protected void BindGrid()
    {
        if (_View_RainGutterDT == null)
            _View_RainGutterDT = GetData();
        gvRainGutterList.SetDataSource(_View_RainGutterDT);
    }

    protected void gvRainGutterList_PageIndexChanging(object sender, GridViewPageEventArgs e)
    {
        gvRainGutterList.PageIndex = e.NewPageIndex;
        BindGrid();
    }

    protected void gvRainGutterList_PreRender(object sender, EventArgs e)
    {
        GridViewRow gvRow;
        GridViewRow gvNextRow;

        gvRow = gvRainGutterList.Rows[gvRainGutterList.Rows.Count - 1];
        GetData雨水溝(gvRow);

        for (int i = gvRainGutterList.Rows.Count - 2; i >= 0; i--)
        {
            gvRow = gvRainGutterList.Rows[i];
            gvNextRow = gvRainGutterList.Rows[i + 1];

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

            GetData雨水溝(gvRow);
        }
    }

    private void GetData雨水溝(GridViewRow gvRow)
    {
        System.Web.UI.WebControls.Image light;
        string sImg;
        string sDate = "";
        string remark = gvRow.Cells[5].Text;

        if (gvRow.Cells[3].Text == "保養中")
        {
            using (dbVOC db = new dbVOC())
                sDate = db.Get隔離廠區項目區間(gvRow.Cells[0].Text, gvRow.Cells[1].Text);
        }
        if (sDate != "") gvRow.Cells[5].Text = sDate;

        //項目欄位底色
        gvRow.Cells[1].BackColor = Color.DodgerBlue;
        gvRow.Cells[1].ForeColor = Color.White;

        sImg = "G";

        for (int i = 2; i < 4; i++)
        {
            gvRow.Cells[i].Text = gvRow.Cells[i].Text.Replace("&nbsp;", "").Replace(",", "");

            if (gvRow.Cells[i].Text == "" || gvRow.Cells[i].Text == "斷訊" || gvRow.Cells[i].Text == "異常")
            {
                if (gvRow.Cells[i].Text == "") gvRow.Cells[i].Text = "異常";
                gvRow.Cells[i].ForeColor = Color.Red;
                gvRow.Cells[i].BorderColor = Color.Black;
            }
        }

        //即時值欄位底色
        gvRow.Cells[3].BackColor = Color.Cornsilk;

        if (gvRow.Cells[2].Text != "" || gvRow.Cells[3].Text != "")
        {
            //紅燈條件：最新讀值=1 且 24H累積雨量=0
            //橘燈條件：斷訊 或 異常
            //綠燈條件：正常狀態
            string Sum24H = gvRow.Cells[2].Text;
            string rvalue = gvRow.Cells[3].Text;

            if (Sum24H == "0.0" && rvalue == "1")
            {
                sImg = "R";
            }
            else if (rvalue == "斷訊" || rvalue == "異常")
            {
                sImg = "O";
            }
            else if (Sum24H == "異常" && rvalue == "1")
            {
                sImg = "O";
            }
        }

        //燈號顏色
        light = (System.Web.UI.WebControls.Image)gvRow.FindControl("light");
        light.ImageUrl = (sImg == "G" ? "images/CircleGreen.png" : (sImg == "O" ? "images/CircleOrange.png" : "images/CircleRed.png"));
    }
}