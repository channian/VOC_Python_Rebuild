using System;
using System.Collections;
using System.Collections.Generic;
using System.Data;
using System.Linq;
using System.Web;
using System.Web.UI;
using System.Web.UI.WebControls;
using MTLibrary;

public partial class EditSPEC : BasePage
{
    public int _View_ACL
    {
        get { return MTDBbase.ToInt32(ViewState["VOC_ACL"], -1); }
        set { ViewState["VOC_ACL"] = value; }
    }

    public DataTable _View_EditSPECDT
    {
        get { return ViewState["EditSPEC_DT"] as DataTable; }
        set { ViewState["EditSPEC_DT"] = value; }
    }

    protected void Page_Load(object sender, EventArgs e)
    {
        if (!Page.IsPostBack)
        {
            btnBack.PostBackUrl = "~/Default.aspx";

            tbNum.Text = "10";

            using (dbAclRights db = new dbAclRights())
                _View_ACL = db.Check權限(dbAclRights.使用者權限.法規許可值與規格值維護);

            using (dbVOC db = new dbVOC())
            {
                if (ddlplant.DataSource == null)
                {
                    SetValueList(ddlplant, MTDBbase.AddNullValue(db.List廠區()));
                    SetValueList(ddlitem, MTDBbase.AddNullValue(db.List項目()));
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

        if ((plantno == "K14B" || plantno == "K22" || plantno == "九號放流口") && item == "pH")
            item = "pH1";
        else if (plantno == "K14B" && item == "COD")
            item = "COD2";

        using (dbVOC db = new dbVOC()) return db.List規格值資料(plantno, item);
    }

    protected void BindGrid()
    {
        _View_EditSPECDT = GetData();

        gvtagList.SetDataSource(_View_EditSPECDT);
    }

    protected void gvtagList_RowCommand(object sender, GridViewCommandEventArgs e)
    {
        switch (e.CommandName)
        {
            case "Insert":
                tbdata.Visible = true;
                using (dbVOC db = new dbVOC())
                {
                    SetValueList(_0plant, MTDBbase.AddNullValue(db.List廠區()));
                    SetValueList(_0item, MTDBbase.AddNullValue(db.List項目()));
                    SetValueList(_0source, MTDBbase.AddNullValue(db.List來源()));
                }
                _0plant.SelectedIndex = -1;
                _0item.SelectedIndex = -1;
                __LAW.Text = "";
                __OOS.Text = "";
                __OOC.Text = "";
                __alert.Text = "";
                _0source.SelectedIndex = -1;
                __remark.Text = "";
                _0plant.Enabled = true;
                _0item.Enabled = true;
                __LAW.Enabled = true;
                __OOS.Enabled = true;
                __OOC.Enabled = true;
                __alert.Enabled = true;
                _0source.Enabled = true;
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
                    SetValueList(_0plant, MTDBbase.AddNullValue(db.List廠區()));
                    SetValueList(_0item, MTDBbase.AddNullValue(db.List項目()));
                    SetValueList(_0source, MTDBbase.AddNullValue(db.List來源()));
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
                    SetValueList(_0plant, MTDBbase.AddNullValue(db.List廠區()));
                    SetValueList(_0item, MTDBbase.AddNullValue(db.List項目()));
                    SetValueList(_0source, MTDBbase.AddNullValue(db.List來源()));
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
        string item = dbVOC.GetDataControlFieldCellValue("item", gvtagList.Columns, gvr);
        string LAW = dbVOC.GetDataControlFieldCellValue("LAW", gvtagList.Columns, gvr);
        string OOS = dbVOC.GetDataControlFieldCellValue("OOS", gvtagList.Columns, gvr);
        string OOC = dbVOC.GetDataControlFieldCellValue("OOC", gvtagList.Columns, gvr);
        string alert = dbVOC.GetDataControlFieldCellValue("alert", gvtagList.Columns, gvr);
        string source = dbVOC.GetDataControlFieldCellValue("source", gvtagList.Columns, gvr);

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

        __LAW.Text = LAW;
        __OOS.Text = OOS;
        __OOC.Text = OOC;
        __alert.Text = alert;

        for (int i = 0; i < _0source.Items.Count; i++)
        {
            if (_0source.Items[i].Text == source)
            {
                _0source.SelectedIndex = i;
                break;
            }
        }

        lbLAW1.Text = LAW;
        lbOOS1.Text = OOS;
        lbOOC1.Text = OOC;
        lbAlert.Text = alert;
        lbSource.Text = source;

        _0plant.Enabled = false;
        _0item.Enabled = false;
        __LAW.Enabled = true;
        __OOS.Enabled = true;
        __OOC.Enabled = true;
        __alert.Enabled = true;
        _0source.Enabled = true;
    }

    protected void gvtagList_RowDeleting(object sender, GridViewDeleteEventArgs e)
    {
        int plantid = MTDBbase.ToInt32(e.Keys["plantid"], -1);
        int itemid = MTDBbase.ToInt32(e.Keys["itemid"], -1);

        DataTable DT;
        using (dbVOC db = new dbVOC()) DT = db.ListVOC(plantid, itemid);

        string LAW = DT.Rows[0]["LAW"].ToString();
        string OOS = DT.Rows[0]["OOS"].ToString();
        string OOC = DT.Rows[0]["OOC"].ToString();
        string alert = DT.Rows[0]["alert"].ToString();
        string source = DT.Rows[0]["source"].ToString();

        for (int i = 0; i < _0plant.Items.Count; i++)
        {
            if (_0plant.Items[i].Value == plantid.ToString())
            {
                _0plant.SelectedIndex = i;
                break;
            }
        }

        for (int i = 0; i < _0item.Items.Count; i++)
        {
            if (_0item.Items[i].Value == itemid.ToString())
            {
                _0item.SelectedIndex = i;
                break;
            }
        }

        __LAW.Text = LAW;
        __OOS.Text = OOS;
        __OOC.Text = OOC;
        __alert.Text = alert;

        for (int i = 0; i < _0source.Items.Count; i++)
        {
            if (_0source.Items[i].Value == source)
            {
                _0source.SelectedIndex = i;
                break;
            }
        }

        _0plant.Enabled = false;
        _0item.Enabled = false;
        __LAW.Enabled = false;
        __OOS.Enabled = false;
        __OOC.Enabled = false;
        __alert.Enabled = false;
        _0source.Enabled = false;
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
        _View_EditSPECDT = null;
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
            if (!db.InsertSPEC(row))
            {
                db.MsgBox(Page, "新增規格值資料失敗!\n" + db._Exception);
                return;
            }
            //if (!db.CheckSPEC申請(row))
            //{
            //    db.MsgBox(Page, "新增規格值資料送簽失敗!\n" + "前筆資料待主管簽核中, 不得重覆申請!");
            //    return;
            //}
            //if (!db.CheckSPEC(row))
            //{
            //    db.MsgBox(Page, "新增規格值資料送簽失敗!\n" + "此筆資料已存在規格值資料內!");
            //    return;
            //}
            //if (!db.SPEC送簽(row, "I"))
            //{
            //    db.MsgBox(Page, "新增規格值資料送簽失敗!\n" + db._Exception);
            //    return;
            //}
            db.MsgBox(Page, "新增規格值資料成功!");
        }
        ChangeMode();
    }

    protected void UpdateButton_Click(object sender, EventArgs e)
    {
        Hashtable row = ExtractValue(tbdata);
        using (dbVOC db = new dbVOC())
        {
            if (!db.UpdateSPEC(row, lbLAW1.Text, lbOOS1.Text, lbOOC1.Text, lbAlert.Text, lbSource.Text))
            {
                db.MsgBox(Page, "修改規格值資料失敗!\n" + db._Exception);
                return;
            }
            //if (!db.SPEC送簽(row, "M"))
            //{
            //    db.MsgBox(Page, "修改規格值資料送簽失敗!\n" + db._Exception);
            //    return;
            //}
            db.MsgBox(Page, "修改規格值資料成功!");
        }
        ChangeMode();
    }

    protected void DeleteButton_Click(object sender, EventArgs e)
    {
        Hashtable row = ExtractValue(tbdata);
        using (dbVOC db = new dbVOC())
        {
            if (!db.DeleteSPEC(row))
            {
                db.MsgBox(Page, "刪除規格值資料失敗!\n" + db._Exception);
                return;
            }
            //if (!db.SPEC送簽(row, "D"))
            //{
            //    db.MsgBox(Page, "刪除規格值資料送簽失敗!\n" + db._Exception);
            //    return;
            //}
            db.MsgBox(Page, "刪除規格值資料成功!");
        }
        ChangeMode();
    }
    #endregion

    protected void __LAW_TextChanged(object sender, EventArgs e)
    {
        using (dbVOC db = new dbVOC())
        {
            if (__LAW.Text != "" && __LAW.Text != "N/A")
            {
                __LAW.Text = __LAW.Text.Trim();
                string[] LAW = __LAW.Text.Split('-');

                if (_0item.SelectedItem.Text == "pH" && LAW.Length == 1)
                {
                    db.MsgBox(Page, "法規許可值錯誤, 請輸入雙邊規格(如: 6-9)!");
                    return;
                }

                if (_0item.SelectedItem.Text != "pH" && LAW.Length == 2)
                {
                    db.MsgBox(Page, "法規許可值錯誤, 請輸入單邊規格(如: 6)!");
                    return;
                }

                int no;

                for (int i = 0; i < LAW.Length; i++)
                {
                    int dot = LAW[i].IndexOf(".") + 1;
                    if (dot > 0)
                    {
                        if (LAW[i].Length-dot > 2)
                        {
                            db.MsgBox(Page, "法規許可值(" + LAW[i] + ")錯誤, 請輸入二位小數!");
                            return;
                        }
                    }
                    for (int j = 0; j < LAW[i].Length; j++)
                    {
                        if (LAW[i].Substring(j, 1) != ".")
                        {
                            no = MTDBbase.ToInt32(LAW[i].Substring(j, 1), -1);
                            if (no < 0 || no > 9)
                            {
                                db.MsgBox(Page, "法規許可值(" + LAW[i] + ")錯誤, 請輸入數字!");
                                return;
                            }
                        }
                    }
                }

                if (LAW.Length == 2)
                {
                    if (MTDBbase.ToDecimal(LAW[0]) >= MTDBbase.ToDecimal(LAW[1]))
                    {
                        db.MsgBox(Page, "法規許可值錯誤, 下限規格不能大於或等於上限規格!");
                        return;
                    }
                }
            }

            //__OOS.Text = __LAW.Text;
        }
    }

    protected void __OOS_TextChanged(object sender, EventArgs e)
    {
        using (dbVOC db = new dbVOC())
        {
            if (__OOS.Text != "" && __OOS.Text != "N/A")
            {
                __OOS.Text = __OOS.Text.Trim();
                string[] OOS = __OOS.Text.Split('-');

                if (_0item.SelectedItem.Text == "pH" && OOS.Length == 1)
                {
                    db.MsgBox(Page, "OOS規格值錯誤, 請輸入雙邊規格(如: 6-9)!");
                    return;
                }

                if (_0item.SelectedItem.Text != "pH" && OOS.Length == 2)
                {
                    db.MsgBox(Page, "OOS規格值錯誤, 請輸入單邊規格(如: 6)!");
                    return;
                }

                int no;

                for (int i = 0; i < OOS.Length; i++)
                {
                    int dot = OOS[i].IndexOf(".") + 1;
                    if (dot > 0)
                    {
                        if (OOS[i].Length - dot > 2)
                        {
                            db.MsgBox(Page, "OOS規格值(" + OOS[i] + ")錯誤, 請輸入二位小數!");
                            return;
                        }
                    }
                    for (int j = 0; j < OOS[i].Length; j++)
                    {
                        if (OOS[i].Substring(j, 1) != ".")
                        {
                            no = MTDBbase.ToInt32(OOS[i].Substring(j, 1), -1);
                            if (no < 0 || no > 9)
                            {
                                db.MsgBox(Page, "OOS規格值(" + OOS[i] + ")錯誤, 請輸入數字!");
                                return;
                            }
                        }
                    }
                }

                if (OOS.Length == 2)
                {
                    if (MTDBbase.ToDecimal(OOS[0]) >= MTDBbase.ToDecimal(OOS[1]))
                    {
                        db.MsgBox(Page, "OOS規格值錯誤, 下限規格不能大於或等於上限規格!");
                        return;
                    }
                }
            }
        }
    }

    protected void __OOC_TextChanged(object sender, EventArgs e)
    {
        using (dbVOC db = new dbVOC())
        {
            if (__OOC.Text != "" && __OOC.Text != "N/A")
            {
                __OOC.Text = __OOC.Text.Trim();
                string[] OOC = __OOC.Text.Split('-');

                if (_0item.SelectedItem.Text == "pH" && OOC.Length == 1)
                {
                    db.MsgBox(Page, "OOC規格值錯誤, 請輸入雙邊規格(如: 6-9)!");
                    return;
                }

                if (_0item.SelectedItem.Text != "pH" && OOC.Length == 2)
                {
                    db.MsgBox(Page, "OOC規格值錯誤, 請輸入單邊規格(如: 6)!");
                    return;
                }

                int no;

                for (int i = 0; i < OOC.Length; i++)
                {
                    int dot = OOC[i].IndexOf(".") + 1;
                    if (dot > 0)
                    {
                        if (OOC[i].Length - dot > 2)
                        {
                            db.MsgBox(Page, "OOC規格值(" + OOC[i] + ")錯誤, 請輸入二位小數!");
                            return;
                        }
                    }
                    for (int j = 0; j < OOC[i].Length; j++)
                    {
                        if (OOC[i].Substring(j, 1) != ".")
                        {
                            no = MTDBbase.ToInt32(OOC[i].Substring(j, 1), -1);
                            if (no < 0 || no > 9)
                            {
                                db.MsgBox(Page, "OOC規格值(" + OOC[i] + ")錯誤, 請輸入數字!");
                                return;
                            }
                        }
                    }
                }

                if (OOC.Length == 2)
                {
                    if (MTDBbase.ToDecimal(OOC[0]) >= MTDBbase.ToDecimal(OOC[1]))
                    {
                        db.MsgBox(Page, "OOC規格值錯誤, 下限規格不能大於或等於上限規格!");
                        return;
                    }
                }

                if (__alert.Text != "" && __alert.Text != "N/A")
                {
                    if (_0item.SelectedItem.Text == "pH")
                    {
                        string[] alert = __alert.Text.Split('-');

                        if (MTDBbase.ToDecimal(OOC[0]) <= MTDBbase.ToDecimal(alert[0]) ||
                            MTDBbase.ToDecimal(OOC[1]) <= MTDBbase.ToDecimal(alert[1]))
                        {
                            db.MsgBox(Page, "OOC規格值需大於Alert規格值!");
                            return;
                        }
                    }
                    else
                    {
                        if (MTDBbase.ToDecimal(__OOC.Text) <= MTDBbase.ToDecimal(__alert.Text))
                        {
                            db.MsgBox(Page, "OOC規格值需大於Alert規格值!");
                            return;
                        }
                    }
                }
            }
        }
    }

    protected void __alert_TextChanged(object sender, EventArgs e)
    {
        using (dbVOC db = new dbVOC())
        {
            if (__alert.Text != "" && __alert.Text != "N/A")
            {
                __alert.Text = __alert.Text.Trim();
                string[] alert = __alert.Text.Split('-');

                if (_0item.SelectedItem.Text == "pH" && alert.Length == 1)
                {
                    db.MsgBox(Page, "alert規格值錯誤, 請輸入雙邊規格(如: 6-9)!");
                    return;
                }

                if (_0item.SelectedItem.Text != "pH" && alert.Length == 2)
                {
                    db.MsgBox(Page, "alert規格值錯誤, 請輸入單邊規格(如: 6)!");
                    return;
                }

                int no;

                for (int i = 0; i < alert.Length; i++)
                {
                    int dot = alert[i].IndexOf(".") + 1;
                    if (dot > 0)
                    {
                        if (alert[i].Length - dot > 2)
                        {
                            db.MsgBox(Page, "alert規格值(" + alert[i] + ")錯誤, 請輸入二位小數!");
                            return;
                        }
                    }
                    for (int j = 0; j < alert[i].Length; j++)
                    {
                        if (alert[i].Substring(j, 1) != ".")
                        {
                            no = MTDBbase.ToInt32(alert[i].Substring(j, 1), -1);
                            if (no < 0 || no > 9)
                            {
                                db.MsgBox(Page, "alert規格值(" + alert[i] + ")錯誤, 請輸入數字!");
                                return;
                            }
                        }
                    }
                }

                if (alert.Length == 2)
                {
                    if (MTDBbase.ToDecimal(alert[0]) >= MTDBbase.ToDecimal(alert[1]))
                    {
                        db.MsgBox(Page, "alert規格值錯誤, 下限規格不能大於或等於上限規格!");
                        return;
                    }
                }

                if (__OOC.Text != "" && __OOC.Text != "N/A")
                {
                    if (_0item.SelectedItem.Text == "pH")
                    {
                        string[] OOC = __OOC.Text.Split('-');

                        if (MTDBbase.ToDecimal(alert[0]) >= MTDBbase.ToDecimal(OOC[0]) ||
                            MTDBbase.ToDecimal(alert[1]) >= MTDBbase.ToDecimal(OOC[1]))
                        {
                            db.MsgBox(Page, "Alert規格值需小於OOC規格值!");
                            return;
                        }
                    }
                    else
                    {
                        if (MTDBbase.ToDecimal(__alert.Text) >= MTDBbase.ToDecimal(__OOC.Text))
                        {
                            db.MsgBox(Page, "Alert規格值需小於OOC規格值!");
                            return;
                        }
                    }
                }
            }
        }
    }
}