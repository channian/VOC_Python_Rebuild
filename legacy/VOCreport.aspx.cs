using System;
using System.Collections.Generic;
using System.Linq;
using System.Web;
using System.Web.UI;
using System.Web.UI.WebControls;
using System.Data;
using System.Web.UI.DataVisualization.Charting;
using System.Drawing;
using MTLibrary;

public partial class VOCreport : BasePage
{
    public string _View_sdate
    {
        get { return ViewState["VOCreport_sdate"] as string; }
        set { ViewState["VOCreport_sdate"] = value; }
    }
    public string _View_edate
    {
        get { return ViewState["VOCreport_edate"] as string; }
        set { ViewState["VOCreport_edate"] = value; }
    }

    public int _View_plantcnt
    {
        get { return MTDBbase.ToInt32(ViewState["VOCreport_plantcnt"], -1); }
        set { ViewState["VOCreport_plantcnt"] = value; }
    }

    protected void Page_Load(object sender, EventArgs e)
    {
        if (!Page.IsPostBack)
        {
            if (ddlplantno.DataSource == null)
            {
                using (dbVOC db = new dbVOC())
                    SetValueList(ddlplantno, MTDBbase.AddNullValue(db.List廠區()));
            }

            if (ddlitem.DataSource == null)
            {
                using (dbVOC db = new dbVOC())
                    SetValueList(ddlitem, MTDBbase.AddNullValue(db.List項目()));
            }

            _View_sdate = Request.QueryString["sdate"].ToStringTrim();
            _View_edate = Request.QueryString["edate"].ToStringTrim();
            if (_View_sdate != "") __sdate.Value = _View_sdate;
            if (_View_edate != "") __edate.Value = _View_edate;

            string sort = Request.QueryString["sort"].ToStringTrim();
            if (sort != "") rblsort.SelectedValue = sort;

            string plantno = Request.QueryString["plantno"].ToStringTrim();
            if (plantno != "")
            {
                for (int i = 0; i < ddlplantno.Items.Count; i++)
                {
                    if (ddlplantno.Items[i].Text == plantno)
                    {
                        ddlplantno.SelectedIndex = i;
                        break;
                    }
                }
            }

            string item = Request.QueryString["item"].ToStringTrim();
            if (item != "")
            {
                for (int i = 0; i < ddlitem.Items.Count; i++)
                {
                    if (ddlitem.Items[i].Text == item)
                    {
                        ddlitem.SelectedIndex = i;
                        break;
                    }
                }
            }

            string MT = Request.QueryString["MT"].ToStringTrim();
            if (MT == "True") cbMT.Checked = true;

            BindGrid();
        }
    }

    protected void ddlplantno_SelectedIndexChanged(object sender, EventArgs e)
    {
        ddlitem.SelectedIndex = 0;

        using (dbVOC db = new dbVOC())
        {
            if (ddlplantno.SelectedItem.Text == "")
            {
                SetValueList(ddlitem, MTDBbase.AddNullValue(db.List項目()));
            }
            else
            {
                SetValueList(ddlitem, MTDBbase.AddNullValue(db.List項目3(ddlplantno.SelectedItem.Text)));
            }
        }
    }

    protected void btn查詢_Click(object sender, EventArgs e)
    {
        BindGrid();
    }

    protected void BindGrid()
    {
        string plantno = ddlplantno.SelectedItem.Text;
        string item = ddlitem.SelectedItem.Text;

        if (__sdate.Value == "") __sdate.Value = DateTime.Today.ToString("yyyy/MM/") + "01";
        if (__edate.Value == "") __edate.Value = DateTime.Today.ToString("yyyy/MM/dd");

        _View_sdate = MTDBbase.ToStringTrim(__sdate.Value);
        _View_edate = MTDBbase.ToStringTrim(__edate.Value);

        if (_View_sdate.CompareTo(_View_edate) > 0)
        {
            using (dbVOC db = new dbVOC()) db.MsgBox(Page, "開始日期不可大於結束日期!");
            return;
        }

        string sTitle = _View_sdate + " ~ " + _View_edate;

        DataTable dtb0, dtb1, dtb2, dtb3;
        using (dbVOC db = new dbVOC())
        {
            dtb1 = db.Get廠棟異常件數統計(plantno, item, _View_sdate, _View_edate, rblsort.SelectedItem.Text, cbMT.Checked, false);
            //各廠區長條圖轉表格，要有Total欄位
            dtb2 = db.Get廠棟異常件數統計(plantno, item, _View_sdate, _View_edate, rblsort.SelectedItem.Text, cbMT.Checked, true);
            dtb3 = db.GetPIVOT廠棟異常件數(plantno, item, _View_sdate, _View_edate, rblsort.SelectedItem.Text, cbMT.Checked);
            lbMaxRank.Text = db.Get廠棟異常件數最大排行(plantno, item, _View_sdate, _View_edate, rblsort.SelectedItem.Text, cbMT.Checked);
        }

        if (dtb3 == null) showdata1.Visible = false;
        else
        {
            showdata1.Visible = true;
            //新增gvCaseTTL的欄位-start
            DataTable PlantDT;
            BoundField field;
            using (dbVOC db = new dbVOC()) PlantDT = db.List廠區0();
            field = new BoundField();
            field.DataField = "item";
            field.HeaderText = "項目";
            gvCaseTTL.Columns.Clear();
            gvCaseTTL.Columns.Add(field);
            for (int i = 0; i < PlantDT.Rows.Count; i++)
            {
                field = new BoundField();
                field.DataField = PlantDT.Rows[i][1].ToString();
                field.HeaderText = field.DataField;
                gvCaseTTL.Columns.Add(field);
            }
            field = new BoundField();
            field.DataField = "Total";
            field.HeaderText = "ALL";
            gvCaseTTL.Columns.Add(field);
            _View_plantcnt = PlantDT.Rows.Count + 2;
            //新增gvCaseTTL的欄位-end
        }

        if (dtb1.Rows.Count == 0)
        {
            //查無資料就不顯示長條圖
            showcht.Visible = false;
        }
        else
        {
            showcht.Visible = true;
        }

        chtCaseTTL.Titles[0].Text = sTitle + (plantno == "" ? " 高雄廠各廠區" : " " + ddlplantno.SelectedItem.Text)
            + (item == "" ? "" : " " + ddlitem.SelectedItem.Text) + " 異常件數統計表";
        chtCaseTTL.SetDataSource(dtb1);

        lbTTL.Text = sTitle + (plantno == "" ? " 高雄廠各廠區" : " " + ddlplantno.SelectedItem.Text)
            + (item == "" ? "" : " " + ddlitem.SelectedItem.Text) + " 異常件數統計表";
        gvCaseTTL.DataSource = dtb3;
        gvCaseTTL.DataBind();

        gvCaseTB.DataSource = dtb2;
        gvCaseTB.DataBind();

        if (gvCaseTB.Rows.Count > 0)    //新增 "ALL" 資料
        {
            DataTable dtb;
            using (dbVOC db = new dbVOC())
                dtb = db.Get廠棟異常件數總計(plantno, item, _View_sdate, _View_edate, cbMT.Checked);

            GridViewRow gvr = new GridViewRow(0, 0, DataControlRowType.DataRow, DataControlRowState.Normal);
            gvr.BackColor = Color.AliceBlue;
            TableCell datacell;
            string url;

            for (int i = 0; i < dtb.Columns.Count; i++)
            {
                datacell = new TableCell();
                datacell.Text = dtb.Rows[0][i].ToString();

                if (i == 1 && MTDBbase.ToInt32(dtb.Rows[0][i].ToString(), -1) > 0)
                {
                    url = "~/VOChistory.aspx?sdate=" + _View_sdate + "&edate=" + _View_edate +
                        "&type=TTL&form1=VOCreport&sort=" + rblsort.SelectedValue +
                        "&MT=" + cbMT.Checked;

                    if (plantno != "") url += "&plantno=" + plantno;
                    if (item != "") url += "&item=" + item;

                    datacell.Text = "<a href=\"javascript:var win=window.location.assign('" +
                    ResolveClientUrl(url) + "')\"; target='_self';>" + dtb.Rows[0][i].ToString() + "</a>";
                }

                gvr.Cells.Add(datacell);
            }

            gvCaseTB.Controls[0].Controls.AddAt(gvCaseTB.Rows.Count + 1, gvr);
        }
    }

    protected void chtCaseTTL_Load(object sender, EventArgs e)
    {
        chtCaseTTL.ChartAreas["ChartArea"].AxisX.Interval = 1;
        chtCaseTTL.ChartAreas["ChartArea"].AxisX.IsLabelAutoFit = false;
        chtCaseTTL.ChartAreas["ChartArea"].AxisX.LabelStyle.IsStaggered = true;
        chtCaseTTL.ChartAreas["ChartArea"].AxisX.LabelStyle.Angle = -30;
        /*X與Y軸格線不顯示*/
        chtCaseTTL.ChartAreas["ChartArea"].AxisX.MajorGrid.Enabled = false;
        chtCaseTTL.ChartAreas["ChartArea"].AxisY.MajorGrid.Enabled = false;
        chtCaseTTL.ChartAreas["ChartArea"].AxisY.IntervalAutoMode = IntervalAutoMode.VariableCount;
    }

    protected void chtCaseTTL_Customize(object sender, EventArgs e)
    {
        chtCaseTTL.ChartAreas["ChartArea"].AxisX.LabelStyle.Angle = 0;
    }

    protected void gvCaseTTL_DataBound(object sender, EventArgs e)
    {
        string plant = "";
        string item = "";
        int MaxRank = MTDBbase.ToInt32(lbMaxRank.Text, -1);
        string plantno = ddlplantno.SelectedItem.Text;
        string itemno = ddlitem.SelectedItem.Text;
        string url = "";

        for (int i = 0; i < gvCaseTTL.Rows.Count; i++)
        {
            for (int j = 1; j < _View_plantcnt; j++)
            {
                plant = gvCaseTTL.Columns[j].HeaderText;
                item = gvCaseTTL.Rows[i].Cells[0].Text;

                url = "~/VOChistory.aspx?item=" + item + "&plant=" + plant +
                    "&sdate=" + _View_sdate + "&edate=" + _View_edate +
                    "&type=TTL&form1=VOCreport&sort=" + rblsort.SelectedValue +
                    "&MT=" + cbMT.Checked;

                if (plantno != "") url += "&plantno=" + plantno;
                if (itemno != "") url += "&itemno=" + itemno;

                if (MTDBbase.ToInt32(gvCaseTTL.Rows[i].Cells[j].Text, -1) > 0)
                    gvCaseTTL.Rows[i].Cells[j].Text = "<a href=\"javascript:var win=window.location.assign('" +
                    ResolveClientUrl(url) + "')\"; target='_self';>" + gvCaseTTL.Rows[i].Cells[j].Text + "</a>";
            }
        }
    }

    protected void gvCaseTB_DataBound(object sender, EventArgs e)
    {
        gvCaseTB.Columns[3].Visible = true;

        string plant = "";
        int MaxRank = MTDBbase.ToInt32(lbMaxRank.Text, -1);
        string plantno = ddlplantno.SelectedItem.Text;
        string item = ddlitem.SelectedItem.Text;
        string url = "";

        for (int i = 0; i < gvCaseTB.Rows.Count; i++)
        {
            plant = gvCaseTB.Rows[i].Cells[0].Text;

            if (MTDBbase.ToInt32(gvCaseTB.Rows[i].Cells[1].Text, -1) > 0)
            {
                url = "~/VOChistory.aspx?item=" + gvCaseTB.Rows[i].Cells[3].Text +
                    "&plant=" + plant + "&sdate=" + _View_sdate + "&edate=" + _View_edate +
                    "&type=TTL&form1=VOCreport&sort=" + rblsort.SelectedValue +
                    "&MT=" + cbMT.Checked;

                if (plantno != "") url += "&plantno=" + plantno;
                if (item != "") url += "&item=" + item;

                gvCaseTB.Rows[i].Cells[1].Text = "<a href=\"javascript:var win=window.location.assign('" +
                ResolveClientUrl(url) + "')\"; target='_self';>" + gvCaseTB.Rows[i].Cells[1].Text + "</a>";
            }

            //Ranking color setting start
            if (MTDBbase.ToInt32(gvCaseTB.Rows[i].Cells[2].Text, -1) <= 3) //top 3->red color
            {
                gvCaseTB.Rows[i].BackColor = System.Drawing.Color.LightPink;
            }
            if (MTDBbase.ToInt32(gvCaseTB.Rows[i].Cells[2].Text, -1) >= MaxRank - 2) //last 3->blue color
            {
                gvCaseTB.Rows[i].BackColor = System.Drawing.Color.LightGreen;
            }
            //Ranking color setting end
        }

        gvCaseTB.Columns[3].Visible = false;
    }
}