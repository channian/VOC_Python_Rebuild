using System;
using System.Collections;
using System.Collections.Generic;
using System.Data;
using System.Linq;
using System.Web;
using System.Web.UI;
using System.Web.UI.WebControls;
using MTLibrary;

public partial class EditControl : BasePage
{
    public DataTable _View_ControlDT
    {
        get { return ViewState["EditControl_DT"] as DataTable; }
        set { ViewState["EditControl_DT"] = value; }
    }

    protected void Page_Load(object sender, EventArgs e)
    {

        if (!Page.IsPostBack)
        {
            if (ddlplant.DataSource == null)
            {
                using (dbVOC db = new dbVOC())
                    SetValueList(ddlplant, MTDBbase.AddNullValue(db.List廠區2(), "請選擇"));
            }
            ddlplant.SelectedIndex = -1;
            __ccno.Text = "自動編號";
            __cempno.Text = AppConfig.Sess_UserEmpNo;
            __cempname.Text = AppConfig.Sess_UserEmpName;
            SetCtrlReadonly(new Control[] { _0plantid }, true);
            JoinData();
        }
    }

    protected void btn查詢_Click(object sender, EventArgs e)
    {
        _View_ControlDT = null;
        using (dbVOC db = new dbVOC())
        {
            SetValueList(_0plantid, MTDBbase.AddNullValue(db.List廠區2()));
            _0plantid.SelectedValue = ddlplant.SelectedValue;
        }
        JoinData();
        SetCtrlVisible(new Control[] { btnSave, btnCommit }, true);
    }

    private DataTable GetData()
    {
        using (dbVOC db = new dbVOC())
        {
            int plantid = MTDBbase.ToInt32(ddlplant.SelectedValue, -1);
            return db.List廠區項目(plantid);
        }
    }

    protected void JoinData()
    {
        if (_View_ControlDT == null)
            _View_ControlDT = GetData();
        gvTag.SetDataSource(_View_ControlDT);
    }

    protected void gvTag_PageIndexChanging(object sender, GridViewPageEventArgs e)
    {
        gvTag.EditIndex = -1;
        gvTag.PageIndex = e.NewPageIndex;
        JoinData();
    }

    protected void ckbselected_CheckedChanged(object sender, EventArgs e)
    {
        CheckBox chkSampleStatus = sender as CheckBox;
        bool sample = chkSampleStatus.Checked;
        GridViewRow row = chkSampleStatus.NamingContainer as GridViewRow;
        HiddenField VOC_NO = row.FindControl("hfTagName") as HiddenField;
        HiddenField VOC_SO = row.FindControl("hfsource") as HiddenField;
        DataRow[] rows = _View_ControlDT.Select("TagName='" + VOC_NO.Value + "' and source='" + VOC_SO.Value + "'");
        if (rows.Length == 1)
            rows[0]["isselect"] = MTDBbase.ToInt32(rows[0]["isselect"]) == 1 ? 0 : 1;
        _View_ControlDT.AcceptChanges();
    }

    private bool DataValidation(dbVOC db, Hashtable vals)
    {
        if (MTDBbase.ToInt32(vals["plantid"], -1) < 0)
        {
            db._Exception = "請選擇廠區!";
            return false;
        }
        return IsValid;
    }

    protected void btnSave_Click(object sender, EventArgs e)
    {   //暫存
        Proc新增隔離廠區項目(false);
    }

    protected void btnCommit_Click(object sender, EventArgs e)
    {   //送簽
        Proc新增隔離廠區項目(true);
    }

    protected void CancelButton_Click(object sender, EventArgs e)
    {
        Response.Redirect(ResolveClientUrl("~/MyApply.aspx"));
    }

    void Proc新增隔離廠區項目(bool isCommit)
    {
        using (dbVOC db = new dbVOC())
        {
            DataRow[] rows = _View_ControlDT.Select("isselect=1");
            if (rows.Length == 0)
            {
                db.MsgBox(Page, "尚未選擇要隔離的廠區項目!");
                return;
            }

            Hashtable hrow = new Hashtable();
            hrow = ExtractValue(table);
            hrow["ttypeid"] = (int)dbVOC.Ttype.新增;
            if (!DataValidation(db, hrow))
            {
                db.MsgBox(Page, db._Exception);
                return;
            }
            else
            {
                if (!db.Check申請隔離廠區項目(hrow, rows))
                {
                    db.MsgBox(Page, "重覆申請隔離廠區項目!");
                    return;
                }

                DateTime stime = Convert.ToDateTime(__stime.Value);
                DateTime etime = Convert.ToDateTime(__etime.Value);
                TimeSpan ts = etime - stime;

                if (stime.CompareTo(DateTime.Now) < 0)
                {
                    db.MsgBox(Page, "開始時間不可小於系統時間!");
                    return;
                }

                if (stime.CompareTo(etime) > 0)
                {
                    db.MsgBox(Page, "開始時間不可大於結束時間!");
                    return;
                }

                if (ts.Days > 0 || ts.Hours > 1 || (ts.Hours == 1 && ts.Minutes != 0))
                {
                    db.MsgBox(Page, "隔離廠區項目時間不得超過1小時!");
                    return;
                }

                if (!db.Insert隔離廠區項目(hrow, rows, isCommit))
                {
                    db.MsgBox(Page, db._Exception);
                    return;
                }
            }

            db.MsgBox(Page, "隔離廠區項目區間" + (!isCommit ? "暫存" : "送簽") + "成功!");
            if (isCommit) SetCtrlVisible(new Control[] { btnSave, btnCommit }, false);
        }
    }

    protected void btnSelectAll_Click(object sender, EventArgs e)
    {
        UpdateSelect(1);
    }

    protected void btnNotSelect_Click(object sender, EventArgs e)
    {
        UpdateSelect(0);
    }

    void UpdateSelect(int isselect)
    {
        int size = gvTag.PageSize;
        if (gvTag.PageCount - 1 == gvTag.PageIndex)
            size = _View_ControlDT.Rows.Count % gvTag.PageSize;
        if (size == 0)
            size = gvTag.PageSize;
        for (int i = 0; i < size; i++)
        {
            _View_ControlDT.Rows[gvTag.PageIndex * 15 + i]["isselect"] = isselect;
        }
        _View_ControlDT.AcceptChanges();
        JoinData();
    }
}