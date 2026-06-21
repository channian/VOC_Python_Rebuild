using System;
using System.Collections;
using System.Collections.Generic;
using System.Data;
using System.Linq;
using System.Web;
using System.Web.UI;
using System.Web.UI.WebControls;
using MTLibrary;

public partial class EditQA : BasePage
{
    public int _View_ACL
    {
        get { return MTDBbase.ToInt32(ViewState["VOC_ACL"], -1); }
        set { ViewState["VOC_ACL"] = value; }
    }

    public DataTable _View_EditQADT
    {
        get { return ViewState["EditQA_DT"] as DataTable; }
        set { ViewState["EditQA_DT"] = value; }
    }

    protected void Page_Load(object sender, EventArgs e)
    {
        if (!Page.IsPostBack)
        {
            btnBack.PostBackUrl = "~/Default.aspx";

            tbNum.Text = "10";

            using (dbAclRights db = new dbAclRights())
                _View_ACL = db.Check權限(dbAclRights.使用者權限.QA手測值更新);

            using (dbVOC db = new dbVOC())
            {
                if (ddlplant.DataSource == null)
                {
                    SetValueList(ddlplant, MTDBbase.AddNullValue(db.List廠區8()));
                    SetValueList(ddlitem, MTDBbase.AddNullValue(db.List項目4()));
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
                SetValueList(ddlplant, MTDBbase.AddNullValue(db.List廠區1(ddlplant.SelectedValue, ddlitem.SelectedValue)));
            if (ddlitem.SelectedItem.Text == "")
                SetValueList(ddlitem, MTDBbase.AddNullValue(db.List項目1(ddlplant.SelectedValue, ddlitem.SelectedValue)));
        }
    }

    protected void ddlitem_SelectedIndexChanged(object sender, EventArgs e)
    {
        using (dbVOC db = new dbVOC())
        {
            if (ddlplant.SelectedItem.Text == "")
                SetValueList(ddlplant, MTDBbase.AddNullValue(db.List廠區1(ddlplant.SelectedValue, ddlitem.SelectedValue)));
            if (ddlitem.SelectedItem.Text == "")
                SetValueList(ddlitem, MTDBbase.AddNullValue(db.List項目1(ddlplant.SelectedValue, ddlitem.SelectedValue)));
        }
    }

    protected void _0plant_SelectedIndexChanged(object sender, EventArgs e)
    {
        using (dbVOC db = new dbVOC())
            SetValueList(_0item, MTDBbase.AddNullValue(db.List項目1(_0plant.SelectedValue, _0item.SelectedValue)));
    }

    protected void btn查詢_Click(object sender, EventArgs e)
    {
        BindGrid();
    }

    private DataTable GetData()
    {
        string plantno = ddlplant.SelectedItem.Text;
        string item = ddlitem.SelectedItem.Text;
        using (dbVOC db = new dbVOC()) return db.List最新讀值資料(plantno, item);
    }

    protected void BindGrid()
    {
        _View_EditQADT = GetData();

        gvtagList.SetDataSource(_View_EditQADT);
    }

    protected void gvtagList_RowCommand(object sender, GridViewCommandEventArgs e)
    {
        switch (e.CommandName)
        {
            case "Edit":
                tbdata.Visible = true;
                __remark.Text = "";
                using (dbVOC db = new dbVOC())
                {
                    SetValueList(_0plant, MTDBbase.AddNullValue(db.List廠區8()));
                    SetValueList(_0item, MTDBbase.AddNullValue(db.List項目4()));
                }
                UpdateButton.Visible = true;
                gvtagList.Visible = false;
                break;
        }
    }

    protected void gvtagList_RowEditing(object sender, GridViewEditEventArgs e)
    {
        GridViewRow gvr = gvtagList.Rows[e.NewEditIndex];

        string plantno = dbVOC.GetDataControlFieldCellValue("plantno", gvtagList.Columns, gvr);
        string item = dbVOC.GetDataControlFieldCellValue("item", gvtagList.Columns, gvr);
        string rvalue = dbVOC.GetDataControlFieldCellValue("rvalue", gvtagList.Columns, gvr);

        for (int i = 0; i < _0plant.Items.Count; i++)
        {
            if (_0plant.Items[i].Text == plantno)
            {
                _0plant.SelectedIndex = i;
                _0plant_SelectedIndexChanged(sender, e);
                break;
            }
        }

        for (int i = 0; i < _0item.Items.Count; i++)
        {
            if (_0item.Items[i].Text == item)
            {
                _0item.SelectedIndex = i;
                break;
            }
        }

        __rvalue.Text = rvalue;
        lbrvalue1.Text = rvalue;

        _0plant.Enabled = false;
        _0item.Enabled = false;
        __rvalue.Enabled = true;
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
        _View_EditQADT = null;
        BindGrid();
    }

    protected void CancelButton_Click(object sender, EventArgs e)
    {
        ChangeMode();
    }

    protected void UpdateButton_Click(object sender, EventArgs e)
    {
        Hashtable row = ExtractValue(tbdata);
        using (dbVOC db = new dbVOC())
        {
            if (!db.UpdateQA(row, lbrvalue1.Text))
            {
                db.MsgBox(Page, "修改最新讀值資料失敗!\n" + db._Exception);
                return;
            }
            db.MsgBox(Page, "修改最新讀值資料成功!");
        }
        ChangeMode();
    }
    #endregion

    protected void __rvalue_TextChanged(object sender, EventArgs e)
    {
        using (dbVOC db = new dbVOC())
        {
            if (__rvalue.Text != "")
            {
                __rvalue.Text = __rvalue.Text.Trim();
                string rvalue = __rvalue.Text;

                if (rvalue != "<0.05" && rvalue != "<0.02" && rvalue != "<0.01" && rvalue != "N.D")
                {
                    int no;

                    for (int i = 0; i < rvalue.Length; i++)
                    {
                        if (rvalue.Substring(i, 1) != ".")
                        {
                            no = MTDBbase.ToInt32(rvalue.Substring(i, 1), -1);
                            if (no < 0 || no > 9)
                            {
                                db.MsgBox(Page, "最新讀值(" + rvalue + ")錯誤, 請輸入數字!");
                                return;
                            }
                        }
                    }
                }
            }
        }
    }
}