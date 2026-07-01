using MTLibrary;
using System;
using System.Collections.Generic;
using System.Data;
using System.Data.SqlClient;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Web.Script.Serialization;  //Bermy added on 2018/12/19

namespace Job
{
    // ─────────────────────────────────────────────────────────────────
    // 說明（2026-07-01）：這是 JOB 端的 dbVOC 類別（namespace Job），
    // 與網頁端 legacy/dbVOC.cs（namespace 未標示，屬 MTLibrary 專案）是
    // 兩個不同檔案，但都對應同一顆 VOC 資料庫。
    // 這支檔案補完了先前分析認定「缺失」的所有方法本體：
    //   GetDataRed / GetMsg / GetMsg1 / GetMsg2 / GetData()（無參數）/
    //   GetMailList / GetCellPhoneList / InsertMAIL / List隔離廠區項目 /
    //   Update隔離廠區項目 / Get前筆派報資料
    // 詳細解讀見 docs/legacy_source_analysis.md 第〇節「JOB 派報流程完整還原」。
    // 檔案後半段（UpdateVOCData 系列、IH/Kepware 資料寫入邏輯）屬於
    // JOB 讀值寫入的部分，與 Email 派報無直接關係，僅供未來 JOB 遷移參考。
    // ─────────────────────────────────────────────────────────────────
    public class dbVOC : MTDBbase<dbVOC>
    {
        public dbVOC()
            : base((int)AppConfig.DataBaseCI.VOC)
        {
        }

        public DataTable List隔離廠區項目()
        {
            string DT = DateTime.Now.ToString("yyyy/MM/dd HH:mm");
            DateTime dt1 = Convert.ToDateTime(DT + ":00");
            int m = dt1.Minute % 15;
            string dt0 = dt1.AddMinutes(-m).ToString("yyyy/MM/dd HH:mm:00");

            SqlParameterClear();
            SqlCommandText = "DECLARE @ccDT TABLE " +
                "(ccid int PRIMARY KEY); " +
                "Insert @ccDT " +
                "Select C.ccid " +
                "From [VOC].[dbo].[VOC_closectl] C " +
                "Join (Select Iif(orgccid is null,ccid,orgccid) orgccid,Max(ccid) ccid " +
                "From [VOC].[dbo].[VOC_closectl] Where fstatusid=@fstatusid " +
                "Group by Iif(orgccid is null,ccid,orgccid)) D On C.ccid=D.ccid " +
                "Where stime<=@ttime and etime>=@ttime and fstatusid=@fstatusid; " +
                "Select W.plantno,W.item,W.cdatetime,S1.source " +
                "From @ccDT C " +
                "Join [VOC].[dbo].[VOC_closectl_list] L On C.ccid=L.ccid " +
                "Join [VOC].[dbo].[VOC_SPEC] S On L.plantno=S.plantno And L.item=S.item " +
                "Join [VOC].[dbo].[VOC_SCADA_WEB] W On L.plantno=W.plantno And L.item=W.item " +
                "Join [VOC].[dbo].[VOC_source] S1 On L.sourceid=S1.sourceid " +
                "Where W.rvalue != '保養中' " +
                "Group by W.plantno,W.item,W.cdatetime,S1.source";
            SqlParameterAdd("@ttime", dt0);
            SqlParameterAdd("@fstatusid", (int)MTFlowBase.FlowStatus.核准);
            return SqlFillDT();
        }

        public DataTable List隔離廠區項目_雨水溝預警()
        {
            string DT = DateTime.Now.ToString("yyyy/MM/dd HH:mm");
            DateTime dt1 = Convert.ToDateTime(DT + ":00");
            int m = dt1.Minute % 15;
            string dt0 = dt1.AddMinutes(-m).ToString("yyyy/MM/dd HH:mm:00");

            SqlParameterClear();
            SqlCommandText = "DECLARE @ccDT TABLE " +
                "(ccid int PRIMARY KEY); " +
                "Insert @ccDT " +
                "Select C.ccid " +
                "From [VOC].[dbo].[VOC_closectl] C " +
                "Join (Select Iif(orgccid is null,ccid,orgccid) orgccid,Max(ccid) ccid " +
                "From [VOC].[dbo].[VOC_closectl] Where fstatusid=@fstatusid " +
                "Group by Iif(orgccid is null,ccid,orgccid)) D On C.ccid=D.ccid " +
                "Where stime<=@ttime and etime>=@ttime and fstatusid=@fstatusid; " +
                "Select W.plantno,W.item,W.cdatetime,'SCADA' source " +
                "From @ccDT C " +
                "Join [VOC].[dbo].[VOC_closectl_list] L On C.ccid=L.ccid " +
                "Join [VOC].[dbo].[VOC_SCADA_WEB] W On L.plantno=W.plantno And L.item=W.item " +
                "Where W.item Like '%雨水溝%' And W.rvalue != '保養中' " +
                "Group by W.plantno,W.item,W.cdatetime; ";
            SqlParameterAdd("@ttime", dt0);
            SqlParameterAdd("@fstatusid", (int)MTFlowBase.FlowStatus.核准);
            return SqlFillDT();
        }

        public void Update隔離廠區項目(DataRow row)
        {
            string tdate = DateTime.Now.ToString("yyyy/MM/dd HH:mm:ss");
            string plantno = row["plantno"].ToString();
            string item = row["item"].ToString();
            string cdatetime = row["cdatetime"].ToString();
            string source = row["source"].ToString();

            SqlParameterClear();
            SqlCommandText = "Update [VOC].[dbo].[VOC_SCADA_WEB] Set ";

            if (item.IndexOf("雨水溝") < 0)
            {
                if (source == "SCADA")
                    SqlCommandText += "OOS_HH=Iif(OOS_HH='-','-',@status), OOC_H=Iif(OOC_H='-','-',@status), alert=Iif(alert='-','-',@status), " +
                        "OOS_LL=Iif(OOS_LL='-','-',@status), OOC_L=Iif(OOC_L='-','-',@status), alert_L=Iif(alert_L='-','-',@status), ";
                else
                    SqlCommandText += "OOS_HH1=@status, OOC_H1=@status, OOS_LL1=@status, OOC_L1=@status, ";
            }

            SqlCommandText += "rvalue=@status, cdatetime=@tdate, broken=2, light=3 Where plantno=@plantno And item=@item";
            SqlParameterAdd("@tdate", tdate);
            SqlParameterAdd("@plantno", plantno);
            SqlParameterAdd("@item", item);
            SqlParameterAdd("@status", "保養中");
            SqlExecuteNonQuery();

            string DT = DateTime.Now.ToString("yyyy/MM/dd HH:mm");
            DateTime dt1 = Convert.ToDateTime(DT + ":00");
            int m = dt1.Minute % 15;
            string dt0 = dt1.AddMinutes(-m).ToString("yyyy/MM/dd HH:mm:00");

            SqlParameterClear();
            SqlCommandText = "Update [VOC].[dbo].[VOC_SCADA_HIST] Set ";

            if (item.IndexOf("雨水溝") < 0)
            {
                if (source == "SCADA")
                    SqlCommandText += "OOS_HH=Iif(OOS_HH='-','-',@status), OOC_H=Iif(OOC_H='-','-',@status), alert=Iif(alert='-','-',@status), " +
                        "OOS_LL=Iif(OOS_LL='-','-',@status), OOC_L=Iif(OOC_L='-','-',@status), alert_L=Iif(alert_L='-','-',@status), ";
                else
                    SqlCommandText += "OOS_HH1=@status, OOC_H1=@status, OOS_LL1=@status, OOC_L1=@status, ";
            }

            SqlCommandText += "rvalue=@status, cdatetime=@tdate, broken=2, light=3 " +
                "Where plantno=@plantno And item=@item And cdatetime=@tdate";
            SqlParameterAdd("@tdate", dt0);
            SqlParameterAdd("@plantno", plantno);
            SqlParameterAdd("@item", item);
            SqlParameterAdd("@cdatetime", cdatetime);
            SqlParameterAdd("@status", "保養中");
            SqlExecuteNonQuery();
        }

        public string Get隔離廠區項目區間(string plantno, string item)
        {
            string DT = DateTime.Now.ToString("yyyy/MM/dd HH:mm");
            DateTime dt1 = Convert.ToDateTime(DT + ":00");
            int m = dt1.Minute % 15;
            string dt0 = dt1.AddMinutes(-m).ToString("yyyy/MM/dd HH:mm:00");

            SqlParameterClear();
            SqlCommandText = "Select concat('從',format(stime,'MM/dd HH:mm'),'到',format(etime,'MM/dd HH:mm')) " +
                "From [VOC].[dbo].[VOC_closectl] C " +
                "Join (Select Iif(orgccid is null,ccid,orgccid) orgccid,Max(ccid) ccid " +
                "From [VOC].[dbo].[VOC_closectl] Where fstatusid=@fstatusid " +
                "Group by Iif(orgccid is null,ccid,orgccid)) D On C.ccid=D.ccid " +
                "Join [VOC].[dbo].[VOC_closectl_list] L On C.ccid=L.ccid And L.plantno=@plantno And L.item=@item " +
                "Where stime<=@ttime and etime>=@ttime and fstatusid=@fstatusid";
            SqlParameterAdd("@plantno", plantno);
            SqlParameterAdd("@item", item);
            SqlParameterAdd("@ttime", dt0);
            SqlParameterAdd("@fstatusid", (int)MTFlowBase.FlowStatus.核准);
            return SqlExecuteScalarString();
        }

        public DataTable Get前筆派報資料(string plantno, string item)
        {
            SqlParameterClear();
            SqlCommandText = "Select Top 1 cdatetime, msg1 " +
                "From [VOC].[dbo].[VOC_MAIL_Log] " +
                "Where plantno=@plantno and msg1 like @msg " +
                "Order by cdatetime desc";
            SqlParameterAdd("@plantno", plantno);
            SqlParameterAdd("@msg", "%|" + item + "|%");

            return SqlFillDT();
        }

        public DataTable Get前筆派報資料(string plantno, string item, string item1)
        {
            SqlParameterClear();
            SqlCommandText = "Select Top 1 cdatetime, msg1 " +
                "From [VOC].[dbo].[VOC_MAIL_Log] " +
                "Where plantno=@plantno and (msg1 like @msg or msg1 like @msg1) " +
                "Order by cdatetime desc";
            SqlParameterAdd("@plantno", plantno);
            SqlParameterAdd("@msg", "%|" + item + "|%");
            SqlParameterAdd("@msg1", "%|" + item1 + "|%");

            return SqlFillDT();
        }

        public DataTable GetData()
        {
            SqlParameterClear();
            SqlCommandText = "Select S.plantno,Replace(Replace(S.item,'COD2','COD'),'pH1','pH') item,I.unit,S.LAW,S.OOS,S.OOC,S.alert,S.recv," +
                "W.OOS_HH,W.OOC_H,W.alert alert1,W.OOS_HH1,W.OOC_H1,Replace(Replace(Replace(Replace(W.rvalue,'N.D',0),'<0.05',0),'<0.02',0),'<0.01',0) rvalue," +
                "P.plantid,S.seqno,W.broken,concat(Iif(W.rvalue='N.D','N.D',null),Iif(W.rvalue='<0.05','<0.05',null),Iif(W.rvalue='<0.02','<0.02',null)," +
                "Iif(W.rvalue='<0.01','<0.01',null),'|',S.source) remark,E.emptycell,space(1000) msg,space(50) sdate,space(1000) msg1,space(4) status,space(1000) msg2," +
                "space(11) LAW_v,space(11) OOS_v,space(11) OOC_v,space(11) alert_v,space(11) recv_v,space(11) OOS_HH_v,space(11) OOC_H_v " +
                "From [VOC].[dbo].[VOC_SPEC] S " +
                "Join [VOC].[dbo].[VOC_plant] P On S.plantno=P.plantno " +
                "Join [VOC].[dbo].[VOC_item] I On S.item=I.item " +
                "Left Join [VOC].[dbo].[VOC_SCADA_WEB] W On S.plantno=W.plantno And S.item=W.item " +
                "Left Join [VOC].[dbo].[VOC_EmptyCell] E On S.plantno=E.plantno And S.item=E.item " +
                "Order By plantid,seqno ";
            return SqlFillDT();
        }

        public void UpdateData(string plantno, string item, int light)
        {
            int source = GetSource(plantno, item);
            string DT = DateTime.Now.ToString("yyyy/MM/dd HH:mm");
            DateTime dt2 = Convert.ToDateTime(DT + ":00");
            int m = dt2.Minute % 15;
            string dt0 = dt2.AddMinutes(-m).ToString("yyyy/MM/dd HH:mm:00");
            string dt1 = dt2.AddMinutes(-m - 15).ToString("yyyy/MM/dd HH:mm:00");

            SqlParameterClear();
            SqlCommandText = "Update [VOC].[dbo].[VOC_SCADA_WEB] " +
                "Set cdatetime = @tdate, light = @light " +
                "Where plantno = @plantno And item = @item ";
            SqlParameterAdd("@tdate", DateTime.Now.ToString("yyyy/MM/dd HH:mm:ss"));
            SqlParameterAdd("@plantno", plantno);
            SqlParameterAdd("@item", item);
            SqlParameterAdd("@light", light);
            SqlExecuteNonQuery();

            SqlParameterClear();
            SqlCommandText = "Update [VOC].[dbo].[VOC_SCADA_HIST] " +
                "Set cdatetime = @tdate, light = @light " +
                "Where plantno = @plantno And item = @item ";

            if (source == 3)  //QA手測資料
                SqlCommandText += "And cdatetime > @tdate1 And cdatetime <= @tdate ";
            else
                SqlCommandText += "And cdatetime = @tdate ";

            SqlParameterAdd("@tdate", dt0);
            SqlParameterAdd("@tdate1", dt1);
            SqlParameterAdd("@plantno", plantno);
            SqlParameterAdd("@item", item);
            SqlParameterAdd("@light", light);
            SqlExecuteNonQuery();
        }

        public int GetSource(string plantno, string item)
        {
            SqlParameterClear();
            SqlCommandText = "Select source From [VOC].[dbo].[VOC_SPEC] Where plantno=@plantno And item=@item";
            SqlParameterAdd("@plantno", plantno);
            SqlParameterAdd("@item", item);
            return SqlExecuteScalarInt32(0);
        }

        public string ChangeData(string V, int D)
        {
            string S = (D == 0 ? "#0" : "#0.00");
            string X = "";
            string[] N = V.Split('-');

            if (N.Length < 2 || N[0] == "")
                return MTDBbase.ToDecimal(V).ToString(S);
            else
            {
                for (int i = 0; i < N.Length; i++)
                {
                    X = X + (i == 0 ? "" : "-") + MTDBbase.ToDecimal(N[i]).ToString(S);
                }
                return X;
            }
        }

        public string CheckData(string[] V)
        {
            string X = "";
            if (V.Length == 2)
            {
                for (int i = 0; i < V.Length; i++)
                {
                    int idx = V[i].IndexOf('.');
                    if (idx > 0)
                    {
                        int j = V[i].Length - 1;
                        for (; j >= 0; j--)
                        {
                            string S = V[i].Substring(j, 1);
                            if ((S != "0" && S != ".") || j < idx) break;
                        }

                        V[i] = V[i].Substring(0, j + 1);
                    }
                    X = X + (i == 0 ? "" : "-") + V[i];
                }
                return X;
            }
            else
                return V[0];
        }

        // ── GetDataRed：判斷是否列入派報、決定燈號、組出 msg/msg1/msg2、首發/再發 ──
        // 完整邏輯解讀見 docs/legacy_source_analysis.md「GetDataRed 完整還原」節。
        public string GetDataRed(DataRow row, DateTime dt2)
        {
            //紅燈條件：最新讀值>=OOS
            //橘燈條件：OOC<=最新讀值<OOS 或 SCADA與CWMS之管制值<>SPEC
            //黃燈條件：Alert<最新讀值<OOC 或 最新讀值>允收值
            //綠燈條件：正常狀態
            string sRed = "";
            string sData;
            string msg = "";
            string msg1 = "";
            string sDate = "";
            int light = 3;  //燈號: 1=紅燈, 2=黃燈, 3=綠燈, 4=橘燈
            string sPlant = row["plantno"].ToString();
            string sItem = row["item"].ToString();
            string oItem = sItem;
            DataTable dtb;
            DateTime dt1;
            TimeSpan ts;
            int first = 0;  //1=首發, 0=再發
            string dt0 = "";
            string msg0 = "";
            string msg2 = "";
            string sData1 = "";
            string msg3 = "";
            bool bWater = (sItem.IndexOf("pH") > -1 || sItem.IndexOf("Cu") > -1 || sItem.IndexOf("Ni") > -1 ||
                sItem.IndexOf("SS") > -1 || sItem.IndexOf("COD") > -1);
            string[] ArrOOCS = { "", "15", "30" };
            string sOOCS;
            string sData2;
            int cnt;
            bool bVOC = (sItem.IndexOf("VOC") > -1);

            if ((sPlant == "K14B" || sPlant == "K22" || sPlant == "九號放流口") && sItem == "pH")
                oItem = "pH1";
            else if (sPlant == "K14B" && sItem == "COD")
                oItem = "COD2";

            if (row["OOS_HH"].ToString() == "保養中" || row["OOS_HH1"].ToString() == "保養中" || row["OOS_HH"].ToString() == "-")
                sDate = Get隔離廠區項目區間(sPlant, oItem);

            dtb = Get前筆派報資料(sPlant, sItem);
            if (dtb.Rows.Count == 0)
                first = 1;
            else
            {
                dt1 = Convert.ToDateTime(dtb.Rows[0]["cdatetime"].ToString());
                ts =dt2 - dt1;
                if (ts.Days >= 1 || ts.Hours > 4 || (ts.Hours == 4 && ts.Minutes > 0))
                    first = 1;
                else
                {
                    dt0 = dtb.Rows[0]["cdatetime"].ToString();
                    msg0 = dtb.Rows[0]["msg1"].ToString();
                }
            }

            if ((sItem.IndexOf("pH") < 0 && sItem != "溫度") || (sItem == "溫度" && sPlant != "K21"))
            {
                string sOOS = row["OOS"].ToString();
                string sOOC = row["OOC_v"].ToString();
                string sAlert = row["Alert_v"].ToString();
                string sRecv = row["Recv_v"].ToString();
                string sOOS_HH = row["OOS_HH_v"].ToString();
                string sOOC_H = row["OOC_H_v"].ToString();
                string sAlert1 = row["Alert1"].ToString();
                string sOOS_HH1 = row["OOS_HH1"].ToString();
                string sOOC_H1 = row["OOC_H1"].ToString();
                string sWEB = row["rvalue"].ToString();
                string sBroken = row["broken"].ToString();
                string sType = (sItem.IndexOf("VOC") > -1 ? "空" : "水");

                if ((sOOS_HH == "-" || sOOS_HH == "N/A" || sOOS_HH == "建置中" || sOOS_HH == "異常") &&
                    (sOOC_H == "-" || sOOC_H == "N/A" || sOOC_H == "建置中" || sOOC_H == "異常") &&
                    (sAlert1 == "-" || sAlert1 == "N/A" || sAlert1 == "建置中" || sAlert1 == "異常") && sWEB != "")
                {
                    if (sAlert != "" && sAlert != "-" && sAlert != "N/A" && MTDBbase.ToDecimal(sWEB) > MTDBbase.ToDecimal(sAlert) &&
                        MTDBbase.ToDecimal(sWEB) < MTDBbase.ToDecimal(sOOC) && sOOC != "-" && sOOC != "N/A")
                    {
                        sData1 = "|" + sItem + "|：Alert＜最新讀值＜SPEC-OOC";

                        if (first != 1)
                        {
                            if (msg0.IndexOf(sData1) < 0) first = 1;
                        }

                        sData = sType + "Alert" + "-" + sPlant;
                        if (sRed.IndexOf(sData) < 0)
                            sRed += (sRed == "" ? "" : ",") + sData;
                        light = 2;
                        msg += sItem + "：Alert(" + MTDBbase.ToDecimal(sAlert) +
                            ")＜最新讀值(" + MTDBbase.ToDecimal(sWEB) + ")＜SPEC-OOC(" + MTDBbase.ToDecimal(sOOC) + ")；";
                        if (msg1.IndexOf(sData1) < 0)
                        {
                            msg1 += (msg1 == "" ? "" : ",") + sData1;
                            msg3 += (msg3 == "" ? "" : ",") + sData1;
                        }
                    }

                    if (sRecv != "" && sRecv != "-" && sRecv != "N/A" && MTDBbase.ToDecimal(sWEB) > MTDBbase.ToDecimal(sRecv))
                    {
                        sData1 = "|" + sItem + "|：最新讀值＞允收值";

                        if (first != 1)
                        {
                            if (msg0.IndexOf(sData1) < 0) first = 1;
                        }

                        sData = sType + "Alert" + "-" + sPlant;
                        if (sRed.IndexOf(sData) < 0)
                            sRed += (sRed == "" ? "" : ",") + sData;
                        light = 2;
                        msg += sItem + "：最新讀值(" + MTDBbase.ToDecimal(sWEB) + ")＞允收值(" + MTDBbase.ToDecimal(sRecv) + ")；";
                        if (msg1.IndexOf(sData1) < 0)
                        {
                            msg1 += (msg1 == "" ? "" : ",") + sData1;
                            msg3 += (msg3 == "" ? "" : ",") + sData1;
                        }
                    }

                    //CWMS OOS_HH
                    if (MTDBbase.ToDecimal(sOOS_HH1) != MTDBbase.ToDecimal(sOOS) && sOOS_HH1 != "" && sOOS_HH1 != "-" &&
                        sOOS_HH1 != "N/A" && sOOS_HH1 != "建置中" && sOOS_HH1 != "異常")
                    {
                        sData1 = "|" + sItem + "|：CWMS-OOS" + ((sOOS_HH1 == "斷訊" || sOOS_HH1 == "保養中") ? "(" + sOOS_HH1 + ")" : "與SPEC-OOS不一致");

                        if (first != 1)
                        {
                            if (msg0.IndexOf(sData1) < 0) first = 1;
                        }

                        sData = sType + (sOOS_HH1 == "斷訊" ? "斷訊" : (sOOS_HH1 == "保養中" ? "保養中" : "管制值不")) + "-" + sPlant;
                        if (sRed.IndexOf(sData) < 0)
                            sRed += (sRed == "" ? "" : ",") + sData;
                        if (sOOS_HH1 != "保養中") light = 4;
                        if (sOOS_HH1 == "斷訊" || sOOS_HH1 == "保養中")
                        {
                            msg2 = sItem + "：CWMS(" + sOOS_HH1 + ")；";
                            if (msg.IndexOf(msg2) < 0) msg += msg2;
                        }
                        else
                            msg += sItem + "：CWMS-OOS(" + MTDBbase.ToDecimal(sOOS_HH1) + ")與SPEC-OOS(" + MTDBbase.ToDecimal(sOOS) + ")不一致；";
                        if (msg1.IndexOf(sData1) < 0)
                        {
                            msg1 += (msg1 == "" ? "" : ",") + sData1;
                            if (sOOS_HH1 != "保養中") msg3 += (msg3 == "" ? "" : ",") + sData1;
                        }
                    }

                    //CWMS OOC_H
                    if (MTDBbase.ToDecimal(sOOC_H1) != MTDBbase.ToDecimal(sOOC) && sOOC_H1 != "" && sOOC_H1 != "-" &&
                        sOOC_H1 != "N/A" && sOOC_H1 != "建置中" && sOOC_H1 != "異常")
                    {
                        sData1 = "|" + sItem + "|：CWMS-OOC" + ((sOOC_H1 == "斷訊" || sOOC_H1 == "保養中") ? "(" + sOOC_H1 + ")" : "與SPEC-OOC不一致");

                        if (first != 1)
                        {
                            if (msg0.IndexOf(sData1) < 0) first = 1;
                        }

                        sData = sType + (sOOC_H1 == "斷訊" ? "斷訊" : (sOOC_H1 == "保養中" ? "保養中" : "管制值不")) + "-" + sPlant;
                        if (sRed.IndexOf(sData) < 0)
                            sRed += (sRed == "" ? "" : ",") + sData;
                        if (sOOC_H1 != "保養中") light = 4;
                        if (sOOC_H1 == "斷訊" || sOOC_H1 == "保養中")
                        {
                            msg2 = sItem + "：CWMS(" + sOOC_H1 + ")；";
                            if (msg.IndexOf(msg2) < 0) msg += msg2;
                        }
                        else
                            msg += sItem + "：CWMS-OOC(" + MTDBbase.ToDecimal(sOOC_H1) + ")與SPEC-OOC(" + MTDBbase.ToDecimal(sOOC) + ")不一致；";
                        if (msg1.IndexOf(sData1) < 0)
                        {
                            msg1 += (msg1 == "" ? "" : ",") + sData1;
                            if (sOOC_H1 != "保養中") msg3 += (msg3 == "" ? "" : ",") + sData1;
                        }
                    }

                    if (MTDBbase.ToDecimal(sWEB) >= MTDBbase.ToDecimal(sOOC) && sOOC != "" && sOOC != "-" && sOOC != "N/A" &&
                        MTDBbase.ToDecimal(sWEB) < MTDBbase.ToDecimal(sOOS) && sOOS != "" && sOOS != "-" && sOOS != "N/A")
                    {
                        if (bWater == true || bVOC == true)
                        {
                            cnt = 0;
                            sOOCS = "";
                            sData2 = "";
                            sData1 = "|" + sItem + "|：SPEC-OOC＜＝最新讀值＜SPEC-OOS";

                            if (first != 1)
                            {
                                if (msg0.IndexOf(sData1) < 0) first = 1;
                                else
                                {
                                    for (cnt = 0; cnt < ArrOOCS.Length; cnt++)
                                    {
                                        sOOCS = (cnt == 0 ? "；" : "(" + ArrOOCS[cnt] + ")；");
                                        if (msg0.IndexOf(sData1 + sOOCS) > -1)
                                        {
                                            cnt = cnt + 1;
                                            break;
                                        }
                                    }
                                }
                            }

                            if (cnt != 3)
                            {
                                sOOCS = ArrOOCS[cnt];
                                sData = sType + "OOC" + sOOCS + "-" + sPlant;
                                if (sRed.IndexOf(sData) < 0)
                                    sRed += (sRed == "" ? "" : ",") + sData;
                                light = 4;
                                msg += sItem + "：SPEC-OOC(" + MTDBbase.ToDecimal(sOOC) +
                                    ")＜＝最新讀值(" + MTDBbase.ToDecimal(sWEB) + ")＜SPEC-OOS(" + MTDBbase.ToDecimal(sOOS) + ")；";
                                sData2 = sData1 + (cnt == 0 ? sOOCS : "(" + sOOCS + ")");
                                if (msg1.IndexOf(sData2) < 0)
                                {
                                    msg1 += (msg1 == "" ? "" : ",") + sData2;
                                    msg3 += (msg3 == "" ? "" : ",") + sData1;
                                }
                            }
                            else light = 4;
                        }
                        else light = 4;
                    }

                    if (MTDBbase.ToDecimal(sWEB) >= MTDBbase.ToDecimal(sOOS) && sOOS != "" && sOOS != "-" && sOOS != "N/A")
                    {
                        if (bWater == true || bVOC == true)
                        {
                            cnt = 0;
                            sOOCS = "";
                            sData2 = "";
                            sData1 = "|" + sItem + "|：最新讀值＞＝SPEC-OOS";

                            if (first != 1)
                            {
                                if (msg0.IndexOf(sData1) < 0) first = 1;
                                else
                                {
                                    for (cnt = 0; cnt < ArrOOCS.Length; cnt++)
                                    {
                                        sOOCS = (cnt == 0 ? "；" : "(" + ArrOOCS[cnt] + ")；");
                                        if (msg0.IndexOf(sData1 + sOOCS) > -1)
                                        {
                                            cnt = cnt + 1;
                                            break;
                                        }
                                    }
                                }
                            }

                            if (cnt != 3)
                            {
                                sOOCS = ArrOOCS[cnt];
                                sData = sType + "OOS" + sOOCS + "-" + sPlant;
                                if (sRed.IndexOf(sData) < 0)
                                    sRed += (sRed == "" ? "" : ",") + sData;
                                light = 1;
                                msg += sItem + "：最新讀值(" + MTDBbase.ToDecimal(sWEB) +
                                    ")＞＝SPEC-OOS(" + MTDBbase.ToDecimal(sOOS) + ")；";
                                sData2 = sData1 + (cnt == 0 ? sOOCS : "(" + sOOCS + ")");
                                if (msg1.IndexOf(sData2) < 0)
                                {
                                    msg1 += (msg1 == "" ? "" : ",") + sData2;
                                    msg3 += (msg3 == "" ? "" : ",") + sData1;
                                }
                            }
                            else light = 1;
                        }
                        else light = 1;
                    }
                }
                else
                {
                    if (sAlert != "" && sAlert != "-" && sAlert != "N/A" && MTDBbase.ToDecimal(sWEB) > MTDBbase.ToDecimal(sAlert) &&
                        MTDBbase.ToDecimal(sWEB) < MTDBbase.ToDecimal(sOOC) && sOOC != "-" && sOOC != "N/A")
                    {
                        sData1 = "|" + sItem + "|：Alert＜最新讀值＜SPEC-OOC";

                        if (first != 1)
                        {
                            if (msg0.IndexOf(sData1) < 0) first = 1;
                        }

                        sData = sType + "Alert" + "-" + sPlant;
                        if (sRed.IndexOf(sData) < 0)
                            sRed += (sRed == "" ? "" : ",") + sData;
                        light = 2;
                        msg += sItem + "：Alert(" + MTDBbase.ToDecimal(sAlert) +
                            ")＜最新讀值(" + MTDBbase.ToDecimal(sWEB) + ")＜SPEC-OOC(" + MTDBbase.ToDecimal(sOOC) + ")；";
                        if (msg1.IndexOf(sData1) < 0)
                        {
                            msg1 += (msg1 == "" ? "" : ",") + sData1;
                            msg3 += (msg3 == "" ? "" : ",") + sData1;
                        }
                    }

                    if (sRecv != "" && sRecv != "-" && sRecv != "N/A" && MTDBbase.ToDecimal(sWEB) > MTDBbase.ToDecimal(sRecv))
                    {
                        sData1 = "|" + sItem + "|：最新讀值＞允收值";

                        if (first != 1)
                        {
                            if (msg0.IndexOf(sData1) < 0) first = 1;
                        }

                        sData = sType + "Alert" + "-" + sPlant;
                        if (sRed.IndexOf(sData) < 0)
                            sRed += (sRed == "" ? "" : ",") + sData;
                        light = 2;
                        msg += sItem + "：最新讀值(" + MTDBbase.ToDecimal(sWEB) + ")＞允收值(" + MTDBbase.ToDecimal(sRecv) + ")；";
                        if (msg1.IndexOf(sData1) < 0)
                        {
                            msg1 += (msg1 == "" ? "" : ",") + sData1;
                            msg3 += (msg3 == "" ? "" : ",") + sData1;
                        }
                    }

                    if (MTDBbase.ToDecimal(sAlert1) != MTDBbase.ToDecimal(sAlert) && sAlert1 != "" && sAlert1 != "-" &&
                        sAlert1 != "N/A" && sAlert1 != "建置中" && sAlert1 != "異常")
                    {
                        sData1 = "|" + sItem + "|：SCADA-Alert" + ((sAlert1 == "斷訊" || sAlert1 == "保養中") ? "(" + sAlert1 + ")" : "與Alert不一致");

                        if (first != 1)
                        {
                            if (msg0.IndexOf(sData1) < 0) first = 1;
                        }

                        sData = sType + (sAlert1 == "斷訊" ? "斷訊" : (sAlert1 == "保養中" ? "保養中" : "管制值不")) + "-" + sPlant;
                        if (sRed.IndexOf(sData) < 0)
                            sRed += (sRed == "" ? "" : ",") + sData;
                        if (sAlert1 != "保養中") light = 4;
                        if (sAlert1 == "斷訊" || sAlert1 == "保養中")
                        {
                            msg2 = sItem + "：SCADA(" + sAlert1 + ")；";
                            if (msg.IndexOf(msg2) < 0) msg += msg2;
                        }
                        else
                            msg += sItem + "：SCADA-Alert(" + MTDBbase.ToDecimal(sAlert1) + ")與Alert(" + MTDBbase.ToDecimal(sAlert) + ")不一致；";
                        if (msg1.IndexOf(sData1) < 0)
                        {
                            msg1 += (msg1 == "" ? "" : ",") + sData1;
                            if (sAlert1 != "保養中") msg3 += (msg3 == "" ? "" : ",") + sData1;
                        }
                    }

                    //SCADA OOS_HH
                    if (MTDBbase.ToDecimal(sOOS_HH) != MTDBbase.ToDecimal(sOOS) && sOOS_HH != "" && sOOS_HH != "-" &&
                        sOOS_HH != "N/A" && sOOS_HH != "建置中" && sOOS_HH != "異常")
                    {
                        if (sItem.IndexOf("VOC") > -1 && MTDBbase.ToDecimal(sOOS_HH) < MTDBbase.ToDecimal(sOOS))
                        {

                        }
                        else
                        {
                            sData1 = "|" + sItem + "|：SCADA-OOS" + ((sOOS_HH == "斷訊" || sOOS_HH == "保養中") ? "(" + sOOS_HH + ")" : "與SPEC-OOS不一致");

                            if (first != 1)
                            {
                                if (msg0.IndexOf(sData1) < 0) first = 1;
                            }

                            sData = sType + (sOOS_HH == "斷訊" ? "斷訊" : (sOOS_HH == "保養中" ? "保養中" : "管制值不")) + "-" + sPlant;
                            if (sRed.IndexOf(sData) < 0)
                                sRed += (sRed == "" ? "" : ",") + sData;
                            if (sOOS_HH != "保養中") light = 4;
                            if (sOOS_HH == "斷訊" || sOOS_HH == "保養中")
                            {
                                msg2 = sItem + "：SCADA(" + sOOS_HH + ")；";
                                if (msg.IndexOf(msg2) < 0) msg += msg2;
                            }
                            else
                                msg += sItem + "：SCADA-OOS(" + MTDBbase.ToDecimal(sOOS_HH) + ")與SPEC-OOS(" + MTDBbase.ToDecimal(sOOS) + ")不一致；";
                            if (msg1.IndexOf(sData1) < 0)
                            {
                                msg1 += (msg1 == "" ? "" : ",") + sData1;
                                if (sOOS_HH != "保養中") msg3 += (msg3 == "" ? "" : ",") + sData1;
                            }
                        }
                    }

                    //SCADA OOC_H
                    if (MTDBbase.ToDecimal(sOOC_H) != MTDBbase.ToDecimal(sOOC) && sOOC_H != "" && sOOC_H != "-" &&
                        sOOC_H != "N/A" && sOOC_H != "建置中" && sOOC_H != "異常")
                    {
                        if (sItem.IndexOf("VOC") > -1 && MTDBbase.ToDecimal(sOOC_H) < MTDBbase.ToDecimal(sOOC))
                        {

                        }
                        else
                        {
                            sData1 = "|" + sItem + "|：SCADA-OOC" + ((sOOC_H == "斷訊" || sOOC_H == "保養中") ? "(" + sOOC_H + ")" : "與SPEC-OOC不一致");

                            if (first != 1)
                            {
                                if (msg0.IndexOf(sData1) < 0) first = 1;
                            }

                            sData = sType + (sOOC_H == "斷訊" ? "斷訊" : (sOOC_H == "保養中" ? "保養中" : "管制值不")) + "-" + sPlant;
                            if (sRed.IndexOf(sData) < 0)
                                sRed += (sRed == "" ? "" : ",") + sData;
                            if (sOOC_H != "保養中") light = 4;
                            if (sOOC_H == "斷訊" || sOOC_H == "保養中")
                            {
                                msg2 = sItem + "：SCADA(" + sOOC_H + ")；";
                                if (msg.IndexOf(msg2) < 0) msg += msg2;
                            }
                            else
                                msg += sItem + "：SCADA-OOC(" + MTDBbase.ToDecimal(sOOC_H) + ")與SPEC-OOC(" + MTDBbase.ToDecimal(sOOC) + ")不一致；";
                            if (msg1.IndexOf(sData1) < 0)
                            {
                                msg1 += (msg1 == "" ? "" : ",") + sData1;
                                if (sOOC_H != "保養中") msg3 += (msg3 == "" ? "" : ",") + sData1;
                            }
                        }
                    }

                    //CWMS OOS_HH
                    if (MTDBbase.ToDecimal(sOOS_HH1) != MTDBbase.ToDecimal(sOOS) && sOOS_HH1 != "" && sOOS_HH1 != "-" &&
                        sOOS_HH1 != "N/A" && sOOS_HH1 != "建置中" && sOOS_HH1 != "異常")
                    {
                        sData1 = "|" + sItem + "|：CWMS-OOS" + ((sOOS_HH1 == "斷訊" || sOOS_HH1 == "保養中") ? "(" + sOOS_HH1 + ")" : "與SPEC-OOS不一致");

                        if (first != 1)
                        {
                            if (msg0.IndexOf(sData1) < 0) first = 1;
                        }

                        sData = sType + (sOOS_HH1 == "斷訊" ? "斷訊" : (sOOS_HH1 == "保養中" ? "保養中" : "管制值不")) + "-" + sPlant;
                        if (sRed.IndexOf(sData) < 0)
                            sRed += (sRed == "" ? "" : ",") + sData;
                        if (sOOS_HH1 != "保養中") light = 4;
                        if (sOOS_HH1 == "斷訊" || sOOS_HH1 == "保養中")
                        {
                            msg2 = sItem + "：CWMS(" + sOOS_HH1 + ")；";
                            if (msg.IndexOf(msg2) < 0) msg += msg2;
                        }
                        else
                            msg += sItem + "：CWMS-OOS(" + MTDBbase.ToDecimal(sOOS_HH1) + ")與SPEC-OOS(" + MTDBbase.ToDecimal(sOOS) + ")不一致；";
                        if (msg1.IndexOf(sData1) < 0)
                        {
                            msg1 += (msg1 == "" ? "" : ",") + sData1;
                            if (sOOS_HH1 != "保養中") msg3 += (msg3 == "" ? "" : ",") + sData1;
                        }
                    }

                    //CWMS OOC_H
                    if (MTDBbase.ToDecimal(sOOC_H1) != MTDBbase.ToDecimal(sOOC) && sOOC_H1 != "" && sOOC_H1 != "-" &&
                        sOOC_H1 != "N/A" && sOOC_H1 != "建置中" && sOOC_H1 != "異常")
                    {
                        sData1 = "|" + sItem + "|：CWMS-OOC" + ((sOOC_H1 == "斷訊" || sOOC_H1 == "保養中") ? "(" + sOOC_H1 + ")" : "與SPEC-OOC不一致");

                        if (first != 1)
                        {
                            if (msg0.IndexOf(sData1) < 0) first = 1;
                        }

                        sData = sType + (sOOC_H1 == "斷訊" ? "斷訊" : (sOOC_H1 == "保養中" ? "保養中" : "管制值不")) + "-" + sPlant;
                        if (sRed.IndexOf(sData) < 0)
                            sRed += (sRed == "" ? "" : ",") + sData;
                        if (sOOC_H1 != "保養中") light = 4;
                        if (sOOC_H1 == "斷訊" || sOOC_H1 == "保養中")
                        {
                            msg2 = sItem + "：CWMS(" + sOOC_H1 + ")；";
                            if (msg.IndexOf(msg2) < 0) msg += msg2;
                        }
                        else
                            msg += sItem + "：CWMS-OOC(" + MTDBbase.ToDecimal(sOOC_H1) + ")與SPEC-OOC(" + MTDBbase.ToDecimal(sOOC) + ")不一致；";
                        if (msg1.IndexOf(sData1) < 0)
                        {
                            msg1 += (msg1 == "" ? "" : ",") + sData1;
                            if (sOOC_H1 != "保養中") msg3 += (msg3 == "" ? "" : ",") + sData1;
                        }
                    }

                    if (sWEB == "")
                    {
                        if (sOOS_HH == "" && sOOC_H == "" && sAlert1 == "")
                        {
                            if (sBroken == "0") //沒斷訊
                            {
                                sData = sType + "OOS" + "-" + sPlant;
                                if (sRed.IndexOf(sData) < 0)
                                    sRed += (sRed == "" ? "" : ",") + sData;
                                sData = sType + "OOC" + "-" + sPlant;
                                if (sRed.IndexOf(sData) < 0)
                                    sRed += (sRed == "" ? "" : ",") + sData;
                            }
                            light = 1;
                        }
                    }
                    else
                    {
                        if (MTDBbase.ToDecimal(sWEB) >= MTDBbase.ToDecimal(sOOC) && sOOC != "" && sOOC != "-" && sOOC != "N/A" &&
                            MTDBbase.ToDecimal(sWEB) < MTDBbase.ToDecimal(sOOS) && sOOS != "" && sOOS != "-" && sOOS != "N/A")
                        {
                            if (bWater == true || bVOC == true)
                            {
                                cnt = 0;
                                sOOCS = "";
                                sData2 = "";
                                sData1 = "|" + sItem + "|：SPEC-OOC＜＝最新讀值＜SPEC-OOS";

                                if (first != 1)
                                {
                                    if (msg0.IndexOf(sData1) < 0) first = 1;
                                    else
                                    {
                                        for (cnt = 0; cnt < ArrOOCS.Length; cnt++)
                                        {
                                            sOOCS = (cnt == 0 ? "；" : "(" + ArrOOCS[cnt] + ")；");
                                            if (msg0.IndexOf(sData1 + sOOCS) > -1)
                                            {
                                                cnt = cnt + 1;
                                                break;
                                            }
                                        }
                                    }
                                }

                                if (cnt != 3)
                                {
                                    sOOCS = ArrOOCS[cnt];
                                    sData = sType + "OOC" + sOOCS + "-" + sPlant;
                                    if (sRed.IndexOf(sData) < 0)
                                        sRed += (sRed == "" ? "" : ",") + sData;
                                    light = 4;
                                    msg += sItem + "：SPEC-OOC(" + MTDBbase.ToDecimal(sOOC) +
                                        ")＜＝最新讀值(" + MTDBbase.ToDecimal(sWEB) + ")＜SPEC-OOS(" + MTDBbase.ToDecimal(sOOS) + ")；";
                                    sData2 = sData1 + (cnt == 0 ? sOOCS : "(" + sOOCS + ")");
                                    if (msg1.IndexOf(sData2) < 0)
                                    {
                                        msg1 += (msg1 == "" ? "" : ",") + sData2;
                                        msg3 += (msg3 == "" ? "" : ",") + sData1;
                                    }
                                }
                                else light = 4;
                            }
                            else light = 4;
                        }

                        if (MTDBbase.ToDecimal(sWEB) >= MTDBbase.ToDecimal(sOOS) && sOOS != "" && sOOS != "-" && sOOS != "N/A")
                        {
                            if (bWater == true || bVOC == true)
                            {
                                cnt = 0;
                                sOOCS = "";
                                sData2 = "";
                                sData1 = "|" + sItem + "|：最新讀值＞＝SPEC-OOS";

                                if (first != 1)
                                {
                                    if (msg0.IndexOf(sData1) < 0) first = 1;
                                    else
                                    {
                                        for (cnt = 0; cnt < ArrOOCS.Length; cnt++)
                                        {
                                            sOOCS = (cnt == 0 ? "；" : "(" + ArrOOCS[cnt] + ")；");
                                            if (msg0.IndexOf(sData1 + sOOCS) > -1)
                                            {
                                                cnt = cnt + 1;
                                                break;
                                            }
                                        }
                                    }
                                }

                                if (cnt != 3)
                                {
                                    sOOCS = ArrOOCS[cnt];
                                    if (sBroken == "0") //沒斷訊
                                    {
                                        sData = sType + "OOS" + sOOCS + "-" + sPlant;
                                        if (sRed.IndexOf(sData) < 0)
                                            sRed += (sRed == "" ? "" : ",") + sData;
                                    }
                                    light = 1;
                                    msg += sItem + "：最新讀值(" + MTDBbase.ToDecimal(sWEB) +
                                        ")＞＝SPEC-OOS(" + MTDBbase.ToDecimal(sOOS) + ")；";
                                    sData2 = sData1 + (cnt == 0 ? sOOCS : "(" + sOOCS + ")");
                                    if (msg1.IndexOf(sData2) < 0)
                                    {
                                        msg1 += (msg1 == "" ? "" : ",") + sData2;
                                        msg3 += (msg3 == "" ? "" : ",") + sData1;
                                    }
                                }
                                else light = 1;
                            }
                            else light = 1;
                        }
                    }
                }
            }
            else
            {
                string sOOS = row["OOS_v"].ToString();
                string sOOC = row["OOC_v"].ToString();
                string sAlert = row["Alert_v"].ToString();
                string sRecv = row["Recv_v"].ToString();
                string sOOS_HH = row["OOS_HH_v"].ToString();
                string sOOC_H = row["OOC_H_v"].ToString();
                string sAlert1 = row["Alert1"].ToString();
                string sOOS_HH1 = row["OOS_HH1"].ToString();
                string sOOC_H1 = row["OOC_H1"].ToString();
                string[] OOS = sOOS.Split('-');
                string[] OOC = sOOC.Split('-');
                string[] Alert = sAlert.Split('-');
                string[] Recv = sRecv.Split('-');
                string[] OOS_HH = sOOS_HH.Split('-');
                string[] OOC_H = sOOC_H.Split('-');
                string[] Alert1 = sAlert1.Split('-');
                string[] OOS_HH1 = sOOS_HH1.Split('-');
                string[] OOC_H1 = sOOC_H1.Split('-');
                string WEB = row["rvalue"].ToString();
                string Broken = row["broken"].ToString();

                if ((sOOS_HH == "-" || sOOS_HH == "N/A" || sOOS_HH == "建置中" || sOOS_HH == "異常") &&
                    (sOOC_H == "-" || sOOC_H == "N/A" || sOOC_H == "建置中" || sOOC_H == "異常") &&
                    (sAlert1 == "-" || sAlert1 == "N/A" || sAlert1 == "建置中" || sAlert1 == "異常") && WEB != "")
                {
                    if (sAlert != "-" && Alert.Length == 2 && OOC.Length == 2)
                    {
                        if (MTDBbase.ToDecimal(WEB) > MTDBbase.ToDecimal(Alert[1]) &&
                            MTDBbase.ToDecimal(WEB) < MTDBbase.ToDecimal(OOC[1]))
                        {
                            sData1 = "|" + sItem + "|：Alert＜最新讀值＜SPEC-OOC";

                            if (first != 1)
                            {
                                if (msg0.IndexOf(sData1) < 0) first = 1;
                            }

                            sData = "水Alert" + "-" + sPlant;
                            if (sRed.IndexOf(sData) < 0)
                                sRed += (sRed == "" ? "" : ",") + sData;
                            light = 2;
                            msg += sItem + "：Alert(" + MTDBbase.ToDecimal(Alert[1]) +
                               ")＜最新讀值(" + MTDBbase.ToDecimal(WEB) + ")＜SPEC-OOC(" + MTDBbase.ToDecimal(OOC[1]) + ")；";
                            if (msg1.IndexOf(sData1) < 0)
                            {
                                msg1 += (msg1 == "" ? "" : ",") + sData1;
                                msg3 += (msg3 == "" ? "" : ",") + sData1;
                            }
                        }
                    }

                    if (sRecv != "-" && Recv.Length == 2)
                    {
                        if (MTDBbase.ToDecimal(WEB) > MTDBbase.ToDecimal(Recv[1]))
                        {
                            sData1 = "|" + sItem + "|：最新讀值＞允收值";

                            if (first != 1)
                            {
                                if (msg0.IndexOf(sData1) < 0) first = 1;
                            }

                            sData = "水Alert" + "-" + sPlant;
                            if (sRed.IndexOf(sData) < 0)
                                sRed += (sRed == "" ? "" : ",") + sData;
                            light = 2;
                            msg += sItem + "：最新讀值(" + MTDBbase.ToDecimal(WEB) + ")＞允收值(" + MTDBbase.ToDecimal(Recv[1]) + ")；";
                            if (msg1.IndexOf(sData1) < 0)
                            {
                                msg1 += (msg1 == "" ? "" : ",") + sData1;
                                msg3 += (msg3 == "" ? "" : ",") + sData1;
                            }
                        }
                    }

                    //CWMS OOS_HH
                    if (CheckData(OOS_HH1) != CheckData(OOS) && sOOS_HH1 != "" && sOOS_HH1 != "-" &&
                        sOOS_HH1 != "N/A" && sOOS_HH1 != "建置中" && sOOS_HH1 != "異常")
                    {
                        sData1 = "|" + sItem + "|：CWMS-OOS" + ((sOOS_HH1 == "斷訊" || sOOS_HH1 == "保養中") ? "(" + sOOS_HH1 + ")" : "與SPEC-OOS不一致");

                        if (first != 1)
                        {
                            if (msg0.IndexOf(sData1) < 0) first = 1;
                        }

                        sData = (sOOS_HH1 == "斷訊" ? "水斷訊" : (sOOS_HH1 == "保養中" ? "水保養中" : "水管制值不")) + "-" + sPlant;
                        if (sRed.IndexOf(sData) < 0)
                            sRed += (sRed == "" ? "" : ",") + sData;
                        if (sOOS_HH1 != "保養中") light = 4;
                        if (sOOS_HH1 == "斷訊" || sOOS_HH1 == "保養中")
                        {
                            msg2 = sItem + "：CWMS(" + sOOS_HH1 + ")；";
                            if (msg.IndexOf(msg2) < 0) msg += msg2;
                        }
                        else
                            msg += sItem + "：CWMS-OOS(" + CheckData(OOS_HH1) + ")與SPEC-OOS(" + CheckData(OOS) + ")不一致；";
                        if (msg1.IndexOf(sData1) < 0)
                        {
                            msg1 += (msg1 == "" ? "" : ",") + sData1;
                            if (sOOS_HH1 != "保養中") msg3 += (msg3 == "" ? "" : ",") + sData1;
                        }
                    }

                    //CWMS OOC_H
                    if (CheckData(OOC_H1) != CheckData(OOC) && sOOC_H1 != "" && sOOC_H1 != "-" &&
                        sOOC_H1 != "N/A" && sOOC_H1 != "建置中" && sOOC_H1 != "異常")
                    {
                        sData1 = "|" + sItem + "|：CWMS-OOC" + ((sOOC_H1 == "斷訊" || sOOC_H1 == "保養中") ? "(" + sOOC_H1 + ")" : "與SPEC-OOC不一致");

                        if (first != 1)
                        {
                            if (msg0.IndexOf(sData1) < 0) first = 1;
                        }

                        sData = (sOOC_H1 == "斷訊" ? "水斷訊" : (sOOC_H1 == "保養中" ? "水保養中" : "水管制值不")) + "-" + sPlant;
                        if (sRed.IndexOf(sData) < 0)
                            sRed += (sRed == "" ? "" : ",") + sData;
                        if (sOOC_H1 != "保養中") light = 4;
                        if (sOOC_H1 == "斷訊" || sOOC_H1 == "保養中")
                        {
                            msg2 = sItem + "：CWMS(" + sOOC_H1 + ")；";
                            if (msg.IndexOf(msg2) < 0) msg += msg2;
                        }
                        else
                            msg += sItem + "：CWMS-OOC(" + CheckData(OOC_H1) + ")與SPEC-OOC(" + CheckData(OOC) + ")不一致；";
                        if (msg1.IndexOf(sData1) < 0)
                        {
                            msg1 += (msg1 == "" ? "" : ",") + sData1;
                            if (sOOC_H1 != "保養中") msg3 += (msg3 == "" ? "" : ",") + sData1;
                        }
                    }

                    if (OOC.Length == 2 && OOS.Length == 2)
                    {
                        if (MTDBbase.ToDecimal(WEB) >= MTDBbase.ToDecimal(OOC[1]) && sOOC != "-" &&
                            MTDBbase.ToDecimal(WEB) < MTDBbase.ToDecimal(OOS[1]) && sOOS != "-")
                        {
                            if (bWater == true)
                            {
                                cnt = 0;
                                sOOCS = "";
                                sData2 = "";
                                sData1 = "|" + sItem + "|：SPEC-OOC＜＝最新讀值＜SPEC-OOS";

                                if (first != 1)
                                {
                                    if (msg0.IndexOf(sData1) < 0) first = 1;
                                    else
                                    {
                                        for (cnt = 0; cnt < ArrOOCS.Length; cnt++)
                                        {
                                            sOOCS = (cnt == 0 ? "；" : "(" + ArrOOCS[cnt] + ")；");
                                            if (msg0.IndexOf(sData1 + sOOCS) > -1)
                                            {
                                                cnt = cnt + 1;
                                                break;
                                            }
                                        }
                                    }
                                }

                                if (cnt != 3)
                                {
                                    sOOCS = ArrOOCS[cnt];
                                    sData = "水OOC" + sOOCS + "-" + sPlant;
                                    if (sRed.IndexOf(sData) < 0)
                                        sRed += (sRed == "" ? "" : ",") + sData;
                                    light = 4;
                                    msg += sItem + "：SPEC-OOC(" + MTDBbase.ToDecimal(OOC[1]) +
                                        ")＜＝最新讀值(" + MTDBbase.ToDecimal(WEB) + ")＜SPEC-OOS(" + MTDBbase.ToDecimal(OOS[1]) + ")；";
                                    sData2 = sData1 + (cnt == 0 ? sOOCS : "(" + sOOCS + ")");
                                    if (msg1.IndexOf(sData2) < 0)
                                    {
                                        msg1 += (msg1 == "" ? "" : ",") + sData2;
                                        msg3 += (msg3 == "" ? "" : ",") + sData1;
                                    }
                                }
                                else light = 4;
                            }
                            else light = 4;
                        }
                    }

                    if (OOS.Length == 2)
                    {
                        if (MTDBbase.ToDecimal(WEB) >= MTDBbase.ToDecimal(OOS[1]) && sOOS != "-")
                        {
                            if (bWater == true)
                            {
                                cnt = 0;
                                sOOCS = "";
                                sData2 = "";
                                sData1 = "|" + sItem + "|：最新讀值＞＝SPEC-OOS";

                                if (first != 1)
                                {
                                    if (msg0.IndexOf(sData1) < 0) first = 1;
                                    else
                                    {
                                        for (cnt = 0; cnt < ArrOOCS.Length; cnt++)
                                        {
                                            sOOCS = (cnt == 0 ? "；" : "(" + ArrOOCS[cnt] + ")；");
                                            if (msg0.IndexOf(sData1 + sOOCS) > -1)
                                            {
                                                cnt = cnt + 1;
                                                break;
                                            }
                                        }
                                    }
                                }

                                if (cnt != 3)
                                {
                                    sOOCS = ArrOOCS[cnt];
                                    sData = "水OOS" + sOOCS + "-" + sPlant;
                                    if (sRed.IndexOf(sData) < 0)
                                        sRed += (sRed == "" ? "" : ",") + sData;
                                    light = 1;
                                    msg += sItem + "：最新讀值(" + MTDBbase.ToDecimal(WEB) +
                                        ")＞＝SPEC-OOS(" + MTDBbase.ToDecimal(OOS[1]) + ")；";
                                    sData2 = sData1 + (cnt == 0 ? sOOCS : "(" + sOOCS + ")");
                                    if (msg1.IndexOf(sData2) < 0)
                                    {
                                        msg1 += (msg1 == "" ? "" : ",") + sData2;
                                        msg3 += (msg3 == "" ? "" : ",") + sData1;
                                    }
                                }
                                else light = 1;
                            }
                            else light = 1;
                        }
                    }
                }
                else
                {
                    if (CheckData(Alert1) != CheckData(Alert) && sAlert1 != "" && sAlert1 != "-" &&
                        sAlert1 != "N/A" && sAlert1 != "建置中" && sAlert1 != "異常")
                    {
                        sData1 = "|" + sItem + "|：SCADA-Alert" + ((sAlert1 == "斷訊" || sAlert1 == "保養中") ? "(" + sAlert1 + ")" : "與Alert不一致");

                        if (first != 1)
                        {
                            if (msg0.IndexOf(sData1) < 0) first = 1;
                        }

                        sData = (sAlert1 == "斷訊" ? "水斷訊" : (sAlert1 == "保養中" ? "水保養中" : "水管制值不")) + "-" + sPlant;
                        if (sRed.IndexOf(sData) < 0)
                            sRed += (sRed == "" ? "" : ",") + sData;
                        if (sAlert1 != "保養中") light = 4;
                        if (sAlert1 == "斷訊" || sAlert1 == "保養中")
                        {
                            msg2 = sItem + "：SCADA(" + sAlert1 + ")；";
                            if (msg.IndexOf(msg2) < 0) msg += msg2;
                        }
                        else
                            msg += sItem + "：SCADA-Alert(" + CheckData(Alert1) + ")與Alert(" + CheckData(Alert) + ")不一致；";
                        if (msg1.IndexOf(sData1) < 0)
                        {
                            msg1 += (msg1 == "" ? "" : ",") + sData1;
                            if (sAlert1 != "保養中") msg3 += (msg3 == "" ? "" : ",") + sData1;
                        }
                    }

                    //SCADA OOS_HH
                    if (CheckData(OOS_HH) != CheckData(OOS) && sOOS_HH != "" && sOOS_HH != "-" &&
                        sOOS_HH != "N/A" && sOOS_HH != "建置中" && sOOS_HH != "異常")
                    {
                        sData1 = "|" + sItem + "|：SCADA-OOS" + ((sOOS_HH == "斷訊" || sOOS_HH == "保養中") ? "(" + sOOS_HH + ")" : "與SPEC-OOS不一致");

                        if (first != 1)
                        {
                            if (msg0.IndexOf(sData1) < 0) first = 1;
                        }

                        sData = (sOOS_HH == "斷訊" ? "水斷訊" : (sOOS_HH == "保養中" ? "水保養中" : "水管制值不")) + "-" + sPlant;
                        if (sRed.IndexOf(sData) < 0)
                            sRed += (sRed == "" ? "" : ",") + sData;
                        if (sOOS_HH != "保養中") light = 4;
                        if (sOOS_HH == "斷訊" || sOOS_HH == "保養中")
                        {
                            msg2 = sItem + "：SCADA(" + sOOS_HH + ")；";
                            if (msg.IndexOf(msg2) < 0) msg += msg2;
                        }
                        else
                            msg += sItem + "：SCADA-OOS(" + CheckData(OOS_HH) + ")與SPEC-OOS(" + CheckData(OOS) + ")不一致；";
                        if (msg1.IndexOf(sData1) < 0)
                        {
                            msg1 += (msg1 == "" ? "" : ",") + sData1;
                            if (sOOS_HH != "保養中") msg3 += (msg3 == "" ? "" : ",") + sData1;
                        }
                    }

                    //SCADA OOC_H
                    if (CheckData(OOC_H) != CheckData(OOC) && sOOC_H != "" && sOOC_H != "-" &&
                        sOOC_H != "N/A" && sOOC_H != "建置中" && sOOC_H != "異常")
                    {
                        sData1 = "|" + sItem + "|：SCADA-OOC" + ((sOOC_H == "斷訊" || sOOC_H == "保養中") ? "(" + sOOC_H + ")" : "與SPEC-OOC不一致");

                        if (first != 1)
                        {
                            if (msg0.IndexOf(sData1) < 0) first = 1;
                        }

                        sData = (sOOC_H == "斷訊" ? "水斷訊" : (sOOC_H == "保養中" ? "水保養中" : "水管制值不")) + "-" + sPlant;
                        if (sRed.IndexOf(sData) < 0)
                            sRed += (sRed == "" ? "" : ",") + sData;
                        if (sOOC_H != "保養中") light = 4;
                        if (sOOC_H == "斷訊" || sOOC_H == "保養中")
                        {
                            msg2 = sItem + "：SCADA(" + sOOC_H + ")；";
                            if (msg.IndexOf(msg2) < 0) msg += msg2;
                        }
                        else
                            msg += sItem + "：SCADA-OOC(" + CheckData(OOC_H) + ")與SPEC-OOC(" + CheckData(OOC) + ")不一致；";
                        if (msg1.IndexOf(sData1) < 0)
                        {
                            msg1 += (msg1 == "" ? "" : ",") + sData1;
                            if (sOOC_H != "保養中") msg3 += (msg3 == "" ? "" : ",") + sData1;
                        }
                    }

                    //CWMS OOS_HH
                    if (CheckData(OOS_HH1) != CheckData(OOS) && sOOS_HH1 != "" && sOOS_HH1 != "-" &&
                        sOOS_HH1 != "N/A" && sOOS_HH1 != "建置中" && sOOS_HH1 != "異常")
                    {
                        sData1 = "|" + sItem + "|：CWMS-OOS" + ((sOOS_HH1 == "斷訊" || sOOS_HH1 == "保養中") ? "(" + sOOS_HH1 + ")" : "與SPEC-OOS不一致");

                        if (first != 1)
                        {
                            if (msg0.IndexOf(sData1) < 0) first = 1;
                        }

                        sData = (sOOS_HH1 == "斷訊" ? "水斷訊" : (sOOS_HH1 == "保養中" ? "水保養中" : "水管制值不")) + "-" + sPlant;
                        if (sRed.IndexOf(sData) < 0)
                            sRed += (sRed == "" ? "" : ",") + sData;
                        if (sOOS_HH1 != "保養中") light = 4;
                        if (sOOS_HH1 == "斷訊" || sOOS_HH1 == "保養中")
                        {
                            msg2 = sItem + "：CWMS(" + sOOS_HH1 + ")；";
                            if (msg.IndexOf(msg2) < 0) msg += msg2;
                        }
                        else
                            msg += sItem + "：CWMS-OOS(" + CheckData(OOS_HH1) + ")與SPEC-OOS(" + CheckData(OOS) + ")不一致；";
                        if (msg1.IndexOf(sData1) < 0)
                        {
                            msg1 += (msg1 == "" ? "" : ",") + sData1;
                            if (sOOS_HH1 != "保養中") msg3 += (msg3 == "" ? "" : ",") + sData1;
                        }
                    }

                    //CWMS OOC_H
                    if (CheckData(OOC_H1) != CheckData(OOC) && sOOC_H1 != "" && sOOC_H1 != "-" &&
                        sOOC_H1 != "N/A" && sOOC_H1 != "建置中" && sOOC_H1 != "異常")
                    {
                        sData1 = "|" + sItem + "|：CWMS-OOC" + ((sOOC_H1 == "斷訊" || sOOC_H1 == "保養中") ? "(" + sOOC_H1 + ")" : "與SPEC-OOC不一致");

                        if (first != 1)
                        {
                            if (msg0.IndexOf(sData1) < 0) first = 1;
                        }

                        sData = (sOOC_H1 == "斷訊" ? "水斷訊" : (sOOC_H1 == "保養中" ? "水保養中" : "水管制值不")) + "-" + sPlant;
                        if (sRed.IndexOf(sData) < 0)
                            sRed += (sRed == "" ? "" : ",") + sData;
                        if (sOOC_H1 != "保養中") light = 4;
                        if (sOOC_H1 == "斷訊" || sOOC_H1 == "保養中")
                        {
                            msg2 = sItem + "：CWMS(" + sOOC_H1 + ")；";
                            if (msg.IndexOf(msg2) < 0) msg += msg2;
                        }
                        else
                            msg += sItem + "：CWMS-OOC(" + CheckData(OOC_H1) + ")與SPEC-OOC(" + CheckData(OOC) + ")不一致；";
                        if (msg1.IndexOf(sData1) < 0)
                        {
                            msg1 += (msg1 == "" ? "" : ",") + sData1;
                            if (sOOC_H1 != "保養中") msg3 += (msg3 == "" ? "" : ",") + sData1;
                        }
                    }

                    if (WEB == "")
                    {
                        if (sOOS_HH == "" && sOOC_H == "" && sAlert1 == "")
                        {
                            light = 1;
                        }
                    }
                    else
                    {
                        if (sAlert != "-" && Alert.Length == 2 && OOC.Length == 2)
                        {
                            if (MTDBbase.ToDecimal(WEB) > MTDBbase.ToDecimal(Alert[1]) &&
                                MTDBbase.ToDecimal(WEB) < MTDBbase.ToDecimal(OOC[1]))
                            {
                                sData1 = "|" + sItem + "|：Alert＜最新讀值＜SPEC-OOC";

                                if (first != 1)
                                {
                                    if (msg0.IndexOf(sData1) < 0) first = 1;
                                }

                                sData = "水Alert" + "-" + sPlant;
                                if (sRed.IndexOf(sData) < 0)
                                    sRed += (sRed == "" ? "" : ",") + sData;
                                light = 2;
                                msg += sItem + "：Alert(" + MTDBbase.ToDecimal(Alert[1]) +
                                   ")＜最新讀值(" + MTDBbase.ToDecimal(WEB) + ")＜SPEC-OOC(" + MTDBbase.ToDecimal(OOC[1]) + ")；";
                                if (msg1.IndexOf(sData1) < 0)
                                {
                                    msg1 += (msg1 == "" ? "" : ",") + sData1;
                                    msg3 += (msg3 == "" ? "" : ",") + sData1;
                                }
                            }
                        }

                        if (sRecv != "-" && Recv.Length == 2)
                        {
                            if (MTDBbase.ToDecimal(WEB) > MTDBbase.ToDecimal(Recv[1]))
                            {
                                sData1 = "|" + sItem + "|：最新讀值＞允收值";

                                if (first != 1)
                                {
                                    if (msg0.IndexOf(sData1) < 0) first = 1;
                                }

                                sData = "水Alert" + "-" + sPlant;
                                if (sRed.IndexOf(sData) < 0)
                                    sRed += (sRed == "" ? "" : ",") + sData;
                                light = 2;
                                msg += sItem + "：最新讀值(" + MTDBbase.ToDecimal(WEB) + ")＞允收值(" + MTDBbase.ToDecimal(Recv[1]) + ")；";
                                if (msg1.IndexOf(sData1) < 0)
                                {
                                    msg1 += (msg1 == "" ? "" : ",") + sData1;
                                    msg3 += (msg3 == "" ? "" : ",") + sData1;
                                }
                            }
                        }

                        if (OOC.Length == 2 && OOS.Length == 2)
                        {
                            if (MTDBbase.ToDecimal(WEB) >= MTDBbase.ToDecimal(OOC[1]) && sOOC != "-" &&
                                MTDBbase.ToDecimal(WEB) < MTDBbase.ToDecimal(OOS[1]) && sOOS != "-")
                            {
                                if (bWater == true)
                                {
                                    cnt = 0;
                                    sOOCS = "";
                                    sData2 = "";
                                    sData1 = "|" + sItem + "|：SPEC-OOC＜＝最新讀值＜SPEC-OOS";

                                    if (first != 1)
                                    {
                                        if (msg0.IndexOf(sData1) < 0) first = 1;
                                        else
                                        {
                                            for (cnt = 0; cnt < ArrOOCS.Length; cnt++)
                                            {
                                                sOOCS = (cnt == 0 ? "；" : "(" + ArrOOCS[cnt] + ")；");
                                                if (msg0.IndexOf(sData1 + sOOCS) > -1)
                                                {
                                                    cnt = cnt + 1;
                                                    break;
                                                }
                                            }
                                        }
                                    }

                                    if (cnt != 3)
                                    {
                                        sOOCS = ArrOOCS[cnt];
                                        sData = "水OOC" + sOOCS + "-" + sPlant;
                                        if (sRed.IndexOf(sData) < 0)
                                            sRed += (sRed == "" ? "" : ",") + sData;
                                        light = 4;
                                        msg += sItem + "：SPEC-OOC(" + MTDBbase.ToDecimal(OOC[1]) +
                                            ")＜＝最新讀值(" + MTDBbase.ToDecimal(WEB) + ")＜SPEC-OOS(" + MTDBbase.ToDecimal(OOS[1]) + ")；";
                                        sData2 = sData1 + (cnt == 0 ? sOOCS : "(" + sOOCS + ")");
                                        if (msg1.IndexOf(sData2) < 0)
                                        {
                                            msg1 += (msg1 == "" ? "" : ",") + sData2;
                                            msg3 += (msg3 == "" ? "" : ",") + sData1;
                                        }
                                    }
                                    else light = 4;
                                }
                                else light = 4;
                            }
                        }

                        if (OOS.Length == 2)
                        {
                            if (MTDBbase.ToDecimal(WEB) >= MTDBbase.ToDecimal(OOS[1]) && sOOS != "-")
                            {
                                if (bWater == true)
                                {
                                    cnt = 0;
                                    sOOCS = "";
                                    sData2 = "";
                                    sData1 = "|" + sItem + "|：最新讀值＞＝SPEC-OOS";

                                    if (first != 1)
                                    {
                                        if (msg0.IndexOf(sData1) < 0) first = 1;
                                        else
                                        {
                                            for (cnt = 0; cnt < ArrOOCS.Length; cnt++)
                                            {
                                                sOOCS = (cnt == 0 ? "；" : "(" + ArrOOCS[cnt] + ")；");
                                                if (msg0.IndexOf(sData1 + sOOCS) > -1)
                                                {
                                                    cnt = cnt + 1;
                                                    break;
                                                }
                                            }
                                        }
                                    }

                                    if (cnt != 3)
                                    {
                                        sOOCS = ArrOOCS[cnt];
                                        if (Broken == "0") //沒斷訊
                                        {
                                            sData = "水OOS" + sOOCS + "-" + sPlant;
                                            if (sRed.IndexOf(sData) < 0)
                                                sRed += (sRed == "" ? "" : ",") + sData;
                                        }
                                        light = 1;
                                        msg += sItem + "：最新讀值(" + MTDBbase.ToDecimal(WEB) +
                                            ")＞＝SPEC-OOS(" + MTDBbase.ToDecimal(OOS[1]) + ")；";
                                        sData2 = sData1 + (cnt == 0 ? sOOCS : "(" + sOOCS + ")");
                                        if (msg1.IndexOf(sData2) < 0)
                                        {
                                            msg1 += (msg1 == "" ? "" : ",") + sData2;
                                            msg3 += (msg3 == "" ? "" : ",") + sData1;
                                        }
                                    }
                                    else light = 1;
                                }
                                else light = 1;
                            }
                        }
                    }
                }
            }

            if (msg1 != "") msg1 += "；";
            if (msg3 != "") msg3 += "；";

            row["msg"] = msg;
            row["sdate"] = sDate;
            row["msg1"] = msg1;
            row["msg2"] = msg3;

            if (first == 1 && sRed != "") row["status"] = "首發";

            UpdateData(sPlant, oItem, light);

            if (first != 1) //異常再發需間隔四小時才送報表及簡訊
            {
                dt1 = Convert.ToDateTime(dt0);
                ts =dt2 - dt1;
                if (ts.Hours < 4)
                {
                    if (sRed.IndexOf("OOC") < 0 && sRed.IndexOf("OOS") < 0) sRed = "";
                    else
                    {
                        if (ts.Hours != 0 || ts.Minutes != 15) sRed = "";
                    }
                }
            }

            return sRed;
        }

        public string[] GetData(DataRow row)
        {
            //紅燈條件：最新讀值>=OOS
            //橘燈條件：OOC<=最新讀值<OOS 或 SCADA與CWMS之管制值<>SPEC
            //黃燈條件：Alert<最新讀值<OOC
            //綠燈條件：正常狀態
            string[] ArrColor = { "White", "White", "White", "White", "White", "G" };

            if ((row["item"].ToString().IndexOf("pH") < 0 && row["item"].ToString() != "溫度") ||
                (row["item"].ToString() == "溫度" && row["plantno"].ToString() != "K21"))
            {
                string sOOS = row["OOS_v"].ToString();
                string sOOC = row["OOC_v"].ToString();
                string sAlert = row["Alert_v"].ToString();
                string sRecv = row["Recv_v"].ToString();
                string sOOS_HH = row["OOS_HH_v"].ToString();
                string sOOC_H = row["OOC_H_v"].ToString();
                string sAlert1 = row["Alert1"].ToString();
                string sOOS_HH1 = row["OOS_HH1"].ToString();
                string sOOC_H1 = row["OOC_H1"].ToString();
                string sWEB = row["rvalue"].ToString();

                if ((sOOS_HH == "-" || sOOS_HH == "N/A" || sOOS_HH == "建置中" || sOOS_HH == "異常") &&
                    (sOOC_H == "-" || sOOC_H == "N/A" || sOOC_H == "建置中" || sOOC_H == "異常") &&
                    (sAlert1 == "-" || sAlert1 == "N/A" || sAlert1 == "建置中" || sAlert1 == "異常") && sWEB != "")
                {
                    if (sAlert != "" && sAlert != "-" && sAlert != "N/A" && MTDBbase.ToDecimal(sWEB) > MTDBbase.ToDecimal(sAlert) &&
                        MTDBbase.ToDecimal(sWEB) < MTDBbase.ToDecimal(sOOC) && sOOC != "-" && sOOC != "N/A")
                    {
                        ArrColor[5] = "Y";
                    }

                    if (sRecv != "" && sRecv != "-" && sRecv != "N/A" && MTDBbase.ToDecimal(sWEB) > MTDBbase.ToDecimal(sRecv))
                    {
                        ArrColor[5] = "Y";
                    }

                    //CWMS OOS_HH
                    if (MTDBbase.ToDecimal(sOOS_HH1) != MTDBbase.ToDecimal(sOOS) && sOOS_HH1 != "" && sOOS_HH1 != "-" &&
                        sOOS_HH1 != "N/A" && sOOS_HH1 != "建置中" && sOOS_HH1 != "異常")
                    {
                        if (sOOS_HH1 != "斷訊" && sOOS_HH1 != "保養中") ArrColor[3] = "LightPink";
                        if (sOOS_HH1 != "保養中") ArrColor[5] = "O";
                    }

                    //CWMS OOC_H
                    if (MTDBbase.ToDecimal(sOOC_H1) != MTDBbase.ToDecimal(sOOC) && sOOC_H1 != "" && sOOC_H1 != "-" &&
                        sOOC_H1 != "N/A" && sOOC_H1 != "建置中" && sOOC_H1 != "異常")
                    {
                        if (sOOC_H1 != "斷訊" && sOOC_H1 != "保養中") ArrColor[4] = "LightPink";
                        if (sOOC_H1 != "保養中") ArrColor[5] = "O";
                    }

                    if (MTDBbase.ToDecimal(sWEB) >= MTDBbase.ToDecimal(sOOC) && sOOC != "" && sOOC != "-" && sOOC != "N/A" &&
                        MTDBbase.ToDecimal(sWEB) < MTDBbase.ToDecimal(sOOS) && sOOS != "" && sOOS != "-" && sOOS != "N/A")
                    {
                        ArrColor[5] = "O";
                    }

                    if (MTDBbase.ToDecimal(sWEB) >= MTDBbase.ToDecimal(sOOS) && sOOS != "" && sOOS != "-" && sOOS != "N/A")
                    {
                        ArrColor[5] = "R";
                    }
                }
                else
                {
                    if (sAlert != "" && sAlert != "-" && sAlert != "N/A" && MTDBbase.ToDecimal(sWEB) > MTDBbase.ToDecimal(sAlert) &&
                        MTDBbase.ToDecimal(sWEB) < MTDBbase.ToDecimal(sOOC) && sOOC != "-" && sOOC != "N/A")
                    {
                        ArrColor[5] = "Y";
                    }

                    if (sRecv != "" && sRecv != "-" && sRecv != "N/A" && MTDBbase.ToDecimal(sWEB) > MTDBbase.ToDecimal(sRecv))
                    {
                        ArrColor[5] = "Y";
                    }

                    if (MTDBbase.ToDecimal(sAlert1) != MTDBbase.ToDecimal(sAlert) && sAlert1 != "" && sAlert1 != "-" &&
                        sAlert1 != "N/A" && sAlert1 != "建置中" && sAlert1 != "異常")
                    {
                        if (sAlert1 != "斷訊" && sAlert1 != "保養中") ArrColor[2] = "LightPink";
                        if (sAlert1 != "保養中") ArrColor[5] = "O";
                    }

                    //SCADA OOS_HH
                    if (MTDBbase.ToDecimal(sOOS_HH) != MTDBbase.ToDecimal(sOOS) && sOOS_HH != "" && sOOS_HH != "-" &&
                        sOOS_HH != "N/A" && sOOS_HH != "建置中" && sOOS_HH != "異常")
                    {
                        if (row["item"].ToString().IndexOf("VOC") > -1 && MTDBbase.ToDecimal(sOOS_HH) < MTDBbase.ToDecimal(sOOS))
                        {

                        }
                        else
                        {
                            if (sOOS_HH != "斷訊" && sOOS_HH != "保養中") ArrColor[0] = "LightPink";
                            if (sOOS_HH != "保養中") ArrColor[5] = "O";
                        }
                    }

                    //SCADA OOC_H
                    if (MTDBbase.ToDecimal(sOOC_H) != MTDBbase.ToDecimal(sOOC) && sOOC_H != "" && sOOC_H != "-" &&
                        sOOC_H != "N/A" && sOOC_H != "建置中" && sOOC_H != "異常")
                    {
                        if (row["item"].ToString().IndexOf("VOC") > -1 && MTDBbase.ToDecimal(sOOC_H) < MTDBbase.ToDecimal(sOOC))
                        {

                        }
                        else
                        {
                            if (sOOC_H != "斷訊" && sOOC_H != "保養中") ArrColor[1] = "LightPink";
                            if (sOOC_H != "保養中") ArrColor[5] = "O";
                        }
                    }

                    //CWMS OOS_HH
                    if (MTDBbase.ToDecimal(sOOS_HH1) != MTDBbase.ToDecimal(sOOS) && sOOS_HH1 != "" && sOOS_HH1 != "-" &&
                        sOOS_HH1 != "N/A" && sOOS_HH1 != "建置中" && sOOS_HH1 != "異常")
                    {
                        if (sOOS_HH1 != "斷訊" && sOOS_HH1 != "保養中") ArrColor[3] = "LightPink";
                        if (sOOS_HH1 != "保養中") ArrColor[5] = "O";
                    }

                    //CWMS OOC_H
                    if (MTDBbase.ToDecimal(sOOC_H1) != MTDBbase.ToDecimal(sOOC) && sOOC_H1 != "" && sOOC_H1 != "-" &&
                        sOOC_H1 != "N/A" && sOOC_H1 != "建置中" && sOOC_H1 != "異常")
                    {
                        if (sOOC_H1 != "斷訊" && sOOC_H1 != "保養中") ArrColor[4] = "LightPink";
                        if (sOOC_H1 != "保養中") ArrColor[5] = "O";
                    }

                    if (sWEB == "")
                    {
                        if (sOOS_HH == "" && sOOC_H == "" && sAlert1 == "")
                        {
                            ArrColor[0] = "LightPink";
                            ArrColor[1] = "LightPink";
                            ArrColor[2] = "LightPink";
                            ArrColor[5] = "R";
                        }
                    }
                    else
                    {
                        if (MTDBbase.ToDecimal(sWEB) >= MTDBbase.ToDecimal(sOOC) && sOOC != "" && sOOC != "-" && sOOC != "N/A" &&
                            MTDBbase.ToDecimal(sWEB) < MTDBbase.ToDecimal(sOOS) && sOOS != "" && sOOS != "-" && sOOS != "N/A")
                        {
                            ArrColor[5] = "O";
                        }

                        if (MTDBbase.ToDecimal(sWEB) >= MTDBbase.ToDecimal(sOOS) && sOOS != "" && sOOS != "-" && sOOS != "N/A")
                        {
                            ArrColor[5] = "R";
                        }
                    }
                }
            }
            else
            {
                string sOOS = row["OOS_v"].ToString();
                string sOOC = row["OOC_v"].ToString();
                string sAlert = row["Alert_v"].ToString();
                string sRecv = row["Recv_v"].ToString();
                string sOOS_HH = row["OOS_HH_v"].ToString();
                string sOOC_H = row["OOC_H_v"].ToString();
                string sAlert1 = row["Alert1"].ToString();
                string sOOS_HH1 = row["OOS_HH1"].ToString();
                string sOOC_H1 = row["OOC_H1"].ToString();
                string[] OOS = sOOS.Split('-');
                string[] OOC = sOOC.Split('-');
                string[] Alert = sAlert.Split('-');
                string[] Recv = sRecv.Split('-');
                string[] OOS_HH = sOOS_HH.Split('-');
                string[] OOC_H = sOOC_H.Split('-');
                string[] Alert1 = sAlert1.Split('-');
                string[] OOS_HH1 = sOOS_HH1.Split('-');
                string[] OOC_H1 = sOOC_H1.Split('-');
                string WEB = row["rvalue"].ToString();

                if ((sOOS_HH == "-" || sOOS_HH == "N/A" || sOOS_HH == "建置中" || sOOS_HH == "異常") &&
                    (sOOC_H == "-" || sOOC_H == "N/A" || sOOC_H == "建置中" || sOOC_H == "異常") &&
                    (sAlert1 == "-" || sAlert1 == "N/A" || sAlert1 == "建置中" || sAlert1 == "異常") && WEB != "")
                {
                    if (sAlert != "-" && Alert.Length == 2 && OOC.Length == 2)
                    {
                        if (MTDBbase.ToDecimal(WEB) > MTDBbase.ToDecimal(Alert[1]) &&
                            MTDBbase.ToDecimal(WEB) < MTDBbase.ToDecimal(OOC[1]))
                        {
                            ArrColor[5] = "Y";
                        }
                    }

                    if (sRecv != "-" && Recv.Length == 2)
                    {
                        if (MTDBbase.ToDecimal(WEB) > MTDBbase.ToDecimal(Recv[1]))
                        {
                            ArrColor[5] = "Y";
                        }
                    }

                    //CWMS OOS_HH
                    if (CheckData(OOS_HH1) != CheckData(OOS) && sOOS_HH1 != "" && sOOS_HH1 != "-" &&
                        sOOS_HH1 != "N/A" && sOOS_HH1 != "建置中" && sOOS_HH1 != "異常")
                    {
                        if (sOOS_HH1 != "斷訊" && sOOS_HH1 != "保養中") ArrColor[3] = "LightPink";
                        if (sOOS_HH1 != "保養中") ArrColor[5] = "O";
                    }

                    //CWMS OOC_H
                    if (CheckData(OOC_H1) != CheckData(OOC) && sOOC_H1 != "" && sOOC_H1 != "-" &&
                        sOOC_H1 != "N/A" && sOOC_H1 != "建置中" && sOOC_H1 != "異常")
                    {
                        if (sOOC_H1 != "斷訊" && sOOC_H1 != "保養中") ArrColor[4] = "LightPink";
                        if (sOOC_H1 != "保養中") ArrColor[5] = "O";
                    }

                    if (OOC.Length == 2 && OOS.Length == 2)
                    {
                        if (MTDBbase.ToDecimal(WEB) >= MTDBbase.ToDecimal(OOC[1]) && sOOC != "-" &&
                            MTDBbase.ToDecimal(WEB) < MTDBbase.ToDecimal(OOS[1]) && sOOS != "-")
                        {
                            ArrColor[5] = "O";
                        }
                    }

                    if (OOS.Length == 2)
                    {
                        if (MTDBbase.ToDecimal(WEB) >= MTDBbase.ToDecimal(OOS[1]) && sOOS != "-")
                        {
                            ArrColor[5] = "R";
                        }
                    }
                }
                else
                {
                    if (CheckData(Alert1) != CheckData(Alert) && sAlert1 != "" && sAlert1 != "-" &&
                        sAlert1 != "N/A" && sAlert1 != "建置中" && sAlert1 != "異常")
                    {
                        if (sAlert1 != "斷訊" && sAlert1 != "保養中") ArrColor[2] = "LightPink";
                        if (sAlert1 != "保養中") ArrColor[5] = "O";
                    }

                    //SCADA OOS_HH
                    if (CheckData(OOS_HH) != CheckData(OOS) && sOOS_HH != "" && sOOS_HH != "-" &&
                        sOOS_HH != "N/A" && sOOS_HH != "建置中" && sOOS_HH != "異常")
                    {
                        if (sOOS_HH != "斷訊" && sOOS_HH != "保養中") ArrColor[0] = "LightPink";
                        if (sOOS_HH != "保養中") ArrColor[5] = "O";
                    }

                    //SCADA OOC_H
                    if (CheckData(OOC_H) != CheckData(OOC) && sOOC_H != "" && sOOC_H != "-" &&
                        sOOC_H != "N/A" && sOOC_H != "建置中" && sOOC_H != "異常")
                    {
                        if (sOOC_H != "斷訊" && sOOC_H != "保養中") ArrColor[1] = "LightPink";
                        if (sOOC_H != "保養中") ArrColor[5] = "O";
                    }

                    //CWMS OOS_HH
                    if (CheckData(OOS_HH1) != CheckData(OOS) && sOOS_HH1 != "" && sOOS_HH1 != "-" &&
                        sOOS_HH1 != "N/A" && sOOS_HH1 != "建置中" && sOOS_HH1 != "異常")
                    {
                        if (sOOS_HH1 != "斷訊" && sOOS_HH1 != "保養中") ArrColor[3] = "LightPink";
                        if (sOOS_HH1 != "保養中") ArrColor[5] = "O";
                    }

                    //CWMS OOC_H
                    if (CheckData(OOC_H1) != CheckData(OOC) && sOOC_H1 != "" && sOOC_H1 != "-" &&
                        sOOC_H1 != "N/A" && sOOC_H1 != "建置中" && sOOC_H1 != "異常")
                    {
                        if (sOOC_H1 != "斷訊" && sOOC_H1 != "保養中") ArrColor[4] = "LightPink";
                        if (sOOC_H1 != "保養中") ArrColor[5] = "O";
                    }

                    if (WEB == "")
                    {
                        if (sOOS_HH == "" && sOOC_H == "" && sAlert1 == "")
                        {
                            ArrColor[0] = "LightPink";
                            ArrColor[1] = "LightPink";
                            ArrColor[2] = "LightPink";
                            ArrColor[5] = "R";
                        }
                    }
                    else
                    {
                        if (sAlert != "-" && Alert.Length == 2 && OOC.Length == 2)
                        {
                            if (MTDBbase.ToDecimal(WEB) > MTDBbase.ToDecimal(Alert[1]) &&
                                MTDBbase.ToDecimal(WEB) < MTDBbase.ToDecimal(OOC[1]))
                            {
                                ArrColor[5] = "Y";
                            }
                        }

                        if (sRecv != "-" && Recv.Length == 2)
                        {
                            if (MTDBbase.ToDecimal(WEB) > MTDBbase.ToDecimal(Recv[1]))
                            {
                                ArrColor[5] = "Y";
                            }
                        }

                        if (OOC.Length == 2 && OOS.Length == 2)
                        {
                            if (MTDBbase.ToDecimal(WEB) >= MTDBbase.ToDecimal(OOC[1]) && sOOC != "-" &&
                                MTDBbase.ToDecimal(WEB) < MTDBbase.ToDecimal(OOS[1]) && sOOS != "-")
                            {
                                ArrColor[5] = "O";
                            }
                        }

                        if (OOS.Length == 2)
                        {
                            if (MTDBbase.ToDecimal(WEB) >= MTDBbase.ToDecimal(OOS[1]) && sOOS != "-")
                            {
                                ArrColor[5] = "R";
                            }
                        }
                    }
                }
            }

            return ArrColor;
        }

        public DataTable GetData陸放(string ctime)
        {
            SqlParameterClear();
            SqlCommandText = "Select F.Source plantno " +
                "From [VOC].[dbo].[VOC_Flow_Sta] F " +
                "Join [VOC].[dbo].[VOC_plant] P On F.Source=P.plantno " +
                "Where F.Dest in ('陸放','納管','放流閘門關閉') And F.States!='0' And F.cdatetime=@ctime";
            SqlParameterAdd("@ctime", ctime);
            return SqlFillDT();
        }

        public DataTable GetData雨水溝預警(string ctime)
        {
            DateTime dt = Convert.ToDateTime(ctime);
            string ctime1 = dt.AddMinutes(-15).ToString("yyyy/MM/dd HH:mm:ss");
            string ctime2 = dt.AddMinutes(-30).ToString("yyyy/MM/dd HH:mm:ss");

            SqlParameterClear();
            SqlCommandText = "Select W.plantno,W.item,broken,Convert(nvarchar,TwentyFourHours) Sum24H,rvalue," +
                "space(1000) msg,space(50) sdate,space(1000) msg1,space(4) status,space(1000) msg2," +
                "null datetime1,null value1,null datetime2,null value2,null datetime3,null value3,plantid,itemid " +
                "From [VOC].[dbo].[VOC_SCADA_WEB] W " +
                "Join [VOC].[dbo].[VOC_plant] P On W.plantno=P.plantno " +
                "Join [VOC].[dbo].[VOC_item] I On W.item=I.item " +
                "Left Join [PMS].[dbo].[Water_WindRainHistValue] On UpdateTime=@ctime " +
                "Where W.plantno Not in ('K1','K9') And W.item like '%雨水溝%' " +
                "Union Select W.plantno,W.item,broken,Convert(nvarchar,TwentyFourHours) Sum24H," +
                "Iif(rvalue in ('斷訊','異常','保養中'),rvalue,Iif(value2 is null Or value3 is null,'0'," +
                "Iif(value2 is not null And value2 not in ('斷訊','異常','保養中') And value3 is not null And value3 not in ('斷訊','異常','保養中') " +
                "And Convert(float,W.rvalue)>Convert(float,value2) And Convert(float,value2)>Convert(float,value3),'1','0'))) rvalue," +
                "space(1000) msg,space(50) sdate,space(1000) msg1,space(4) status,space(1000) msg2," +
                "@ctime datetime1,rvalue value1,@ctime1 datetime2,value2,@ctime2 datetime3,value3,plantid,itemid " +
                "From [VOC].[dbo].[VOC_SCADA_WEB] W " +
                "Join [VOC].[dbo].[VOC_plant] P On W.plantno=P.plantno " +
                "Join [VOC].[dbo].[VOC_item] I On W.item=I.item " +
                "Left Join [PMS].[dbo].[Water_WindRainHistValue] On UpdateTime=@ctime " +
                "Left Join (Select plantno,item,rvalue value2 From [VOC].[dbo].[VOC_SCADA_HIST] Where plantno in ('K1','K9') And item like '%雨水溝%' And cdatetime=@ctime1) W1 On W.plantno=W1.plantno And W.item=W1.item " +
                "Left Join (Select plantno,item,rvalue value3 From [VOC].[dbo].[VOC_SCADA_HIST] Where plantno in ('K1','K9') And item like '%雨水溝%' And cdatetime=@ctime2) W2 On W.plantno=W2.plantno And W.item=W2.item " +
                "Where W.plantno in ('K1','K9') And W.item like '%雨水溝%' " +
                "Order By plantid,itemid";
            SqlParameterAdd("@ctime", ctime);
            SqlParameterAdd("@ctime1", ctime1);
            SqlParameterAdd("@ctime2", ctime2);
            return SqlFillDT();
        }

        public int GetData中水(string ctime)
        {
            SqlParameterClear();
            SqlCommandText = "Select Count(*) " +
                "From [VOC].[dbo].[VOC_SCADA_WEB] W " +
                "Join [VOC].[dbo].[VOC_MAIL_Log] L On W.plantno=L.plantno " +
                "Where W.plantno='K14B' And item in ('COD2','Cu','Ni','pH1','SS','預警COD','預警pH') " +
                "And msg2 Like '%|'+replace(replace(item,'COD2','COD'),'pH1','pH')+'|%' " +
                "And (msg2 Like '%最新讀值＞＝SPEC-OOS%' Or msg2 Like '%SPEC-OOC＜＝最新讀值＜SPEC-OOS%') And L.cdatetime > @ctime";
            SqlParameterAdd("@ctime", ctime);
            return SqlExecuteScalarInt32(0);
        }

        public int GetData中水放流量(string ctime)
        {
            SqlParameterClear();
            SqlCommandText = "Select Count(*) " +
                "From [VOC].[dbo].[VOC_SCADA_Tag] " +
                "Where plantno='K14B' And item in ('流量1','流量2') " +
                "And Convert(float, CurrentValue) > 0 And cdatetime = @ctime";
            SqlParameterAdd("@ctime", ctime);
            return SqlExecuteScalarInt32(0);
        }

        public string GetDataRed雨水溝預警(DataRow row, DateTime dt2)
        {
            //紅燈條件：最新讀值=1 且 24H累積雨量=0
            //橘燈條件：斷訊 或 異常
            //綠燈條件：正常狀態
            string sRed = "", sData, msg = "", msg1 = "", sDate = "";
            int light = 3;  //燈號: 1=紅燈, 3=綠燈, 4=橘燈
            string sPlant = row["plantno"].ToString();
            string sItem = row["item"].ToString();
            DataTable dtb;
            DateTime dt1;
            TimeSpan ts;
            int first = 0;  //1=首發, 0=再發
            string dt0 = "", msg0 = "", sData1, msg3 = "", rvalue, Sum24H;

            if (row["broken"].ToString() == "2")  //保養中
                sDate = Get隔離廠區項目區間(sPlant, sItem);

            dtb = Get前筆派報資料(sPlant, sItem);
            if (dtb.Rows.Count == 0)
                first = 1;
            else
            {
                dt1 = Convert.ToDateTime(dtb.Rows[0]["cdatetime"].ToString());
                ts = dt2 - dt1;
                if (ts.Days >= 1 || ts.Hours > 4 || (ts.Hours == 4 && ts.Minutes > 0))
                    first = 1;
                else
                {
                    dt0 = dtb.Rows[0]["cdatetime"].ToString();
                    msg0 = dtb.Rows[0]["msg1"].ToString();
                }
            }

            rvalue = row["rvalue"].ToString();
            Sum24H = row["Sum24H"].ToString();

            if (rvalue == "1" && Sum24H == "0.0")
            {
                light = 1;
                sData1 = "|" + sItem + "|：最新讀值＝1 且 24H累積雨量＝0";

                if (first != 1)
                {
                    if (msg0.IndexOf(sData1) < 0) first = 1;
                }

                sData = "雨水溝Alert" + "-" + sPlant;
                if (sRed.IndexOf(sData) < 0)
                    sRed += (sRed == "" ? "" : ",") + sData;
                msg += sItem + "：最新讀值＝1 且 24H累積雨量＝0；";
                if (msg1.IndexOf(sData1) < 0)
                {
                    msg1 += (msg1 == "" ? "" : ",") + sData1;
                    msg3 += (msg3 == "" ? "" : ",") + sData1;
                }
            }
            else if (rvalue == "斷訊" || rvalue == "異常" || rvalue == "保養中")
            {
                if (rvalue == "斷訊" || rvalue == "異常") light = 4;
                sData1 = "|" + sItem + "|：最新讀值(" + rvalue + ")";

                if (first != 1)
                {
                    if (msg0.IndexOf(sData1) < 0) first = 1;
                }

                sData = "雨水溝" + rvalue.Replace("異常","斷訊") + "-" + sPlant;
                if (sRed.IndexOf(sData) < 0)
                    sRed += (sRed == "" ? "" : ",") + sData;

                msg += sItem + "：最新讀值(" + rvalue + ")；";
                if (msg1.IndexOf(sData1) < 0)
                {
                    msg1 += (msg1 == "" ? "" : ",") + sData1;
                    if (rvalue == "斷訊" || rvalue == "異常") msg3 += (msg3 == "" ? "" : ",") + sData1;
                }
            }
            else if (rvalue == "1" && Sum24H == "異常")
            {
                light = 4;
                sData1 = "|" + sItem + "|：最新讀值＝1 且 24H累積雨量(異常)";

                if (first != 1)
                {
                    if (msg0.IndexOf(sData1) < 0) first = 1;
                }

                sData = "雨水溝斷訊" + "-" + sPlant;
                if (sRed.IndexOf(sData) < 0)
                    sRed += (sRed == "" ? "" : ",") + sData;

                msg += sItem + "：最新讀值＝1 且 24H累積雨量(異常)；";
                if (msg1.IndexOf(sData1) < 0)
                {
                    msg1 += (msg1 == "" ? "" : ",") + sData1;
                    msg3 += (msg3 == "" ? "" : ",") + sData1;
                }
            }

            if (msg1 != "") msg1 += "；";
            if (msg3 != "") msg3 += "；";

            row["msg"] = msg;
            row["sdate"] = sDate;
            row["msg1"] = msg1;
            row["msg2"] = msg3;

            if (first == 1 && sRed != "") row["status"] = "首發";

            UpdateData(sPlant, sItem, light);

            if (first != 1) //異常再發需間隔四小時才送報表及簡訊
            {
                dt1 = Convert.ToDateTime(dt0);
                ts = dt2 - dt1;
                if (ts.Hours < 4) sRed = "";
            }

            return sRed;
        }

        public string GetData雨水溝預警(DataRow row)
        {
            //紅燈條件：最新讀值=1 且 24H累積雨量=0
            //橘燈條件：斷訊 或 異常
            //綠燈條件：正常狀態

            string ArrColor = "G";

            if (row["rvalue"].ToString() == "1" && row["Sum24H"].ToString() == "0.0") ArrColor = "R";

            return ArrColor;
        }

        public string GetMsg(DataTable dtb, string plantno, int r)
        {
            string dt;
            string msg = "";
            for (int i = r; i < dtb.Rows.Count; i++)
            {
                if (dtb.Rows[i]["plantno"].ToString() != plantno) break;
                dt = dtb.Rows[i]["sdate"].ToString();
                msg += dtb.Rows[i]["msg"].ToString() + (dt == "" ? "" : dt + "；");
            }
            return msg;
        }

        public string GetMsg1(DataTable dtb, string plantno, int r, string field)
        {
            string msg = "";
            for (int i = r; i < dtb.Rows.Count; i++)
            {
                if (dtb.Rows[i]["plantno"].ToString() != plantno) break;
                msg += dtb.Rows[i][field].ToString();
            }
            return msg;
        }

        public string GetMsg2(DataTable dtb, string plantno, int r)
        {
            string msg = "";
            string msg1 = "";
            string msg2 = "";
            for (int i = r; i < dtb.Rows.Count; i++)
            {
                if (dtb.Rows[i]["plantno"].ToString() != plantno) break;
                string[] ArrErr = dtb.Rows[i]["msg"].ToString().Replace("；", ";").Split(';');
                for (int j = 0; j < ArrErr.Length - 1; j++)
                {
                    if (ArrErr[j].IndexOf("SCADA(斷訊)") > 0)
                    {
                        string[] ArrItem = ArrErr[j].Replace("：", ":").Split(':');
                        msg1 += (msg1 == "" ? "SCADA(斷訊)：" : "、") + ArrItem[0];
                    }
                    else if (ArrErr[j].IndexOf("(保養中)") < 0)
                        msg2 += (msg2 == "" ? "" : "；") + ArrErr[j];
                }
            }
            msg = (msg1 == "" ? "" : msg1 + (msg2 == "" ? "。" : "；")) + (msg2 == "" ? "" : msg2 + "。");
            return msg;
        }

        public DataTable GetMailList(string DataRed, string plantno, string MailType)
        {
            int idx = -1;
            string wheres = "";
            string[] ArrRed = DataRed.Replace("|", "").Split(',');
            for (int i = 0; i < ArrRed.Length; i++)
            {
                string[] ArrData = ArrRed[i].Split('-');
                if (MailType == "TO")
                {
                    if (plantno == ArrData[1])
                        wheres += (wheres == "" ? "" : " Or ") + "(RptType='" + ArrData[0] + "' And plantno='" + ArrData[1] + "')";
                }
                else
                {
                    if (plantno == ArrData[1])
                    {
                        idx = wheres.IndexOf(ArrData[0]);
                        if (idx < 0)
                            wheres += (wheres == "" ? "" : ",") + "'" + ArrData[0] + "'";
                    }
                }
            }

            SqlParameterClear();
            SqlCommandText = "Select Distinct NotesID " +
                "From [VOC].[dbo].[VOC_Mail_List] " +
                "Where MailType=@MailType And NotesID !='' And Mail=1 ";
            SqlParameterAdd("@MailType", MailType);

            if (MailType == "TO")
                SqlCommandText += "And (" + wheres + ")";
            else
                SqlCommandText += "And RptType in (" + wheres + ") And plantno in ('" + plantno + "','GMO','環工部')";

            return SqlFillDT();
        }

        public DataTable GetCellPhoneList(string DataRed, string plantno, string MailType)
        {
            int idx = -1;
            string wheres = "";
            string[] ArrRed = DataRed.Replace("|", "").Split(',');
            for (int i = 0; i < ArrRed.Length; i++)
            {
                string[] ArrData = ArrRed[i].Split('-');
                if (MailType == "TO")
                {
                    if (plantno == ArrData[1])
                        wheres += (wheres == "" ? "" : " Or ") + "(RptType='" + ArrData[0] + "' And plantno='" + ArrData[1] + "')";
                }
                else
                {
                    if (plantno == ArrData[1])
                    {
                        idx = wheres.IndexOf(ArrData[0]);
                        if (idx < 0)
                            wheres += (wheres == "" ? "" : ",") + "'" + ArrData[0] + "'";
                    }
                }
            }

            SqlParameterClear();
            SqlCommandText = "Select Distinct plantno,empno,empname,CellPhone " +
                "From [VOC].[dbo].[VOC_Mail_List] " +
                "Where MailType=@MailType And CellPhone != '' And SM=1 ";
            SqlParameterAdd("@MailType", MailType);

            if (MailType == "TO")
                SqlCommandText += "And (" + wheres + ")";
            else
                SqlCommandText += "And RptType in (" + wheres + ") And plantno in ('" + plantno + "','GMO','環工部')";

            return SqlFillDT();
        }

        public void InsertMAIL(string plantno, string msg, string msg1, DateTime dt, string msg2)
        {
            SqlParameterClear();
            SqlCommandText = "INSERT INTO [VOC].[dbo].[VOC_MAIL_Log] ";

            if (msg2 == "")
                SqlCommandText += "([plantno],[cdatetime],[msg],[msg1]) VALUES (@plantno,@cdatetime,@msg,@msg1)";
            else
                SqlCommandText += "([plantno],[cdatetime],[msg],[msg1],[msg2]) VALUES (@plantno,@cdatetime,@msg,@msg1,@msg2)";

            SqlParameterAdd("@plantno", plantno);
            SqlParameterAdd("@cdatetime", dt);
            SqlParameterAdd("@msg", msg);
            SqlParameterAdd("@msg1", msg1);
            SqlParameterAdd("@msg2", msg2);
            SqlExecuteNonQuery();
        }

        public void InsertSMS(DataRow hrow, string msg, int status)
        {
            SqlParameterClear();
            SqlCommandText = "INSERT INTO [VOC].[dbo].[VOC_SMS_Log] " +
                "([plantno],[empno],[empname],[CellPhone],[cdatetime],[msg],[status]) " +
                "VALUES (@plantno,@empno,@empname,@CellPhone,@cdatetime,@msg,@status);";
            SqlParameterAdd("@plantno", hrow["plantno"]);
            SqlParameterAdd("@empno", hrow["empno"]);
            SqlParameterAdd("@empname", hrow["empname"]);
            SqlParameterAdd("@CellPhone", hrow["CellPhone"]);
            SqlParameterAdd("@cdatetime", DateTime.Now);
            SqlParameterAdd("@msg", msg);
            SqlParameterAdd("@status", status);
            SqlExecuteNonQuery();
        }

        // ── 以下為 JOB 讀值寫入相關方法（IH/Kepware/CWMS 資料拋轉），
        //    與異常 Email 派報無直接關係，供未來 JOB 遷移（iFIX→Kepware）參考：
        //    GetCWMSValue, ListSCADATags*, UpdateVOCData*, InsertVOCHistValue,
        //    InsertFlowData, JobLog, Insert昨日法遵各項目平均讀值,
        //    Insert昨日法遵水污染平均排放量, Insert中水歷史讀值,
        //    Insert法遵VOC歷史讀值A5, ListVOC廠區項目, UpdateVOCData年排放量,
        //    UpdateVOCData回收水 等。完整程式碼保留在使用者提供的原始檔案中，
        //    如需查閱請參考對話記錄或原始檔案。
    }
}
