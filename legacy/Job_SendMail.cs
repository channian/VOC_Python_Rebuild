using MTLibrary;
using NPOI.HSSF.UserModel;
using System;
using System.Collections.Generic;
using System.Data;
using System.IO;
using System.Linq;
using System.Net.Mail;
using System.Net.Mime;
using System.Text;
using System.Threading.Tasks;
using System.Net;           //Bermy added on 2018/11/09
using System.Diagnostics;   //Bermy added on 2018/11/09
using System.Net.NetworkInformation;
using Newtonsoft.Json;
using System.Net.Http; //Bermy added on 2019/12/04

namespace Job
{
    public class SendMail
    {
        //public DateTime ChingDueday = new DateTime(2016, 5, 20);
        public string SendFrom = "Albee_Weng@global.com";
        public string SendFromName = "Albee Weng";
        public string UJ = "UJ_Lee@global.com";
        public string Albee = "Albee_Weng@global.com";
        //public string Wanching = "wanching_chen@global.com";
        //public string Bermy = "Bermy_Po@global.com"; //Bermy added on 2016/11/04 for bcc mail list
        public string Jeff = "Jeff_Liang@global.com"; //Bermy added on 2020/04/06
        public string Andy = "Andy_Chu@global.com"; //Bermy added on 2020/04/06
        public string YuBin = "YuBin_Kuo@global.com"; //Bermy added on 2020/04/06
        public string Welly = "Welly_Lu@global.com"; //Bermy added on 2020/07/15
        public string Hank = "HankJH_Wang@global.com"; //Bermy added on 2021/01/27
        public string Bonnie = "Bonnie_Lin@global.com"; //Bermy added on 2024/10/04
        public string Errol = "Errol_Chen@global.com"; //Bermy added on 2024/12/05
        public string Jason = "JasonBH_Feng@global.com"; //Bermy added on 2024/12/05
        public string Ray = "Ray_Chung@global.com"; //Bermy added on 2024/12/05
        public string Huching = "Huching_Huang@global.com"; //Albee added on 2025/01/21
        public string YG = "YG_Tsao@global.com"; //Albee added on 2025/01/21
        public string HowardZC = "HowardZC_Kao@global.com"; //Albee added on 2025/01/21

        // ─────────────────────────────────────────────────────────────────
        // 說明（2026-07-01）：本檔為 JOB 端的通用寄信類別，橫跨公司多套系統
        // （PSN 品質異常統計、水錶、CCTV 履歷、PLC、異常管理、電力品質…）。
        // VOC「廠務法規許可標準化管控平台」只用到以下方法，其餘為其他系統，
        // 移植 VOC 平台時可忽略：
        //   - SendMail_廠務法規許可值標準化管控報表()   ← 主派報（水質等一般監測項目）
        //   - SendMail_廠務雨水溝預警報表()             ← 雨水溝預警派報（同結構）
        //   - SendMail_廠務中水陸放管控()                ← K1/K9 陸放/閘門專用 SMS 通知
        //   - SendMail_廠務中水放流量管控()              ← K14B 放流量專用通知
        //   - SendMail_IH主機連線異常通知() / SendMail_IH_TAG斷訊通知()
        //     ← IH Historian 斷線通知（新架構若拿掉 IH Historian 可能不再需要）
        // 完整分析見 docs/legacy_source_analysis.md 第〇節。
        // ─────────────────────────────────────────────────────────────────

        public int SendMail_品質異常統計通知(DateTime tdate)
        {
            try
            {
                DataTable dtb, maildt;
                DateTime sdate, edate;
                if (tdate.Hour > 8 && tdate.Hour <= 20)
                {   //在晚上8點發出的信件,撈出早上8點之後到晚上8點的PSN
                    sdate = new DateTime(tdate.Year, tdate.Month, tdate.Day, 8, 0, 0);
                    edate = new DateTime(tdate.Year, tdate.Month, tdate.Day, 20, 0, 0);
                }
                else
                {   //在早上8點發出的信件,撈出前一天晚上8點之後到早上8點的PSN
                    DateTime ydate = tdate.AddDays(-1);
                    sdate = new DateTime(ydate.Year, ydate.Month, ydate.Day, 20, 0, 0);
                    edate = new DateTime(tdate.Year, tdate.Month, tdate.Day, 8, 0, 0);
                }

                using (dbFacPsnData db = new dbFacPsnData())
                {
                    dtb = db.ListPSN(sdate, edate);
                    maildt = db.ListMailList("DAY");
                }
                SmtpMessage sm = new SmtpMessage();
                sm.Message.From = new MailAddress(Albee, "品質異常統計平台");
                foreach (DataRow mrow in maildt.Rows)
                    sm.Message.To.Add(mrow["email"].ToString());
                sm.Message.Bcc.Add(Albee);
                if (sm.Message.To.Count == 0)
                    return 0;
                string body = "<table style='background-color: yellow;width: 100%;'  width='100%'>" +
                    "<tr><td style='font-size: large; font-weight: bold; color: #0000FF'> " +
                    "如計畫性擴充案、現場數據失去資訊上傳功能無法正常上拋情況下，請系統負責人執行警報隔離作業 <br />" +
                    "如需隔離Tag警報，請使用 隔離警報維護作業-新增隔離警報，詳細操作手冊請參考平台上的說明文件 <br />" +
                    "⊕提醒您~ 請提早申請，此隔離警報需經上兩階主管簽核核准才會生效⊕ " +
                    "</td></tr></table>";
                body +=string.Format("統計區間: {0:yyyy/MM/dd HH:mm}~{1:yyyy/MM/dd HH:mm} </br>", sdate, edate);
                body += "<html><body><table style='margin-bottom: 10px;border: #999999 3px solid;background-color: #CCCCCC;width: 400px;'  width='400px'>" +
                    "<tr style=' background-color: black;color: #FFFFFF;font-weight: bold;'>" +
                    "<td style='text-align: center; width: 80px;'><strong>廠區</strong></td>" +
                    "<td style='text-align: center; width: 80px;'><strong>OOC Count</strong></td>" +
                    "<td style='text-align: center; width: 80px;'><strong>回覆數</strong></td>" +
                    "</tr>";
                string plantstr = "";
                foreach (DataRow row in dtb.Rows)
                {
                    body += "<tr>" +
                        "<td style='text-align: center; background-color: #FFFFFF;'><strong>" + row["plantno"].ToString() + "</strong></td>" +
                        "<td style='text-align: center; background-color: #FFFFFF;'><strong>" + row["psncnt"].ToString() + "</strong></td>" +
                        "<td style='text-align: center; background-color: #FFFFFF;'><strong>" + row["sumcnt"].ToString() + "</strong></td>" +
                        "</tr>";
                    if (MTDBb.ToInt32(row["psncnt"]) > 0 && !row["plantno"].Equals("總計"))
                    {
                        if (!MTDBb.IsNullOrEmpty(plantstr))
                            plantstr += ",";
                        plantstr += row["plantno"].ToString();
                    }
                }
                body += "<tr><td colspan=3><a href='http://khfacsv01/PSN/Home.aspx'>進行查看</a></td></tr>";
                body += "</table>";
                body += "</body></html>";

                sm.Message.Subject = string.Format("品質異常統計通知 {0:yyyy/MM/dd HH:mm}~{1:yyyy/MM/dd HH:mm} 廠區:{2}", sdate, edate, plantstr);
                sm.Message.IsBodyHtml = true;
                sm.Message.Body = body;
                sm.Message.BodyEncoding = Encoding.UTF8;
                sm.Send(sm.Message);
                return 0;
            }
            catch (Exception ex)
            {
                Program.error = ex.Message;
                return -1;
            }
        }

        //Bermy start added on 2018/11/27 for 廠務法規許可值標準化管控報表
        public int SendMail_廠務法規許可值標準化管控報表()
        {
            try
            {
                string DT = DateTime.Now.ToString("yyyy/MM/dd HH:mm");
                DateTime dt2 = Convert.ToDateTime(DT + ":00");
                DataTable dtb0, dtb, mailto, mailcc, phoneto, phonecc;
                string[] ArrTO = null;

                string url = "http://khfacsv01/VOC/";
                string plantno = "";
                string remark;
                string source;
                string emptycell;
                string DataRed = "";
                string body = "";
                string style;
                string slash;
                string sColor;
                string light;
                string sRed;
                string msg = "";
                string msg1 = "";
                string status = "";
                string msg2 = "";
                string first;
                string[] ArrRed;
                string[] ArrColor;
                int rcnt = 0;
                int rowspan = 0;
                int rows = 0;
                int r = -1;
                Boolean rtn;
                string url1, sdate, edate, stime, msg3 = "";

                using (dbVOC db = new dbVOC())
                {
                    dtb0 = db.List隔離廠區項目();
                    if (dtb0.Rows.Count > 0)
                    {
                        for (int i = 0; i < dtb0.Rows.Count; i++)
                        {
                            db.Update隔離廠區項目(dtb0.Rows[i]);
                        }
                    }

                    dtb = db.GetData();
                    foreach (DataRow row in dtb.Rows)
                    {
                        source = row["remark"].ToString().Substring(row["remark"].ToString().IndexOf("|") + 1, 1);
                        emptycell = row["emptycell"].ToString();

                        for (int i = 3; i < 14; i++)
                        {
                            row[i] = row[i].ToString().Replace(",", "");

                            if (row[i].ToString() == "")
                                if (emptycell.IndexOf(i + ";") < 0) row[i] = "異常";

                            if (i > 2 && i < 10) row[i + 21] = row[i];

                            //統一數字欄位到小數二位, 第三位四捨五入; 導電度 & 日累積水量 四捨五入到整數
                            if (row[i].ToString() != "" && row[i].ToString() != "-" && row[i].ToString() != "N/A" &&
                                row[i].ToString() != "建置中" && row[i].ToString() != "斷訊" &&
                                row[i].ToString() != "異常" && row[i].ToString() != "保養中")
                            {
                                if (i > 2 && i < 10)
                                {
                                    if (row["item"].ToString() == "導電度" || row["item"].ToString().IndexOf("日累積水量") > -1)
                                        row[i + 21] = db.ChangeData(row[i].ToString(), 0);
                                    else row[i + 21] = db.ChangeData(row[i].ToString(), 2);
                                }
                                else
                                {
                                    if (row["item"].ToString() == "導電度" || row["item"].ToString().IndexOf("日累積水量") > -1)
                                        row[i] = db.ChangeData(row[i].ToString(), 0);
                                    else row[i] = db.ChangeData(row[i].ToString(), 2);
                                }
                            }
                        }

                        sRed = db.GetDataRed(row, dt2);
                        if (sRed != "")
                        {
                            ArrRed = sRed.Split(',');
                            for (int j = 0; j < ArrRed.Length; j++)
                            {
                                if (DataRed.IndexOf(ArrRed[j]) < 0)
                                    DataRed += (DataRed == "" ? "" : ",") + ArrRed[j];
                            }
                        }
                    }
                }

                //DataRed = "水Alert-九號放流口";
                if (DataRed != "")
                {
                    foreach (DataRow row in dtb.Rows)
                    {
                        r++;

                        if (DataRed.IndexOf(row["plantno"].ToString()) > -1)
                        {
                            if (row["plantno"].ToString() != plantno)
                            {
                                using (dbVOC db = new dbVOC())
                                {
                                    msg = db.GetMsg(dtb, row["plantno"].ToString(), r);
                                    msg1 = db.GetMsg1(dtb, row["plantno"].ToString(), r, "msg1");
                                    status = db.GetMsg1(dtb, row["plantno"].ToString(), r, "status");
                                    msg2 = db.GetMsg2(dtb, row["plantno"].ToString(), r);
                                    msg3 = db.GetMsg1(dtb, row["plantno"].ToString(), r, "msg2");
                                }

                                body = "<html><body><label>Dear Sir,<br />" +
                                    "您好, 您所負責的" + row["plantno"] + "有以下異常或提醒, 呈現(紅燈/橘燈/黃燈/保養中)警示, 請儘速處理, 謝謝!</label><br /><br />" +
                                    "<table><tr><td style='text-align: left; font-size: small;'>" +
                                    "<img src='file://khfacsv01/VOCimages$/CircleRed.jpg'><font style='color: Red'><b>最新讀值＞＝OOS</b></font>&nbsp" +
                                    "<img src='file://khfacsv01/VOCimages$/CircleOrange.jpg'><font style='color: Orange'><b>OOC＜＝最新讀值＜OOS 或 SCADA與CWMS之管制值＜＞SPEC</b></font>&nbsp" +
                                    "<img src='file://khfacsv01/VOCimages$/CircleYellow.jpg'><font style='color: #CC9900'><b>Alert＜最新讀值＜OOC 或 最新讀值＞允收值</b></font>&nbsp" +
                                    "<img src='file://khfacsv01/VOCimages$/CircleGreen.jpg'><font style='color: Green'><b>正常狀態</b></td>" +
                                    "<td style='text-align: right; color: #FF66FF; font-size: small;'><b>最新讀值：</b></td>" +
                                    "<td style='text-align: center; background-color: Cornsilk; font-size: small;'><b>SCADA資料</b></td>" +
                                    "<td style='text-align: center; background-color: Orange; font-size: small;'><b>CWMS資料</b></td>" +
                                    "<td style='text-align: center; background-color: #D3D3D3; font-size: small;'><b>QA手測值</b></td>" +
                                    "<td style='color: #FF66FF; font-size: small;'>；</td>" +
                                    "<td><img src='file://khfacsv01/VOCimages$/slash.jpg'></td>" +
                                    "<td style='text-align: center; font-size: small;'><b>：無</b></td></tr></table>" +
                                    "<table style='border: black 1px solid'>" +
                                    "<tr style='background-color: #CCFFFF; font-weight: bold; font-size: small;'>" +
                                    "<td rowspan='2' style='text-align: center'><strong>廠區</strong></td>" +
                                    "<td rowspan='2' style='text-align: center'><strong>項目</strong></td>" +
                                    "<td rowspan='2' style='text-align: center'><strong>單位</strong></td>" +
                                    "<td rowspan='2' style='text-align: center; border-top: 3px solid; border-left: 3px solid;'><strong>法規許可值</strong></td>" +
                                    "<td colspan='2' style='text-align: center; border-top: 3px solid;'><strong>SPEC(三階文件)</strong></td>" +
                                    "<td rowspan='2' style='text-align: center; border-top: 3px solid;'><strong>Alert</strong></td>" +
                                    "<td rowspan='2' style='text-align: center; border-top: 3px solid;'><strong>允收值</strong></td>" +
                                    "<td colspan='3' style='text-align: center; border-top: 3px solid; border-left: 3px solid;'><strong>SCADA自動量測/QA手動量測</strong></td>" +
                                    "<td colspan='2' style='text-align: center; border-top: 3px solid; border-left: 3px solid;'><strong>CWMS</strong></td>" +
                                    "<td colspan='2' style='text-align: center; border-left: 3px solid;'><strong>Web</strong></td>" +
                                    "<td rowspan='3' style='text-align: center'><strong>備註</strong></td></tr>" +
                                    "<tr style='background-color: #CCFFFF; font-weight: bold; font-size: small;'>" +
                                    "<td style='text-align: center'><strong>OOS</strong></td>" +
                                    "<td style='text-align: center'><strong>OOC</strong></td>" +
                                    "<td style='text-align: center; border-left: 3px solid;'><strong>OOS-HH</strong></td>" +
                                    "<td style='text-align: center'><strong>OOC-H</strong></td>" +
                                    "<td style='text-align: center; border-right: 3px solid;'><strong>Alert</strong></td>" +
                                    "<td style='text-align: center'><strong>OOS-HH</strong></td>" +
                                    "<td style='text-align: center; border-right: 3px solid;'><strong>OOC-H</strong></td>" +
                                    "<td style='text-align: center'><strong>最新讀值</strong></td>" +
                                    "<td rowspan='2' style='text-align: center'><strong>狀態</strong></td></tr>" +
                                    "<tr style='background-color: #CCFFFF; font-weight: bold; font-size: small;'>" +
                                    "<td colspan='3' style='text-align: center'><strong>管理權責</strong></td>" +
                                    "<td colspan='5' style='text-align: center; background-color: LightSalmon; border-left: 3px solid;'><strong>4K30</strong></td>" +
                                    "<td colspan='6' style='text-align: center; background-color: LightSalmon; border-left: 3px solid;'><strong>Site FAC</strong></td></tr>";
                            }

                            body += "<tr style='background-color: #FFFFFF; color: black; font-weight: bold; font-size: small;'>";

                            if (row["plantno"].ToString() != plantno)
                            {
                                plantno = row["plantno"].ToString();
                                for (int i = r; i < dtb.Rows.Count; i++)
                                {
                                    if (dtb.Rows[i].Field<string>("plantno") != plantno) break;
                                    rowspan += 1;
                                }
                                body += "<td rowspan='" + rowspan + "' style='text-align: center'><strong>" + row["plantno"] + "</strong></td>";
                                rows = rowspan;
                            }
                            else rowspan = 0;

                            rcnt++;

                            remark = row["remark"].ToString().Substring(0, row["remark"].ToString().IndexOf("|"));
                            source = row["remark"].ToString().Substring(row["remark"].ToString().IndexOf("|") + 1, 1);
                            emptycell = row["emptycell"].ToString();

                            if (row["item"].ToString().IndexOf("VOC") > -1)
                            {
                                body += "<td style='text-align: center; background-color: YellowGreen;'><strong>" + row["item"] + "</strong></td>" +
                                "<td style='text-align: center; background-color: YellowGreen;'><strong>" + row["unit"] + "</strong></td>";
                            }
                            else if (source == "2") //CWMS
                            {
                                body += "<td style='text-align: center; background-color: Orange;'><strong>" + row["item"] + "</strong></td>" +
                                "<td style='text-align: center; background-color: Orange;'><strong>" + row["unit"] + "</strong></td>";
                            }
                            else
                            {
                                body += "<td style='text-align: center; background-color: DodgerBlue; color: White;'><strong>" + row["item"] + "</strong></td>" +
                                "<td style='text-align: center; background-color: DodgerBlue; color: White;'><strong>" + row["unit"] + "</strong></td>";
                            }

                            body += "<td style='text-align: center; background-color: LightYellow; border-left: 3px solid;";
                            if (rcnt == rows) body += " border-bottom: 3px solid;";
                            body += "'><strong>" + row["LAW"] + "</strong></td><td style='text-align: center;";
                            if (rcnt == rows) body += " border-bottom: 3px solid;";
                            body += "'><strong>" + row["OOS"] + "</strong></td><td style='text-align: center;";
                            if (rcnt == rows) body += " border-bottom: 3px solid;";
                            body += "'><strong>" + row["OOC"] + "</strong></td><td style='text-align: center;";
                            if (rcnt == rows) body += " border-bottom: 3px solid;";
                            body += "'><strong>" + row["alert"] + "</strong></td><td style='text-align: center; border-right: 3px solid;";
                            if (rcnt == rows) body += " border-bottom: 3px solid;";
                            body += "'><strong>" + row["recv"] + "</strong></td>";

                            using (dbVOC db = new dbVOC()) ArrColor = db.GetData(row);
                            light = (ArrColor[5] == "G" ? "Green" : (ArrColor[5] == "Y" ? "Yellow" : (ArrColor[5] == "O" ? "Orange" : "Red")));

                            for (int i = 0; i < 5; i++)
                            {
                                int j = i + 8;

                                body += "<td style='text-align: center;";

                                style = "";
                                if (row[j].ToString() == "斷訊" || row[j].ToString() == "異常")
                                    style = " color: Red; bordercolor: Black;";
                                else if (row[j].ToString() == "建置中")
                                    style = " background-color: Gray; color: White;";
                                else
                                    style = " background-color: " + ArrColor[i] + ";";

                                slash = "";

                                body += style + slash;

                                if (j == 10 || j == 12) body += " border-right: 3px solid;";
                                if (rcnt == rows) body += " border-bottom: 3px solid;";

                                if (row[j].ToString() == "")
                                {
                                    if (emptycell.IndexOf(j + ";") > -1)
                                        body += "'><img src='file://khfacsv01/VOCimages$/slash1.jpg'></td>";
                                    else
                                        body += "'><strong>" + row[j] + "</strong></td>";
                                }
                                else
                                    body += "'><strong>" + row[j] + "</strong></td>";
                            }

                            if (source == "1")  //SCADA
                                sColor = "Cornsilk";
                            else if (source == "2") //CWMS
                                sColor = "Orange";
                            else //QA
                                sColor = "LightGray";

                            body += "<td style='text-align: center; background-color: " + sColor;
                            if (row["rvalue"].ToString() == "斷訊") body += "; color: Red; bordercolor: Black";
                            body += "'><strong>" + row["rvalue"] + "</strong></td>";

                            body += "<td style='text-align: center'><img src='file://khfacsv01/VOCimages$/Circle" + light + ".jpg'></td>" +
                                "<td style='text-align: center'><strong>" + remark;
                            if (row["sdate"].ToString() != "") body += (remark == "" ? "" : ";") + row["sdate"];
                            body += "</strong></td></tr>";
                        }

                        if (DataRed.IndexOf(row["plantno"].ToString()) < 0 || r == dtb.Rows.Count-1)
                        {
                            if (rcnt > 0)
                            {
                                sdate = edate = dt2.ToString("yyyy/MM/dd");
                                stime = dt2.ToString("yyyy/MM/dd HH:mm");
                                url1 = "http://khfacsv01/VOC/VOCreason.aspx?plantno=" + plantno + "&sdate=" + sdate + "&edate=" + edate + "&stime=" + stime;
                                body += "</table><table style='border: black 1px solid'><tr style='font-weight: bold;'>" +
                                    "<td colspan='16' style='text-align: left'><a href='" + url + "'>進行查看</a>" +
                                    "&nbsp&nbsp&nbsp<a href='" + url1 + "'>異常原因回覆</a>" +
                                    "</td></tr></table></body></html>";

                                SmtpMessage sm = new SmtpMessage();
                                sm.Message.From = new MailAddress(Jeff, "法遵平台");

                                using (dbVOC db = new dbVOC())
                                {
                                    mailto = db.GetMailList(DataRed, plantno, "TO");
                                    mailcc = db.GetMailList(DataRed, plantno, "CC");
                                }

                                foreach (DataRow mrow in mailto.Rows)
                                    sm.Message.To.Add(mrow["NotesID"].ToString().Replace(" ", "_") + "@global.com");

                                foreach (DataRow mrow in mailcc.Rows)
                                    sm.Message.CC.Add(mrow["NotesID"].ToString().Replace(" ", "_") + "@global.com");

                                if (plantno != "K14B" && msg2.IndexOf("＞允收值") > -1)
                                {
                                    using (dbVOC db = new dbVOC())
                                        mailcc = db.GetMailList("水Alert-K14B", "K14B", "TO");
                                    foreach (DataRow mrow in mailcc.Rows)
                                        sm.Message.CC.Add(mrow["NotesID"].ToString().Replace(" ", "_") + "@global.com");
                                }

                                sm.Message.Bcc.Add(Ray);
                                sm.Message.Bcc.Add(Albee);

                                if (sm.Message.To.Count == 0) return 0;

                                first = (status.IndexOf("首發") > -1 ? "首發" : "再發");

                                sm.Message.Subject = string.Format("【{0}】請確認「法遵平台」即時監控狀況 : {1}-{2} (Security C)", first, plantno, DT);

                                sm.Message.IsBodyHtml = true;
                                sm.Message.Body = body;
                                sm.Message.BodyEncoding = Encoding.UTF8;
                                sm.Send(sm.Message);

                                using (dbVOC db = new dbVOC())
                                {
                                    db.InsertMAIL(plantno, msg, msg1, dt2, msg3);

                                    msg = "【" + first + "】" + plantno + "有異常,請儘速處理,謝謝!" + msg2;

                                    phoneto = db.GetCellPhoneList(DataRed, plantno, "TO");
                                    phonecc = db.GetCellPhoneList(DataRed, plantno, "CC");

                                    foreach (DataRow mrow in phoneto.Rows)
                                    {
                                        rtn = SendSMS.SendSMSByCHTProxy(msg, mrow["CellPhone"].ToString(), 1);
                                        db.InsertSMS(mrow, msg, (rtn == true ? 1 : 0));
                                    }

                                    if (phoneto.Rows.Count > 0)
                                    {
                                        foreach (DataRow mrow in phonecc.Rows)
                                        {
                                            rtn = SendSMS.SendSMSByCHTProxy(msg, mrow["CellPhone"].ToString(), 1);
                                            db.InsertSMS(mrow, msg, (rtn == true ? 1 : 0));
                                        }
                                    }

                                    if (plantno != "K14B" && msg2.IndexOf("＞允收值") > -1)
                                    {
                                        phonecc = db.GetCellPhoneList("水Alert-K14B", "K14B", "TO");
                                        if (phoneto.Rows.Count > 0)
                                        {
                                            foreach (DataRow mrow in phonecc.Rows)
                                            {
                                                rtn = SendSMS.SendSMSByCHTProxy(msg, mrow["CellPhone"].ToString(), 1);
                                                db.InsertSMS(mrow, msg, (rtn == true ? 1 : 0));
                                            }
                                        }
                                    }
                                }

                                if (msg2 != "") new CallPushPlus().Notice(sm.Message.Subject.Replace(" (Security C)", ""), plantno, msg2);

                                rcnt = 0;
                            }
                        }
                    }
                }

                return 0;
            }
            catch (Exception ex)
            {
                Program.error = ex.Message;
                return -1;
            }
        }
        //Bermy end added on 2018/11/27 for 廠務法規許可值標準化管控報表

        //Bermy start added on 2019/03/22 for 廠務中水陸放管控
        public int SendMail_廠務中水陸放管控()
        {
            try
            {
                string DT = DateTime.Now.ToString("yyyy/MM/dd HH:mm");
                DateTime dt2 = Convert.ToDateTime(DT + ":00");
                int m = dt2.Minute % 15;
                string dt0 = dt2.AddMinutes(-m).ToString("yyyy/MM/dd HH:mm:00");
                DataTable dtb, dtb1, phoneto, phonecc;

                string plantno = "";
                string msg;
                string msg1;
                string status;
                string DataRed;
                int first;
                DateTime dt1;
                TimeSpan ts;
                Boolean rtn;
                string dt3 = "";

                using (dbVOC db = new dbVOC())
                {
                    dtb = db.GetData陸放(dt0);
                    foreach (DataRow row in dtb.Rows)
                    {
                        plantno = row["plantno"].ToString();

                        dtb1 = db.Get前筆派報資料(plantno, "陸放", "放流閘門關閉");
                        if (dtb1.Rows.Count == 0)
                            first = 1;
                        else
                        {
                            dt1 = Convert.ToDateTime(dtb1.Rows[0]["cdatetime"].ToString());
                            ts = dt2 - dt1;
                            if (ts.Days >= 1 || ts.Hours > 4 || (ts.Hours == 4 && ts.Minutes > 0))
                                first = 1;
                            else
                            {
                                first = 0;
                                dt3 = dtb1.Rows[0]["cdatetime"].ToString();
                            }
                        }

                        if (plantno != "K9")
                        {
                            msg = "放流水停止入中水廠切換至陸放/納管";
                            msg1 = "放流水停止入中水廠切換至|陸放|/納管";
                            DataRed = "水陸放-" + plantno;
                        }
                        else
                        {
                            msg = "放流閘門關閉，停止放流水排放";
                            msg1 = "|放流閘門關閉|，停止放流水排放";
                            DataRed = "水閘關-" + plantno;
                        }

                        status = (first == 1 ? "首發" : "再發");

                        if (first != 1) //異常再發需間隔四小時才派送
                        {
                            dt1 = Convert.ToDateTime(dt3);
                            ts = dt2 - dt1;
                            if (ts.Hours < 4) DataRed = "";
                        }

                        if (DataRed != "")
                        {
                            db.InsertMAIL(plantno, msg, msg1, dt2, "");

                            msg = "【" + status + "】" + plantno + "廠 " + dt0.Substring(0, 16) + " " + msg + "，特派簡訊告知，謝謝!";

                            phoneto = db.GetCellPhoneList(DataRed, plantno, "TO");
                            phonecc = db.GetCellPhoneList(DataRed, plantno, "CC");

                            foreach (DataRow mrow in phoneto.Rows)
                            {
                                rtn = SendSMS.SendSMSByCHTProxy(msg, mrow["CellPhone"].ToString(), 1);
                                db.InsertSMS(mrow, msg, (rtn == true ? 1 : 0));
                            }

                            if (phoneto.Rows.Count > 0)
                            {
                                foreach (DataRow mrow in phonecc.Rows)
                                {
                                    rtn = SendSMS.SendSMSByCHTProxy(msg, mrow["CellPhone"].ToString(), 1);
                                    db.InsertSMS(mrow, msg, (rtn == true ? 1 : 0));
                                }
                            }
                        }
                    }
                }

                return 0;
            }
            catch (Exception ex)
            {
                Program.error = ex.Message;
                return -1;
            }
        }
        //Bermy end added on 2019/03/22 for 廠務中水陸放管控

        //Bermy start added on 2021/12/01 for 廠務雨水溝預警報表
        public int SendMail_廠務雨水溝預警報表()
        {
            try
            {
                string DT = DateTime.Now.ToString("yyyy/MM/dd HH:mm");
                DateTime dt2 = Convert.ToDateTime(DT + ":00");
                int m = dt2.Minute % 15;
                string dt0 = dt2.AddMinutes(-m).ToString("yyyy/MM/dd HH:mm:00");
                DataTable dtb0, dtb, mailto, mailcc, phoneto, phonecc;

                string url = "http://khfacsv01/VOC/RainGutter.aspx";
                string plantno = "", msg = "", msg1 = "", msg2 = "", msg3 = "", status = "", DataRed = "", body = "";
                string sRed, ArrColor, light, url1, sdate, edate, stime, first, item;
                string[] ArrRed, ArrMsg, ArrMsg1;
                int rcnt = 0, rowspan = 0, rows = 0, r = -1, sflg = 0;
                Boolean rtn;

                using (dbVOC db = new dbVOC())
                {
                    dtb0 = db.List隔離廠區項目_雨水溝預警();
                    if (dtb0.Rows.Count > 0)
                    {
                        for (int i = 0; i < dtb0.Rows.Count; i++)
                        {
                            db.Update隔離廠區項目(dtb0.Rows[i]);
                        }
                    }

                    dtb = db.GetData雨水溝預警(dt0);
                    foreach (DataRow row in dtb.Rows)
                    {
                        sRed = db.GetDataRed雨水溝預警(row, dt2);
                        if (sRed != "")
                        {
                            ArrRed = sRed.Split(',');
                            for (int j = 0; j < ArrRed.Length; j++)
                            {
                                if (DataRed.IndexOf(ArrRed[j] + "|") < 0)
                                    DataRed += (DataRed == "" ? "" : ",") + ArrRed[j] + "|";
                            }
                        }
                    }
                }

                if (DataRed != "")
                {
                    foreach (DataRow row in dtb.Rows)
                    {
                        r++;

                        if (DataRed.IndexOf(row["plantno"].ToString() + "|") > -1)
                        {
                            if (row["plantno"].ToString() != plantno)
                            {
                                sflg = row["plantno"].ToString() == "K1" || row["plantno"].ToString() == "K9" ? 1 : 0;

                                using (dbVOC db = new dbVOC())
                                {
                                    msg = db.GetMsg(dtb, row["plantno"].ToString(), r);
                                    msg1 = db.GetMsg1(dtb, row["plantno"].ToString(), r, "msg1");
                                    status = db.GetMsg1(dtb, row["plantno"].ToString(), r, "status");
                                    msg2 = db.GetMsg2(dtb, row["plantno"].ToString(), r);
                                    msg3 = db.GetMsg1(dtb, row["plantno"].ToString(), r, "msg2");
                                }

                                body = "<html><body><label>Dear Sir,<br />" +
                                    "您好, 您所負責的" + row["plantno"] + "有以下異常或提醒, 呈現(紅燈/橘燈/保養中)警示, 請儘速處理, 謝謝!</label><br /><br />" +
                                    "<table><tr><td style='text-align: left; font-size: small;'>" +
                                    "<img src='file://khfacsv01/VOCimages$/CircleRed.jpg'><font style='color: Red'><b>最新讀值＝1 且 24H累積雨量＝0</b></font>&nbsp" +
                                    "<img src='file://khfacsv01/VOCimages$/CircleOrange.jpg'><font style='color: Orange'><b>斷訊 或 異常</b></font>&nbsp" +
                                    "<img src='file://khfacsv01/VOCimages$/CircleGreen.jpg'><font style='color: Green'><b>正常狀態</b></td></tr></table>" +
                                    "<table style='border: black 1px solid' width='" + (sflg == 0 ? 600 : 900) + "px'>" +
                                    "<tr style='background-color: #CCFFFF; font-weight: bold; font-size: small;'>" +
                                    "<td style='text-align: center'><strong>廠區</strong></td>" +
                                    "<td style='text-align: center'><strong>項目</strong></td>" +
                                    "<td style='text-align: center'><strong>24H累積雨量</strong></td>" +
                                    "<td style='text-align: center'><strong>最新讀值</strong></td>" +
                                    "<td style='text-align: center'><strong>狀態</strong></td>" +
                                    "<td style='text-align: center'><strong>備註</strong></td>";

                                if (sflg == 1)
                                {
                                    body += "<td style='text-align: center'><strong>日期時間1</strong></td>" +
                                        "<td style='text-align: center'><strong>讀值1</strong></td>" +
                                        "<td style='text-align: center'><strong>日期時間2</strong></td>" +
                                        "<td style='text-align: center'><strong>讀值2</strong></td>" +
                                        "<td style='text-align: center'><strong>日期時間3</strong></td>" +
                                        "<td style='text-align: center'><strong>讀值3</strong></td>";
                                }

                                body += "</tr>";
                            }

                            body += "<tr style='background-color: #FFFFFF; color: black; font-weight: bold; font-size: small;'>";

                            if (row["plantno"].ToString() != plantno)
                            {
                                plantno = row["plantno"].ToString();
                                for (int i = r; i < dtb.Rows.Count; i++)
                                {
                                    if (dtb.Rows[i].Field<string>("plantno") != plantno) break;
                                    rowspan += 1;
                                }
                                body += "<td rowspan='" + rowspan + "' style='text-align: center'><strong>" + row["plantno"] + "</strong></td>";
                                rows = rowspan;
                            }
                            else rowspan = 0;

                            rcnt++;

                            body += "<td style='text-align: center; background-color: DodgerBlue; color: White'><strong>" + row["item"] + "</strong></td>";
                            body += "<td style='text-align: center'><strong>" + row["Sum24H"] + "</strong></td>";
                            body += "<td style='text-align: center; background-color: Cornsilk";
                            if (row["rvalue"].ToString() == "斷訊") body += "; color: Red; bordercolor: Black";
                            body += "'><strong>" + row["rvalue"] + "</strong></td>";

                            using (dbVOC db = new dbVOC()) ArrColor = db.GetData雨水溝預警(row);

                            light = (ArrColor == "G" ? "Green" : (ArrColor == "O" ? "Orange" : "Red"));

                            body += "<td style='text-align: center'><img src='file://khfacsv01/VOCimages$/Circle" + light + ".jpg'></td>" +
                                "<td style='text-align: center'><strong>";
                            if (row["sdate"].ToString() != "") body += row["sdate"];
                            body += "</strong></td>";

                            if (sflg == 1)
                            {
                                body += "<td style='text-align: center'><strong>" + row["datetime1"].ToString().Replace(" ", "<br />") + "</strong></td>";
                                body += "<td style='text-align: center'><strong>" + row["value1"] + "</strong></td>";
                                body += "<td style='text-align: center'><strong>" + row["datetime2"].ToString().Replace(" ", "<br />") + "</strong></td>";
                                body += "<td style='text-align: center'><strong>" + row["value2"] + "</strong></td>";
                                body += "<td style='text-align: center'><strong>" + row["datetime3"].ToString().Replace(" ", "<br />") + "</strong></td>";
                                body += "<td style='text-align: center'><strong>" + row["value3"] + "</strong></td>";
                            }

                            body += "</tr>";
                        }
                    }

                    if (rcnt > 0)
                    {
                        sdate = edate = dt2.ToString("yyyy/MM/dd");
                        stime = dt2.ToString("yyyy/MM/dd HH:mm");
                        url1 = "http://khfacsv01/VOC/VOCreason.aspx?plantno=" + plantno + "&sdate=" + sdate + "&edate=" + edate + "&stime=" + stime + "&type=R";
                        body += "</table><table style='border: black 1px solid' width='" + (sflg == 0 ? 600 : 900) + "px'><tr style='font-weight: bold;'>" +
                            "<td colspan=" + (sflg == 0 ? 6 : 12) + " style='text-align: left'><a href='" + url + "'>進行查看</a>" +
                            "&nbsp&nbsp&nbsp<a href='" + url1 + "'>異常原因回覆</a>" +
                            "</td></tr></table></body></html>";

                        SmtpMessage sm = new SmtpMessage();
                        sm.Message.From = new MailAddress(Jeff, "法遵平台");

                        using (dbVOC db = new dbVOC())
                        {
                            mailto = db.GetMailList(DataRed, plantno, "TO");
                            mailcc = db.GetMailList(DataRed, plantno, "CC");
                        }

                        foreach (DataRow mrow in mailto.Rows)
                            sm.Message.To.Add(mrow["NotesID"].ToString().Replace(" ", "_") + "@global.com");

                        foreach (DataRow mrow in mailcc.Rows)
                            sm.Message.CC.Add(mrow["NotesID"].ToString().Replace(" ", "_") + "@global.com");

                        sm.Message.Bcc.Add(Ray);
                        sm.Message.Bcc.Add(Albee);

                        if (sm.Message.To.Count == 0) return 0;

                        first = (status.IndexOf("首發") > -1 ? "首發" : "再發");

                        sm.Message.Subject = string.Format("【{0}】請確認「法遵平台-雨水溝預警」即時監控狀況 : {1}-{2} (Security C)", first, plantno, DT);
                        sm.Message.IsBodyHtml = true;
                        sm.Message.Body = body;
                        sm.Message.BodyEncoding = Encoding.UTF8;
                        sm.Send(sm.Message);

                        using (dbVOC db = new dbVOC())
                        {
                            db.InsertMAIL(plantno, msg, msg1, dt2, msg3);

                            item = "";
                            ArrMsg = msg.Replace("；", ";").Split(';');
                            for (int i = 0; i < ArrMsg.Length - 1; i++)
                            {
                                ArrMsg1 = ArrMsg[i].Replace("：", ":").Split(':');
                                item += (i == 0 ? "" : "、") + ArrMsg1[0].Substring(0, 3);
                            }

                            msg = "【" + first + "】" + plantno + "雨水溝預警：" + item + "有異常，請儘速處理，謝謝！";

                            phoneto = db.GetCellPhoneList(DataRed, plantno, "TO");
                            phonecc = db.GetCellPhoneList(DataRed, plantno, "CC");

                            foreach (DataRow mrow in phoneto.Rows)
                            {
                                rtn = SendSMS.SendSMSByCHTProxy(msg, mrow["CellPhone"].ToString(), 1);
                                db.InsertSMS(mrow, msg, (rtn == true ? 1 : 0));
                            }

                            if (phoneto.Rows.Count > 0)
                            {
                                foreach (DataRow mrow in phonecc.Rows)
                                {
                                    rtn = SendSMS.SendSMSByCHTProxy(msg, mrow["CellPhone"].ToString(), 1);
                                    db.InsertSMS(mrow, msg, (rtn == true ? 1 : 0));
                                }
                            }
                        }

                        rcnt = 0;
                    }
                }

                return 0;
            }
            catch (Exception ex)
            {
                Program.error = ex.Message;
                return -1;
            }
        }
        //Bermy end added on 2021/12/01 for 廠務雨水溝預警報表

        //Bermy start added on 2023/01/31 for 廠務中水放流量管控
        public int SendMail_廠務中水放流量管控()
        {
            try
            {
                string DT = DateTime.Now.ToString("yyyy/MM/dd HH:mm");
                DateTime dt2 = Convert.ToDateTime(DT + ":00");
                int m = dt2.Minute % 15;
                string dt0 = dt2.AddMinutes(-m).ToString("yyyy/MM/dd HH:mm:00");
                string dt1 = dt2.AddMinutes(-m + 3).ToString("yyyy/MM/dd HH:mm:00");
                DataTable mailto, mailcc, phoneto, phonecc;
                string msg, msg1, body;
                Boolean rtn;

                using (dbVOC db = new dbVOC())
                {
                    if (db.GetData中水(dt0) == 0) return 0;

                    if (db.GetData中水放流量(dt1) == 0) return 0;

                    msg = msg1 = "K14B有異常，請盡速處理，謝謝。放流水質OOC/OOS異常，放流量未完全停止(= 0 CMH)。";

                    body = "<html><body><label>Dear Sir,<br />您好，" + msg + "</label></body></html>";

                    SmtpMessage sm = new SmtpMessage();
                    sm.Message.From = new MailAddress(Jeff, "法遵平台");

                    mailto = db.GetMailList("水質異常-K14B", "K14B", "TO");
                    foreach (DataRow mrow in mailto.Rows) sm.Message.To.Add(mrow["NotesID"].ToString().Replace(" ", "_") + "@global.com");
                    mailcc = db.GetMailList("水質異常-K14B", "K14B", "CC");
                    foreach (DataRow mrow in mailcc.Rows) sm.Message.CC.Add(mrow["NotesID"].ToString().Replace(" ", "_") + "@global.com");

                    sm.Message.Bcc.Add(Ray);
                    sm.Message.Bcc.Add(Albee);

                    if (sm.Message.To.Count == 0) return -1;

                    sm.Message.Subject = string.Format("請確認「法遵平台-中水放流管制」即時監控狀況 : {0}-{1} (Security C)", "K14B", DT);
                    sm.Message.IsBodyHtml = true;
                    sm.Message.Body = body;
                    sm.Message.BodyEncoding = Encoding.UTF8;
                    sm.Send(sm.Message);

                    db.InsertMAIL("K14B", msg, msg1, dt2, "");

                    phoneto = db.GetCellPhoneList("水質異常-K14B", "K14B", "TO");
                    phonecc = db.GetCellPhoneList("水質異常-K14B", "K14B", "CC");

                    foreach (DataRow mrow in phoneto.Rows)
                    {
                        rtn = SendSMS.SendSMSByCHTProxy(msg, mrow["CellPhone"].ToString(), 1);
                        db.InsertSMS(mrow, msg, (rtn == true ? 1 : 0));
                    }

                    if (phoneto.Rows.Count > 0)
                    {
                        foreach (DataRow mrow in phonecc.Rows)
                        {
                            rtn = SendSMS.SendSMSByCHTProxy(msg, mrow["CellPhone"].ToString(), 1);
                            db.InsertSMS(mrow, msg, (rtn == true ? 1 : 0));
                        }
                    }
                }

                return 0;
            }
            catch (Exception ex)
            {
                Program.error = ex.Message;
                return -1;
            }
        }
        //Bermy end added on 2023/01/31 for 廠務中水放流量管控

        public int SendMail_JOB失敗通知(string cmd)
        {
            try
            {
                SmtpMessage sm = new SmtpMessage();
                sm.Message.From = new MailAddress(SendFrom, SendFromName);
                sm.Message.To.Add(Albee);
                sm.Message.To.Add(Errol);
                sm.Message.To.Add(Jason);
                sm.Message.To.Add(Ray);
                sm.Message.To.Add(YG);
                sm.Message.To.Add(HowardZC);
                sm.Message.CC.Add(Hank);
                sm.Message.CC.Add(Huching);

                sm.Message.Subject = string.Format("JOB:" + cmd + " 失敗通知 {0:yyyy/MM/dd HH:mm:ss}", DateTime.Now);
                sm.Message.IsBodyHtml = true;
                sm.Message.Body = "JobName:" + cmd + " 失敗! <br />失敗原因：" + Program.error;
                sm.Message.BodyEncoding = Encoding.UTF8;
                sm.Send(sm.Message);
                return 0;
            }
            catch (Exception ex)
            {
                Program.error = ex.Message;
                return -1;
            }
        }

        //Bermy start added on 2020/04/24 for IH主機連線異常通知
        public int SendMail_IH主機連線異常通知(string BU)
        {
            try
            {
                using (dbPMS db = new dbPMS())
                {
                    DateTime dt = DateTime.Now;
                    string msg = BU + "-IH主機無法連線!";
                    if (db.CheckMAILlog(BU, msg) == 0)  //檢查當天MAIL是否發送過: 1=是, 0=否
                    {
                        SmtpMessage sm;
                        string subject = "", body = "";
                        DataTable mailto;
                        sm = new SmtpMessage();
                        sm.Message.From = new MailAddress(Albee, "IH連線異常");
                        subject = string.Format(BU + "-IH主機無法連線! {0:yyyy/MM/dd HH:mm}", dt);
                        body = BU + "-IH主機無法連線, 請儘速處理, 謝謝!";
                        mailto = db.GetMailList(BU);
                        foreach (DataRow mrow in mailto.Rows)
                            sm.Message.To.Add(mrow["NotesID"].ToString().Replace(" ", "_") + "@global.com");
                        sm.Message.CC.Add(Albee);
                        sm.Message.CC.Add(Errol);
                        sm.Message.CC.Add(Jason);
                        sm.Message.CC.Add(Ray);
                        sm.Message.CC.Add(YG);
                        sm.Message.CC.Add(HowardZC);
                        sm.Message.CC.Add(Hank);
                        sm.Message.CC.Add(Huching);
                        sm.Message.Subject = subject;
                        sm.Message.IsBodyHtml = true;
                        sm.Message.Body = body;
                        sm.Message.BodyEncoding = Encoding.UTF8;
                        sm.Send(sm.Message);
                        db.InsertMAIL(BU, msg, dt);
                    }
                }

                return 0;
            }
            catch (Exception ex)
            {
                Program.WriteLogMsg("SendMail_IH主機連線異常通知:" + ex.Message);
                return -1;
            }
        }
        //Bermy end added on 2020/04/24 for IH主機連線異常通知

        //Bermy start added on 2020/04/24 for IH_TAG斷訊通知
        public int SendMail_IH_TAG斷訊通知(int logid, string BU, DateTime dt, string seq)
        {
            try
            {
                using (dbPMS db = new dbPMS())
                {
                    string msg = BU + "-IH_TAG斷訊" + seq + "!";
                    if (db.CheckMAILlog1(BU, msg) > 0)  //檢查是否要發送MAIL
                    {
                        SmtpMessage sm;
                        string subject = "", body = "";
                        DataTable mailto;
                        sm = new SmtpMessage();
                        sm.Message.From = new MailAddress(Albee, "IH-TAG斷訊");
                        subject = string.Format(BU + "-IH_TAG斷訊通知! {0:yyyy/MM/dd HH:mm}", dt);
                        mailto = db.GetMailList(BU);
                        foreach (DataRow mrow in mailto.Rows)
                            sm.Message.To.Add(mrow["NotesID"].ToString().Replace(" ", "_") + "@global.com");
                        sm.Message.CC.Add(Albee);
                        sm.Message.CC.Add(Errol);
                        sm.Message.CC.Add(Jason);
                        sm.Message.CC.Add(Ray);
                        sm.Message.CC.Add(YG);
                        sm.Message.CC.Add(HowardZC);
                        sm.Message.CC.Add(Hank);
                        sm.Message.CC.Add(Huching);

                        body = "<html><body><label>" + BU + "-IH_TAG斷訊, 請儘速處理, 謝謝!</label><br />" +
                            "<table style='margin-bottom: 10px;border: #999999 3px solid;' width='1000px'>" +
                            "<tr style='background-color: #CCFFFF;color: black;font-weight: bold;'>" +
                            "<td style='text-align: center'><strong>BU</strong></td>" +
                            "<td style='text-align: center'><strong>TAGNAME</strong></td>" +
                            "<td style='text-align: center'><strong>DESCRIPTION</strong></td></tr>";

                        DataTable dtb = db.GetMAILtag(logid);

                        foreach (DataRow row in dtb.Rows)
                        {
                            body += "<tr style='background-color: #FFFFFF;'>" +
                            "<td style='text-align: center;'><strong>" + row["BU"].ToString() + "</strong></td>" +
                            "<td style='text-align: center;'><strong>" + row["tagname"].ToString() + "</strong></td>" +
                            "<td style='text-align: center;'><strong>" + row["Description"].ToString() + "</strong></td></tr>";
                        }

                        body += "</table></body></html>";

                        sm.Message.Subject = subject;
                        sm.Message.IsBodyHtml = true;
                        sm.Message.Body = body;
                        sm.Message.BodyEncoding = Encoding.UTF8;
                        sm.Send(sm.Message);

                        db.UpdateMAILflg(logid);
                    }
                }

                return 0;
            }
            catch (Exception ex)
            {
                Program.WriteLogMsg("SendMail_IH主機連線異常通知:" + ex.Message);
                return -1;
            }
        }
        //Bermy end added on 2020/04/24 for IH_TAG斷訊通知

        // ── 以下為其他系統（PSN/CCTV/PLC/異常管理/電力品質等），與 VOC 平台無關，
        //    完整內容略（原始檔案過長)。如需完整比對請參考使用者原始貼上內容。
    }
}
