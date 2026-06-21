using System;
using System.Collections;
using System.Collections.Generic;
using System.Data;
using System.Linq;
using System.Web;
using System.Web.UI;
using System.Web.UI.WebControls;
using MTLibrary;

public partial class VOChistory : BasePage
{
    public DataTable _View_VOClogDT
    {
        get { return ViewState["VOChistory_DT"] as DataTable; }
        set { ViewState["VOChistory_DT"] = value; }
    }

    public string _View_sdate
    {
        get { return ViewState["VOChistory_sdate"] as string; }
        set { ViewState["VOChistory_sdate"] = value; }
    }
    public string _View_edate
    {
        get { return ViewState["VOChistory_edate"] as string; }
        set { ViewState["VOChistory_edate"] = value; }
    }

    protected void Page_Load(object sender, EventArgs e)
    {
        if (!Page.IsPostBack)
        {
            if (_0plantid.DataSource == null)
            {
                using (dbVOC db = new dbVOC())
                {
                    SetValueList(_0plantid, MTDBbase.AddNullValue(db.List廠區()));
                    SetValueList(_0itemid, MTDBbase.AddNullValue(db.List項目()));

                    if (Request.QueryString.HasKeys())
                    {
                        string plant = Request.QueryString["plant"].ToStringTrim();
                        string item = Request.QueryString["item"].ToStringTrim();
                        int ipage = MTDBbase.ToInt32(Request.QueryString["ipage"], -1);
                        _View_sdate = Request.QueryString["sdate"].ToStringTrim();
                        _View_edate = Request.QueryString["edate"].ToStringTrim();

                        if (_View_sdate != "") __sdate.Value = _View_sdate;
                        if (_View_edate != "") __edate.Value = _View_edate;
                        if (plant != "")
                        {
                            for (int i = 0; i < _0plantid.Items.Count; i++)
                            {
                                if (_0plantid.Items[i].Text == plant)
                                {
                                    _0plantid.SelectedIndex = i;
                                    break;
                                }
                            }
                        }
                        if (item != "")
                        {
                            for (int i = 0; i < _0itemid.Items.Count; i++)
                            {
                                if (_0itemid.Items[i].Text == item)
                                {
                                    _0itemid.SelectedIndex = i;
                                    break;
                                }
                            }
                        }
                        string MT = Request.QueryString["MT"].ToStringTrim();
                        if (MT == "True") cbMT.Checked = true;

                        if (ipage >= 0) gvList.PageIndex = ipage;
                        __sdate.Disabled = true;
                        __edate.Disabled = true;
                        SetCtrlReadonly(new Control[] { _0plantid, _0itemid, cbMT }, true);
                        lbtitle.Text = (_0plantid.SelectedItem.Text == "" ? "高雄廠" : _0plantid.SelectedItem.Text)
                            + "-" + (_0itemid.SelectedItem.Text == "" ? "全部項目" : _0itemid.SelectedItem.Text)
                            + "-" + "異常紀錄查詢";
                    }
                }
            }

            BindGrid();
        }
    }

    protected void _0plantid_SelectedIndexChanged(object sender, EventArgs e)
    {
        _0itemid.SelectedIndex = 0;

        using (dbVOC db = new dbVOC())
        {
            if (_0plantid.SelectedItem.Text == "")
            {
                SetValueList(_0itemid, MTDBbase.AddNullValue(db.List項目()));
            }
            else
            {
                SetValueList(_0itemid, MTDBbase.AddNullValue(db.List項目3(_0plantid.SelectedItem.Text)));
            }
        }
    }

    protected void QueryButton_Click(object sender, EventArgs e)
    {
        BindGrid();
    }

    private DataTable GetData()
    {
        string plant = _0plantid.SelectedItem.Text;
        string item = _0itemid.SelectedItem.Text;
        bool MT = cbMT.Checked;

        using (dbVOC db = new dbVOC()) return db.ListVOClog(plant, item, _View_sdate, _View_edate, MT, "", "", "");
    }

    protected void BindGrid()
    {
        if (__sdate.Value == "") __sdate.Value = DateTime.Today.ToString("yyyy/MM/") + "01";
        if (__edate.Value == "") __edate.Value = DateTime.Today.ToString("yyyy/MM/dd");

        _View_sdate = MTDBbase.ToStringTrim(__sdate.Value);
        _View_edate = MTDBbase.ToStringTrim(__edate.Value);

        if (_View_sdate.CompareTo(_View_edate) > 0)
        {
            using (dbVOC db = new dbVOC()) db.MsgBox(Page, "開始日期不可大於結束日期!");
            return;
        }

        _View_VOClogDT = GetData();

        gvList.SetDataSource(_View_VOClogDT);
    }

    protected void gvList_PageIndexChanging(object sender, GridViewPageEventArgs e)
    {
        gvList.PageIndex = e.NewPageIndex;
        BindGrid();
    }

    protected void CancelButton_Click(object sender, EventArgs e)
    {
        if (Request.QueryString.HasKeys())
        {
            string form = Request.QueryString["form1"].ToStringTrim();
            if (form == "")
                Response.Redirect(ResolveClientUrl("~/Default.aspx"));
            else
            {
                string sdate = Request.QueryString["sdate"].ToStringTrim();
                string edate = Request.QueryString["edate"].ToStringTrim();
                string sort = Request.QueryString["sort"].ToStringTrim();
                string plantno = Request.QueryString["plantno"].ToStringTrim();
                string cctvtypeid = Request.QueryString["cctvtypeid"].ToStringTrim();
                string MT = Request.QueryString["MT"].ToStringTrim();

                string url = "~/" + form + ".aspx?sort=" + sort;

                if (sdate != "") url += "&sdate=" + sdate + "&edate=" + edate;
                if (plantno != "") url += "&plantno=" + plantno;
                if (cctvtypeid != "") url += "&cctvtypeid=" + cctvtypeid;
                if (MT != "") url += "&MT=" + MT;

                Response.Redirect(ResolveClientUrl(url));
            }
        }
        else Response.Redirect(ResolveClientUrl("~/Default.aspx"));
    }
}