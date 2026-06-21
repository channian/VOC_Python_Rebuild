using System;
using System.Collections;
using System.Collections.Generic;
using System.Data;
using System.Linq;
using System.Web;
using System.Web.UI;
using System.Web.UI.WebControls;
using MTLibrary;

public partial class VOCreason : BasePage
{
    public DataTable _View_VOClogDT
    {
        get { return ViewState["VOCreason_DT"] as DataTable; }
        set { ViewState["VOCreason_DT"] = value; }
    }

    public string _View_sdate
    {
        get { return ViewState["VOCreason_sdate"] as string; }
        set { ViewState["VOCreason_sdate"] = value; }
    }

    public string _View_edate
    {
        get { return ViewState["VOCreason_edate"] as string; }
        set { ViewState["VOCreason_edate"] = value; }
    }

    public string _View_stime
    {
        get { return ViewState["VOCreason_stime"] as string; }
        set { ViewState["VOCreason_stime"] = value; }
    }

    public string _View_access
    {
        get { return ViewState["VOCreason_access"] as string; }
        set { ViewState["VOCreason_access"] = value; }
    }

    public string _View_type
    {
        get { return ViewState["VOCreason_type"] as string; }
        set { ViewState["VOCreason_type"] = value; }
    }

    public string _View_change
    {
        get { return ViewState["VOCreason_change"] as string; }
        set { ViewState["VOCreason_change"] = value; }
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
                    SetValueList(_0itemid, MTDBbase.AddNullValue(db.List項目1()));
                    _View_stime = "";
                    _View_access = "Y";
                    _View_type = "";

                    if (Request.QueryString.HasKeys())
                    {
                        string plant = Request.QueryString["plantno"].ToStringTrim();
                        string item = Request.QueryString["item"].ToStringTrim();
                        int ipage = MTDBbase.ToInt32(Request.QueryString["ipage"], -1);
                        _View_sdate = Request.QueryString["sdate"].ToStringTrim();
                        _View_edate = Request.QueryString["edate"].ToStringTrim();
                        _View_stime = Request.QueryString["stime"].ToStringTrim();
                        _View_access = Request.QueryString["access"].ToStringTrim();
                        _View_type = Request.QueryString["type"].ToStringTrim();
                        _View_change = Request.QueryString["change"].ToStringTrim();

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
                        //string MT = Request.QueryString["MT"].ToStringTrim();
                        //if (MT == "True") cbMT.Checked = true;

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
                SetValueList(_0itemid, MTDBbase.AddNullValue(db.List項目1()));
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

        using (dbVOC db = new dbVOC()) return db.ListVOClog(plant, item, _View_sdate, _View_edate, MT, _View_stime, _View_type, _View_change);
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

        gvList_BindGrid(_View_VOClogDT);
    }

    protected void gvList_BindGrid(DataTable dtb)
    {
       gvList.SetDataSource(dtb);
       foreach (GridViewRow gvr in gvList.Rows)
       {
            Button reply = (Button)(gvr.FindControl("btnEdit"));
            Label reason = (Label)(gvr.FindControl("lbreason"));
            //if (_View_access == "N" || (reason != null && reason.Text != "")) reply.Enabled = false;
        }
    }

    protected void gvList_RowEditing(object sender, GridViewEditEventArgs e)
    {
        gvList.EditIndex = e.NewEditIndex;
        BindGrid();
    }

    protected void gvList_RowCancelingEdit(object sender, GridViewCancelEditEventArgs e)
    {
        gvList.EditIndex = -1;
        BindGrid();
    }

    protected void gvList_RowUpdating(object sender, GridViewUpdateEventArgs e)
    {
        string logid = ((HiddenField)gvList.Rows[e.RowIndex].FindControl("hflogid")).Value;
        string plantno = ((Label)gvList.Rows[e.RowIndex].Cells[1].FindControl("lbplantno1")).Text;
        string cdatetime = ((Label)gvList.Rows[e.RowIndex].Cells[2].FindControl("lbcdatetime1")).Text;
        string msg = ((Label)gvList.Rows[e.RowIndex].Cells[3].FindControl("lbmsg1")).Text;
        string reason = ((TextBox)gvList.Rows[e.RowIndex].Cells[4].FindControl("tbreason")).Text;
        string msg1 = ((HiddenField)gvList.Rows[e.RowIndex].FindControl("hfmsg1")).Value;

        DateTime dt1 = Convert.ToDateTime(cdatetime + ":00.000");
        int m = dt1.Minute % 5;
        string dt0 = dt1.AddMinutes(-m).ToString("yyyy/MM/dd HH:mm:00");

        using (dbVOC db = new dbVOC())
        {
            Hashtable hrow = new Hashtable();
            hrow["logid"] = logid;
            hrow["reason"] = reason;

            if (!db.Update異常原因(hrow))
            {
                db.MsgBox(Page, db._Exception);
                return;
            }

            hrow["plantno"] = plantno;
            hrow["cdatetime"] = cdatetime;
            hrow["cdatetime1"] = dt0;
            hrow["msg"] = msg;
            hrow["msg1"] = msg1;

            if (msg.IndexOf("24H累積雨量") < 0)
            {
                if (msg.IndexOf("水質異常") < 0)
                {
                    if (msg.IndexOf("改排水") < 0)
                    {
                        if (!db.SendMail_異常原因回覆(hrow))
                        {
                            db.MsgBox(Page, db._Exception);
                            return;
                        }
                    }
                    else
                    {
                        if (!db.SendMail_異常原因回覆_改排水(hrow))
                        {
                            db.MsgBox(Page, db._Exception);
                            return;
                        }
                    }
                }
                else
                {
                    if (!db.SendMail_異常原因回覆_水質異常(hrow))
                    {
                        db.MsgBox(Page, db._Exception);
                        return;
                    }
                }
            }
            else
            {
                if (!db.SendMail_異常原因回覆_雨水溝(hrow))
                {
                    db.MsgBox(Page, db._Exception);
                    return;
                }
            }
        }
        gvList.EditIndex = -1;
        _View_VOClogDT = null;
        BindGrid();
    }

    protected void gvList_PageIndexChanging(object sender, GridViewPageEventArgs e)
    {
        gvList.EditIndex = -1;
        gvList.PageIndex = e.NewPageIndex;
        BindGrid();
    }

    protected void CancelButton_Click(object sender, EventArgs e)
    {
        if (Request.QueryString.HasKeys())
            Response.Write("<script language=javascript>window.opener=null;window.close();</script>");
        else
            Response.Redirect(ResolveClientUrl("~/Default.aspx"));
    }
}