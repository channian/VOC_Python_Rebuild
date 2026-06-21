using System;
using System.Collections;
using System.Collections.Generic;
using System.Data;
using System.Linq;
using System.Web;
using System.Web.UI;
using System.Web.UI.WebControls;
using MTLibrary;

public partial class ModifyControl : BasePage
{
    public int _View_ttypeid
    {
        get { return MTDBbase.ToInt32(ViewState["ModifyControl_ttypeid"], -1); }
        set { ViewState["ModifyControl_ttypeid"] = value; }
    }
    public int _View_ccid
    {
        get { return MTDBbase.ToInt32(ViewState["ModifyControl_ccid"], -1); }
        set { ViewState["ModifyControl_ccid"] = value; }
    }

    public DataTable _View_TagDT
    {
        get { return ViewState["ModifyControl_PointDT"] as DataTable; }
        set { ViewState["ModifyControl_PointDT"] = value; }
    }

    protected void Page_Load(object sender, EventArgs e)
    {
        if (!Page.IsPostBack)
        {
            if (_0plantid.DataSource == null)
            {
                using (dbVOC db = new dbVOC())
                {
                    SetValueList(_0plantid, MTDBbase.AddNullValue(db.List廠區2()));
                }
            }
            __ccno.Text = "自動編號";
            __cempno.Text = AppConfig.Sess_UserEmpNo;
            __cempname.Text = AppConfig.Sess_UserEmpName;
            SetCtrlReadonly(new Control[] { _0plantid }, true);
            if (Request.QueryString.HasKeys())
            {
                _View_ccid = MTDBbase.ToInt32(Request.QueryString["ccid"].ToString(), -1);
                _View_ttypeid = 2;
                if (_View_ccid > 0) JoinData();
            }
        }
    }

    protected void btn查詢_Click(object sender, EventArgs e)
    {
        _View_TagDT = null;
        JoinData();
    }

    private DataTable GetData()
    {
        using (dbVOC db = new dbVOC())
            return db.List隔離廠區項目(_View_ccid);
    }

    protected void JoinData()
    {
        if (_View_TagDT == null)
            _View_TagDT = GetData();
        gvTag.SetDataSource(_View_TagDT);
        DataTable dtb;
        using (dbVOC db = new dbVOC())
            dtb = db.List申請單(_View_ccid);
        FillValue(table, dtb.Rows[0]);
        __stime.Value = string.Format("{0:yyyy/MM/dd HH:mm}", dtb.Rows[0]["stime"]);
        __etime.Value = string.Format("{0:yyyy/MM/dd HH:mm}", dtb.Rows[0]["etime"]);
        //CompareTo
        //若前面字串大於後面 回傳1
        //若前面字串等於後面 回傳0
        //若前面字串小於後面 回傳-1
        int stimecp = string.Format("{0:yyyy/MM/dd HH:mm}", dtb.Rows[0]["stime"]).CompareTo(DateTime.Now.ToString("yyyy/MM/dd HH:mm"));
        int etimecp = string.Format("{0:yyyy/MM/dd HH:mm}", dtb.Rows[0]["etime"]).CompareTo(DateTime.Now.ToString("yyyy/MM/dd HH:mm"));
        if (stimecp < 0)
            SetCtrlReadonly(new Control[] { __stime }, true);
        if (etimecp < 0)
            SetCtrlReadonly(new Control[] { __etime }, true);
        if (stimecp < 0 && etimecp < 0)
        {
            btnSave.Enabled = btnCommit.Enabled = false;
            using (dbVOC db = new dbVOC())
                db.MsgBox(Page, "隔離廠區項目區間為過去的資料，已不能再修改，請重新申請!");
        }
    }

    protected void gvTag_PageIndexChanging(object sender, GridViewPageEventArgs e)
    {
        gvTag.EditIndex = -1;
        gvTag.PageIndex = e.NewPageIndex;
        JoinData();
    }

    private bool DataValidation(dbVOC db, Hashtable vals)
    {
        if (MTDBbase.ToInt32(vals["plantid"], -1) < 0)
        {
            db._Exception = "請輸入廠區!";
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
        DataRow[] rows = _View_TagDT.Select("isselect=1");
        using (dbVOC db = new dbVOC())
        {
            Hashtable hrow = new Hashtable();
            hrow = ExtractValue(table);
            hrow["ttypeid"] = (int)dbVOC.Ttype.修改隔離區間;
            hrow["orgccid"] = _View_ccid;
            if (!DataValidation(db, hrow))
            {
                db.MsgBox(Page, db._Exception);
                return;
            }
            else
            {
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
            db.MsgBox(Page, "隔離廠區項目區間" + (!isCommit ? "暫存" : "送簽") + "成功");
            if (isCommit) SetCtrlVisible(new Control[] { btnSave, btnCommit }, false);
        }
    }
}