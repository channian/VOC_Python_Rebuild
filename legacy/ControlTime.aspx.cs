using System;
using System.Collections;
using System.Collections.Generic;
using System.Data;
using System.Linq;
using System.Web;
using System.Web.UI;
using System.Web.UI.WebControls;
using MTLibrary;

public partial class ControlTime : BasePage
{
    public string _View_sdate
    {
        get { return ViewState["ControlTime_sdate"] as string; }
        set { ViewState["ControlTime_sdate"] = value; }
    }

    public string _View_edate
    {
        get { return ViewState["ControlTime_edate"] as string; }
        set { ViewState["ControlTime_edate"] = value; }
    }

    public DataTable _View_查詢結果
    {
        get { return ViewState["ControlTime_查詢結果DT"] as DataTable; }
        set { ViewState["ControlTime_查詢結果DT"] = value; }
    }

    public DataTable _View_TagDT
    {
        get { return ViewState["ControlTime_PointDT"] as DataTable; }
        set { ViewState["ControlTime_PointDT"] = value; }
    }

    public int _View_ccid
    {
        get { return MTDBbase.ToInt32(ViewState["ControlTime_View_ccid"], -1); }
        set { ViewState["ControlTime_View_ccid"] = value; }
    }

    protected void Page_Load(object sender, EventArgs e)
    {
        if (!Page.IsPostBack)
        {
            SetCtrlVisible(new Control[] { timeTable, btnUpdate, CancelButton }, false);
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

    protected void btn查詢_Click(object sender, EventArgs e)
    {
        _View_查詢結果 = null;
        _View_ccid = -1;
        SetCtrlVisible(new Control[] { timeTable, btnUpdate, CancelButton }, false);
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
            using (dbVOC db = new dbVOC()) db.MsgBox(Page, "開始時間不可大於結束時間!");
            return;
        }
        int plantid = MTDBbase.ToInt32(ddlplant.SelectedValue);
        int statusid = MTDBbase.ToInt32(rblStatusid.SelectedValue);
        if (_View_查詢結果 == null)
        {
            using (dbVOC db = new dbVOC())
                _View_查詢結果 = db.List廠區的申請單(inputsdate.Value, inputedate.Value, plantid, statusid, _View_ccid);
        }
        gvList.SetDataSource(_View_查詢結果);
    }

    protected void gvList_SelectedIndexChanged(object sender, EventArgs e)
    {
        //__ccno.Text = gvList.SelectedDataKey.Values["ccno"].ToString();
        _View_ccid = MTDBbase.ToInt32(gvList.SelectedDataKey.Values["ccid"]);
        DataTable dtb;
        using (dbVOC db = new dbVOC()) dtb = db.List申請單(_View_ccid);
        FillValue(timeTable, dtb.Rows[0]);
        __stime.Value = Convert.ToDateTime(__stime.Value).ToString("yyyy/MM/dd HH:mm:ss");
        __etime.Value = Convert.ToDateTime(__etime.Value).ToString("yyyy/MM/dd HH:mm:ss");
        _0etime.Value = __etime.Value;
        SetCtrlVisible(new Control[] { timeTable, btnUpdate, CancelButton }, true);
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

     protected void btnUpdate_Click(object sender, EventArgs e)
    {
        Proc修改隔離廠區項目();
        btn查詢_Click(sender, e);
    }

    protected void CancelButton_Click(object sender, EventArgs e)
    {
        SetCtrlVisible(new Control[] { timeTable, btnUpdate, CancelButton }, false);
    }

    void Proc修改隔離廠區項目()
    {
        using (dbVOC db = new dbVOC())
        {
            Hashtable hrow = new Hashtable();
            hrow = ExtractValue(timeTable);
            if (_0etime.Value.CompareTo(hrow["etime"].ToString()) > 0)
            {
                db.MsgBox(Page, "結束時間需大於 " + _0etime.Value + " !");
                return;
            }
            if (!db.Update隔離廠區項目(hrow, _0etime.Value))
            {
                db.MsgBox(Page, db._Exception);
                return;
            }
            db.MsgBox(Page, "隔離廠區項目結束時間修改成功");
        }
    }
}