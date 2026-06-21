using System;
using System.Collections;
using System.Collections.Generic;
using System.Data;
using System.Linq;
using System.Web;
using System.Web.UI;
using System.Web.UI.WebControls;
using MTLibrary;

public partial class EditAclUser : BasePage
{
    public int _View_EditAclUserACL
    {
        get { return MTDBbase.ToInt32(ViewState["EditAclUser_ACL"], -1); }
        set { ViewState["EditAclUser_ACL"] = value; }
    }

    public DataTable _View_EditAclUserDT
    {
        get { return ViewState["EditAclUser_DT"] as DataTable; }
        set { ViewState["EditAclUser_DT"] = value; }
    }

    protected void Page_Load(object sender, EventArgs e)
    {
        if (!Page.IsPostBack)
        {
            btnBack.PostBackUrl = "~/Default.aspx";

            tbNum.Text = "10";

            using (dbAclRights db = new dbAclRights())
                _View_EditAclUserACL = db.Check權限(dbAclRights.使用者權限.隔離權限維護);

            using (dbVOC db = new dbVOC())
            {
                if (ddlplant.DataSource == null)
                {
                    SetValueList(ddlplant, MTDBbase.AddNullValue(db.List廠區6()));
                    SetValueList(ddltype, MTDBbase.AddNullValue(db.List權限()));
                }
            }

            BindGrid();
        }
    }

    protected void ddlplant_SelectedIndexChanged(object sender, EventArgs e)
    {
        using (dbVOC db = new dbVOC())
        {
            if (ddlplant.SelectedItem.Text == "")
                SetValueList(ddlplant, MTDBbase.AddNullValue(db.List廠區7(ddlplant.SelectedValue, ddltype.SelectedValue)));
            if (ddltype.SelectedItem.Text == "")
                SetValueList(ddltype, MTDBbase.AddNullValue(db.List權限1(ddlplant.SelectedValue, ddltype.SelectedValue)));
        }
    }

    protected void ddltype_SelectedIndexChanged(object sender, EventArgs e)
    {
        using (dbVOC db = new dbVOC())
        {
            if (ddlplant.SelectedItem.Text == "")
                SetValueList(ddlplant, MTDBbase.AddNullValue(db.List廠區7(ddlplant.SelectedValue, ddltype.SelectedValue)));
            if (ddltype.SelectedItem.Text == "")
                SetValueList(ddltype, MTDBbase.AddNullValue(db.List權限1(ddlplant.SelectedValue, ddltype.SelectedValue)));
        }
    }

    protected void btn查詢_Click(object sender, EventArgs e)
    {
        BindGrid();
    }

    private DataTable GetData()
    {
        string plantno = ddlplant.SelectedItem.Text;
        string roletype = ddltype.SelectedItem.Text;

        using (dbVOC db = new dbVOC()) return db.List隔離權限名單資料(plantno, roletype);
    }

    protected void BindGrid()
    {
        _View_EditAclUserDT = GetData();

        gvtagList.SetDataSource(_View_EditAclUserDT);
    }

    protected void gvtagList_RowCommand(object sender, GridViewCommandEventArgs e)
    {
        switch (e.CommandName)
        {
            case "Insert":
                tbdata.Visible = true;
                using (dbVOC db = new dbVOC())
                {
                    SetValueList(_0plant, MTDBbase.AddNullValue(db.List廠區6()));
                    SetValueList(_0type, MTDBbase.AddNullValue(db.List權限()));
                }
                _0plant.SelectedIndex = -1;
                __empno.Text = "";
                __empname.Text = "";
                __notesid.Text = "";
                __stype.SelectedValue = "2";
                __remark.Text = "";
                _0plant.Enabled = true;
                __empno.Enabled = true;
                __empname.Enabled = false;
                __notesid.Enabled = true;
                __stype.Enabled = true;
                __remark.Text = "";
                InsertButton.Visible = true;
                UpdateButton.Visible = false;
                DeleteButton.Visible = false;
                gvtagList.Visible = false;
                break;
            case "Edit":
                tbdata.Visible = true;
                __remark.Text = "";
                using (dbVOC db = new dbVOC())
                {
                    SetValueList(_0plant, MTDBbase.AddNullValue(db.List廠區6()));
                    SetValueList(_0type, MTDBbase.AddNullValue(db.List權限()));
                }
                InsertButton.Visible = false;
                UpdateButton.Visible = true;
                DeleteButton.Visible = false;
                gvtagList.Visible = false;
                break;
            case "Delete":
                tbdata.Visible = true;
                __remark.Text = "";
                using (dbVOC db = new dbVOC())
                {
                    SetValueList(_0plant, MTDBbase.AddNullValue(db.List廠區6()));
                    SetValueList(_0type, MTDBbase.AddNullValue(db.List權限()));
                }
                InsertButton.Visible = false;
                UpdateButton.Visible = false;
                DeleteButton.Visible = true;
                gvtagList.Visible = false;
                break;
        }
    }

    protected void gvtagList_RowEditing(object sender, GridViewEditEventArgs e)
    {
        GridViewRow gvr = gvtagList.Rows[e.NewEditIndex];

        string plantno = dbVOC.GetDataControlFieldCellValue("plantno", gvtagList.Columns, gvr);
        string roletype = dbVOC.GetDataControlFieldCellValue("roletype", gvtagList.Columns, gvr);
        string empno = dbVOC.GetDataControlFieldCellValue("empno", gvtagList.Columns, gvr);
        string empname = dbVOC.GetDataControlFieldCellValue("empname", gvtagList.Columns, gvr);
        string notesid = dbVOC.GetDataControlFieldCellValue("notesid", gvtagList.Columns, gvr);
        string stype = dbVOC.GetDataControlFieldCellValue("stype", gvtagList.Columns, gvr);

        for (int i = 0; i < _0plant.Items.Count; i++)
        {
            if (_0plant.Items[i].Text == plantno)
            {
                _0plant.SelectedIndex = i;
                break;
            }
        }

        for (int i = 0; i < _0type.Items.Count; i++)
        {
            if (_0type.Items[i].Text == roletype)
            {
                _0type.SelectedIndex = i;
                break;
            }
        }

        __empno.Text = empno;
        __empname.Text = empname;
        __notesid.Text = notesid;
        __stype.SelectedValue = (stype == "空" ? "1" : (stype == "水" ? "2" : "3"));

        lbempno1.Text = empno;
        lbempname.Text = empname;
        lbnotesid.Text = notesid;
        lbstype1.Text = stype;

        _0plant.Enabled = false;
        _0type.Enabled = false;
        __empno.Enabled = true;
        __empname.Enabled = false;
        __notesid.Enabled = true;
        __stype.Enabled = true;
    }

    protected void gvtagList_RowDeleting(object sender, GridViewDeleteEventArgs e)
    {
        string plantno = e.Keys["plantno"].ToString();
        string roletype = e.Keys["roletype"].ToString();
        string empno = e.Keys["empno"].ToString();

        DataTable DT;
        using (dbVOC db = new dbVOC()) DT = db.List隔離權限名單資料(plantno, roletype, empno);

        string empname = DT.Rows[0]["empname"].ToString();
        string notesid = DT.Rows[0]["notesid"].ToString();
        string stype = DT.Rows[0]["stype"].ToString();

        for (int i = 0; i < _0plant.Items.Count; i++)
        {
            if (_0plant.Items[i].Text == plantno)
            {
                _0plant.SelectedIndex = i;
                break;
            }
        }

        for (int i = 0; i < _0type.Items.Count; i++)
        {
            if (_0type.Items[i].Text == roletype)
            {
                _0type.SelectedIndex = i;
                break;
            }
        }

        __empno.Text = empno;
        __empname.Text = empname;
        __notesid.Text = notesid;
        __stype.SelectedValue = (stype == "空" ? "1" : (stype == "水" ? "2" : "3"));

        _0plant.Enabled = false;
        _0type.Enabled = false;
        __empno.Enabled = false;
        __empname.Enabled = false;
        __notesid.Enabled = false;
        __stype.Enabled = false;
    }

    protected void gvtagList_PageIndexChanging(object sender, GridViewPageEventArgs e)
    {
        gvtagList.PageIndex = e.NewPageIndex;
        BindGrid();
    }

    protected void tbNum_TextChanged(object sender, EventArgs e)
    {
        gvtagList.PageSize = MTDBbase.ToInt32(tbNum.Text, 10);
        BindGrid();
    }

    #region tbdata
    private void ChangeMode()
    {
        tbdata.Visible = false;
        gvtagList.Visible = true;
        gvtagList.EditIndex = -1;
        _View_EditAclUserDT = null;
        BindGrid();
    }

    protected void CancelButton_Click(object sender, EventArgs e)
    {
        ChangeMode();
    }

    protected void InsertButton_Click(object sender, EventArgs e)
    {
        Hashtable row = ExtractValue(tbdata);
        using (dbVOC db = new dbVOC())
        {
            if (!db.InsertAclUserList(row))
            {
                db.MsgBox(Page, "新增隔離權限名單資料失敗!\n" + db._Exception);
                return;
            }
        }
        ChangeMode();
    }

    protected void UpdateButton_Click(object sender, EventArgs e)
    {
        Hashtable row = ExtractValue(tbdata);
        using (dbVOC db = new dbVOC())
        {
            if (!db.UpdateAclUserList(row, lbempno1.Text, lbstype1.Text))
            {
                db.MsgBox(Page, "修改隔離權限名單資料失敗!\n" + db._Exception);
                return;
            }
        }
        ChangeMode();
    }

    protected void DeleteButton_Click(object sender, EventArgs e)
    {
        Hashtable row = ExtractValue(tbdata);
        using (dbVOC db = new dbVOC())
        {
            if (!db.DeleteAclUserList(row))
            {
                db.MsgBox(Page, "刪除隔離權限名單資料失敗!\n" + db._Exception);
                return;
            }
        }
        ChangeMode();
    }
    #endregion

    protected void __empno_TextChanged(object sender, EventArgs e)
    {
        if (__empno.Text != "")
        {
            int empid = -1;
            DataTable dtb;
            using (dbSignFlow db = new dbSignFlow())
            {
                empid = db.Get員工id(__empno.Text);
                dtb = db.Get員工資訊(empid);
                if (dtb.Rows.Count > 0)
                {
                    __empname.Text = dtb.Rows[0]["empname"].ToString();
                    __notesid.Text = dtb.Rows[0]["email"].ToString().Replace("_", " ").Replace("@aseglobal.com", "");
                    __notesid.Enabled = false;
                }
            }
        }
        else
        {
            __empname.Text = "";
            __notesid.Text = "";
            __notesid.Enabled = true;
        }
    }
}