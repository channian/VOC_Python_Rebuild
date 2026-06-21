using System;
using System.Collections;
using System.Collections.Generic;
using System.Data;
using System.Linq;
using System.Web;
using System.Web.UI;
using System.Web.UI.WebControls;
using MTLibrary;

public partial class SignControl : BasePage
{
    public string _View_sdate
    {
        get { return ViewState["SignControl_sdate"] as string; }
        set { ViewState["SignControl_sdate"] = value; }
    }

    public string _View_edate
    {
        get { return ViewState["SignControl_edate"] as string; }
        set { ViewState["SignControl_edate"] = value; }
    }

    public DataTable _View_查詢結果
    {
        get { return ViewState["SignControl_查詢結果DT"] as DataTable; }
        set { ViewState["SignControl_查詢結果DT"] = value; }
    }

    public DataTable _View_隔離廠區項目
    {
        get { return ViewState["SignControl_隔離廠區項目DT"] as DataTable; }
        set { ViewState["SignControl_隔離廠區項目DT"] = value; }
    }

    public int _View_ccid
    {
        get { return MTDBbase.ToInt32(ViewState["SignControl_View_ccid"], -1); }
        set { ViewState["SignControl_View_ccid"] = value; }
    }

    public int _View_flowid
    {
        get { return MTDBbase.ToInt32(ViewState["SignControl_View_flowid"], -1); }
        set { ViewState["SignControl_View_flowid"] = value; }
    }

    public int _View_close
    {
        get { return MTDBbase.ToInt32(ViewState["SignControl_View_close"], -1); }
        set { ViewState["SignControl_View_close"] = value; }
    }

    protected void Page_Load(object sender, EventArgs e)
    {
        if (!Page.IsPostBack)
        {
            spanTable.Visible = gvTag.Visible = false;
            if (Request.QueryString.HasKeys())
            {
                _View_close = 1;
                _View_ccid = MTDBbase.ToInt32(Request.QueryString["ccid"].ToString(), -1);
                if (_View_ccid > 0)
                {
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
                _View_close = 0;
                inputsdate.Value = DateTime.Today.AddDays(-6).ToString("yyyy/MM/dd");
                inputedate.Value = DateTime.Today.ToString("yyyy/MM/dd");
                btn查詢_Click(sender, e);
            }
        }
        if (_0signactionid.DataSource == null)
        {
            SetValueList(_0signactionid, MTDBbase.AddNullValue(MTFlowBase.List簽核結果VL(1)));
        }
    }


    protected void btn查詢_Click(object sender, EventArgs e)
    {
        _View_查詢結果 = null;
        _View_ccid = _View_flowid = -1;
        lbccno.InnerText = "";
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
        if (_View_查詢結果 == null)
        {
            using (dbVOC db = new dbVOC())
                _View_查詢結果 = db.List我的待辦事項(inputsdate.Value, inputedate.Value, _View_ccid);
        }
        gvList.SetDataSource(_View_查詢結果);
    }
    void BindTag()
    {
        if (_View_隔離廠區項目 == null)
            return;
        gvTag.SetDataSource(_View_隔離廠區項目);
    }
    protected void gvList_SelectedIndexChanged(object sender, EventArgs e)
    {
        _View_flowid = MTDBbase.ToInt32(gvList.SelectedDataKey.Values["flowid"]);
        _View_ccid = MTDBbase.ToInt32(gvList.SelectedDataKey.Values["ccid"]);
        lbccno.InnerText = gvList.SelectedDataKey.Values["ccno"].ToString();

        if (_View_flowid <= 0)
        {
            using (dbVOC db = new dbVOC()) db.MsgBox(Page, "請先選擇!");
            return;
        }
        spanTable.Visible = gvTag.Visible = true;
        gvListSign.SetDataSource(MTFlowBase.List簽核流程(_View_flowid));
        __empno.Text = AppConfig.Sess_UserEmpNo;
        using (dbVOC db = new dbVOC())
            _View_隔離廠區項目 = db.List隔離廠區項目(MTDBbase.ToInt32(gvList.SelectedDataKey.Values["ccid"]));
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

    protected void gvListSign_PageIndexChanging(object sender, GridViewPageEventArgs e)
    {
        gvListSign.EditIndex = -1;
        gvListSign.PageIndex = e.NewPageIndex;
        gvListSign.SetDataSource(MTFlowBase.List簽核流程(_View_flowid));
    }

    private bool DataValidation(dbVOC db, Hashtable vals)
    {
        if (MTDBbase.ToInt32(vals["signactionid"], -1) < 0)
        {
            db._Exception = "請選擇簽核結果!";
            return false;
        }

        if ((MTDBbase.ToInt32(vals["signactionid"], -1) == (int)MTFlowBase.SignAction.否決) && __signmemo.Text == "")
        {
            db._Exception = "請輸入否決原因!";
            return false;
        }

        return IsValid;
    }

    protected void btn簽核_Click(object sender, EventArgs e)
    {
        Hashtable row = ExtractValue(signtable);
        row["flowid"] = _View_flowid;
        row["ccid"] = _View_ccid;
        using (dbVOC db = new dbVOC())
        {
            if (!DataValidation(db, row))
            {
                db.MsgBox(Page, db._Exception);
                return;
            }

            if (!db.ProcSign(row))
            {
                db.MsgBox(Page, "簽核失敗!" + db._Exception);
                return;
            }
            else
            {
                db.MsgBox(Page, "簽核成功!");
                btn查詢_Click(sender, e);
            }
        }
    }

    protected void btn關閉_Click(object sender, EventArgs e)
    {
        if (_View_close > 0)
        {
            string script = "window.opener=null;window.close();";
            ScriptManager.RegisterStartupScript(this.Page, this.Page.GetType(), "", script, true);
        }
        else
            btn查詢_Click(sender, e);
    }
}