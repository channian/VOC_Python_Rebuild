using System;
using System.Collections.Generic;
using System.Data;
using System.Linq;
using System.Web;
using System.Web.UI;
using System.Web.UI.WebControls;
using MTLibrary;

public partial class ApplySPEC : BasePage
{
    public string _View_sdate
    {
        get { return ViewState["ApplySPEC_sdate"] as string; }
        set { ViewState["ApplySPEC_sdate"] = value; }
    }

    public string _View_edate
    {
        get { return ViewState["ApplySPEC_edate"] as string; }
        set { ViewState["ApplySPEC_edate"] = value; }
    }

    public DataTable _View_查詢結果
    {
        get { return ViewState["ApplySPEC_查詢結果DT"] as DataTable; }
        set { ViewState["ApplySPEC_查詢結果DT"] = value; }
    }

    public DataTable _View_廠區項目
    {
        get { return ViewState["ApplySPEC_廠區項目DT"] as DataTable; }
        set { ViewState["ApplySPEC_廠區項目DT"] = value; }
    }

    public int _View_formid
    {
        get { return MTDBbase.ToInt32(ViewState["ApplySPEC_View_formid"], -1); }
        set { ViewState["ApplySPEC_View_formid"] = value; }
    }

    public int _View_flowid
    {
        get { return MTDBbase.ToInt32(ViewState["ApplySPEC_View_flowid"], -1); }
        set { ViewState["ApplySPEC_View_flowid"] = value; }
    }

    protected void Page_Load(object sender, EventArgs e)
    {
        if (!Page.IsPostBack)
        {
            spanTable.Visible = gvTag.Visible = false;
            if (Request.QueryString.HasKeys())
            {
                _View_formid = MTDBbase.ToInt32(Request.QueryString["formid"].ToString(), -1);
                if (_View_formid > 0)
                {
                    if (ddlplant.DataSource == null)
                    {
                        using (dbVOC db = new dbVOC())
                            SetValueList(ddlplant, MTDBbase.AddNullValue(db.List廠區2()));
                    }
                    ddlplant.SelectedIndex = -1;
                    rblStatusid.SelectedValue = "-1";
                    _View_查詢結果 = null;
                    BindGrid();
                    if (_View_查詢結果.Rows.Count > 0)
                    {
                        gvList.SelectedIndex = 0;
                        gvList_SelectedIndexChanged(null, null);
                    }
                }
            }
            else
            {
                inputsdate.Value = DateTime.Today.AddDays(-6).ToString("yyyy/MM/dd");
                inputedate.Value = DateTime.Today.ToString("yyyy/MM/dd");
                if (ddlplant.DataSource == null)
                {
                    using (dbVOC db = new dbVOC())
                        SetValueList(ddlplant, MTDBbase.AddNullValue(db.List廠區2()));
                }
                ddlplant.SelectedIndex = -1;
                btn查詢_Click(sender, e);
            }
        }
    }

    protected void btn查詢_Click(object sender, EventArgs e)
    {
        _View_查詢結果 = null;
        _View_formid = -1;
        _View_flowid = -1;
        lbformno.InnerText = "";
        spanTable.Visible = gvTag.Visible = false;
        BindGrid();
    }

    void BindGrid()
    {
        _View_sdate = MTDBbase.ToStringTrim(inputsdate.Value);
        _View_edate = MTDBbase.ToStringTrim(inputedate.Value);
        //CompareTo
        //若前面字串大於後面 回傳1
        //若前面字串等於後面 回傳0
        //若前面字串小於後面 回傳-1
        if (!MTDBbase.IsNullOrEmpty(_View_sdate) && !MTDBbase.IsNullOrEmpty(_View_edate) && _View_sdate.CompareTo(_View_edate) > 0)
        {
            using (dbVOC db = new dbVOC()) db.MsgBox(Page, "開始日期不可大於結束日期!");
            return;
        }
        int plantid = MTDBbase.ToInt32(ddlplant.SelectedValue);
        int statusid = MTDBbase.ToInt32(rblStatusid.SelectedValue);
        if (_View_查詢結果 == null)
        {
            using (dbVOC db = new dbVOC())
                _View_查詢結果 = db.List廠區的申請單(inputsdate.Value, inputedate.Value, plantid, statusid, _View_formid);
        }
        gvList.SetDataSource(_View_查詢結果);
    }

    void BindTag()
    {
        if (_View_廠區項目 == null)
            return;
        gvTag.SetDataSource(_View_廠區項目);
    }

    protected void gvList_SelectedIndexChanged(object sender, EventArgs e)
    {
        _View_flowid = MTDBbase.ToInt32(gvList.SelectedDataKey.Values["flowid"]);
        lbformno.InnerText = gvList.SelectedDataKey.Values["formno"].ToString();
        spanTable.Visible = gvTag.Visible = true;
        gvListSign.SetDataSource(MTFlowBase.List簽核流程(_View_flowid));
        using (dbVOC db = new dbVOC())
            _View_廠區項目 = db.List廠區項目(MTDBbase.ToInt32(gvList.SelectedDataKey.Values["formid"]));
        BindTag();
    }

    protected void gvtagList_PageIndexChanging(object sender, GridViewPageEventArgs e)
    {
        gvList.PageIndex = e.NewPageIndex;
        BindGrid();
    }

    private int GetEditIndex(GridView GridView, int RowIndex)
    {
        int iEditIndex = 0;

        if (GridView.AllowPaging)
        {
            //GridView有分頁時，index=頁次*分頁大小+頁面的index
            iEditIndex = (GridView.PageIndex) * GridView.PageSize + RowIndex;
        }
        else
        {
            //GridView無分頁時，直接使用RowIndex
            iEditIndex = RowIndex;
        }
        return iEditIndex;
    }

    protected void gvTag_PageIndexChanging(object sender, GridViewPageEventArgs e)
    {
        gvTag.EditIndex = -1;
        gvTag.PageIndex = e.NewPageIndex;
        BindTag();
    }
}