using System;
using System.Collections;
using System.Collections.Generic;
using System.Data;
using System.IO;
using System.Linq;
using System.Text;
using System.Web;
using System.Web.UI;
using System.Web.UI.WebControls;
using Microsoft.VisualBasic.FileIO;
using MTLibrary;

public partial class EditMailList : BasePage
{
    public int _View_EditMailListACL
    {
        get { return MTDBbase.ToInt32(ViewState["EditMailList_ACL"], -1); }
        set { ViewState["EditMailList_ACL"] = value; }
    }

    public DataTable _View_EditMailListDT
    {
        get { return ViewState["EditMailList_DT"] as DataTable; }
        set { ViewState["EditMailList_DT"] = value; }
    }

    protected void Page_Load(object sender, EventArgs e)
    {
        if (!Page.IsPostBack)
        {
            btnBack.PostBackUrl = "~/Default.aspx";

            tbNum.Text = "10";

            using (dbAclRights db = new dbAclRights())
                _View_EditMailListACL = db.Check權限(dbAclRights.使用者權限.派送名單維護);

            using (dbVOC db = new dbVOC())
            {
                if (ddlplant.DataSource == null)
                {
                    SetValueList(ddlplant, MTDBbase.AddNullValue(db.List廠區4()));
                    SetValueList(ddltype, MTDBbase.AddNullValue(db.List派送類型()));
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
                SetValueList(ddlplant, MTDBbase.AddNullValue(db.List廠區5(ddlplant.SelectedValue, ddltype.SelectedValue)));
            if (ddltype.SelectedItem.Text == "")
                SetValueList(ddltype, MTDBbase.AddNullValue(db.List派送類型1(ddlplant.SelectedValue, ddltype.SelectedValue)));
        }
    }

    protected void ddltype_SelectedIndexChanged(object sender, EventArgs e)
    {
        using (dbVOC db = new dbVOC())
        {
            if (ddlplant.SelectedItem.Text == "")
                SetValueList(ddlplant, MTDBbase.AddNullValue(db.List廠區5(ddlplant.SelectedValue, ddltype.SelectedValue)));
            if (ddltype.SelectedItem.Text == "")
                SetValueList(ddltype, MTDBbase.AddNullValue(db.List派送類型1(ddlplant.SelectedValue, ddltype.SelectedValue)));
        }
    }

    protected void _0rtype_SelectedIndexChanged(object sender, EventArgs e)
    {
        if (_0rtype.SelectedItem.Text.IndexOf("保養") > -1)
        {
            __SM.SelectedValue = "0";
            __SM.Enabled = false;
            __signgrp.Enabled = true;
        }
        else
        {
            __SM.SelectedValue = "1";
            __SM.Enabled = true;
            __signgrp.Enabled = false;
        }
    }

    protected void btn查詢_Click(object sender, EventArgs e)
    {
        BindGrid();
    }

    protected void btn匯入_Click(object sender, EventArgs e)
    {
        string extension = Path.GetExtension(fuAtt.FileName).ToUpper();
        // 判斷是否為允許上傳的檔案附檔名 
        List<string> allowedExtextsion = new List<string> { ".CSV" };
        if (allowedExtextsion.IndexOf(extension) == -1)
        {
            using (dbVOC db = new dbVOC())
            {
                db.MsgBox(Page, "請選擇正確的匯入檔格式(CSV檔)!");
                return;
            }
        }

        string SaveDir = @"D:\FileUpload\VOC\";
        string FileName = SaveDir + fuAtt.FileName;

        if (!System.IO.Directory.Exists(SaveDir))
            System.IO.Directory.CreateDirectory(SaveDir);

        HttpPostedFile file = fuAtt.PostedFile;
        if (file == null || MTLibrary.MTDBbase.IsNullOrEmpty(file.FileName)) return;

        file.SaveAs(FileName);
        DataImport(FileName);
        System.IO.File.Delete(FileName);

        BindGrid();
    }

    protected DataTable GetDataTableFromCsvFile(string CsvFileName)
    {
        DataTable CsvData = new DataTable();

        try
        {
            using (TextFieldParser CsvReader = new TextFieldParser(CsvFileName, Encoding.Default))
            {
                CsvReader.SetDelimiters(new string[] { "," });
                CsvReader.HasFieldsEnclosedInQuotes = true;
                string[] colFields = CsvReader.ReadFields();
                foreach (string column in colFields)
                {
                    DataColumn datecolumn = new DataColumn(column);
                    datecolumn.AllowDBNull = true;
                    CsvData.Columns.Add(datecolumn);
                }
                while (!CsvReader.EndOfData)
                {
                    Boolean HasData = false;
                    string[] fieldData = CsvReader.ReadFields();
                    //Making empty value as null
                    for (int i = 0; i < fieldData.Length; i++)
                    {
                        if (fieldData[i] == "") fieldData[i] = null;
                        else HasData = true;
                    }
                    if (HasData) CsvData.Rows.Add(fieldData);
                }
            }
        }
        catch (Exception ex)
        {
            return null;
        }

        return CsvData;
    }

    protected void DataImport(string CsvFileName)
    {
        DataTable dtb = GetDataTableFromCsvFile(CsvFileName);

        int RowCount = dtb.Rows.Count;

        if (RowCount == 0)
        {
            using (dbVOC db = new dbVOC()) db.MsgBox(Page, "派送名單沒有資料!");
            return;
        }

        int ColCount = dtb.Columns.Count;
        string[] ColName = { "廠區", "派送類型", "工號", "姓名", "Notes ID", "手機號碼", "派送方式", "郵件", "簡訊", "簽核群組", "動作" };
        string[] ColName1 = { "plantno", "RptType", "empno", "empname", "NotesID", "CellPhone", "MailType", "Mail", "SM", "SignGrp", "action" };
        string[] ColValue = new string[11];
        int[] HeadCol = new int[ColCount];
        string HeadStr, sValue = "";
        int k = 0, fnd, no;
        string plantno = "", rpttype = "", empno = "", empname = "", notesid = "", cellphone = "";
        string mailtype = "", mail = "", sm = "", signgrp = "", action = "", ErrorStr = "";

        for (int i = 0; i < ColCount; i++)
        {
            HeadCol[i] = -1;
            HeadStr = dtb.Columns[i].ToStringTrim();
            for (int j = 0; j < ColName.Length; j++)
                if (HeadStr == ColName[j]) HeadCol[i] = j;
        }

        using (dbVOC db = new dbVOC())
        {
            for (int i = 0; i < ColName.Length; i++)
            {
                fnd = 0;
                for (int j = 0; j < HeadCol.Length; j++)
                {
                    if (HeadCol[j] == i)
                    {
                        fnd = 1;
                        break;
                    }
                }
                if (fnd == 0)
                {
                    db.MsgBox(Page, "找不到表頭名稱[" + ColName[i] + "]!");
                    return;
                }
            }

            for (int i = 0; i < RowCount; i++)
            {
                for (int j = 0; j < ColCount; j++)
                {
                    k = HeadCol[j];
                    if (k != -1)
                    {
                        sValue = dtb.Rows[i][j].ToStringTrim();
                        ColValue[k] = sValue;

                        switch (ColName[k])
                        {
                            case "廠區":
                                plantno = ColValue[k];
                                break;
                            case "派送類型":
                                rpttype = ColValue[k];
                                break;
                            case "工號":
                                empno = ColValue[k];
                                break;
                            case "姓名":
                                empname = ColValue[k];
                                break;
                            case "Notes ID":
                                notesid = ColValue[k];
                                break;
                            case "手機號碼":
                                cellphone = ColValue[k];
                                break;
                            case "派送方式":
                                mailtype = ColValue[k];
                                break;
                            case "郵件":
                                mail = ColValue[k];
                                break;
                            case "簡訊":
                                sm = ColValue[k];
                                break;
                            case "簽核群組":
                                signgrp = ColValue[k];
                                break;
                            case "動作":
                                action = ColValue[k];
                                break;
                        }
                    }
                }

                no = i + 1;
                ErrorStr = "第 " + no + " 筆的";

                if (db.Check廠區(plantno) == 0)
                {
                    db.MsgBox(Page, ErrorStr + "「廠區」錯誤!");
                    return;
                }

                if (db.Check派送類型(rpttype) == 0)
                {
                    db.MsgBox(Page, ErrorStr + "「派送類型」錯誤!");
                    return;
                }

                if (empno.IndexOf("群組") < 0 && empno.IndexOf("值班") < 0)
                {
                    if (db.Check工號(empno) == 0)
                    {
                        db.MsgBox(Page, ErrorStr + "「工號」非在職人員!");
                        return;
                    }

                    if (db.Check姓名(empno, empname) == 0)
                    {
                        db.MsgBox(Page, ErrorStr + "「姓名」錯誤!");
                        return;
                    }
                }

                if (mailtype != "TO" && mailtype != "CC")
                {
                    db.MsgBox(Page, ErrorStr + "「派送方式」錯誤, 請填寫 TO 或 CC!");
                    return;
                }

                if (mail != "要" && mail != "否")
                {
                    db.MsgBox(Page, ErrorStr + "「郵件」錯誤, 請填寫 要 或 否!");
                    return;
                }
                else if (mail == "要" && notesid == "")
                {
                    db.MsgBox(Page, ErrorStr + "「Notes ID」不得為空白!");
                    return;
                }

                if (sm != "要" && sm != "否")
                {
                    db.MsgBox(Page, ErrorStr + "「簡訊」錯誤, 請填寫 要 或 否!");
                    return;
                }
                else if (sm == "要" && cellphone == "")
                {
                    db.MsgBox(Page, ErrorStr + "「手機號碼」不得為空白!");
                    return;
                }

                if (signgrp != "要" && signgrp != "否")
                {
                    db.MsgBox(Page, ErrorStr + "「簽核群組」錯誤, 請填寫 要 或 否!");
                    return;
                }

                if (action != "新增" && action != "修改" && action != "刪除")
                {
                    db.MsgBox(Page, ErrorStr + "「動作」錯誤, 請填寫 新增 或 修改 或 刪除!");
                    return;
                }
                else if (db.Check派送名單(rpttype, plantno, empno, action) == 0)
                {
                    db.MsgBox(Page, ErrorStr + "「派送名單」" + (action == "新增" ? "已" : "不") + "存在!");
                    return;
                }
            }

            for (int i = 0; i < RowCount; i++)
            {
                for (int j = 0; j < ColCount; j++)
                {
                    k = HeadCol[j];
                    if (k != -1)
                    {
                        sValue = dtb.Rows[i][j].ToStringTrim();
                        ColValue[k] = sValue;
                    }
                }
                if (!db.UpdateMail(ColName1, ColValue, ColName))
                {
                    db.MsgBox(Page, "派送名單匯入失敗!\n" + db._Exception);
                    return;
                }
            }

            db.MsgBox(Page, "派送名單匯入成功!");
        }
    }

    protected void btn匯出_Click(object sender, EventArgs e)
    {
        DataTable dt;
        Response.Clear();
        Response.ContentType = "text/comma-separated-values;charset=BIG5";
        Response.AddHeader("content-disposition", "attachment; filename=CCTV_Mail_List.csv");

        StreamWriter sw = new StreamWriter(Response.OutputStream, Encoding.GetEncoding("BIG5"));
        dt = GetData();
        sw.Write("廠區,派送類型,工號,姓名,Notes ID,手機號碼,派送方式,郵件,簡訊,簽核群組\r\n");
        for (int i = 0; i < dt.Rows.Count; i++)
        {
            for (int j = 0; j < dt.Columns.Count-2; j++)
            {
                if (j > 0) sw.Write(",");
                sw.Write(dt.Rows[i][j]);
            }
            sw.Write("\r\n");
        }
        sw.WriteLine();
        sw.Close();

        Response.End();
    }

    private DataTable GetData()
    {
        string plantno = ddlplant.SelectedItem.Text;
        string rpttype = ddltype.SelectedItem.Text;

        using (dbVOC db = new dbVOC()) return db.List派送名單資料(plantno, rpttype);
    }

    protected void BindGrid()
    {
        _View_EditMailListDT = GetData();

        gvtagList.SetDataSource(_View_EditMailListDT);
    }

    protected void gvtagList_RowCommand(object sender, GridViewCommandEventArgs e)
    {
        switch (e.CommandName)
        {
            case "Insert":
                tbdata.Visible = true;
                using (dbVOC db = new dbVOC())
                {
                    SetValueList(_0plant, MTDBbase.AddNullValue(db.List廠區4()));
                    SetValueList(_0rtype, MTDBbase.AddNullValue(db.List派送類型()));
                }
                _0plant.SelectedIndex = -1;
                _0rtype.SelectedIndex = -1;
                __empno.Text = "";
                __empname.Text = "";
                __notesid.Text = "";
                __cellphone.Text = "";
                __mailtype.SelectedValue = "1";
                __mail.SelectedValue = "1";
                __SM.SelectedValue = "1";
                __signgrp.SelectedValue = "0";
                __remark.Text = "";
                _0plant.Enabled = true;
                _0rtype.Enabled = true;
                __empno.Enabled = true;
                __empname.Enabled = false;
                __notesid.Enabled = true;
                __cellphone.Enabled = true;
                __mailtype.Enabled = true;
                __mail.Enabled = true;
                __SM.Enabled = true;
                __signgrp.Enabled = true;
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
                    SetValueList(_0plant, MTDBbase.AddNullValue(db.List廠區4()));
                    SetValueList(_0rtype, MTDBbase.AddNullValue(db.List派送類型()));
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
                    SetValueList(_0plant, MTDBbase.AddNullValue(db.List廠區4()));
                    SetValueList(_0rtype, MTDBbase.AddNullValue(db.List派送類型()));
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
        string rpttype = dbVOC.GetDataControlFieldCellValue("rpttype", gvtagList.Columns, gvr);
        string empno = dbVOC.GetDataControlFieldCellValue("empno", gvtagList.Columns, gvr);
        string empname = dbVOC.GetDataControlFieldCellValue("empname", gvtagList.Columns, gvr);
        string notesid = dbVOC.GetDataControlFieldCellValue("notesid", gvtagList.Columns, gvr);
        string cellphone = dbVOC.GetDataControlFieldCellValue("cellphone", gvtagList.Columns, gvr);
        string mailtype = dbVOC.GetDataControlFieldCellValue("mailtype", gvtagList.Columns, gvr);
        string mail = dbVOC.GetDataControlFieldCellValue("mail", gvtagList.Columns, gvr);
        string SM = dbVOC.GetDataControlFieldCellValue("SM", gvtagList.Columns, gvr);
        string signgrp = dbVOC.GetDataControlFieldCellValue("signgrp", gvtagList.Columns, gvr);

        for (int i = 0; i < _0plant.Items.Count; i++)
        {
            if (_0plant.Items[i].Text == plantno)
            {
                _0plant.SelectedIndex = i;
                break;
            }
        }

        for (int i = 0; i < _0rtype.Items.Count; i++)
        {
            if (_0rtype.Items[i].Text == rpttype)
            {
                _0rtype.SelectedIndex = i;
                break;
            }
        }

        __empno.Text = empno;
        __empname.Text = empname;
        __notesid.Text = notesid;
        __cellphone.Text = cellphone;
        __mailtype.SelectedValue = (mailtype == "TO" ? "1" : "2");
        __mail.SelectedValue = (mail == "要" ? "1" : "0");
        __SM.SelectedValue = (SM == "要" ? "1" : "0");
        __signgrp.SelectedValue = (signgrp == "是" ? "1" : "0");

        lbempno1.Text = empno;
        lbempname.Text = empname;
        lbnotesid.Text = notesid;
        lbcellphone.Text = cellphone;
        lbmailtype1.Text = mailtype;
        lbmail1.Text = mail;
        lbSM1.Text = SM;
        lbsigngrp1.Text = signgrp;

        _0plant.Enabled = false;
        _0rtype.Enabled = false;
        __empno.Enabled = true;
        __empname.Enabled = false;
        __notesid.Enabled = true;
        __cellphone.Enabled = true;
        __mailtype.Enabled = true;
        __mail.Enabled = true;
        if (rpttype.IndexOf("保養") > -1) __SM.Enabled = false; else __SM.Enabled = true;
        __signgrp.Enabled = true;
    }

    protected void gvtagList_RowDeleting(object sender, GridViewDeleteEventArgs e)
    {
        string plantno = e.Keys["plantno"].ToString();
        string rpttype = e.Keys["rpttype"].ToString();
        string empno = e.Keys["empno"].ToString();

        DataTable DT;
        using (dbVOC db = new dbVOC()) DT = db.List派送名單資料(plantno, rpttype, empno);

        string empname = DT.Rows[0]["empname"].ToString();
        string notesid = DT.Rows[0]["notesid"].ToString();
        string cellphone = DT.Rows[0]["cellphone"].ToString();
        string mailtype = DT.Rows[0]["mailtype"].ToString();
        string mail = DT.Rows[0]["mail"].ToString();
        string SM = DT.Rows[0]["SM"].ToString();
        string signgrp = DT.Rows[0]["signgrp"].ToString();

        for (int i = 0; i < _0plant.Items.Count; i++)
        {
            if (_0plant.Items[i].Text == plantno)
            {
                _0plant.SelectedIndex = i;
                break;
            }
        }

        for (int i = 0; i < _0rtype.Items.Count; i++)
        {
            if (_0rtype.Items[i].Text == rpttype)
            {
                _0rtype.SelectedIndex = i;
                break;
            }
        }

        __empno.Text = empno;
        __empname.Text = empname;
        __notesid.Text = notesid;
        __cellphone.Text = cellphone;
        __mailtype.SelectedValue = (mailtype == "TO" ? "1" : "2");
        __mail.SelectedValue = (mail == "要" ? "1" : "0");
        __SM.SelectedValue = (SM == "要" ? "1" : "0");
        __signgrp.SelectedValue = (signgrp == "是" ? "1" : "0");

        _0plant.Enabled = false;
        _0rtype.Enabled = false;
        __empno.Enabled = false;
        __empname.Enabled = false;
        __notesid.Enabled = false;
        __cellphone.Enabled = false;
        __mailtype.Enabled = false;
        __mail.Enabled = false;
        __SM.Enabled = false;
        __signgrp.Enabled = false;
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
        _View_EditMailListDT = null;
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
            if (!db.InsertMailList(row))
            {
                db.MsgBox(Page, "新增派送名單資料失敗!\n" + db._Exception);
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
            if (!db.UpdateMailList(row, lbempno1.Text, lbempname.Text, lbnotesid.Text, lbcellphone.Text, lbmailtype1.Text, lbmail1.Text, lbSM1.Text, lbsigngrp1.Text))
            {
                db.MsgBox(Page, "修改派送名單資料失敗!\n" + db._Exception);
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
            if (!db.DeleteMailList(row))
            {
                db.MsgBox(Page, "刪除派送名單資料失敗!\n" + db._Exception);
                return;
            }
        }
        ChangeMode();
    }
    #endregion

    protected void __empno_TextChanged(object sender, EventArgs e)
    {
        if (__empno.Text != "" && __empno.Text.IndexOf("群組") < 0 && __empno.Text.IndexOf("值班") < 0)
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

    protected void __cellphone_TextChanged(object sender, EventArgs e)
    {
        if (__cellphone.Text != "")
        {
            using (dbVOC db = new dbVOC())
            {
                __cellphone.Text = __cellphone.Text.Trim();

                if (__cellphone.Text.Substring(0, 2) != "09")
                {
                    db.MsgBox(Page, "手機號碼輸入錯誤, 應為09開頭!");
                    return;
                }

                if (__cellphone.Text.Length < 10)
                {
                    db.MsgBox(Page, "手機號碼輸入錯誤, 應為10碼!");
                    return;
                }

                int no;

                for (int i = 0; i < __cellphone.Text.Length; i++)
                {
                    no = MTDBbase.ToInt32(__cellphone.Text.Substring(i, 1), -1);
                    if (no < 0 || no > 9)
                    {
                        db.MsgBox(Page, "手機號碼錯誤, 請輸入數字!");
                        return;
                    }
                }
            }
        }
    }
}