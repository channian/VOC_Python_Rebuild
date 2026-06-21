using System;
using System.Collections;
using System.Collections.Generic;
using System.Data;
using System.Linq;
using System.Web;
using System.Web.UI;
using System.Web.UI.WebControls;
using MTLibrary;

public partial class EditDeptList : BasePage
{
    public int _View_EditDeptListACL
    {
        get { return MTDBbase.ToInt32(ViewState["EditDeptList_ACL"], -1); }
        set { ViewState["EditDeptList_ACL"] = value; }
    }

    public DataTable _View_EditDeptListDT
    {
        get { return ViewState["EditDeptList_DT"] as DataTable; }
        set { ViewState["EditDeptList_DT"] = value; }
    }

    protected void Page_Load(object sender, EventArgs e)
    {
        if (!Page.IsPostBack)
        {
            btnBack.PostBackUrl = "~/Default.aspx";

            tbNum.Text = "10";

            using (dbAclRights db = new dbAclRights())
                _View_EditDeptListACL = db.Check權限(dbAclRights.使用者權限.部門權限維護);

            using (dbVOC db = new dbVOC())
            {
                if (ddlplant.DataSource == null)
                {
                    SetValueList(ddlplant, MTDBbase.AddNullValue(db.List廠區9()));
                    SetValueList(ddldept, MTDBbase.AddNullValue(db.List部門()));
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
                SetValueList(ddlplant, MTDBbase.AddNullValue(db.List廠區10(ddlplant.SelectedValue, ddldept.SelectedValue)));
            if (ddldept.SelectedItem.Text == "")
                SetValueList(ddldept, MTDBbase.AddNullValue(db.List部門1(ddlplant.SelectedValue, ddldept.SelectedValue)));
        }
    }

    protected void ddldept_SelectedIndexChanged(object sender, EventArgs e)
    {
        using (dbVOC db = new dbVOC())
        {
            if (ddlplant.SelectedItem.Text == "")
                SetValueList(ddlplant, MTDBbase.AddNullValue(db.List廠區10(ddlplant.SelectedValue, ddldept.SelectedValue)));
            if (ddldept.SelectedItem.Text == "")
                SetValueList(ddldept, MTDBbase.AddNullValue(db.List部門1(ddlplant.SelectedValue, ddldept.SelectedValue)));
        }
    }

    protected void btn查詢_Click(object sender, EventArgs e)
    {
        BindGrid();
    }

    private DataTable GetData()
    {
        string plantid = ddlplant.SelectedValue.ToString();
        string deptno = ddldept.SelectedValue.ToString();

        using (dbVOC db = new dbVOC()) return db.List部門資料(plantid, deptno);
    }

    protected void BindGrid()
    {
        _View_EditDeptListDT = GetData();

        gvtagList.SetDataSource(_View_EditDeptListDT);
    }

    protected void gvtagList_RowCommand(object sender, GridViewCommandEventArgs e)
    {
        switch (e.CommandName)
        {
            case "Insert":
                tbdata.Visible = true;
                using (dbVOC db = new dbVOC()) SetValueList(_0plant, MTDBbase.AddNullValue(db.List廠區9()));
                _0plant.SelectedIndex = -1;
                __deptno.Text = "";
                __deptname.Text = "";
                __remark.Text = "";
                _0plant.Enabled = true;
                __deptno.Enabled = true;
                __deptname.Enabled = false;
                __remark.Text = "";
                InsertButton.Visible = true;
                UpdateButton.Visible = false;
                DeleteButton.Visible = false;
                gvtagList.Visible = false;
                break;
            case "Edit":
                tbdata.Visible = true;
                __remark.Text = "";
                using (dbVOC db = new dbVOC()) SetValueList(_0plant, MTDBbase.AddNullValue(db.List廠區9()));
                InsertButton.Visible = false;
                UpdateButton.Visible = true;
                DeleteButton.Visible = false;
                gvtagList.Visible = false;
                break;
            case "Delete":
                tbdata.Visible = true;
                __remark.Text = "";
                using (dbVOC db = new dbVOC()) SetValueList(_0plant, MTDBbase.AddNullValue(db.List廠區9()));
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
        string deptno = dbVOC.GetDataControlFieldCellValue("deptno", gvtagList.Columns, gvr);
        string deptname = dbVOC.GetDataControlFieldCellValue("deptname", gvtagList.Columns, gvr);

        for (int i = 0; i < _0plant.Items.Count; i++)
        {
            if (_0plant.Items[i].Text == plantno)
            {
                _0plant.SelectedIndex = i;
                break;
            }
        }

        __deptno.Text = deptno;
        __deptname.Text = deptname;

        lbdeptno1.Text = deptno;
        lbdeptname.Text = deptname;

        _0plant.Enabled = false;
        __deptno.Enabled = true;
        __deptname.Enabled = false;
    }

    protected void gvtagList_RowDeleting(object sender, GridViewDeleteEventArgs e)
    {
        string plantno = e.Keys["plantno"].ToString();
        string deptno = e.Keys["deptno"].ToString();

        DataTable DT;
        using (dbVOC db = new dbVOC()) DT = db.List部門資料(plantno, deptno);

        string deptname = DT.Rows[0]["deptname"].ToString();

        for (int i = 0; i < _0plant.Items.Count; i++)
        {
            if (_0plant.Items[i].Text == plantno)
            {
                _0plant.SelectedIndex = i;
                break;
            }
        }

        __deptno.Text = deptno;
        __deptname.Text = deptname;

        _0plant.Enabled = false;
        __deptno.Enabled = false;
        __deptname.Enabled = false;
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
        _View_EditDeptListDT = null;
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
            if (!db.InsertDeptList(row))
            {
                db.MsgBox(Page, "新增部門資料失敗!\n" + db._Exception);
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
            if (!db.UpdateDeptList(row, lbdeptno1.Text, lbdeptname.Text))
            {
                db.MsgBox(Page, "修改部門資料失敗!\n" + db._Exception);
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
            if (!db.DeleteDeptList(row))
            {
                db.MsgBox(Page, "刪除部門資料失敗!\n" + db._Exception);
                return;
            }
        }
        ChangeMode();
    }
    #endregion

    protected void __deptno_TextChanged(object sender, EventArgs e)
    {
        if (__deptno.Text != "")
        {
            DataTable dtb;
            using (dbVOC db = new dbVOC())
            {
                dtb = db.Get部門名稱(__deptno.Text);
                if (dtb.Rows.Count == 0)
                {
                    __deptname.Text = "";
                    db.MsgBox(Page, "部門代碼錯誤!\n" + db._Exception);
                    return;
                }
                __deptname.Text = dtb.Rows[0]["deptname"].ToString();
            }
        }
        else __deptname.Text = "";
    }
}