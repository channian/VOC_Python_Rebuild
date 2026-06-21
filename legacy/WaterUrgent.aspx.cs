using MTLibrary;
using System;
using System.Collections.Generic;
using System.Data;
using System.Linq;
using System.Web;
using System.Web.UI;
using System.Web.UI.WebControls;

public partial class WaterUrgent : BasePage
{
    protected void Page_Load(object sender, EventArgs e)
    {
        if (!Page.IsPostBack)
        {
            btnBack.PostBackUrl = "~/Default.aspx";
        }
    }

    protected void btnWaterAbnormal_Click(object sender, EventArgs e)
    {
        plantlist.Visible = false;
        lbreason.Visible = false;
        _0reasonid.Visible = false;
        lbothers.Visible = false;
        __others.Visible = false;
        btn水質異常通知確定.Visible = true;
        btn水質異常通知取消.Visible = true;
        btn改排水通知確定.Visible = false;
        btn改排水通知取消.Visible = false;
    }

    protected void btn水質異常通知取消_Click(object sender, EventArgs e)
    {
        btn水質異常通知確定.Visible = false;
        btn水質異常通知取消.Visible = false;
    }

    protected void btn水質異常通知確定_Click(object sender, EventArgs e)
    {
        DateTime sdate = DateTime.Now;
        sdate = sdate.AddMinutes(-1).AddSeconds(-1 * sdate.Second);
        DateTime edate = sdate.AddMinutes(1);

        using (dbVOC db = new dbVOC())
        {
            if (db.SendMail_水質異常通知(sdate)) db.MsgBox(Page, "水質異常通知成功!");
            else db.MsgBox(Page, "水質異常通知失敗!");

            btn水質異常通知確定.Visible = false;
            btn水質異常通知取消.Visible = false;
        }
    }

    protected void btnWaterChange_Click(object sender, EventArgs e)
    {
        DataTable dtb;
        ListItem li = null;
        string plant, plantid;

        plantlist.Visible = true;
        lbreason.Visible = true;
        _0reasonid.Visible = true;
        lbothers.Visible = false;
        __others.Visible = false;
        btn水質異常通知確定.Visible = false;
        btn水質異常通知取消.Visible = false;
        btn改排水通知確定.Visible = true;
        btn改排水通知取消.Visible = true;

        using (dbVOC db = new dbVOC())
        {
            dtb = db.GetData水質廠區(1);
            plantlist.Items.Clear();
            for (int i = 0; i < dtb.Rows.Count; i++)
            {
                plant = dtb.Rows[i][1].ToString();
                plantid = dtb.Rows[i][0].ToString();
                li = new ListItem(plant, plantid);
                plantlist.Items.Add(li);
            }

            SetValueList(_0reasonid, MTDBbase.AddNullValue(db.List改排水原因()));
        }
    }

    protected void _0reasonid_SelectedIndexChanged(object sender, EventArgs e)
    {
        if (_0reasonid.SelectedItem.Text == "其他異常")
        {
            lbothers.Visible = true;
            __others.Visible = true;
        }
        else
        {
            lbothers.Visible = false;
            __others.Visible = false;
        }
    }

    protected void btn改排水通知取消_Click(object sender, EventArgs e)
    {
        plantlist.Visible = false;
        lbreason.Visible = false;
        _0reasonid.Visible = false;
        lbothers.Visible = false;
        __others.Visible = false;
        btn改排水通知確定.Visible = false;
        btn改排水通知取消.Visible = false;
    }

    protected void btn改排水通知確定_Click(object sender, EventArgs e)
    {
        DateTime sdate = DateTime.Now;
        //sdate = Convert.ToDateTime("2023-01-12 20:44:00");
        sdate = sdate.AddSeconds(-1 * sdate.Second);

        using (dbVOC db = new dbVOC())
        {
            if (plantlist.SelectedIndex < 0)
            {
                db.MsgBox(Page, "請選擇廠區!");
                return;
            }

            if (_0reasonid.SelectedIndex == -1)
            {
                db.MsgBox(Page, "請選擇改排水原因!");
                return;
            }

            if (_0reasonid.SelectedItem.Text == "其他異常")
            {
                if (__others.Text.ToStringTrim() == "")
                {
                    db.MsgBox(Page, "請輸入其他異常原因!");
                    return;
                }
            }
            else __others.Text = "";

            if (db.SendMail_改排水通知(sdate, plantlist, (__others.Text != "" ? __others.Text : _0reasonid.SelectedItem.Text))) db.MsgBox(Page, "改排水通知成功!");
            else db.MsgBox(Page, "改排水通知失敗!");

            plantlist.Visible = false;
            lbreason.Visible = false;
            _0reasonid.Visible = false;
            lbothers.Visible = false;
            __others.Visible = false;
            btn改排水通知確定.Visible = false;
            btn改排水通知取消.Visible = false;
        }
    }
}