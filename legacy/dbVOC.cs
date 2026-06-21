using MTLibrary;
using System;
using System.Collections;
using System.Collections.Generic;
using System.Collections.Specialized;
using System.Data;
//using System.Linq;
using System.Net.Mail;
using System.Text;
using System.Web;
using System.Web.UI;
using System.Web.UI.WebControls;

/// <summary>
/// dbVOC 的摘要描述
/// </summary>
public class dbVOC : MTDBbase<dbVOC>
{
	public dbVOC()
        : base((int)AppConfig.DataBaseCI.VOC)
    {

    }

    public int Check登入權限()
    {
        SqlParameterClear();
        SqlCommandText = "Select Count(*) From [VOC].[dbo].[VOC_dept] Where deptno=@deptno";
        SqlParameterAdd("@deptno", AppConfig.Sess_UserDept);
        return SqlExecuteScalarInt32(0);
    }

    public string GetPlantID()
    {
        if (AppConfig.Sess_UserDept == "")
        {
            using (dbUTIDB db = new dbUTIDB()) db.GetUserDept();
        }
        SqlParameterClear();
        SqlCommandText = "Select plantid From [VOC].[dbo].[VOC_dept] Where deptno=@deptno";
        SqlParameterAdd("@deptno", AppConfig.Sess_UserDept);
        DataTable PlantDT = SqlFillDT();
        string PlantID = "";
        for (int i = 0; i < PlantDT.Rows.Count; i++)
            PlantID += (i == 0 ? "" : ",") + PlantDT.Rows[i][0].ToString();
        return PlantID;
    }

    public DateTime Get資料更新時間()
    {
        SqlParameterClear();
        SqlCommandText = "Select max(cdatetime) From [VOC].[dbo].[VOC_SCADA_WEB] Where cdatetime<=@stime ";
        SqlParameterAdd("@stime", DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss.000"));
        return Convert.ToDateTime(SqlExecuteScalar());
    }

    public DataTable ListVOC()
    {
        string PlantID = GetPlantID();
        SqlParameterClear();
        SqlCommandText = "Select S.plantno,Replace(Replace(S.item,'COD2','COD'),'pH1','pH') item,S.LAW,S.OOS,S.OOC,S.alert,S.recv,S.seqno," +
            "P.plantid,I.unit,W.OOS_HH,W.OOC_H,W.alert alert1,W.OOS_HH1,W.OOC_H1,Replace(Replace(Replace(Replace(W.rvalue,'N.D',0),'<0.05',0),'<0.02',0),'<0.01',0) rvalue," +
            "C.URL,Iif(C.URL is null,null,'歷史曲線') content,concat(Iif(W.broken=0,null,'斷訊'),Iif(W.rvalue='N.D','N.D',null),Iif(W.rvalue='<0.05','<0.05',null)," +
            "Iif(W.rvalue='<0.02','<0.02',null),Iif(W.rvalue='<0.01','<0.01',null),'|',S.source) remark,E.emptycell " +
            "From [VOC].[dbo].[VOC_SPEC] S " +
            "Join [VOC].[dbo].[VOC_item] I On S.item=I.item " +
            "Join [VOC].[dbo].[VOC_plant] P On S.plantno=P.plantno And isShow=1 " +
            "Left Join [VOC].[dbo].[VOC_SCADA_WEB] W On S.plantno=W.plantno And S.item=W.item " +
            "Left Join [VOC].[dbo].[VOC_Curve] C On S.plantno=C.plantno And S.item=C.item " +
            "Left Join [VOC].[dbo].[VOC_EmptyCell] E On S.plantno=E.plantno And S.item=E.item ";
        if (PlantID.IndexOf("29") < 0)  //plantid: 29=ALL
            SqlCommandText += "Where P.plantid in (" + PlantID + ") ";
        SqlCommandText += "Order By sort,seqno ";
        return SqlFillDT();
    }

    public DataTable ListVOC(int plantid, int itemid)
    {
        SqlParameterClear();
        SqlCommandText = "Select S.plantno,S.item,S.LAW,S.OOS,S.OOC,S.alert,P.plantid,I.itemid,S1.source,T.status " +
            "From [VOC].[dbo].[VOC_SPEC] S " +
            "Join [VOC].[dbo].[VOC_item] I On S.item=I.item " +
            "Join [VOC].[dbo].[VOC_plant] P On S.plantno=P.plantno " +
            "Join [VOC].[dbo].[VOC_source] S1 On S.source=S1.sourceid " +
            "Join [VOC].[dbo].[VOC_status] T On S.status=T.statusid " +
            "Where P.plantid = @plantid And I.itemid = @itemid ";
        SqlParameterAdd("@plantid", plantid);
        SqlParameterAdd("@itemid", itemid);
        return SqlFillDT();
    }

    public DataTable List雨水溝預警()
    {
        DateTime dt = DateTime.Now;
        int m = dt.Minute % 15;
        dt = dt.AddMinutes(-m).AddSeconds(-dt.Second);
        string ctime = dt.ToString("yyyy/MM/dd HH:mm:ss");
        string ctime1 = dt.AddMinutes(-15).ToString("yyyy/MM/dd HH:mm:ss");
        string ctime2 = dt.AddMinutes(-30).ToString("yyyy/MM/dd HH:mm:ss");
        string PlantID = GetPlantID();
        SqlParameterClear();
        SqlCommandText = "Select W.plantno,W.item,Convert(nvarchar,TwentyFourHours) Sum24H,W.rvalue,null remark," +
            "null datetime1,null value1,null datetime2,null value2,null datetime3,null value3,plantid,itemid,sort " +
            "From [VOC].[dbo].[VOC_SCADA_WEB] W " +
            "Join [VOC].[dbo].[VOC_plant] P On W.plantno=P.plantno " +
            "Join [VOC].[dbo].[VOC_item] I On W.item=I.item " +
            "Left Join [PMS].[dbo].[Water_WindRainHistValue] On UpdateTime=@stime " +
            "Where W.plantno not in ('K1','K9') And W.item like '%雨水溝%' ";
        if (PlantID.IndexOf("29") < 0)  //plantid: 29=ALL
            SqlCommandText += "And P.plantid in (" + PlantID + ") ";
        SqlCommandText += "Union Select W.plantno,W.item,Convert(nvarchar,TwentyFourHours) Sum24H," +
            "Iif(rvalue in ('斷訊','異常','保養中'),rvalue,Iif(value2 is null Or value3 is null,'0'," +
            "Iif(value2 is not null And value2 not in ('斷訊','異常','保養中') And value3 is not null And value3 not in ('斷訊','異常','保養中') " +
            "And Convert(float,W.rvalue)>Convert(float,value2) And Convert(float,value2)>Convert(float,value3),'1','0'))) rvalue,null remark," +
            "@stime datetime1,rvalue value1,@stime1 datetime2,value2,@stime2 datetime3,value3,plantid,itemid,sort " +
            "From [VOC].[dbo].[VOC_SCADA_WEB] W " +
            "Join [VOC].[dbo].[VOC_plant] P On W.plantno=P.plantno " +
            "Join [VOC].[dbo].[VOC_item] I On W.item=I.item " +
            "Left Join [PMS].[dbo].[Water_WindRainHistValue] On UpdateTime=@stime " +
            "Left Join (Select plantno,item,rvalue value2 From [VOC].[dbo].[VOC_SCADA_HIST] Where plantno in ('K1','K9') And item like '%雨水溝%' And cdatetime Between @stime1 And @etime1) W1 On W.plantno=W1.plantno And W.item=W1.item " +
            "Left Join (Select plantno,item,rvalue value3 From [VOC].[dbo].[VOC_SCADA_HIST] Where plantno in ('K1','K9') And item like '%雨水溝%' And cdatetime Between @stime2 And @etime2) W2 On W.plantno=W2.plantno And W.item=W2.item " +
            "Where W.plantno in ('K1','K9') And W.item like '%雨水溝%' ";
        if (PlantID.IndexOf("29") < 0)  //plantid: 29=ALL
            SqlCommandText += "And P.plantid in (" + PlantID + ") ";
        SqlCommandText += "Order By sort,itemid";
        SqlParameterAdd("@stime", ctime);
        SqlParameterAdd("@etime", Convert.ToDateTime(ctime).AddMinutes(5).ToString("yyyy/MM/dd HH:mm:ss"));
        SqlParameterAdd("@stime1", ctime1);
        SqlParameterAdd("@etime1", Convert.ToDateTime(ctime1).AddMinutes(5).ToString("yyyy/MM/dd HH:mm:ss"));
        SqlParameterAdd("@stime2", ctime2);
        SqlParameterAdd("@etime2", Convert.ToDateTime(ctime2).AddMinutes(5).ToString("yyyy/MM/dd HH:mm:ss"));
        return SqlFillDT();
    }

    public DataTable List廠區0()
    {
        SqlCommandText = "SELECT DISTINCT P.plantid,P.plantno FROM [VOC].[dbo].[VOC_report] R " +
            "JOIN [VOC].[dbo].[VOC_plant] P On R.plantno=P.plantno ORDER BY plantid";
        return SqlFillDT();
    }

    public DataTable List廠區()
    {
        string PlantID = GetPlantID();

        SqlCommandText = "Select plantid,plantno From [VOC].[dbo].[VOC_plant] ";

        if (PlantID.IndexOf("29") < 0)  //plantid: 29=ALL
            SqlCommandText += "Where plantid in (" + PlantID + ") ";
        else
            SqlCommandText += "Where plantno Not in ('環工部','GMO','ALL') ";

        SqlCommandText += "Order by sort";
        return SqlFillDT();
    }

    public DataTable List廠區1(string sPlantid, string sItemid)
    {
        int plantid = MTDBbase.ToInt32(sPlantid, -1);
        int itemid = MTDBbase.ToInt32(sItemid, -1);

        SqlParameterClear();
        SqlCommandText = "Select Distinct P.plantid,P.plantno " +
            "From [VOC].[dbo].[VOC_SPEC] S " +
            "Join [VOC].[dbo].[VOC_item] I On S.item=I.item " +
            "Join [VOC].[dbo].[VOC_plant] P On S.plantno=P.plantno " +
            "Where 1=1 ";

        if (plantid > 0)
        {
            SqlCommandText += "And P.plantid = @plantid ";
            SqlParameterAdd("@plantid", plantid);
        }

        if (itemid > 0)
        {
            SqlCommandText += "And I.itemid = @itemid ";
            SqlParameterAdd("@itemid", itemid);
        }

        SqlCommandText += "Order by plantid ";
        return SqlFillDT();
    }

    public DataTable List廠區2()
    {
        int cnt = 0;
        string plantno = "";

        using (dbAclRights db = new dbAclRights())
        {
            SqlParameterClear();
            SqlCommandText = "Select Count(*) From [VOC].[dbo].[sys_acluserrole] " +
                "Where (roleid=@roleid Or roleid=@roleid1 Or roleid=@roleid2) And (empno=@empno Or deptno=@deptno) And (plantno='ALL' Or stype='ALL') ";
            SqlParameterAdd("@roleid", (int)dbAclRights.使用者權限.廠區項目隔離抑制維護);
            SqlParameterAdd("@roleid1", (int)dbAclRights.使用者權限.系統管理員);
            SqlParameterAdd("@roleid2", (int)dbAclRights.使用者權限.廠區項目隔離抑制查詢);
            SqlParameterAdd("@empno", AppConfig.Sess_UserEmpNo);
            SqlParameterAdd("@deptno", AppConfig.Sess_UserDept);
            cnt = SqlExecuteScalarInt32(0);

            if (cnt > 0)
            {
                SqlParameterClear();
                SqlCommandText = "Select plantno From [VOC].[dbo].[sys_acluserrole] " +
                    "Where (roleid=@roleid Or roleid=@roleid1 Or roleid=@roleid2) And (empno=@empno Or deptno=@deptno) And (plantno='ALL' Or stype='ALL') ";
                SqlParameterAdd("@roleid", (int)dbAclRights.使用者權限.廠區項目隔離抑制維護);
                SqlParameterAdd("@roleid1", (int)dbAclRights.使用者權限.系統管理員);
                SqlParameterAdd("@roleid2", (int)dbAclRights.使用者權限.廠區項目隔離抑制查詢);
                SqlParameterAdd("@empno", AppConfig.Sess_UserEmpNo);
                SqlParameterAdd("@deptno", AppConfig.Sess_UserDept);
                plantno = SqlExecuteScalarString();
            }
        }

        if (cnt == 0)
        {
            SqlParameterClear();
            SqlCommandText = "Select plantid,plantno From (" +
                "Select Distinct P.plantid,P.plantno,P.sort " +
                "From [VOC].[dbo].[VOC_SPEC] S " +
                "Join [VOC].[dbo].[VOC_item] I On S.item=I.item " +
                "Join [VOC].[dbo].[VOC_plant] P On S.plantno=P.plantno " +
                "Join [VOC].[dbo].[sys_acluserrole] R On S.plantno=R.plantno And I.stype=R.stype " +
                "And (R.empno=@empno Or R.deptno=@deptno) ";
            SqlParameterAdd("@empno", AppConfig.Sess_UserEmpNo);
            SqlParameterAdd("@deptno", AppConfig.Sess_UserDept);
        }
        else
        {
            using (dbAclRights db = new dbAclRights())
            {
                SqlParameterClear();
                SqlCommandText = "Select Count(*) From [VOC].[dbo].[sys_acluserrole] " +
                    "Where (roleid=@roleid Or roleid=@roleid1 Or roleid=@roleid2) And (empno=@empno Or deptno=@deptno) And stype='ALL' ";
                SqlParameterAdd("@roleid", (int)dbAclRights.使用者權限.廠區項目隔離抑制維護);
                SqlParameterAdd("@roleid1", (int)dbAclRights.使用者權限.系統管理員);
                SqlParameterAdd("@roleid2", (int)dbAclRights.使用者權限.廠區項目隔離抑制查詢);
                SqlParameterAdd("@empno", AppConfig.Sess_UserEmpNo);
                SqlParameterAdd("@deptno", AppConfig.Sess_UserDept);
                cnt = SqlExecuteScalarInt32(0);
            }

            SqlParameterClear();
            SqlCommandText = "Select plantid,plantno From (" +
                "Select Distinct P.plantid,P.plantno,P.sort " +
                "From [VOC].[dbo].[VOC_SPEC] S " +
                "Join [VOC].[dbo].[VOC_item] I On S.item=I.item " +
                "Join [VOC].[dbo].[VOC_plant] P On S.plantno=P.plantno " +
                "Join [VOC].[dbo].[VOC_source] S1 On S.source=S1.sourceid ";

            if (cnt == 0)
            {
                SqlCommandText += "Join [VOC].[dbo].[sys_acluserrole] R On I.stype=R.stype " +
                    "And (R.empno=@empno Or R.deptno=@deptno) ";
                SqlParameterAdd("@empno", AppConfig.Sess_UserEmpNo);
                SqlParameterAdd("@deptno", AppConfig.Sess_UserDept);
            }
            else
            {
                if (plantno != "" && plantno != "ALL")
                {
                    SqlCommandText += "Join [VOC].[dbo].[sys_acluserrole] R On P.plantno=R.plantno " +
                        "And (R.empno=@empno Or R.deptno=@deptno) ";
                    SqlParameterAdd("@empno", AppConfig.Sess_UserEmpNo);
                    SqlParameterAdd("@deptno", AppConfig.Sess_UserDept);
                }
            }
        }

        SqlCommandText += "Where S.source<3 And S.status=1) A Order by sort";
        return SqlFillDT();
    }

    public DataTable List廠區3(string sPlantid, string sItemid)
    {
        int plantid = MTDBbase.ToInt32(sPlantid, -1);
        int itemid = MTDBbase.ToInt32(sItemid, -1);

        SqlParameterClear();
        SqlCommandText = "Select Distinct P.plantid,P.plantno " +
            "From [VOC].[dbo].[VOC_SPEC] S " +
            "Join [VOC].[dbo].[VOC_item] I On S.item=I.item " +
            "Join [VOC].[dbo].[VOC_plant] P On S.plantno=P.plantno " +
            "Join [VOC].[dbo].[sys_acluserrole] R On S.plantno=R.plantno And R.empno=@empno " +
            "Where 1=1 ";

        if (plantid > 0)
        {
            SqlCommandText += "And P.plantid = @plantid ";
            SqlParameterAdd("@plantid", plantid);
        }

        if (itemid > 0)
        {
            SqlCommandText += "And I.itemid = @itemid ";
            SqlParameterAdd("@itemid", itemid);
        }

        SqlCommandText += "Order by plantid ";
        SqlParameterAdd("@empno", AppConfig.Sess_UserEmpNo);
        return SqlFillDT();
    }

    public DataTable List廠區4()
    {
        SqlCommandText = "Select plantid,plantno From [VOC].[dbo].[VOC_plant] " +
            "Where plantno != 'ALL' Order by sort ";
        return SqlFillDT();
    }

    public DataTable List廠區5(string sPlantid, string sTypeid)
    {
        int plantid = MTDBbase.ToInt32(sPlantid, -1);
        int typeid = MTDBbase.ToInt32(sTypeid, -1);

        SqlParameterClear();
        SqlCommandText = "Select Distinct P.plantid,P.plantno " +
            "From [VOC].[dbo].[VOC_Mail_List] M " +
            "Join [VOC].[dbo].[VOC_plant] P On M.plantno=P.plantno " +
            "Join [VOC].[dbo].[VOC_Mail_Type] T On M.RptType=T.RptType " +
            "Where 1=1 ";

        if (plantid > 0)
        {
            SqlCommandText += "And P.plantid = @plantid ";
            SqlParameterAdd("@plantid", plantid);
        }

        if (typeid > 0)
        {
            SqlCommandText += "And T.typeid = @typeid ";
            SqlParameterAdd("@typeid", typeid);
        }

        SqlCommandText += "Order by plantid ";
        return SqlFillDT();
    }

    public DataTable List廠區6()
    {
        SqlCommandText = "Select Distinct P.plantid,P.plantno " +
            "From [VOC].[dbo].[VOC_SPEC] S " +
            "Join [VOC].[dbo].[VOC_plant] P On S.plantno=P.plantno " +
            "Where S.source < 3 " +
            "Union Select plantid,plantno " +
            "From [VOC].[dbo].[VOC_plant] " +
            "Where plantno = 'ALL' Order by plantid ";
        return SqlFillDT();
    }

    public DataTable List廠區7(string sPlantid, string sTypeid)
    {
        int plantid = MTDBbase.ToInt32(sPlantid, -1);
        int typeid = MTDBbase.ToInt32(sTypeid, -1);

        SqlParameterClear();
        SqlCommandText = "Select Distinct P.plantid,P.plantno " +
            "From [VOC].[dbo].[sys_acluserrole] R " +
            "Join [VOC].[dbo].[VOC_plant] P On R.plantno=P.plantno " +
            "Join [VOC].[dbo].[sys_aclrole] T On R.roleid=T.roleid " +
            "Where 1=1 ";

        if (plantid > 0)
        {
            SqlCommandText += "And P.plantid = @plantid ";
            SqlParameterAdd("@plantid", plantid);
        }

        if (typeid > 0)
        {
            SqlCommandText += "And T.roleid = @typeid ";
            SqlParameterAdd("@typeid", typeid);
        }

        SqlCommandText += "Order by plantid ";
        return SqlFillDT();
    }

    public DataTable List廠區8()
    {
        SqlCommandText = "Select Distinct P.plantid,P.plantno " +
            "From [VOC].[dbo].[VOC_SPEC] S " +
            "Join [VOC].[dbo].[VOC_plant] P On S.plantno=P.plantno " +
            "Where S.source=3 Order by plantid ";
        return SqlFillDT();
    }

    public DataTable List廠區9()
    {
        SqlCommandText = "Select plantid,plantno From [VOC].[dbo].[VOC_plant] " +
            "Where plantno Not in ('環工部','GMO') Order by sort ";
        return SqlFillDT();
    }

    public DataTable List廠區10(string sPlantid, string deptno)
    {
        int plantid = MTDBbase.ToInt32(sPlantid, -1);

        SqlParameterClear();
        SqlCommandText = "Select Distinct P.plantid,P.plantno " +
            "From [VOC].[dbo].[VOC_dept] D " +
            "Join [VOC].[dbo].[VOC_plant] P On D.plantid=P.plantid " +
            "Join [UTIDB].[dbo].[Employee] E On D.deptno=E.DeptNo And E.isLeave=0 " +
            "Where 1=1 ";

        if (plantid > 0)
        {
            SqlCommandText += "And D.plantid = @plantid ";
            SqlParameterAdd("@plantid", plantid);
        }

        if (deptno != "")
        {
            SqlCommandText += "And D.deptno = @deptno ";
            SqlParameterAdd("@deptno", deptno);
        }

        SqlCommandText += "Order by plantid ";
        return SqlFillDT();
    }

    public DataTable List項目()
    {
        SqlCommandText = "Select Distinct itemid,item " +
            "From [VOC].[dbo].[VOC_item] Where item not in ('COD1','COD2','pH1','pH2','東南側雨水溝','西南側雨水溝','東北側雨水溝','西北側雨水溝','東北側雨水溝(超高)','東北側雨水溝(過高)') " +
            "And IsActive=1 Order by itemid ";
        return SqlFillDT();
    }

    public DataTable List項目1()
    {
        SqlCommandText = "Select Distinct itemid,item " +
            "From [VOC].[dbo].[VOC_item] Where item not in ('COD1','COD2','pH1','pH2') " +
            "And IsActive=1 Order by itemid ";
        return SqlFillDT();
    }

    public DataTable List項目1(string sPlantid, string sItemid)
    {
        int plantid = MTDBbase.ToInt32(sPlantid, -1);
        int itemid = MTDBbase.ToInt32(sItemid, -1);

        SqlParameterClear();
        SqlCommandText = "Select I.itemid,Replace(Replace(I.item,'COD2','COD'),'pH1','pH') item " +
            "From [VOC].[dbo].[VOC_SPEC] S " +
            "Join [VOC].[dbo].[VOC_item] I On S.item=I.item " +
            "Join [VOC].[dbo].[VOC_plant] P On S.plantno=P.plantno " +
            "Where 1=1 And S.item != 'pH2' ";

        if (plantid > 0)
        {
            SqlCommandText += "And P.plantid = @plantid ";
            SqlParameterAdd("@plantid", plantid);
        }

        if (itemid > 0)
        {
            SqlCommandText += "And I.itemid = @itemid ";
            SqlParameterAdd("@itemid", itemid);
        }

        SqlCommandText += "Order by itemid ";
        return SqlFillDT();
    }

    public DataTable List項目2(string plant, string item)
    {
        SqlParameterClear();
        SqlCommandText = "Select I.itemid,Replace(Replace(I.item,'COD2','COD'),'pH1','pH') item " +
            "From [VOC].[dbo].[VOC_SPEC] S " +
            "Join [VOC].[dbo].[VOC_item] I On S.item=I.item " +
            "Join [VOC].[dbo].[VOC_plant] P On S.plantno=P.plantno " +
            "Where 1=1 And S.item != 'pH2' ";

        if (plant != "")
        {
            SqlCommandText += "And S.plantno = @plant ";
            SqlParameterAdd("@plant", plant);
        }

        if (item != "")
        {
            SqlCommandText += "And S.item Like @item ";
            SqlParameterAdd("@item", item + "%");
        }

        SqlCommandText += "Order by itemid ";
        return SqlFillDT();
    }

    public DataTable List項目3(string plant)
    {
        SqlParameterClear();
        SqlCommandText = "Select I.itemid,Replace(Replace(I.item,'COD2','COD'),'pH1','pH') item " +
            "From [VOC].[dbo].[VOC_SPEC] S " +
            "Join [VOC].[dbo].[VOC_item] I On S.item=I.item " +
            "Join [VOC].[dbo].[VOC_plant] P On S.plantno=P.plantno " +
            "Where S.item != 'pH2' ";

        if (plant != "")
        {
            SqlCommandText += "And S.plantno = @plant ";
            SqlParameterAdd("@plant", plant);

            if (plant == "K5")
            {
                SqlCommandText += "Union Select I.itemid,I.item " +
                    "From [VOC].[dbo].[VOC_SCADA_WEB] W " +
                    "Join [VOC].[dbo].[VOC_item] I On W.item=I.item " +
                    "Join [VOC].[dbo].[VOC_plant] P On W.plantno=P.plantno " +
                    "Where W.plantno = @plant And W.item Like '%雨水溝%' ";
            }
        }

        SqlCommandText += "Order by itemid";
        return SqlFillDT();
    }

    public DataTable List項目4()
    {
        SqlCommandText = "Select Distinct I.itemid,I.item " +
            "From [VOC].[dbo].[VOC_SPEC] S " +
            "Join [VOC].[dbo].[VOC_item] I On S.item=I.item " +
            "Where S.source=3 Order by itemid ";
        return SqlFillDT();
    }

    public DataTable List廠區項目(int plantid)
    {
        int cnt = 0;
        int cnt1 = 0;
        string plantno = "";

        using (dbAclRights db = new dbAclRights())
        {
            SqlParameterClear();
            SqlCommandText = "Select Count(*) From [VOC].[dbo].[sys_acluserrole] " +
                "Where (roleid=@roleid Or roleid=@roleid1) And (empno=@empno Or deptno=@deptno) And (plantno='ALL' Or stype='ALL') ";
            SqlParameterAdd("@roleid", (int)dbAclRights.使用者權限.廠區項目隔離抑制維護);
            SqlParameterAdd("@roleid1", (int)dbAclRights.使用者權限.系統管理員);
            SqlParameterAdd("@empno", AppConfig.Sess_UserEmpNo);
            SqlParameterAdd("@deptno", AppConfig.Sess_UserDept);
            cnt = SqlExecuteScalarInt32(0);

            if (cnt > 0)
            {
                SqlParameterClear();
                SqlCommandText = "Select plantno From [VOC].[dbo].[sys_acluserrole] " +
                    "Where (roleid=@roleid Or roleid=@roleid1) And (empno=@empno Or deptno=@deptno) And (plantno='ALL' Or stype='ALL') ";
                SqlParameterAdd("@roleid", (int)dbAclRights.使用者權限.廠區項目隔離抑制維護);
                SqlParameterAdd("@roleid1", (int)dbAclRights.使用者權限.系統管理員);
                SqlParameterAdd("@empno", AppConfig.Sess_UserEmpNo);
                SqlParameterAdd("@deptno", AppConfig.Sess_UserDept);
                plantno = SqlExecuteScalarString();
            }
        }

        if (cnt == 0)
        {
            SqlParameterClear();
            SqlCommandText = "Select 0 isselect,S.plantno,Replace(Replace(S.item,'COD2','COD'),'pH1','pH') item," +
                "S.LAW,S.OOS,S.OOC,S.alert,S.tagname,I.unit,S1.source,I.itemid,'1' sort,S1.sourceid " +
                "From [VOC].[dbo].[VOC_SPEC] S " +
                "Join [VOC].[dbo].[VOC_item] I On S.item=I.item " +
                "Join [VOC].[dbo].[VOC_plant] P On S.plantno=P.plantno " +
                "Join [VOC].[dbo].[VOC_source] S1 On S.source=S1.sourceid " +
                "Join [VOC].[dbo].[sys_acluserrole] R On S.plantno=R.plantno And I.stype=R.stype " +
                "And (R.empno=@empno Or R.deptno=@deptno) ";
            SqlParameterAdd("@empno", AppConfig.Sess_UserEmpNo);
            SqlParameterAdd("@deptno", AppConfig.Sess_UserDept);
        }
        else
        {
            using (dbAclRights db = new dbAclRights())
            {
                SqlParameterClear();
                SqlCommandText = "Select Count(*) From [VOC].[dbo].[sys_acluserrole] " +
                    "Where (roleid=@roleid Or roleid=@roleid1) And (empno=@empno Or deptno=@deptno) And stype='ALL' ";
                SqlParameterAdd("@roleid", (int)dbAclRights.使用者權限.廠區項目隔離抑制維護);
                SqlParameterAdd("@roleid1", (int)dbAclRights.使用者權限.系統管理員);
                SqlParameterAdd("@empno", AppConfig.Sess_UserEmpNo);
                SqlParameterAdd("@deptno", AppConfig.Sess_UserDept);
                cnt1 = SqlExecuteScalarInt32(0);
            }

            SqlParameterClear();
            SqlCommandText = "Select 0 isselect,S.plantno,Replace(Replace(S.item,'COD2','COD'),'pH1','pH') item," +
                "S.LAW,S.OOS,S.OOC,S.alert,S.tagname,I.unit,S1.source,I.itemid,'1' sort,S1.sourceid " +
                "From [VOC].[dbo].[VOC_SPEC] S " +
                "Join [VOC].[dbo].[VOC_item] I On S.item=I.item " +
                "Join [VOC].[dbo].[VOC_plant] P On S.plantno=P.plantno " +
                "Join [VOC].[dbo].[VOC_source] S1 On S.source=S1.sourceid ";

            if (cnt1 == 0)
            {
                SqlCommandText += "Join [VOC].[dbo].[sys_acluserrole] R On I.stype=R.stype " +
                    "And (R.empno=@empno Or R.deptno=@deptno) ";
                SqlParameterAdd("@empno", AppConfig.Sess_UserEmpNo);
                SqlParameterAdd("@deptno", AppConfig.Sess_UserDept);
            }
            else
            {
                if (plantno != "" && plantno != "ALL")
                {
                    SqlCommandText += "Join [VOC].[dbo].[sys_acluserrole] R On P.plantno=R.plantno " +
                        "And (R.empno=@empno Or R.deptno=@deptno) ";
                    SqlParameterAdd("@empno", AppConfig.Sess_UserEmpNo);
                    SqlParameterAdd("@deptno", AppConfig.Sess_UserDept);
                }
            }
        }

        SqlCommandText += "Where S.source<3 And S.status=1 And P.plantid=@plantid And tagname is not null " +
            "Union " +
            "Select 0 isselect,S.plantno,Replace(Replace(S.item,'COD2','COD'),'pH1','pH') item," +
            "S.LAW,S.OOS,S.OOC,S.alert,S.tagname,I.unit,S1.source,I.itemid,'2' sort,S1.sourceid " +
            "From [VOC].[dbo].[VOC_SPEC] S " +
            "Join [VOC].[dbo].[VOC_item] I On S.item=I.item " +
            "Join [VOC].[dbo].[VOC_plant] P On S.plantno=P.plantno " +
            "Join [VOC].[dbo].[VOC_source] S1 On S1.sourceid=1 ";

        if (cnt == 0)
        {
            SqlCommandText += "Join [VOC].[dbo].[sys_acluserrole] R On S.plantno=R.plantno And I.stype=R.stype " +
            "And (R.empno=@empno Or R.deptno=@deptno) ";
        }
        else
        {
            if (cnt1 == 0)
            {
                SqlCommandText += "Join [VOC].[dbo].[sys_acluserrole] R On I.stype=R.stype " +
                    "And (R.empno=@empno Or R.deptno=@deptno) ";
            }
            else
            {
                if (plantno != "" && plantno != "ALL")
                {
                    SqlCommandText += "Join [VOC].[dbo].[sys_acluserrole] R On P.plantno=R.plantno " +
                        "And (R.empno=@empno Or R.deptno=@deptno) ";
                }
            }
        }

        SqlCommandText += "Where S.source=2 And P.plantid=@plantid Union " +
            "Select 0 isselect,W.plantno,W.item,'' LAW,'' OOS,'' OOC,'' alert," +
            "Concat(W.plantno,'_',W.item) tagname,'' unit,S.source,I.itemid,'1' sort,S.sourceid " +
            "From [VOC].[dbo].[VOC_SCADA_WEB] W " +
            "Join [VOC].[dbo].[VOC_item] I On W.item=I.item " +
            "Join [VOC].[dbo].[VOC_plant] P On W.plantno=P.plantno " +
            "Join [VOC].[dbo].[VOC_source] S On S.sourceid=1 " +
            "Where P.plantid=@plantid and W.item like '%雨水溝%' Order by sort,itemid";
        SqlParameterAdd("@plantid", plantid);
        return SqlFillDT();
    }

    public DataTable List來源()
    {
        SqlCommandText = "Select sourceid,source " +
            "From [VOC].[dbo].[VOC_source] " +
            "Order by sourceid ";
        return SqlFillDT();
    }

    public DataTable List狀態()
    {
        SqlCommandText = "Select statusid,status " +
            "From [VOC].[dbo].[VOC_status] " +
            "Order by statusid desc ";
        return SqlFillDT();
    }

    public DataTable List規格值資料(string plantno, string item)
    {
        SqlParameterClear();
        SqlCommandText = "Select S.plantno,Replace(Replace(S.item,'COD2','COD'),'pH1','pH') item," +
            "S.LAW,S.OOS,S.OOC,S.alert,P.plantid,I.itemid,S1.source,T.status " +
            "From [VOC].[dbo].[VOC_SPEC] S " +
            "Join [VOC].[dbo].[VOC_item] I On S.item=I.item " +
            "Join [VOC].[dbo].[VOC_plant] P On S.plantno=P.plantno " +
            "Join [VOC].[dbo].[VOC_source] S1 On S.source=S1.sourceid " +
            "Join [VOC].[dbo].[VOC_status] T On S.status=T.statusid " +
            "Where 1=1 ";
        if (plantno != "")
        {
            SqlCommandText += "And S.plantno = @plantno ";
            SqlParameterAdd("@plantno", plantno);
        }
        if (item != "")
        {
            SqlCommandText += "And S.item = @item ";
            SqlParameterAdd("@item", item);
        }
        SqlCommandText += "And S.item != 'pH2' Order By plantid,seqno ";
        return SqlFillDT();
    }

    public DataTable List規格值資料1(string plantno, string item)
    {
        SqlParameterClear();
        SqlCommandText = "Select S.plantno,Replace(Replace(S.item,'COD2','COD'),'pH1','pH') item," +
            "S.LAW,S.OOS,S.OOC,S.alert,P.plantid,I.itemid,S1.source,T.status " +
            "From [VOC].[dbo].[VOC_SPEC] S " +
            "Join [VOC].[dbo].[VOC_item] I On S.item=I.item " +
            "Join [VOC].[dbo].[VOC_plant] P On S.plantno=P.plantno " +
            "Join [VOC].[dbo].[VOC_source] S1 On S.source=S1.sourceid " +
            "Join [VOC].[dbo].[VOC_status] T On S.status=T.statusid " +
            "Join [VOC].[dbo].[sys_acluserrole] R On S.plantno=R.plantno And R.empno=@empno " +
            "Where 1=1 ";
        if (plantno != "")
        {
            SqlCommandText += "And S.plantno = @plantno ";
            SqlParameterAdd("@plantno", plantno);
        }
        if (item != "")
        {
            SqlCommandText += "And S.item = @item ";
            SqlParameterAdd("@item", item);
        }
        SqlCommandText += "And S.item != 'pH2' Order By plantid,seqno ";
        SqlParameterAdd("@empno", AppConfig.Sess_UserEmpNo);
        return SqlFillDT();
    }

    public DataTable List派送類型()
    {
        SqlCommandText = "Select typeid,rpttype From [VOC].[dbo].[VOC_Mail_Type] Order by rpttype";
        return SqlFillDT();
    }

    public DataTable List派送類型1(string sPlantid, string sTypeid)
    {
        int plantid = MTDBbase.ToInt32(sPlantid, -1);
        int typeid = MTDBbase.ToInt32(sTypeid, -1);

        SqlParameterClear();
        SqlCommandText = "Select Distinct T.typeid,T.RptType " +
            "From [VOC].[dbo].[VOC_Mail_Type] T " +
            "Left Join [VOC].[dbo].[VOC_Mail_List] M On T.RptType=M.RptType " +
            "Left Join [VOC].[dbo].[VOC_plant] P On M.plantno=P.plantno " +
            "Where 1=1 ";

        if (plantid > 0)
        {
            SqlCommandText += "And P.plantid = @plantid ";
            SqlParameterAdd("@plantid", plantid);
        }

        if (typeid > 0)
        {
            SqlCommandText += "And T.typeid = @typeid ";
            SqlParameterAdd("@typeid", typeid);
        }

        SqlCommandText += "Order by RptType";
        return SqlFillDT();
    }

    public DataTable List派送名單資料(string plantno, string rpttype)
    {
        SqlParameterClear();
        SqlCommandText = "Select M.plantno,M.rpttype,M.empno,M.empname,M.notesid,M.cellphone,M.mailtype," +
            "Iif(M.mail=1,'要','否') mail,Iif(M.SM=1,'要','否') SM,Iif(M.signgrp=1,'是','否') signgrp,P.plantid,T.typeid " +
            "From [VOC].[dbo].[VOC_Mail_List] M " +
            "Join [VOC].[dbo].[VOC_plant] P On M.plantno=P.plantno " +
            "Join [VOC].[dbo].[VOC_Mail_Type] T On M.rpttype=T.rpttype " +
            "Where 1=1 ";
        if (plantno != "")
        {
            SqlCommandText += "And M.plantno = @plantno ";
            SqlParameterAdd("@plantno", plantno);
        }
        if (rpttype != "")
        {
            SqlCommandText += "And M.rpttype = @rpttype ";
            SqlParameterAdd("@rpttype", rpttype);
        }
        SqlCommandText += "Order By plantid,typeid ";
        return SqlFillDT();
    }

    public DataTable List派送名單資料(string plantno, string rpttype, string empno)
    {
        SqlParameterClear();
        SqlCommandText = "Select plantno,rpttype,empno,empname,notesid,cellphone,mailtype," +
            "Iif(mail=1,'要','否') mail,Iif(SM=1,'要','否') SM,Iif(signgrp=1,'是','否') signgrp " +
            "From [VOC].[dbo].[VOC_Mail_List] " +
            "Where 1=1 ";
        if (plantno != "")
        {
            SqlCommandText += "And plantno = @plantno ";
            SqlParameterAdd("@plantno", plantno);
        }
        if (rpttype != "")
        {
            SqlCommandText += "And rpttype = @rpttype ";
            SqlParameterAdd("@rpttype", rpttype);
        }
        if (empno != "")
        {
            SqlCommandText += "And empno = @empno ";
            SqlParameterAdd("@empno", empno);
        }
        return SqlFillDT();
    }

    public DataTable List權限()
    {
        SqlCommandText = "Select roleid,rolename roletype From [VOC].[dbo].[sys_aclrole] " +
            "Where roleid In (3,7) Order by roleid ";
        return SqlFillDT();
    }

    public DataTable List權限1(string sPlantid, string sTypeid)
    {
        int plantid = MTDBbase.ToInt32(sPlantid, -1);
        int typeid = MTDBbase.ToInt32(sTypeid, -1);

        SqlParameterClear();
        SqlCommandText = "Select Distinct T.roleid,T.rolename roletype " +
            "From [VOC].[dbo].[sys_acluserrole] R " +
            "Join [VOC].[dbo].[VOC_plant] P On R.plantno=P.plantno " +
            "Join [VOC].[dbo].[sys_aclrole] T On R.roleid=T.roleid " +
            "Where T.roleid In (3,7) ";

        if (plantid > 0)
        {
            SqlCommandText += "And P.plantid = @plantid ";
            SqlParameterAdd("@plantid", plantid);
        }

        if (typeid > 0)
        {
            SqlCommandText += "And T.roleid = @typeid ";
            SqlParameterAdd("@typeid", typeid);
        }

        SqlCommandText += "Order by roleid ";
        return SqlFillDT();
    }

    public DataTable List隔離權限名單資料(string plantno, string roletype)
    {
        SqlParameterClear();
        SqlCommandText = "Select R.plantno,T.rolename roletype,R.empno,E.empname,E.notesid,R.stype,P.plantid,T.roleid " +
            "From [VOC].[dbo].[sys_acluserrole] R " +
            "Join [VOC].[dbo].[VOC_plant] P On R.plantno=P.plantno " +
            "Join [VOC].[dbo].[sys_aclrole] T On R.roleid=T.roleid " +
            "Join [UTIDB].[dbo].[Employee] E On R.empno=E.empno " +
            "Where T.roleid In (3,7) ";
        if (plantno != "")
        {
            SqlCommandText += "And R.plantno = @plantno ";
            SqlParameterAdd("@plantno", plantno);
        }
        if (roletype != "")
        {
            SqlCommandText += "And T.rolename = @roletype ";
            SqlParameterAdd("@roletype", roletype);
        }
        SqlCommandText += "Order By plantid,roleid ";
        return SqlFillDT();
    }

    public DataTable List隔離權限名單資料(string plantno, string roletype, string empno)
    {
        SqlParameterClear();
        SqlCommandText = "Select R.plantno,T.rolename roletype,R.empno,E.empname,E.notesid,R.stype " +
            "From [VOC].[dbo].[sys_acluserrole] R " +
            "Join [VOC].[dbo].[sys_aclrole] T On R.roleid=T.roleid " +
            "Join [UTIDB].[dbo].[Employee] E On R.empno=E.empno " +
            "Where T.roleid In (3,7) ";
        if (plantno != "")
        {
            SqlCommandText += "And R.plantno = @plantno ";
            SqlParameterAdd("@plantno", plantno);
        }
        if (roletype != "")
        {
            SqlCommandText += "And T.rolename = @roletype ";
            SqlParameterAdd("@roletype", roletype);
        }
        if (empno != "")
        {
            SqlCommandText += "And R.empno = @empno ";
            SqlParameterAdd("@empno", empno);
        }
        return SqlFillDT();
    }

    public DataTable List部門()
    {
        SqlCommandText = "Select Distinct E.DeptNo,Concat(E.DeptNo,'/',E.DeptName) DeptName " +
            "From [VOC].[dbo].[VOC_dept] D " +
            "Join [UTIDB].[dbo].[Employee] E On D.deptno=E.DeptNo And E.isLeave=0 " +
            "Order by DeptNo ";
        return SqlFillDT();
    }

    public DataTable List部門1(string sPlantid, string deptno)
    {
        int plantid = MTDBbase.ToInt32(sPlantid, -1);

        SqlParameterClear();
        SqlCommandText = "Select Distinct E.DeptNo,Concat(E.DeptNo,'/',E.DeptName) DeptName " +
            "From [VOC].[dbo].[VOC_dept] D " +
            "Join [VOC].[dbo].[VOC_plant] P On D.plantid=P.plantid " +
            "Join [UTIDB].[dbo].[Employee] E On D.deptno=E.DeptNo And E.isLeave=0 " +
            "Where 1=1 ";

        if (plantid > 0)
        {
            SqlCommandText += "And D.plantid = @plantid ";
            SqlParameterAdd("@plantid", plantid);
        }

        if (deptno != "")
        {
            SqlCommandText += "And D.deptno = @deptno ";
            SqlParameterAdd("@deptno", deptno);
        }

        SqlCommandText += "Order by DeptNo ";
        return SqlFillDT();
    }

    public DataTable List部門資料(string sPlantid, string deptno)
    {
        int plantid = MTDBbase.ToInt32(sPlantid, -1);

        SqlParameterClear();
        SqlCommandText = "Select Distinct D.plantid,D.deptno,P.plantno,E.deptname " +
            "From [VOC].[dbo].[VOC_dept] D " +
            "Join [VOC].[dbo].[VOC_plant] P On D.plantid=P.plantid " +
            "Join [UTIDB].[dbo].[Employee] E On D.deptno=E.DeptNo And E.isLeave=0 " +
            "Where 1=1 ";

        if (plantid > 0)
        {
            SqlCommandText += "And D.plantid = @plantid ";
            SqlParameterAdd("@plantid", plantid);
        }

        if (deptno != "")
        {
            SqlCommandText += "And D.deptno = @deptno ";
            SqlParameterAdd("@deptno", deptno);
        }

        SqlCommandText += "Order By plantid,deptno ";
        return SqlFillDT();
    }

    public static string GetDataControlFieldCellValue(string name, DataControlFieldCollection cols, GridViewRow gvr)
    {
        OrderedDictionary od = GetGridViewRowValues(cols, gvr);
        if (od[name] == null) return null;
        return od[name].ToString();
    }

    private static OrderedDictionary GetGridViewRowValues(DataControlFieldCollection cols, GridViewRow gvr)
    {
        if (gvr == null) return null;
        OrderedDictionary fieldValues = new OrderedDictionary(cols.Count);
        OrderedDictionary od = new OrderedDictionary();
        for (int i = 1; i < cols.Count; i++)
        {
            //if(cols[i].Visible == true) {
            od.Clear();
            cols[i].ExtractValuesFromCell(od, (DataControlFieldCell)gvr.Cells[i], gvr.RowState, true);
            foreach (DictionaryEntry de in od)
            {
                fieldValues[de.Key] = de.Value;
            }
            //}
        }
        return fieldValues;
    }

    public void MsgBox(Page ThisPage, string sMsg)
    {
        string sScript = "";
        string sMessage = "";

        sMessage = sMsg.Replace("'", "\\'");        //處理單引號
        sMessage = sMessage.Replace("\n", "\\n");   //處理換行符號
        sScript = "alert('" + sMessage + "');";
        ScriptManager.RegisterStartupScript(ThisPage, ThisPage.GetType(), "alert", sScript, true);  //顯示訊息
    }

    public bool CheckSPEC申請(Hashtable hrow)
    {
        SqlParameterClear();
        SqlCommandText = "Select plantno From [VOC].[dbo].[VOC_plant] Where plantid=@plantid";
        SqlParameterAdd("@plantid", hrow["plant"]);
        string plantno = SqlExecuteScalarString();

        SqlParameterClear();
        SqlCommandText = "Select item From [VOC].[dbo].[VOC_item] Where itemid=@itemid";
        SqlParameterAdd("@itemid", hrow["item"]);
        string item = SqlExecuteScalarString();

        SqlParameterClear();
        SqlCommandText = "Select Count(*) From [VOC].[dbo].[VOC_SPEC_apply] " +
            "Where plantno=@plantno And item=@item And fstatusid=@fstatusid";
        SqlParameterAdd("@plantno", plantno);
        SqlParameterAdd("@item", item);
        SqlParameterAdd("@fstatusid", (int)MTFlowBase.FlowStatus.簽核中);
        int cnt = SqlExecuteScalarInt32(0);
        if (cnt > 0) return false; else return true;
    }

    public bool CheckSPEC(Hashtable hrow)
    {
        SqlParameterClear();
        SqlCommandText = "Select plantno From [VOC].[dbo].[VOC_plant] Where plantid=@plantid";
        SqlParameterAdd("@plantid", hrow["plant"]);
        string plantno = SqlExecuteScalarString();

        SqlParameterClear();
        SqlCommandText = "Select item From [VOC].[dbo].[VOC_item] Where itemid=@itemid";
        SqlParameterAdd("@itemid", hrow["item"]);
        string item = SqlExecuteScalarString();

        SqlParameterClear();
        SqlCommandText = "Select Count(*) From [VOC].[dbo].[VOC_SPEC] Where plantno=@plantno And item=@item";
        SqlParameterAdd("@plantno", plantno);
        SqlParameterAdd("@item", item);
        int cnt = SqlExecuteScalarInt32(0);

        if (cnt > 0) return false; else return true;
    }

    public DataTable GetSPEC(int formid)
    {
        SqlParameterClear();
        SqlCommandText = "Select * From [VOC].[dbo].[VOC_SPEC_apply] Where formid=@formid";
        SqlParameterAdd("@formid", formid);
        return SqlFillDT();
    }

    public DataTable GetSPEC(string plantno, string item)
    {
        SqlParameterClear();
        SqlCommandText = "Select S.*,P.plantid,I.itemid From [VOC].[dbo].[VOC_SPEC] S " +
            "Join [VOC].[dbo].[VOC_plant] P On S.plantno=P.plantno " +
            "Join [VOC].[dbo].[VOC_item] I On S.item=I.item " +
            "Where plantno=@plantno And item=@item";
        SqlParameterAdd("@plantno", plantno);
        SqlParameterAdd("@item", item);
        return SqlFillDT();
    }

    public bool InsertSPEC(Hashtable hrow)
    {
        try
        {
            SqlBeginTransaction();
            SqlParameterClear();
            SqlCommandText = "Select plantno From [VOC].[dbo].[VOC_plant] Where plantid=@plantid";
            SqlParameterAdd("@plantid", hrow["plant"]);
            string plantno = SqlExecuteScalarString();

            SqlParameterClear();
            SqlCommandText = "Select item From [VOC].[dbo].[VOC_item] Where itemid=@itemid";
            SqlParameterAdd("@itemid", hrow["item"]);
            string item = SqlExecuteScalarString();

            SqlParameterClear();
            SqlCommandText = "Select source From [VOC].[dbo].[VOC_source] Where sourceid=@sourceid";
            SqlParameterAdd("@sourceid", hrow["source"]);
            string source = SqlExecuteScalarString();

            SqlParameterClear();
            SqlCommandText = "Select Count(*) From [VOC].[dbo].[VOC_SPEC] " +
                "Where plantno=@plantno And item=@item ";
            SqlParameterAdd("@plantno", plantno);
            SqlParameterAdd("@item", item);
            int cnt = SqlExecuteScalarInt32(0);
            if (cnt > 0)
                throw new Exception("此筆資料已存在規格值資料內!");

            SqlParameterClear();
            SqlCommandText = "INSERT INTO [VOC].[dbo].[VOC_SPEC] " +
                "([plantno],[item],[LAW],[OOS],[OOC],[alert],[source],[status],[tagname]) VALUES (@plantno,@item,@LAW,@OOS,@OOC,@alert,@sourceid,1,@tagname);";
            SqlParameterAdd("@plantno", plantno);
            SqlParameterAdd("@item", item);
            SqlParameterAdd("@LAW", hrow["LAW"]);
            SqlParameterAdd("@OOS", hrow["OOS"]);
            SqlParameterAdd("@OOC", hrow["OOC"]);
            SqlParameterAdd("@alert", hrow["alert"]);
            SqlParameterAdd("@sourceid", hrow["source"]);
            SqlParameterAdd("@tagname", plantno + "_" + item);
            SqlExecuteNonQuery();

            SqlParameterClear();
            SqlCommandText = "INSERT INTO [VOC].[dbo].[VOC_tranlog] " +
                "([empno],[logtype],[databefore],[dataafter],[cdatetime],[remark]) " +
                "VALUES (@empno,@logtype,@databefore,@dataafter,@cdatetime,@remark)";
            SqlParameterAdd("@empno", AppConfig.Sess_UserEmpNo);
            SqlParameterAdd("@logtype", "I");
            SqlParameterAdd("@databefore", "");
            SqlParameterAdd("@dataafter", plantno + "/" + item + "/" + hrow["LAW"] + "/" + hrow["OOS"] + "/" + hrow["OOC"] + "/" + hrow["alert"] + "/" + source);
            SqlParameterAdd("@cdatetime", DateTime.Now);
            SqlParameterAdd("@remark", hrow["remark"]);
            SqlExecuteNonQuery();
            SqlCommit();
        }
        catch (Exception ex)
        {
            SqlRollback();
            _Exception = ex.Message;
            return false;
        }

        return true;
    }

    public bool UpdateSPEC(Hashtable hrow, string pLAW, string pOOS, string pOOC, string pAlert, string pSource)
    {
        try
        {
            SqlBeginTransaction();
            SqlParameterClear();
            SqlCommandText = "Select plantno From [VOC].[dbo].[VOC_plant] Where plantid=@plantid";
            SqlParameterAdd("@plantid", hrow["plant"]);
            string plantno = SqlExecuteScalarString();

            SqlParameterClear();
            SqlCommandText = "Select item From [VOC].[dbo].[VOC_item] Where itemid=@itemid";
            SqlParameterAdd("@itemid", hrow["item"]);
            string item = SqlExecuteScalarString();

            SqlParameterClear();
            SqlCommandText = "Select source From [VOC].[dbo].[VOC_source] Where sourceid=@sourceid";
            SqlParameterAdd("@sourceid", hrow["source"]);
            string source = SqlExecuteScalarString();

            SqlParameterClear();
            SqlCommandText = "Update [VOC].[dbo].[VOC_SPEC] Set LAW=@LAW, OOS=@OOS, OOC=@OOC, alert=@alert, source=@sourceid " +
                "Where plantno=@plantno And item=@item";
            SqlParameterAdd("@plantno", plantno);
            SqlParameterAdd("@item", item);
            SqlParameterAdd("@LAW", hrow["LAW"]);
            SqlParameterAdd("@OOS", hrow["OOS"]);
            SqlParameterAdd("@OOC", hrow["OOC"]);
            SqlParameterAdd("@alert", hrow["alert"]);
            SqlParameterAdd("@sourceid", hrow["source"]);
            SqlExecuteNonQuery();

            if (source == "QA")
            {
                SqlParameterClear();
                SqlCommandText = "Update [VOC].[dbo].[VOC_SCADA_WEB] Set OOS_HH=@OOS, OOC_H=@OOC, alert=@alert " +
                    "Where plantno=@plantno And item=@item";
                SqlParameterAdd("@plantno", plantno);
                SqlParameterAdd("@item", item);
                SqlParameterAdd("@OOS", hrow["OOS"]);
                SqlParameterAdd("@OOC", hrow["OOC"]);
                SqlParameterAdd("@alert", hrow["alert"]);
                SqlExecuteNonQuery();
            }

            SqlParameterClear();
            SqlCommandText = "INSERT INTO [VOC].[dbo].[VOC_tranlog] " +
                "([empno],[logtype],[databefore],[dataafter],[cdatetime],[remark]) " +
                "VALUES (@empno,@logtype,@databefore,@dataafter,@cdatetime,@remark)";
            SqlParameterAdd("@empno", AppConfig.Sess_UserEmpNo);
            SqlParameterAdd("@logtype", "M");
            SqlParameterAdd("@databefore", plantno + "/" + item + "/" + pLAW + "/" + pOOS + "/" + pOOC + "/" + pAlert + "/" + pSource);
            SqlParameterAdd("@dataafter", plantno + "/" + item + "/" + hrow["LAW"] + "/" + hrow["OOS"] + "/" + hrow["OOC"] + "/" + hrow["alert"] + "/" + source);
            SqlParameterAdd("@cdatetime", DateTime.Now);
            SqlParameterAdd("@remark", hrow["remark"]);
            SqlExecuteNonQuery();
            SqlCommit();
        }
        catch (Exception ex)
        {
            SqlRollback();
            _Exception = ex.Message;
            return false;
        }

        return true;
    }

    public bool DeleteSPEC(Hashtable hrow)
    {
        try
        {
            SqlBeginTransaction();
            SqlParameterClear();
            SqlCommandText = "Select plantno From [VOC].[dbo].[VOC_plant] Where plantid=@plantid";
            SqlParameterAdd("@plantid", hrow["plant"]);
            string plantno = SqlExecuteScalarString();

            SqlParameterClear();
            SqlCommandText = "Select item From [VOC].[dbo].[VOC_item] Where itemid=@itemid";
            SqlParameterAdd("@itemid", hrow["item"]);
            string item = SqlExecuteScalarString();

            SqlParameterClear();
            SqlCommandText = "Select source From [VOC].[dbo].[VOC_source] Where sourceid=@sourceid";
            SqlParameterAdd("@sourceid", hrow["source"]);
            string source = SqlExecuteScalarString();

            SqlParameterClear();
            SqlCommandText = "Delete From [VOC].[dbo].[VOC_SPEC] " +
                "Where plantno=@plantno And item=@item ";
            SqlParameterAdd("@plantno", plantno);
            SqlParameterAdd("@item", item);
            SqlExecuteNonQuery();

            SqlParameterClear();
            SqlCommandText = "INSERT INTO [VOC].[dbo].[VOC_tranlog] " +
                "([empno],[logtype],[databefore],[dataafter],[cdatetime],[remark]) " +
                "VALUES (@empno,@logtype,@databefore,@dataafter,@cdatetime,@remark)";
            SqlParameterAdd("@empno", AppConfig.Sess_UserEmpNo);
            SqlParameterAdd("@logtype", "D");
            SqlParameterAdd("@databefore", plantno + "/" + item + "/" + hrow["LAW"] + "/" + hrow["OOS"] + "/" + hrow["OOC"] + "/" + hrow["alert"] + "/" + source);
            SqlParameterAdd("@dataafter", "");
            SqlParameterAdd("@cdatetime", DateTime.Now);
            SqlParameterAdd("@remark", hrow["remark"]);
            SqlExecuteNonQuery();
            SqlCommit();
        }
        catch (Exception ex)
        {
            SqlRollback();
            _Exception = ex.Message;
            return false;
        }
        return true;
    }

    public bool UpdateStatus(Hashtable hrow, string pStatus)
    {
        try
        {
            SqlBeginTransaction();
            SqlParameterClear();
            SqlCommandText = "Select plantno From [VOC].[dbo].[VOC_plant] Where plantid=@plantid";
            SqlParameterAdd("@plantid", hrow["plant"]);
            string plantno = SqlExecuteScalarString();

            SqlParameterClear();
            SqlCommandText = "Select item From [VOC].[dbo].[VOC_item] Where itemid=@itemid";
            SqlParameterAdd("@itemid", hrow["item"]);
            string item = SqlExecuteScalarString();

            SqlParameterClear();
            SqlCommandText = "Select status From [VOC].[dbo].[VOC_status] Where statusid=@statusid";
            SqlParameterAdd("@statusid", hrow["status"]);
            string status = SqlExecuteScalarString();

            SqlParameterClear();
            SqlCommandText = "Update [VOC].[dbo].[VOC_SPEC] Set status=@statusid " +
                "Where plantno=@plantno And item=@item";
            SqlParameterAdd("@plantno", plantno);
            SqlParameterAdd("@item", item);
            SqlParameterAdd("@statusid", hrow["status"]);
            SqlExecuteNonQuery();

            SqlParameterClear();
            SqlCommandText = "INSERT INTO [VOC].[dbo].[VOC_tranlog] " +
                "([empno],[logtype],[databefore],[dataafter],[cdatetime],[remark]) " +
                "VALUES (@empno,@logtype,@databefore,@dataafter,@cdatetime,@remark)";
            SqlParameterAdd("@empno", AppConfig.Sess_UserEmpNo);
            SqlParameterAdd("@logtype", "M");
            SqlParameterAdd("@databefore", plantno + "/" + item + "/" + pStatus);
            SqlParameterAdd("@dataafter", plantno + "/" + item + "/" + status);
            SqlParameterAdd("@cdatetime", DateTime.Now);
            SqlParameterAdd("@remark", hrow["remark"]);
            SqlExecuteNonQuery();
            SqlCommit();
        }
        catch (Exception ex)
        {
            SqlRollback();
            _Exception = ex.Message;
            return false;
        }

        return true;
    }

    public bool InsertMailList(Hashtable hrow)
    {
        try
        {
            SqlBeginTransaction();
            SqlParameterClear();
            SqlCommandText = "Select plantno From [VOC].[dbo].[VOC_plant] Where plantid=@plantid";
            SqlParameterAdd("@plantid", hrow["plant"]);
            string plantno = SqlExecuteScalarString();

            SqlParameterClear();
            SqlCommandText = "Select RptType From [VOC].[dbo].[VOC_Mail_Type] Where typeid=@typeid";
            SqlParameterAdd("@typeid", hrow["rtype"]);
            string rpttype = SqlExecuteScalarString();

            SqlParameterClear();
            SqlCommandText = "Select Count(*) From [VOC].[dbo].[VOC_Mail_List] " +
                "Where plantno=@plantno And rpttype=@rpttype And empno=@empno ";
            SqlParameterAdd("@plantno", plantno);
            SqlParameterAdd("@rpttype", rpttype);
            SqlParameterAdd("@empno", hrow["empno"]);
            int cnt = SqlExecuteScalarInt32(0);
            if (cnt > 0)
                throw new Exception("此筆資料已存在派送名單資料內!");

            string snotesid = hrow["notesid"].ToString().Replace("_", " ").Replace("@aseglobal.com", "");
            string smailtype = (hrow["mailtype"].ToString() == "1" ? "TO" : "CC");
            string smail = (hrow["mail"].ToString() == "1" ? "要" : "否");
            string sSM = (hrow["SM"].ToString() == "1" ? "要" : "否");
            string ssigngrp = (hrow["signgrp"].ToString() == "1" ? "是" : "否");

            SqlParameterClear();
            SqlCommandText = "INSERT INTO [VOC].[dbo].[VOC_Mail_List] " +
                "([plantno],[rpttype],[empno],[empname],[notesid],[cellphone],[mailtype],[mail],[SM],[signgrp]) " +
                "VALUES (@plantno,@rpttype,@empno,@empname,@notesid,@cellphone,@mailtype,@mail,@SM,@signgrp);";
            SqlParameterAdd("@plantno", plantno);
            SqlParameterAdd("@rpttype", rpttype);
            SqlParameterAdd("@empno", hrow["empno"]);
            SqlParameterAdd("@empname", hrow["empname"]);
            SqlParameterAdd("@notesid", snotesid);
            SqlParameterAdd("@cellphone", hrow["cellphone"]);
            SqlParameterAdd("@mailtype", smailtype);
            SqlParameterAdd("@mail", hrow["mail"]);
            SqlParameterAdd("@SM", hrow["SM"]);
            SqlParameterAdd("@signgrp", hrow["signgrp"]);
            SqlExecuteNonQuery();

            SqlParameterClear();
            SqlCommandText = "INSERT INTO [VOC].[dbo].[VOC_tranlog] " +
                "([empno],[logtype],[databefore],[dataafter],[cdatetime],[remark]) " +
                "VALUES (@empno,@logtype,@databefore,@dataafter,@cdatetime,@remark)";
            SqlParameterAdd("@empno", AppConfig.Sess_UserEmpNo);
            SqlParameterAdd("@logtype", "I");
            SqlParameterAdd("@databefore", "");
            SqlParameterAdd("@dataafter", plantno + "/" + rpttype + "/" + hrow["empno"] + "/" + hrow["empname"] + "/" + snotesid + "/" + hrow["cellphone"] + "/" + smailtype + "/" + smail + "/" + sSM + "/" + ssigngrp);
            SqlParameterAdd("@cdatetime", DateTime.Now);
            SqlParameterAdd("@remark", hrow["remark"]);
            SqlExecuteNonQuery();
            SqlCommit();
        }
        catch (Exception ex)
        {
            SqlRollback();
            _Exception = ex.Message;
            return false;
        }

        return true;
    }

    public bool UpdateMailList(Hashtable hrow, string pempno, string pempname, string pnotesid, string pcellphone, string pmailtype, string pmail, string pSM, string psigngrp)
    {
        try
        {
            SqlBeginTransaction();
            SqlParameterClear();
            SqlCommandText = "Select plantno From [VOC].[dbo].[VOC_plant] Where plantid=@plantid";
            SqlParameterAdd("@plantid", hrow["plant"]);
            string plantno = SqlExecuteScalarString();

            SqlParameterClear();
            SqlCommandText = "Select RptType From [VOC].[dbo].[VOC_Mail_Type] Where typeid=@typeid";
            SqlParameterAdd("@typeid", hrow["rtype"]);
            string rpttype = SqlExecuteScalarString();

            string snotesid = hrow["notesid"].ToString().Replace("_", " ").Replace("@aseglobal.com", "");
            string smailtype = (hrow["mailtype"].ToString() == "1" ? "TO" : "CC");
            string smail = (hrow["mail"].ToString() == "1" ? "要" : "否");
            string sSM = (hrow["SM"].ToString() == "1" ? "要" : "否");
            string ssigngrp = (hrow["signgrp"].ToString() == "1" ? "是" : "否");

            SqlParameterClear();
            SqlCommandText = "Update [VOC].[dbo].[VOC_Mail_List] " +
                "Set empno=@empno, empname=@empname, notesid=@notesid, cellphone=@cellphone, " +
                "mailtype=@mailtype, mail=@mail, SM=@SM, signgrp=@signgrp " +
                "Where plantno=@plantno And rpttype=@rpttype And empno=@pempno";
            SqlParameterAdd("@plantno", plantno);
            SqlParameterAdd("@rpttype", rpttype);
            SqlParameterAdd("@pempno", pempno);
            SqlParameterAdd("@empno", hrow["empno"]);
            SqlParameterAdd("@empname", hrow["empname"]);
            SqlParameterAdd("@notesid", snotesid);
            SqlParameterAdd("@cellphone", hrow["cellphone"]);
            SqlParameterAdd("@mailtype", smailtype);
            SqlParameterAdd("@mail", hrow["mail"]);
            SqlParameterAdd("@SM", hrow["SM"]);
            SqlParameterAdd("@signgrp", hrow["signgrp"]);
            SqlExecuteNonQuery();

            SqlParameterClear();
            SqlCommandText = "INSERT INTO [VOC].[dbo].[VOC_tranlog] " +
                "([empno],[logtype],[databefore],[dataafter],[cdatetime],[remark]) " +
                "VALUES (@empno,@logtype,@databefore,@dataafter,@cdatetime,@remark)";
            SqlParameterAdd("@empno", AppConfig.Sess_UserEmpNo);
            SqlParameterAdd("@logtype", "M");
            SqlParameterAdd("@databefore", plantno + "/" + rpttype + "/" + pempno + "/" + pempname + "/" + pnotesid + "/" + pcellphone + "/" + pmailtype + "/" + pmail + "/" + pSM + "/" + psigngrp);
            SqlParameterAdd("@dataafter", plantno + "/" + rpttype + "/" + hrow["empno"] + "/" + hrow["empname"] + "/" + snotesid + "/" + hrow["cellphone"] + "/" + smailtype + "/" + smail + "/" + sSM + "/" + ssigngrp);
            SqlParameterAdd("@cdatetime", DateTime.Now);
            SqlParameterAdd("@remark", hrow["remark"]);
            SqlExecuteNonQuery();
            SqlCommit();
        }
        catch (Exception ex)
        {
            SqlRollback();
            _Exception = ex.Message;
            return false;
        }

        return true;
    }

    public bool DeleteMailList(Hashtable hrow)
    {
        try
        {
            SqlBeginTransaction();
            SqlParameterClear();
            SqlCommandText = "Select plantno From [VOC].[dbo].[VOC_plant] Where plantid=@plantid";
            SqlParameterAdd("@plantid", hrow["plant"]);
            string plantno = SqlExecuteScalarString();

            SqlParameterClear();
            SqlCommandText = "Select RptType From [VOC].[dbo].[VOC_Mail_Type] Where typeid=@typeid";
            SqlParameterAdd("@typeid", hrow["rtype"]);
            string rpttype = SqlExecuteScalarString();

            SqlParameterClear();
            SqlCommandText = "Delete From [VOC].[dbo].[VOC_Mail_List] " +
                "Where plantno=@plantno And rpttype=@rpttype And empno=@empno";
            SqlParameterAdd("@plantno", plantno);
            SqlParameterAdd("@rpttype", rpttype);
            SqlParameterAdd("@empno", hrow["empno"]);
            SqlExecuteNonQuery();

            string snotesid = hrow["notesid"].ToString().Replace("_", " ").Replace("@aseglobal.com", "");
            string smailtype = (hrow["mailtype"].ToString() == "1" ? "TO" : "CC");
            string smail = (hrow["mail"].ToString() == "1" ? "要" : "否");
            string sSM = (hrow["SM"].ToString() == "1" ? "要" : "否");
            string ssigngrp = (hrow["signgrp"].ToString() == "1" ? "是" : "否");

            SqlParameterClear();
            SqlCommandText = "INSERT INTO [VOC].[dbo].[VOC_tranlog] " +
                "([empno],[logtype],[databefore],[dataafter],[cdatetime],[remark]) " +
                "VALUES (@empno,@logtype,@databefore,@dataafter,@cdatetime,@remark)";
            SqlParameterAdd("@empno", AppConfig.Sess_UserEmpNo);
            SqlParameterAdd("@logtype", "D");
            SqlParameterAdd("@databefore", plantno + "/" + rpttype + "/" + hrow["empno"] + "/" + hrow["empname"] + "/" + snotesid + "/" + hrow["cellphone"] + "/" + smailtype + "/" + smail + "/" + sSM + "/" + ssigngrp);
            SqlParameterAdd("@dataafter", "");
            SqlParameterAdd("@cdatetime", DateTime.Now);
            SqlParameterAdd("@remark", hrow["remark"]);
            SqlExecuteNonQuery();
            SqlCommit();
        }
        catch (Exception ex)
        {
            SqlRollback();
            _Exception = ex.Message;
            return false;
        }
        return true;
    }

    public bool InsertAclUserList(Hashtable hrow)
    {
        try
        {
            SqlBeginTransaction();
            SqlParameterClear();
            SqlCommandText = "Select plantno From [VOC].[dbo].[VOC_plant] Where plantid=@plantid";
            SqlParameterAdd("@plantid", hrow["plant"]);
            string plantno = SqlExecuteScalarString();

            SqlParameterClear();
            SqlCommandText = "Select rolename From [VOC].[dbo].[sys_aclrole] Where roleid=@roleid";
            SqlParameterAdd("@roleid", hrow["type"]);
            string roletype = SqlExecuteScalarString();

            SqlParameterClear();
            SqlCommandText = "Select Count(*) From [VOC].[dbo].[sys_acluserrole] " +
                "Where roleid=@roleid And plantno=@plantno And empno=@empno ";
            SqlParameterAdd("@plantno", plantno);
            SqlParameterAdd("@roleid", hrow["type"]);
            SqlParameterAdd("@empno", hrow["empno"]);
            int cnt = SqlExecuteScalarInt32(0);
            if (cnt > 0)
                throw new Exception("此筆資料已存在隔離權限名單資料內!");

            string stype = (hrow["stype"].ToString() == "1" ? "空" : (hrow["stype"].ToString() == "2" ? "水" : "ALL"));

            SqlParameterClear();
            SqlCommandText = "INSERT INTO [VOC].[dbo].[sys_acluserrole] " +
                "([roleid],[plantno],[empno],[stype]) " +
                "VALUES (@roleid,@plantno,@empno,@stype);";
            SqlParameterAdd("@roleid", hrow["type"]);
            SqlParameterAdd("@plantno", plantno);
            SqlParameterAdd("@empno", hrow["empno"]);
            SqlParameterAdd("@stype", stype);
            SqlExecuteNonQuery();

            SqlParameterClear();
            SqlCommandText = "INSERT INTO [VOC].[dbo].[VOC_tranlog] " +
                "([empno],[logtype],[databefore],[dataafter],[cdatetime],[remark]) " +
                "VALUES (@empno,@logtype,@databefore,@dataafter,@cdatetime,@remark)";
            SqlParameterAdd("@empno", AppConfig.Sess_UserEmpNo);
            SqlParameterAdd("@logtype", "I");
            SqlParameterAdd("@databefore", "");
            SqlParameterAdd("@dataafter", plantno + "/" + roletype + "/" + hrow["empno"] + "/" + stype);
            SqlParameterAdd("@cdatetime", DateTime.Now);
            SqlParameterAdd("@remark", hrow["remark"]);
            SqlExecuteNonQuery();
            SqlCommit();
        }
        catch (Exception ex)
        {
            SqlRollback();
            _Exception = ex.Message;
            return false;
        }

        return true;
    }

    public bool UpdateAclUserList(Hashtable hrow, string pempno, string pstype)
    {
        try
        {
            SqlBeginTransaction();
            SqlParameterClear();
            SqlCommandText = "Select plantno From [VOC].[dbo].[VOC_plant] Where plantid=@plantid";
            SqlParameterAdd("@plantid", hrow["plant"]);
            string plantno = SqlExecuteScalarString();

            SqlParameterClear();
            SqlCommandText = "Select rolename From [VOC].[dbo].[sys_aclrole] Where roleid=@roleid";
            SqlParameterAdd("@roleid", hrow["type"]);
            string roletype = SqlExecuteScalarString();

            string stype = (hrow["stype"].ToString() == "1" ? "空" : (hrow["stype"].ToString() == "2" ? "水" : "ALL"));

            SqlParameterClear();
            SqlCommandText = "Update [VOC].[dbo].[sys_acluserrole] " +
                "Set empno=@empno, stype=@stype " +
                "Where roleid=@roleid And plantno=@plantno And empno=@pempno";
            SqlParameterAdd("@roleid", hrow["type"]);
            SqlParameterAdd("@plantno", plantno);
            SqlParameterAdd("@pempno", pempno);
            SqlParameterAdd("@empno", hrow["empno"]);
            SqlParameterAdd("@stype", stype);
            SqlExecuteNonQuery();

            SqlParameterClear();
            SqlCommandText = "INSERT INTO [VOC].[dbo].[VOC_tranlog] " +
                "([empno],[logtype],[databefore],[dataafter],[cdatetime],[remark]) " +
                "VALUES (@empno,@logtype,@databefore,@dataafter,@cdatetime,@remark)";
            SqlParameterAdd("@empno", AppConfig.Sess_UserEmpNo);
            SqlParameterAdd("@logtype", "M");
            SqlParameterAdd("@databefore", plantno + "/" + roletype + "/" + pempno + "/" + pstype);
            SqlParameterAdd("@dataafter", plantno + "/" + roletype + "/" + hrow["empno"] + "/" + stype);
            SqlParameterAdd("@cdatetime", DateTime.Now);
            SqlParameterAdd("@remark", hrow["remark"]);
            SqlExecuteNonQuery();
            SqlCommit();
        }
        catch (Exception ex)
        {
            SqlRollback();
            _Exception = ex.Message;
            return false;
        }

        return true;
    }

    public bool DeleteAclUserList(Hashtable hrow)
    {
        try
        {
            SqlBeginTransaction();
            SqlParameterClear();
            SqlCommandText = "Select plantno From [VOC].[dbo].[VOC_plant] Where plantid=@plantid";
            SqlParameterAdd("@plantid", hrow["plant"]);
            string plantno = SqlExecuteScalarString();

            SqlParameterClear();
            SqlCommandText = "Select rolename From [VOC].[dbo].[sys_aclrole] Where roleid=@roleid";
            SqlParameterAdd("@roleid", hrow["type"]);
            string roletype = SqlExecuteScalarString();

            SqlParameterClear();
            SqlCommandText = "Delete From [VOC].[dbo].[sys_acluserrole] " +
                "Where roleid=@roleid And plantno=@plantno And empno=@empno";
            SqlParameterAdd("@plantno", plantno);
            SqlParameterAdd("@roleid", hrow["type"]);
            SqlParameterAdd("@empno", hrow["empno"]);
            SqlExecuteNonQuery();

            string stype = (hrow["stype"].ToString() == "1" ? "空" : (hrow["stype"].ToString() == "2" ? "水" : "ALL"));

            SqlParameterClear();
            SqlCommandText = "INSERT INTO [VOC].[dbo].[VOC_tranlog] " +
                "([empno],[logtype],[databefore],[dataafter],[cdatetime],[remark]) " +
                "VALUES (@empno,@logtype,@databefore,@dataafter,@cdatetime,@remark)";
            SqlParameterAdd("@empno", AppConfig.Sess_UserEmpNo);
            SqlParameterAdd("@logtype", "D");
            SqlParameterAdd("@databefore", plantno + "/" + roletype + "/" + hrow["empno"] + "/" + stype);
            SqlParameterAdd("@dataafter", "");
            SqlParameterAdd("@cdatetime", DateTime.Now);
            SqlParameterAdd("@remark", hrow["remark"]);
            SqlExecuteNonQuery();
            SqlCommit();
        }
        catch (Exception ex)
        {
            SqlRollback();
            _Exception = ex.Message;
            return false;
        }
        return true;
    }

    #region 新增隔離廠區項目清單
    public enum Ttype
    {
        新增 = 1,
        修改隔離區間 = 2,
    };
    public enum Utype
    {
        新增 = 1,
        送簽 = 2,
        修改隔離區間 = 3,
    };
    public enum 簽核流程
    {
        法遵平台_隔離廠區項目維護 = 8,
        法遵平台_法規許可值與規格值維護 = 9,
    }

    public string GetCCNO(int ccid)
    {
        SqlParameterClear();
        SqlCommandText = "Select ccno From [VOC].[dbo].[VOC_closectl] Where ccid=@ccid ";
        SqlParameterAdd("@ccid", ccid);
        return SqlExecuteScalarString();
    }

    public bool InsertHis(int ccid, Utype utypeid)
    {
        try
        {
            SqlParameterClear();
            SqlCommandText = "INSERT INTO [VOC].[dbo].[VOC_closectl_his] " +
                "([utypeid],[utime],[uclerk],[ccid],[ttypeid],[ccno],[plantid],[mdfdesc],[stime],[etime],[remark],[cempname], " +
                "[cempno],[ctime],[flowid],[fstatusid],[del],[delclerk],[orgccid]) " +
                "Select @utypeid,@utime,@uclerk,@ccid,ttypeid,ccno,plantid,mdfdesc,stime,etime,remark,cempname,  " +
                "cempno,ctime,flowid,fstatusid,del,delclerk,orgccid " +
                "From [VOC].[dbo].[VOC_closectl] " +
                "Where ccid=@ccid ";
            SqlParameterAdd("@ccid", ccid);
            SqlParameterAdd("@utypeid", (int)utypeid);
            SqlParameterAdd("@utime", DateTime.Now.ToString("yyyy/MM/dd HH:mm:ss.fff"));
            SqlParameterAdd("@uclerk", string.Format("{0}-{1}", AppConfig.Sess_UserEmpNo, AppConfig.Sess_UserEmpName));
            SqlExecuteNonQuery();
            return true;
        }
        catch (Exception ex)
        {
            _Exception = ex.Message;
            return false;
        }
    }

    public bool Check申請隔離廠區項目(Hashtable hrow, DataRow[] rows)
    {
        string plantno;
        string item;
        string source;

        foreach (DataRow row in rows)
        {
            plantno = row["plantno"].ToStringTrim();
            item = row["item"].ToStringTrim();
            source = row["source"].ToStringTrim();

            if ((plantno == "K14B" || plantno == "K22" || plantno == "九號放流口") && item == "pH")
                item = "pH1";
            else if (plantno == "K14B" && item == "COD")
                item = "COD2";

            SqlParameterClear();
            SqlCommandText = "Select Count(*) From [VOC].[dbo].[VOC_closectl] C " +
                "Join [VOC].[dbo].[VOC_closectl_list] L On C.ccid=L.ccid " +
                "Join [VOC].[dbo].[VOC_source] S On L.sourceid=S.sourceid " +
                "Where C.stime=@stime And C.etime=@etime And L.plantno=@plantno And L.item=@item And S.source=@source";
            SqlParameterAdd("@stime", hrow["stime"]);
            SqlParameterAdd("@etime", hrow["etime"]);
            SqlParameterAdd("@plantno", plantno);
            SqlParameterAdd("@item", item);
            SqlParameterAdd("@source", source);
            int cnt = SqlExecuteScalarInt32(0);
            if (cnt > 0) return false;
        }

        return true;
    }

    public bool Check申請隔離免簽核(Hashtable hrow, DataRow[] rows)
    {
        string plantno;
        string item;
        string source;
        DateTime dt1 = Convert.ToDateTime(hrow["stime"].ToString());
        DateTime dt2 = Convert.ToDateTime(hrow["etime"].ToString());
        TimeSpan ts = dt2 - dt1;

        foreach (DataRow row in rows)
        {
            plantno = row["plantno"].ToStringTrim();
            item = row["item"].ToStringTrim();
            source = row["source"].ToStringTrim();

            //免簽核規則: pH一小時, Cu/Ni/SS/COD/預警COD均為四小時, 一天僅能申請一次
            if (item.IndexOf("pH") < 0 && item.IndexOf("Cu") < 0 && item.IndexOf("Ni") < 0 &&
                item.IndexOf("SS") < 0 && item.IndexOf("COD") < 0) return false;
            else
            {
                if ((item.IndexOf("pH") > -1 && (ts.Days >= 1 || ts.Hours > 1 || (ts.Hours == 1 && ts.Minutes > 0))) ||
                    (item.IndexOf("pH") < 0 && (ts.Days >= 1 || ts.Hours > 4 || (ts.Hours == 4 && ts.Minutes > 0)))) return false;
            }

            if ((plantno == "K14B" || plantno == "K22" || plantno == "九號放流口") && item == "pH")
                item = "pH1";
            else if (plantno == "K14B" && item == "COD")
                item = "COD2";

            SqlParameterClear();
            SqlCommandText = "Select Count(*) From [VOC].[dbo].[VOC_closectl] C " +
                "Join [VOC].[dbo].[VOC_closectl_list] L On C.ccid=L.ccid " +
                "Join [VOC].[dbo].[VOC_source] S On L.sourceid=S.sourceid " +
                "Where (Convert(varchar,C.stime,112) in (@stime,@etime) Or Convert(varchar,C.etime,112) in (@stime,@etime)) " +
                "And L.plantno=@plantno And L.item=@item And S.source=@source And C.flowid is null And C.fstatusid=@fstatusid";
            SqlParameterAdd("@stime", dt1.ToString("yyyyMMdd"));
            SqlParameterAdd("@etime", dt2.ToString("yyyyMMdd"));
            SqlParameterAdd("@plantno", plantno);
            SqlParameterAdd("@item", item);
            SqlParameterAdd("@source", source);
            SqlParameterAdd("@fstatusid", (int)MTFlowBase.FlowStatus.核准);
            int cnt = SqlExecuteScalarInt32(0);
            if (cnt > 0) return false;
        }

        return true;
    }

    public bool Insert隔離廠區項目(Hashtable hrow, DataRow[] rows, bool isCommit)
    {   //isCommit true:送簽  false:暫存
        try
        {
            bool bPass = false;
            //if (isCommit) bPass = Check申請隔離免簽核(hrow, rows);

            SqlBeginTransaction();
            SqlParameterClear();
            SqlCommandText = "Select TOP 1 ccno From [VOC].[dbo].[VOC_closectl] " +
                "Where ccno like @ccno Order by ccno desc ";
            SqlParameterAdd("@ccno", DateTime.Today.ToString("yyyyMMdd") + "%");
            string cpno = SqlExecuteScalarStringTrim();
            if (MTDBbase.IsNullOrEmpty(cpno))
                cpno = DateTime.Today.ToString("yyyyMMdd") + "000";
            //hrow["ccno"] = MTDBbase.GetNextNo(cpno, MTDBbase.GetNextNoMode.OnlyDight);
            hrow["ccno"] = cpno.Substring(0, 8) + string.Format("{0:000}", MTDBbase.ToInt32(cpno.Substring(8, 3)) + 1);

            SqlParameterClear();
            SqlCommandText = "INSERT INTO [VOC].[dbo].[VOC_closectl] " +
                "([ttypeid],[ccno],[plantid],[mdfdesc],[stime],[etime],[remark],[cempname], " +
                "[cempno],[ctime],[flowid],[fstatusid],[del],[delclerk],[orgccid]) " +
                "VALUES (@ttypeid,@ccno,@plantid,@mdfdesc,@stime,@etime,@remark,@cempname,  " +
                "@cempno,@ctime,NULL,@fstatusid,0,NULL,@orgccid);" +
                "SELECT SCOPE_IDENTITY(); ";
            SqlParameterAdd("@ttypeid", hrow["ttypeid"]);
            SqlParameterAdd("@ccno", hrow["ccno"]);
            SqlParameterAdd("@plantid", hrow["plantid"]);
            SqlParameterAdd("@mdfdesc", hrow["mdfdesc"]);
            SqlParameterAdd("@stime", hrow["stime"]);
            SqlParameterAdd("@etime", hrow["etime"]);
            SqlParameterAdd("@remark", hrow["remark"]);
            SqlParameterAdd("@cempname", hrow["cempname"]);
            SqlParameterAdd("@cempno", hrow["cempno"]);
            SqlParameterAdd("@ctime", DateTime.Now.ToString("yyyy/MM/dd HH:mm:ss.fff"));
            SqlParameterAdd("@fstatusid", (int)MTFlowBase.FlowStatus.待簽核);
            SqlParameterAdd("@orgccid", hrow["orgccid"] ?? DBNull.Value);
            int ccid = SqlExecuteScalarInt32(0);

            if (!InsertHis(ccid, Utype.新增))
                throw new Exception(_Exception);

            string plantno = "";
            string item = "";
            string sourceid = "";
            string stype = "";
            string rtype = "";

            foreach (DataRow row in rows)
            {
                plantno = row["plantno"].ToStringTrim();
                item = row["item"].ToStringTrim();
                sourceid = row["sourceid"].ToStringTrim();
                stype = (item.IndexOf("VOC") > -1 ? "空" : "水") + "保養中";
                rtype += (rtype.IndexOf(stype) > -1 ? "" : (rtype == "" ? "'" : ",'") + stype + "'");

                if ((plantno == "K14B" || plantno == "K22" || plantno == "九號放流口") && item == "pH")
                    item = "pH1";
                else if (plantno == "K14B" && item == "COD")
                    item = "COD2";

                SqlParameterClear();
                SqlCommandText = "Insert Into [VOC].[dbo].[VOC_closectl_list] (ccid,plantno,item,sourceid) Values(@ccid,@plantno,@item,@sourceid) ";
                SqlParameterAdd("@ccid", ccid);
                SqlParameterAdd("@plantno", plantno);
                SqlParameterAdd("@item", item);
                SqlParameterAdd("@sourceid", sourceid);
                SqlExecuteNonQuery();
            }

            if (isCommit)
            {
                if (bPass == true)
                {
                    SqlParameterClear();
                    SqlCommandText = "Update [VOC].[dbo].[VOC_closectl] Set fstatusid=@fstatusid Where ccid=@ccid ";
                    SqlParameterAdd("@ccid", ccid);
                    SqlParameterAdd("@fstatusid", (int)MTFlowBase.FlowStatus.核准);
                    SqlExecuteNonQuery();
                }
                else
                {
                    string showinfo = string.Format(@"申請單號:{0} 廠區:{1}<br \>說明:{2}", hrow["ccno"], plantno, hrow["mdfdesc"]);
                    int flowid = MTFlowBase.Proc建立簽核流程((int)簽核流程.法遵平台_隔離廠區項目維護, ccid, AppConfig.Sess_UserEmpNo, plantno, rtype, @"ccid=" + ccid, showinfo);
                    if (flowid < 0)
                        throw new Exception(MTFlowBase._Exception);
                    SqlParameterClear();
                    SqlCommandText = "Update [VOC].[dbo].[VOC_closectl] Set flowid=@flowid,fstatusid=@fstatusid Where ccid=@ccid ";
                    SqlParameterAdd("@flowid", flowid);
                    SqlParameterAdd("@ccid", ccid);
                    SqlParameterAdd("@fstatusid", (int)MTFlowBase.FlowStatus.簽核中);
                    SqlExecuteNonQuery();

                    if (!MTFlowBase.SendMail通知(hrow, ccid, flowid, MTFlowBase.MsgType.法遵平台簽核))
                        MTDBbase.SysLogE("隔離廠區項目維護ccid[" + ccid + "] SendMail通知 失敗!" + MTFlowBase._Exception);
                }
            }
            SqlCommit();
        }
        catch (Exception ex)
        {
            SqlRollback();
            _Exception = ex.Message;
            return false;
        }
        return true;
    }

    public bool Update隔離廠區項目(Hashtable hrow, string etime)
    {
        try
        {
            SqlBeginTransaction();

            SqlParameterClear();
            SqlCommandText = "UPDATE [VOC].[dbo].[VOC_closectl] SET etime=@etime WHERE ccno=@ccno";
            SqlParameterAdd("@ccno", hrow["ccno"]);
            SqlParameterAdd("@etime", Convert.ToDateTime(hrow["etime"]));
            SqlExecuteNonQuery();
            SqlCommandText = "UPDATE [VOC].[dbo].[VOC_closectl_his] SET etime=@etime WHERE ccno=@ccno";
            SqlExecuteNonQuery();

            SqlCommandText = "INSERT INTO [VOC].[dbo].[VOC_tranlog] " +
                "([empno],[logtype],[databefore],[dataafter],[cdatetime],[remark]) " +
                "VALUES (@empno,@logtype,@databefore,@dataafter,@cdatetime,@remark)";
            SqlParameterAdd("@empno", AppConfig.Sess_UserEmpNo);
            SqlParameterAdd("@logtype", "M");
            SqlParameterAdd("@databefore", "隔離單號:" + hrow["ccno"] + "/結束日期:" + Convert.ToDateTime(etime).ToString("yyyy/MM/dd HH:mm:ss"));
            SqlParameterAdd("@dataafter", "隔離單號:" + hrow["ccno"] + "/結束日期:" + Convert.ToDateTime(hrow["etime"]).ToString("yyyy/MM/dd HH:mm:ss"));
            SqlParameterAdd("@cdatetime", DateTime.Now);
            SqlParameterAdd("@remark", hrow["remark"]);
            SqlExecuteNonQuery();

            SqlCommit();
        }
        catch (Exception ex)
        {
            SqlRollback();
            _Exception = ex.Message;
            return false;
        }
        return true;
    }

    public bool Proc送簽(int ccid)
    {
        try
        {
            SqlBeginTransaction();

            SqlParameterClear();
            SqlCommandText = "Select C.*,L.plantno,L.item From [VOC].[dbo].[VOC_closectl] C " +
                "Join [VOC].[dbo].[VOC_closectl_list] L On C.ccid=L.ccid Where C.ccid=@ccid ";
            SqlParameterAdd("@ccid", ccid);
            DataTable dtb = SqlFillDT();
            if (dtb.Rows.Count == 0)
                throw new Exception("無此筆資料!ccid:" + ccid.ToString());

            string item = "";
            string stype = "";
            string rtype = "";

            foreach (DataRow row in dtb.Rows)
            {
                item = row["item"].ToStringTrim();
                stype = (item.IndexOf("VOC") > -1 ? "空" : "水") + "保養中";
                rtype += (rtype.IndexOf(stype) > -1 ? "" : (rtype == "" ? "'" : ",'") + stype + "'");
            }

            Hashtable hrow = MTDBbase.DataRowToHashtable(dtb.Rows[0]);

            string showinfo = string.Format(@"申請單號:{0} 廠區:{1}<br \>說明:{2}", hrow["ccno"], hrow["plantno"], hrow["mdfdesc"]);
            int flowid = MTFlowBase.Proc建立簽核流程((int)簽核流程.法遵平台_隔離廠區項目維護, ccid, AppConfig.Sess_UserEmpNo, hrow["plantno"].ToString(), rtype, @"ccid=" + ccid, showinfo);
            if (flowid < 0)
                throw new Exception(MTFlowBase._Exception);
            SqlParameterClear();
            SqlCommandText = "Update [VOC].[dbo].[VOC_closectl] Set flowid=@flowid,fstatusid=@fstatusid1 Where ccid=@ccid ";
            SqlParameterAdd("@flowid", flowid);
            SqlParameterAdd("@ccid", ccid);
            SqlParameterAdd("@fstatusid1", (int)MTFlowBase.FlowStatus.簽核中);
            SqlExecuteNonQuery();

            if (!InsertHis(ccid, Utype.送簽))
                throw new Exception(_Exception);

            SqlCommit();
            hrow["ccno"] = GetCCNO(MTDBbase.ToInt32(hrow["ccid"]));
            if (!MTFlowBase.SendMail通知(hrow, ccid, flowid, MTFlowBase.MsgType.法遵平台簽核))
                MTDBbase.SysLogE("隔離廠區項目維護ccid[" + ccid + "] SendMail通知 失敗!" + MTFlowBase._Exception);
            return true;
        }
        catch (Exception ex)
        {
            SqlRollback();
            _Exception = ex.Message;
            return false;
        }
    }

    public bool ProcSign(Hashtable hrow)
    {
        try
        {
            SqlBeginTransaction();
            if (!MTFlowBase.Sign(hrow, AppConfig.Sess_User職位ID, AppConfig.Sess_User員工ID, AppConfig.Sess_UserEmpName))
                throw new Exception(MTFlowBase._Exception);

            MTFlowBase.FlowStatus fstatusid = MTFlowBase.GetFlowStatus(MTDBbase.ToInt32(hrow["flowid"], -1));
            hrow["fstatusid"] = (int)fstatusid;
            SqlParameterClear();
            SqlCommandText = "Update [VOC].[dbo].[VOC_closectl] Set fstatusid=@fstatusid Where ccid=@ccid  ";
            SqlParameterAdd("@fstatusid", hrow["fstatusid"]);
            SqlParameterAdd("@ccid", hrow["ccid"]);
            SqlExecuteNonQuery();

            if (fstatusid == MTFlowBase.FlowStatus.核准)
            {
                SqlParameterClear();
                SqlCommandText = "Select * From [VOC].[dbo].[VOC_closectl] Where ccid=@ccid  ";
                SqlParameterAdd("@ccid", hrow["ccid"]);
                DataTable dtb = SqlFillDT();
                if (MTDBbase.ToInt32(dtb.Rows[0]["ttypeid"]) == (int)Ttype.修改隔離區間)
                {
                    SqlParameterClear();
                    SqlCommandText = "Update [VOC].[dbo].[VOC_closectl] Set stime=@stime,etime=@etime Where ccid=@orgccid  ";
                    SqlParameterAdd("@stime", dtb.Rows[0]["stime"]);
                    SqlParameterAdd("@etime", dtb.Rows[0]["etime"]);
                    SqlParameterAdd("@orgccid", dtb.Rows[0]["orgccid"]);
                    SqlExecuteNonQuery();

                    if (!InsertHis(MTDBbase.ToInt32(hrow["ccid"]), Utype.修改隔離區間))
                        throw new Exception(_Exception);
                }
            }

            SqlCommit();
            hrow["ccno"] = GetCCNO(MTDBbase.ToInt32(hrow["ccid"]));
            if (!MTFlowBase.SendMail通知(hrow, MTDBbase.ToInt32(hrow["ccid"]), MTDBbase.ToInt32(hrow["flowid"]), MTFlowBase.MsgType.法遵平台簽核))
                MTDBbase.SysLogE("隔離廠區項目維護 簽核作業:ccid[" + MTDBbase.ToInt32(hrow["ccid"]) + "] SendMail通知 失敗!" + MTFlowBase._Exception);

            return true;
        }
        catch (Exception ex)
        {
            SqlRollback();
            _Exception = ex.Message;
            return false;
        }
    }

    public bool ProcSignSPEC(Hashtable hrow)
    {
        try
        {
            SqlBeginTransaction();
            if (!MTFlowBase.Sign(hrow, AppConfig.Sess_User職位ID, AppConfig.Sess_User員工ID, AppConfig.Sess_UserEmpName))
                throw new Exception(MTFlowBase._Exception);

            MTFlowBase.FlowStatus fstatusid = MTFlowBase.GetFlowStatus(MTDBbase.ToInt32(hrow["flowid"], -1));
            hrow["fstatusid"] = (int)fstatusid;
            SqlParameterClear();
            SqlCommandText = "Update [VOC].[dbo].[VOC_closectl] Set fstatusid=@fstatusid Where ccid=@ccid  ";
            SqlParameterAdd("@fstatusid", hrow["fstatusid"]);
            SqlParameterAdd("@ccid", hrow["ccid"]);
            SqlExecuteNonQuery();

            if (fstatusid == MTFlowBase.FlowStatus.核准)
            {
                SqlParameterClear();
                SqlCommandText = "Select * From [VOC].[dbo].[VOC_closectl] Where ccid=@ccid  ";
                SqlParameterAdd("@ccid", hrow["ccid"]);
                DataTable dtb = SqlFillDT();
                if (MTDBbase.ToInt32(dtb.Rows[0]["ttypeid"]) == (int)Ttype.修改隔離區間)
                {
                    SqlParameterClear();
                    SqlCommandText = "Update [VOC].[dbo].[VOC_closectl] Set stime=@stime,etime=@etime Where ccid=@orgccid  ";
                    SqlParameterAdd("@stime", dtb.Rows[0]["stime"]);
                    SqlParameterAdd("@etime", dtb.Rows[0]["etime"]);
                    SqlParameterAdd("@orgccid", dtb.Rows[0]["orgccid"]);
                    SqlExecuteNonQuery();

                    if (!InsertHis(MTDBbase.ToInt32(hrow["ccid"]), Utype.修改隔離區間))
                        throw new Exception(_Exception);
                }
            }

            SqlCommit();
            hrow["ccno"] = GetCCNO(MTDBbase.ToInt32(hrow["ccid"]));
            if (!MTFlowBase.SendMail通知(hrow, MTDBbase.ToInt32(hrow["ccid"]), MTDBbase.ToInt32(hrow["flowid"]), MTFlowBase.MsgType.法遵平台簽核))
                MTDBbase.SysLogE("隔離廠區項目維護 簽核作業:ccid[" + MTDBbase.ToInt32(hrow["ccid"]) + "] SendMail通知 失敗!" + MTFlowBase._Exception);

            return true;
        }
        catch (Exception ex)
        {
            SqlRollback();
            _Exception = ex.Message;
            return false;
        }
    }

    public DataTable List我的待辦事項(string sdate, string edate, int ccid = -1)
    {
        WhereStr whstr = new WhereStr();
        SqlParameterClear();
        if (!MTDBbase.IsNullOrEmpty(sdate))
        {
            whstr.And("convert(varchar(10),M.ctime,111)>=@sdate");
            SqlParameterAdd("@sdate", sdate);
        }
        if (!MTDBbase.IsNullOrEmpty(edate))
        {
            whstr.And("convert(varchar(10),M.ctime,111)<=@edate");
            SqlParameterAdd("@edate", edate);
        }
        if (ccid > 0)
        {
            whstr.And("M.ccid=@ccid");
            SqlParameterAdd("@ccid", ccid);
        }
        if (AppConfig.Sess_IsAdmin != 1)
        {
            whstr.And("E.empno=@cempno");
            SqlParameterAdd("@cempno", AppConfig.Sess_UserEmpNo);
        }
        SqlCommandText = "Select Distinct M.*,P.plantno,M.cempno+'-'+M.cempname empstr,CT.ttype " +
           "From [VOC].[dbo].[VOC_closectl] M " +
           "Join [VOC].[dbo].[VOC_plant] P On M.plantid=P.plantid " +
           "Join [VOC].[dbo].[VOC_closectl_ttype] CT On M.ttypeid=CT.ttypeid " +
           "Join [SignFlow].[dbo].[base_flowstatus] FS On M.fstatusid=FS.fstatusid " +
           "Join [SignFlow].[dbo].[base_flow] BF On M.flowid=BF.flowid " +
           "Join [SignFlow].[dbo].[base_flowd] BFD On BF.flowid=BFD.flowid And BF.actstep=BFD.fstep " +
           "Join [SignFlow].[dbo].[base_emp] E On BFD.empid=E.empid " +
           whstr.ToString() +
           " Order by M.ctime desc ";
        return SqlFillDT();
    }

    public DataTable List我的申請單(string sdate, string edate, int plantid, int statusid, int ccid)
    {
        WhereStr whstr = new WhereStr();
        SqlParameterClear();
        if (!MTDBbase.IsNullOrEmpty(sdate))
        {
            whstr.And("convert(varchar(10),M.ctime,111)>=@sdate");  //yyyy/mm/dd
            SqlParameterAdd("@sdate", sdate);
        }
        if (!MTDBbase.IsNullOrEmpty(edate))
        {
            whstr.And("convert(varchar(10),M.ctime,111)<=@edate");  //yyyy/mm/dd
            SqlParameterAdd("@edate", edate);
        }
        if (plantid != -1)
        {
            whstr.And("M.plantid=@plantid");
            SqlParameterAdd("@plantid", plantid);
        }
        if (statusid != -1) //All
        {
            whstr.And("M.fstatusid=@statusid");
            SqlParameterAdd("@statusid", statusid);
        }
        if (ccid == -1)
        {
            if (AppConfig.Sess_IsAdmin != 1)
            {
                whstr.And("M.cempno=@cempno");
                SqlParameterAdd("@cempno", AppConfig.Sess_UserEmpNo);
            }
        }
        else
        {
            whstr.And("M.ccid=@ccid");
            SqlParameterAdd("@ccid", ccid);
        }

        SqlCommandText = "Select M.*,P.plantno,M.cempno+'-'+M.cempname empstr,FS.fstatus,CT.ttype " +
           "From [VOC].[dbo].[VOC_closectl] M " +
           "Join [VOC].[dbo].[VOC_plant] P On M.plantid=P.plantid " +
           "Join [VOC].[dbo].[VOC_closectl_ttype] CT On M.ttypeid=CT.ttypeid " +
           "Join [SignFlow].[dbo].[base_flowstatus] FS On M.fstatusid=FS.fstatusid " +
           whstr.ToString() +
           " Order by M.ctime desc ";
        return SqlFillDT();
    }

    public DataTable List廠區的申請單(string sdate, string edate, int plantid, int statusid, int ccid)
    {
        WhereStr whstr = new WhereStr();

        int cnt = 0;

        using (dbAclRights db = new dbAclRights())
        {
            SqlParameterClear();
            SqlCommandText = "Select Count(*) From [VOC].[dbo].[sys_acluserrole] " +
                "Where (roleid=@roleid Or roleid=@roleid1 Or roleid=@roleid2) And (empno=@empno Or deptno=@deptno) And plantno='ALL' ";
            SqlParameterAdd("@roleid", (int)dbAclRights.使用者權限.廠區項目隔離抑制維護);
            SqlParameterAdd("@roleid1", (int)dbAclRights.使用者權限.系統管理員);
            SqlParameterAdd("@roleid2", (int)dbAclRights.使用者權限.廠區項目隔離抑制查詢);
            SqlParameterAdd("@empno", AppConfig.Sess_UserEmpNo);
            SqlParameterAdd("@deptno", AppConfig.Sess_UserDept);
            cnt = SqlExecuteScalarInt32(0);
        }

        SqlParameterClear();
        if (!MTDBbase.IsNullOrEmpty(sdate))
        {
            whstr.And("convert(varchar(10),M.ctime,111)>=@sdate");  //yyyy/mm/dd
            SqlParameterAdd("@sdate", sdate);
        }
        if (!MTDBbase.IsNullOrEmpty(edate))
        {
            whstr.And("convert(varchar(10),M.ctime,111)<=@edate");  //yyyy/mm/dd
            SqlParameterAdd("@edate", edate);
        }
        if (plantid != -1)
        {
            whstr.And("M.plantid=@plantid");
            SqlParameterAdd("@plantid", plantid);
        }
        if (statusid != -1) //未送簽/待主管簽核/核准
        {
            whstr.And("M.fstatusid=@statusid");
            SqlParameterAdd("@statusid", statusid);
        }
        else //All-不含否決
        {
            whstr.And("M.fstatusid!=@statusid");
            SqlParameterAdd("@statusid", 8);
        }
        if (ccid != -1)
        {
            whstr.And("M.ccid=@ccid");
            SqlParameterAdd("@ccid", ccid);
        }

        SqlCommandText = "Select M.*,P.plantno,M.cempno+'-'+M.cempname empstr,FS.fstatus,CT.ttype " +
           "From [VOC].[dbo].[VOC_closectl] M " +
           "Join [VOC].[dbo].[VOC_plant] P On M.plantid=P.plantid " +
           "Join [VOC].[dbo].[VOC_closectl_ttype] CT On M.ttypeid=CT.ttypeid " +
           "Join [SignFlow].[dbo].[base_flowstatus] FS On M.fstatusid=FS.fstatusid ";

        if (cnt == 0)
        {
            SqlCommandText += "Join [VOC].[dbo].[sys_acluserrole] R On P.plantno=R.plantno " +
                "And (R.empno=@empno Or R.deptno=@deptno) ";
            SqlParameterAdd("@empno", AppConfig.Sess_UserEmpNo);
            SqlParameterAdd("@deptno", AppConfig.Sess_UserDept);
        }

        SqlCommandText += whstr.ToString() + " Order by M.ctime desc ";
        return SqlFillDT();
    }

    public DataTable List隔離廠區項目(int ccid)
    {
        SqlParameterClear();
        SqlCommandText = "Select concat(L.plantno,'_',L.item) oldtagname,L.plantno,Replace(Replace(L.item,'COD2','COD'),'pH1','pH') item," +
           "S.LAW,S.OOS,S.OOC,S.alert,Iif(L.item Like '%雨水溝%',concat(L.plantno,'_',L.item),S.tagname) tagname,I.unit,"+
           "Iif(S1.source is null,'SCADA',S1.source) source,S1.sourceid,1 isselect " +
           "From [VOC].[dbo].[VOC_closectl] C  " +
           "Join [VOC].[dbo].[VOC_closectl_list] L On C.ccid=L.ccid " +
           "Left Join [VOC].[dbo].[VOC_SPEC] S On L.plantno=S.plantno And L.item=S.item " +
           "Join [VOC].[dbo].[VOC_item] I On L.item=I.item " +
           "Left Join [VOC].[dbo].[VOC_source] S1 On L.sourceid=S1.sourceid " +
           "Where C.ccid=@ccid " +
           "Union " +
           "Select concat(L.plantno,'_',L.item) oldtagname,L.plantno,Replace(Replace(L.item,'COD2','COD'),'pH1','pH') item," +
           "S.LAW,S.OOS,S.OOC,S.alert,Iif(L.item Like '%雨水溝%',concat(L.plantno,'_',L.item),S.tagname) tagname,I.unit," +
           "Iif(S1.source is null,'SCADA',S1.source) source,S1.sourceid,1 isselect " +
           "From [VOC].[dbo].[VOC_closectl] C  " +
           "Join [VOC].[dbo].[VOC_closectl_list] L On C.orgccid=L.ccid " +
           "Left Join [VOC].[dbo].[VOC_SPEC] S On L.plantno=S.plantno And L.item=S.item " +
           "Join [VOC].[dbo].[VOC_item] I On L.item=I.item " +
           "Left Join [VOC].[dbo].[VOC_source] S1 On L.sourceid=S1.sourceid " +
           "Where C.ccid=@ccid " +
           "Order by oldtagname ";
        SqlParameterAdd("@ccid", ccid);
        return SqlFillDT();
    }

    public DataTable List申請單(int ccid)
    {
        WhereStr whstr = new WhereStr();
        SqlParameterClear();
        whstr.And("M.ccid=@ccid");
        SqlParameterAdd("@ccid", ccid);
        SqlCommandText = "Select M.*,P.plantno,M.cempno+'-'+M.cempname empstr " +
           "From [VOC].[dbo].[VOC_closectl] M " +
           "Join [VOC].[dbo].[VOC_plant] P On M.plantid=P.plantid " +
           whstr.ToString();
        return SqlFillDT();
    }

    public DataTable List隔離廠區項目()
    {
        string DT = DateTime.Now.ToString("yyyy/MM/dd HH:mm");
        DateTime dt1 = Convert.ToDateTime(DT + ":00.000");
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
            "Select W.plantno,Replace(Replace(W.item,'COD2','COD'),'pH1','pH') item,W.cdatetime,S1.sourceid,S.source " +
            "From @ccDT C " +
            "Join [VOC].[dbo].[VOC_closectl_list] L On C.ccid=L.ccid " +
            "Join [VOC].[dbo].[VOC_SPEC] S On L.plantno=S.plantno And L.item=S.item " +
            "Join [VOC].[dbo].[VOC_SCADA_WEB] W On L.plantno=W.plantno And L.item=W.item " +
            "Join [VOC].[dbo].[VOC_source] S1 On L.sourceid=S1.sourceid " +
            "Where W.rvalue != '保養中' And W.alert != '保養中' " +
            "Group by W.plantno,W.item,W.cdatetime,S1.sourceid,S.source " +
            "Union " +
            "Select W.plantno,W.item,W.cdatetime,S.sourceid,S.sourceid source " +
            "From @ccDT C " +
            "Join [VOC].[dbo].[VOC_closectl_list] L On C.ccid=L.ccid " +
            "Join [VOC].[dbo].[VOC_SCADA_WEB] W On L.plantno=W.plantno And L.item=W.item " +
            "Join [VOC].[dbo].[VOC_source] S On L.sourceid=S.sourceid " +
            "Where W.item Like '%雨水溝%' And W.rvalue != '保養中' " +
            "Group by W.plantno,W.item,W.cdatetime,S.sourceid";
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
        string sourceid = row["sourceid"].ToString();
        string source = row["source"].ToString();

        if ((plantno == "K14B" || plantno == "K22" || plantno == "九號放流口") && item == "pH")
            item = "pH1";
        else if (plantno == "K14B" && item == "COD")
            item = "COD2";

        SqlParameterClear();
        SqlCommandText = "Update [VOC].[dbo].[VOC_SCADA_WEB] Set ";

        if (item.IndexOf("雨水溝") < 0)
        {
            if (sourceid == "1")    //SCADA
                SqlCommandText += "OOS_HH=Iif(OOS_HH='-','-',@status), OOC_H=Iif(OOC_H='-','-',@status), alert=Iif(alert='-','-',@status), " +
                    "OOS_LL=Iif(OOS_LL='-','-',@status), OOC_L=Iif(OOC_L='-','-',@status), alert_L=Iif(alert_L='-','-',@status), ";
            else
                SqlCommandText += "OOS_HH1=@status, OOC_H1=@status, OOS_LL1=@status, OOC_L1=@status, ";
        }

        if (sourceid == source)
            SqlCommandText += "rvalue=@status, cdatetime=@tdate, broken=2, light=3 ";
        else
            SqlCommandText += "cdatetime=@tdate, broken=2 ";

        SqlCommandText += "Where plantno=@plantno And item=@item";
        SqlParameterAdd("@tdate", tdate);
        SqlParameterAdd("@plantno", plantno);
        SqlParameterAdd("@item", item);
        SqlParameterAdd("@status", "保養中");
        SqlExecuteNonQuery();

        //string DT = DateTime.Now.ToString("yyyy/MM/dd HH:mm");
        //DateTime dt1 = Convert.ToDateTime(DT + ":00.000");
        //int m = dt1.Minute % 15;
        //string dt0 = dt1.AddMinutes(-m).ToString("yyyy/MM/dd HH:mm:00");

        //SqlParameterClear();
        //SqlCommandText = "Update [VOC].[dbo].[VOC_SCADA_HIST] Set ";

        //if (item.IndexOf("雨水溝") < 0)
        //{
        //    if (sourceid == "1")    //SCADA
        //        SqlCommandText += "OOS_HH=Iif(OOS_HH='-','-',@status), OOC_H=Iif(OOC_H='-','-',@status), alert=Iif(alert='-','-',@status), " +
        //            "OOS_LL=Iif(OOS_LL='-','-',@status), OOC_L=Iif(OOC_L='-','-',@status), alert_L=Iif(alert_L='-','-',@status), ";
        //    else
        //        SqlCommandText += "OOS_HH1=@status, OOC_H1=@status, OOS_LL1=@status, OOC_L1=@status, ";
        //}

        //if (sourceid == source)
        //    SqlCommandText += "rvalue=@status, cdatetime=@tdate, broken=2, light=3 ";
        //else
        //    SqlCommandText += "cdatetime=@tdate, broken=2 ";

        //SqlCommandText += "Where plantno=@plantno And item=@item And cdatetime=@tdate";
        //SqlParameterAdd("@tdate", dt0);
        //SqlParameterAdd("@plantno", plantno);
        //SqlParameterAdd("@item", item);
        //SqlParameterAdd("@cdatetime", cdatetime);
        //SqlParameterAdd("@status", "保養中");
        //SqlExecuteNonQuery();
    }

    public string Get隔離廠區項目區間(string plantno, string item)
    {
        string DT = DateTime.Now.ToString("yyyy/MM/dd HH:mm");
        DateTime dt1 = Convert.ToDateTime(DT + ":00.000");
        int m = dt1.Minute % 15;
        string dt0 = dt1.AddMinutes(-m).ToString("yyyy/MM/dd HH:mm:00");

        if ((plantno == "K14B" || plantno == "K22" || plantno == "九號放流口") && item == "pH")
            item = "pH1";
        else if (plantno == "K14B" && item == "COD")
            item = "COD2";

        SqlParameterClear();
        SqlCommandText = "Select Distinct Concat('從',format(stime,'MM/dd HH:mm'),'到',format(etime,'MM/dd HH:mm')) " +
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
    #endregion

    public bool CheckStatus()
    {
        SqlCommandText = "Select Count(*) From [VOC].[dbo].[VOC_Mail_List] Where Mail=1";
        int cnt = SqlExecuteScalarInt32(0);
        return (cnt > 0 ? false : true);
    }

    public void Mail啟用()
    {
        SqlCommandText = "Update [VOC].[dbo].[VOC_Mail_List] Set Mail=Mail1, SM=SM1";
        SqlExecuteNonQuery();
    }

    public void Mail停用()
    {
        SqlCommandText = "Update [VOC].[dbo].[VOC_Mail_List] Set Mail1=Mail, SM1=SM";
        SqlExecuteNonQuery();

        SqlCommandText = "Update [VOC].[dbo].[VOC_Mail_List] Set Mail=0, SM=0";
        SqlExecuteNonQuery();
    }

    public bool SPEC送簽(Hashtable hrow, string ftype)
    {
        try
        {
            SqlBeginTransaction();
            SqlParameterClear();
            SqlCommandText = "Select TOP 1 formno From [VOC].[dbo].[VOC_SPEC_apply] " +
                "Where formno like @formno Order by formno desc ";
            SqlParameterAdd("@formno", DateTime.Today.ToString("yyyyMMdd") + "%");
            string cpno = SqlExecuteScalarStringTrim();
            if (MTDBbase.IsNullOrEmpty(cpno))
                cpno = DateTime.Today.ToString("yyyyMMdd") + "000";
            hrow["formno"] = MTDBbase.GetNextNo(cpno, MTDBbase.GetNextNoMode.OnlyDight);

            SqlParameterClear();
            SqlCommandText = "Select plantno From [VOC].[dbo].[VOC_plant] Where plantid=@plantid";
            SqlParameterAdd("@plantid", hrow["plantid"]);
            string plantno = SqlExecuteScalarString();

            SqlParameterClear();
            SqlCommandText = "Select item From [VOC].[dbo].[VOC_item] Where itemid=@itemid";
            SqlParameterAdd("@itemid", hrow["itemid"]);
            string item = SqlExecuteScalarString();
            string item1 = item;

            if ((plantno == "K14B" || plantno == "K22" || plantno == "九號放流口") && item == "pH")
                item = "pH1";
            else if (plantno == "K14B" && item == "COD")
                item = "COD2";

            SqlParameterClear();
            SqlCommandText = "INSERT INTO [VOC].[dbo].[VOC_SPEC_apply] " +
                "([formno],[ftype],[plantno],[item],[LAW],[OOS],[OOC],[alert],[source][remark],[empno],[cdatetime],[flowid],[fstatusid]) " +
                "VALUES (@formno,@ftype,@plantno,@item,@LAW,@OOS,@OOC,@alert,@source,@remark,@empno,@cdatetime,NULL,@fstatusid);" +
                "SELECT SCOPE_IDENTITY(); ";
            SqlParameterAdd("@formno", hrow["formno"]);
            SqlParameterAdd("@ftype", ftype);
            SqlParameterAdd("@plantno", plantno);
            SqlParameterAdd("@item", item);
            SqlParameterAdd("@LAW", hrow["LAW"]);
            SqlParameterAdd("@OOS", hrow["OOS"]);
            SqlParameterAdd("@OOC", hrow["OOC"]);
            SqlParameterAdd("@alert", hrow["alert"]);
            SqlParameterAdd("@source", hrow["sourceid"]);
            SqlParameterAdd("@remark", hrow["remark"]);
            SqlParameterAdd("@empno", hrow["empno"]);
            SqlParameterAdd("@cdatetime", DateTime.Now.ToString("yyyy/MM/dd HH:mm:ss.fff"));
            SqlParameterAdd("@fstatusid", (int)MTFlowBase.FlowStatus.待簽核);
            int formid = SqlExecuteScalarInt32(0);

            string showinfo = string.Format(@"申請單號:{0} 廠區:{1} 項目:{2}<br \>說明:{3}", hrow["formno"], plantno, item1, hrow["remark"]);
            int flowid = MTFlowBase.Proc建立簽核流程((int)簽核流程.法遵平台_法規許可值與規格值維護, formid, AppConfig.Sess_UserEmpNo, plantno, ftype, @"formid=" + formid, showinfo);
            if (flowid < 0)
                throw new Exception(MTFlowBase._Exception);
            SqlParameterClear();
            SqlCommandText = "Update [VOC].[dbo].[VOC_SPEC_apply] Set flowid=@flowid,fstatusid=@fstatusid1 Where formid=@formid ";
            SqlParameterAdd("@flowid", flowid);
            SqlParameterAdd("@formid", formid);
            SqlParameterAdd("@fstatusid1", (int)MTFlowBase.FlowStatus.簽核中);
            SqlExecuteNonQuery();

            if (!MTFlowBase.SendMail通知(hrow, formid, flowid, MTFlowBase.MsgType.法遵平台簽核))
                MTDBbase.SysLogE("法規許可值與規格值維護formid[" + formid + "] SendMail通知 失敗!" + MTFlowBase._Exception);

            SqlCommit();
        }
        catch (Exception ex)
        {
            SqlRollback();
            _Exception = ex.Message;
            return false;
        }
        return true;
    }

    public DataTable List我的待辦事項1(string sdate, string edate, int formid = -1)
    {
        WhereStr whstr = new WhereStr();
        SqlParameterClear();
        if (!MTDBbase.IsNullOrEmpty(sdate))
        {
            whstr.And("convert(varchar(10),M.cdatetime,111)>=@sdate");
            SqlParameterAdd("@sdate", sdate);
        }
        if (!MTDBbase.IsNullOrEmpty(edate))
        {
            whstr.And("convert(varchar(10),M.cdatetime,111)<=@edate");
            SqlParameterAdd("@edate", edate);
        }
        if (formid > 0)
        {
            whstr.And("M.formid=@formid");
            SqlParameterAdd("@formid", formid);
        }
        if (AppConfig.Sess_IsAdmin != 1)
        {
            whstr.And("E.empno=@empno");
            SqlParameterAdd("@empno", AppConfig.Sess_UserEmpNo);
        }
        SqlCommandText = "Select Distinct M.*,E.empno+'-'+E.empname empstr,Iif(M.ftype='I','新增',Iif(M.ftype='M','修改','刪除')) ftype " +
           "From [VOC].[dbo].[VOC_SPEC_apply] M " +
           "Join [SignFlow].[dbo].[base_flowstatus] FS On M.fstatusid=FS.fstatusid " +
           "Join [SignFlow].[dbo].[base_flow] BF On M.flowid=BF.flowid " +
           "Join [SignFlow].[dbo].[base_flowd] BFD On BF.flowid=BFD.flowid And BF.actstep=BFD.fstep " +
           "Join [SignFlow].[dbo].[base_emp] E On BFD.empid=E.empid " +
           whstr.ToString() +
           " Order by M.cdatetime desc ";
        return SqlFillDT();
    }

    public DataTable List廠區項目1(int formid)
    {
        SqlParameterClear();
        SqlCommandText = "Select concat(M.plantno,'_',M.item) tagname,M.plantno,Replace(Replace(M.item,'COD2','COD'),'pH1','pH') item," +
           "M.LAW,M.OOS,M.OOC,M.alert,I.unit,S.source " +
           "From [VOC].[dbo].[VOC_SPEC_apply] M  " +
           "Join [VOC].[dbo].[VOC_item] I On M.item=I.item " +
           "Join [VOC].[dbo].[VOC_source] S On M.source=S.sourceid " +
           "Where M.formid=@formid Order by tagname";
        SqlParameterAdd("@formid", formid);
        return SqlFillDT();
    }

    public DataTable Get廠棟異常件數統計(string plantno, string item, string sdate, string edate, string sort, bool MT, bool total)
    {
        SqlParameterClear();
        string wheres = "";
        if (plantno != "")
        {
            if (!string.IsNullOrWhiteSpace(wheres))
                wheres += " And ";
            wheres += " (P.plantno=@plantno) ";
            SqlParameterAdd("@plantno", plantno);
        }
        if (item != "")
        {
            if (!string.IsNullOrWhiteSpace(wheres))
                wheres += " And ";
            wheres += " (S.item=@item) ";
            SqlParameterAdd("@item", item);
        }
        if (MT != true)
        {
            if (!string.IsNullOrWhiteSpace(wheres))
                wheres += " And ";
            wheres += " (L.msg2 LIKE CONCAT('%|',S.item,'|%')) ";
        }

        SqlCommandText = "DECLARE @DT TABLE " +
            "(PLANTNO nvarchar(10)," +
            " ITEM nvarchar(20)); " +
            "INSERT @DT " +
            "SELECT S.plantno,REPLACE(REPLACE(I.item,'COD2','COD'),'pH1','pH') item " +
            "FROM [VOC].[dbo].[VOC_SPEC] S " +
            "JOIN [VOC].[dbo].[VOC_item] I ON S.item=I.item " +
            "JOIN [VOC].[dbo].[VOC_plant] P ON S.plantno=P.plantno; " +
            "DECLARE @caselist TABLE (PLANTID int,CASE_TTL int) " +
            "INSERT @caselist SELECT P.PLANTID,COUNT(S.item) as CASE_TTL " +
            "FROM @DT S " +
            "JOIN [VOC].[dbo].[VOC_MAIL_Log] L ON S.plantno=L.plantno AND L.msg1 LIKE CONCAT('%|',S.item,'|%') " +
            "JOIN [VOC].[dbo].[VOC_plant] P On L.plantno=P.plantno " +
            "WHERE CONVERT(nvarchar(10), CDATETIME, 111) BETWEEN @sdate AND @edate " +
            (wheres.Trim().Length > 0 ? "And " + wheres : "") + "GROUP BY P.PLANTID; ";
        SqlParameterAdd("@sdate", sdate);
        SqlParameterAdd("@edate", edate);

        SqlCommandText += "SELECT P.PLANTNO,P.PLANTID, ";

        if (item != "") SqlCommandText += "'" + item + "' ITEM, ";
        else SqlCommandText += "'' ITEM, ";

        SqlCommandText += "ISNULL(SUM(M.CASE_TTL),0) as CASE_TTL, " +
            "DENSE_RANK() OVER (ORDER BY SUM(M.CASE_TTL) DESC) as CASE_RANK " +
            "FROM @caselist M " +
            "JOIN [VOC].[dbo].[VOC_plant] P On M.plantid=P.plantid " +
            "GROUP BY P.PLANTNO,P.PLANTID ";

        if (sort == "廠區") SqlCommandText += "ORDER BY PLANTID; ";
        else if (sort == "異常件數(由大到小)+廠區") SqlCommandText += "ORDER BY CASE_RANK,PLANTID; ";
        else SqlCommandText += "ORDER BY CASE_RANK DESC,PLANTID; ";

        return SqlFillDT();
    }

    public DataTable Get廠棟異常件數總計(string plantno, string item, string sdate, string edate, bool MT)
    {
        SqlParameterClear();
        string wheres = "";
        if (plantno != "")
        {
            if (!string.IsNullOrWhiteSpace(wheres))
                wheres += " And ";
            wheres += " (P.plantno=@plantno) ";
            SqlParameterAdd("@plantno", plantno);
        }
        if (item != "")
        {
            if (!string.IsNullOrWhiteSpace(wheres))
                wheres += " And ";
            wheres += " (S.item=@item) ";
            SqlParameterAdd("@item", item);
        }
        if (MT != true)
        {
            if (!string.IsNullOrWhiteSpace(wheres))
                wheres += " And ";
            wheres += " (L.msg2 LIKE CONCAT('%|',S.item,'|%')) ";
        }

        SqlCommandText = "DECLARE @DT TABLE " +
            "(PLANTNO nvarchar(10)," +
            " ITEM nvarchar(20)); " +
            "INSERT @DT " +
            "SELECT S.plantno,REPLACE(REPLACE(I.item,'COD2','COD'),'pH1','pH') item " +
            "FROM [VOC].[dbo].[VOC_SPEC] S " +
            "JOIN [VOC].[dbo].[VOC_item] I ON S.item=I.item " +
            "JOIN [VOC].[dbo].[VOC_plant] P ON S.plantno=P.plantno; " +
            "DECLARE @caselist TABLE (PLANTID int,CASE_TTL int) " +
            "INSERT @caselist SELECT P.PLANTID,COUNT(S.item) as CASE_TTL " +
            "FROM @DT S " +
            "JOIN [VOC].[dbo].[VOC_MAIL_Log] L ON S.plantno=L.plantno AND L.msg1 LIKE CONCAT('%|',S.item,'|%') " +
            "JOIN [VOC].[dbo].[VOC_plant] P On L.plantno=P.plantno " +
            "WHERE CONVERT(nvarchar(10), CDATETIME, 111) BETWEEN @sdate AND @edate " +
            (wheres.Trim().Length > 0 ? "And " + wheres : "") + "GROUP BY P.PLANTID; ";
        SqlParameterAdd("@sdate", sdate);
        SqlParameterAdd("@edate", edate);

        SqlCommandText += "SELECT 'ALL' PLANTNO, " +
            "ISNULL(SUM(M.CASE_TTL),0) as CASE_TTL, " +
            "'' as CASE_RANK " +
            "FROM @caselist M " +
            "JOIN [VOC].[dbo].[VOC_plant] P On M.plantid=P.plantid ";

        return SqlFillDT();
    }

    public DataTable GetPIVOT廠棟異常件數(string plantno, string item, string sdate, string edate, string sort, bool MT)
    {
        SqlParameterClear();
        string wheres = "";
        if (plantno != "")
        {
            if (!string.IsNullOrWhiteSpace(wheres))
                wheres += " And ";
            wheres += " (P.plantno=@plantno) ";
            SqlParameterAdd("@plantno", plantno);
        }
        if (item != "")
        {
            if (!string.IsNullOrWhiteSpace(wheres))
                wheres += " And ";
            wheres += " (S.item=@item) ";
            SqlParameterAdd("@item", item);
        }
        if (MT != true)
        {
            if (!string.IsNullOrWhiteSpace(wheres))
                wheres += " And ";
            wheres += " (L.msg2 LIKE CONCAT('%|',S.item,'|%')) ";
        }

        SqlCommandText = "DELETE FROM [VOC].[dbo].[VOC_report]; " +
            "DECLARE @DT TABLE " +
            "(PLANTNO nvarchar(10)," +
            " ITEM nvarchar(20)); " +
            "INSERT @DT " +
            "SELECT S.plantno,REPLACE(REPLACE(I.item,'COD2','COD'),'pH1','pH') item " +
            "FROM [VOC].[dbo].[VOC_SPEC] S " +
            "JOIN [VOC].[dbo].[VOC_item] I ON S.item=I.item " +
            "JOIN [VOC].[dbo].[VOC_plant] P ON S.plantno=P.plantno; " +
            "INSERT INTO [VOC].[dbo].[VOC_report] " +
            "SELECT S.plantno,S.item,COUNT(S.item) qty " +
            "FROM @DT S " +
            "JOIN [VOC].[dbo].[VOC_MAIL_Log] L ON S.plantno=L.plantno AND L.msg1 LIKE CONCAT('%|',S.item,'|%') " +
            "JOIN [VOC].[dbo].[VOC_plant] P On L.plantno=P.plantno " +
            "WHERE CONVERT(nvarchar(10), CDATETIME, 111) BETWEEN @sdate AND @edate " +
            (wheres.Trim().Length > 0 ? "And " + wheres : "") + "GROUP BY S.plantno,S.item; " +
            "INSERT INTO [VOC].[dbo].[VOC_report] SELECT 'Total',item,SUM(qty) FROM [VOC].[dbo].[VOC_report] GROUP BY item; " +
            "INSERT INTO [VOC].[dbo].[VOC_report] SELECT plantno,'總計',SUM(qty) FROM [VOC].[dbo].[VOC_report] GROUP BY plantno; " +
            "SELECT DISTINCT P.plantid,P.plantno FROM [VOC].[dbo].[VOC_report] R " +
            "JOIN [VOC].[dbo].[VOC_plant] P On R.plantno=P.plantno ORDER BY plantid";
        SqlParameterAdd("@sdate", sdate);
        SqlParameterAdd("@edate", edate);
        DataTable PlantDT = SqlFillDT();

        if (PlantDT.Rows.Count == 0) return null;

        SqlCommandText = "SELECT * FROM (SELECT plantno,item,qty FROM [VOC].[dbo].[VOC_report] GROUP BY plantno,item,qty) K " +
            "PIVOT(sum(K.qty) FOR plantno IN (";

        for (int i = 0; i < PlantDT.Rows.Count; i++)
            SqlCommandText += (i == 0 ? "" : ",") + "[" + PlantDT.Rows[i][1].ToString() + "]";
        SqlCommandText += ",[Total])) PIV";

        return SqlFillDT();
    }

    public string Get廠棟異常件數最大排行(string plantno, string item, string sdate, string edate, string sort, bool MT)
    {
        SqlParameterClear();
        string wheres = "";
        if (plantno != "")
        {
            if (!string.IsNullOrWhiteSpace(wheres))
                wheres += " And ";
            wheres += " (P.plantno=@plantno) ";
            SqlParameterAdd("@plantno", plantno);
        }
        if (item != "")
        {
            if (!string.IsNullOrWhiteSpace(wheres))
                wheres += " And ";
            wheres += " (S.item=@item) ";
            SqlParameterAdd("@item", item);
        }
        if (MT != true)
        {
            if (!string.IsNullOrWhiteSpace(wheres))
                wheres += " And ";
            wheres += " (L.msg2 LIKE CONCAT('%|',S.item,'|%')) ";
        }

        SqlCommandText = "DECLARE @DT TABLE " +
            "(PLANTNO nvarchar(10)," +
            " ITEM nvarchar(20)); " +
            "INSERT @DT " +
            "SELECT S.plantno,REPLACE(REPLACE(I.item,'COD2','COD'),'pH1','pH') item " +
            "FROM [VOC].[dbo].[VOC_SPEC] S " +
            "JOIN [VOC].[dbo].[VOC_item] I ON S.item=I.item " +
            "JOIN [VOC].[dbo].[VOC_plant] P ON S.plantno=P.plantno; " +
            "DECLARE @caselist TABLE (PLANTID int,CASE_TTL int) " +
            "INSERT @caselist SELECT P.PLANTID,COUNT(S.item) as CASE_TTL " +
            "FROM @DT S " +
            "JOIN [VOC].[dbo].[VOC_MAIL_Log] L ON S.plantno=L.plantno AND L.msg1 LIKE CONCAT('%|',S.item,'|%') " +
            "JOIN [VOC].[dbo].[VOC_plant] P On L.plantno=P.plantno " +
            "WHERE CONVERT(nvarchar(10), CDATETIME, 111) BETWEEN @sdate AND @edate " +
            (wheres.Trim().Length > 0 ? "And " + wheres : "") + "GROUP BY P.PLANTID; ";
        SqlParameterAdd("@sdate", sdate);
        SqlParameterAdd("@edate", edate);

        SqlCommandText += "DECLARE @detailDT TABLE " +
            "(PLANTNO nvarchar(10)," +
            " PLANTID int," +
            " ITEM nvarchar(20)," +
            " CASE_TTL int," +
            " CASE_RANK int); " +
            "INSERT @detailDT " +
            "SELECT P.PLANTNO,P.PLANTID, ";

        if (item != "") SqlCommandText += "'" + item + "' ITEM, ";
        else SqlCommandText += "'' ITEM, ";

        SqlCommandText += "ISNULL(SUM(M.CASE_TTL),0) as CASE_TTL, " +
            "DENSE_RANK() OVER (ORDER BY SUM(M.CASE_TTL) DESC) as CASE_RANK " +
            "FROM @caselist M " +
            "JOIN [VOC].[dbo].[VOC_plant] P On M.plantid=P.plantid " +
            "GROUP BY P.PLANTNO,P.PLANTID ";

        if (sort == "廠區") SqlCommandText += "ORDER BY PLANTID; ";
        else if (sort == "異常件數(由大到小)+廠區") SqlCommandText += "ORDER BY CASE_RANK,PLANTID; ";
        else SqlCommandText += "ORDER BY CASE_RANK DESC,PLANTID; ";

        SqlCommandText += "SELECT MAX(CASE_RANK) as RANK_MAX FROM @detailDT ";

        return SqlExecuteScalarString();
    }

    public DataTable ListVOClog(string plant, string item, string sdate, string edate, bool MT, string stime, string stype, string change)
    {
        string PlantID = GetPlantID();
        SqlParameterClear();
        string wheres = "";
        if (plant != "")
        {
            if (!string.IsNullOrWhiteSpace(wheres))
                wheres += " And ";
            wheres += " (S.plantno=@plant) ";
            SqlParameterAdd("@plant", plant);
        }

        if (item != "")
        {
            if (!string.IsNullOrWhiteSpace(wheres))
                wheres += " And ";
            wheres += " (S.item=@item) ";
            SqlParameterAdd("@item", item);
        }

        if (MT != true)
        {
            if (!string.IsNullOrWhiteSpace(wheres))
                wheres += " And ";
            wheres += " (L.msg2 LIKE CONCAT('%|',S.item,'|%')) ";
        }

        SqlCommandText = "DECLARE @DT TABLE " +
            "(PLANTNO nvarchar(10)," +
            " ITEM nvarchar(20)); " +
            "INSERT @DT ";

        if (stype == "")
        {
            SqlCommandText += "SELECT S.plantno,REPLACE(REPLACE(I.item,'COD2','COD'),'pH1','pH') item " +
                "FROM [VOC].[dbo].[VOC_SPEC] S " +
                "JOIN [VOC].[dbo].[VOC_item] I ON S.item=I.item " +
                "JOIN [VOC].[dbo].[VOC_plant] P ON S.plantno=P.plantno ";

            if (PlantID.IndexOf("29") < 0)  //plantid: 29=ALL
                SqlCommandText += "WHERE P.plantid IN (" + PlantID + ") ";

            SqlCommandText += "UNION ";
        }

        SqlCommandText += "SELECT W.plantno,I.item " +
            "FROM [VOC].[dbo].[VOC_SCADA_WEB] W " +
            "JOIN [VOC].[dbo].[VOC_item] I ON W.item=I.item " +
            "JOIN [VOC].[dbo].[VOC_plant] P ON W.plantno=P.plantno " +
            "WHERE W.item LIKE '%雨水溝%' ";

        if (PlantID.IndexOf("29") < 0)  //plantid: 29=ALL
            SqlCommandText += "AND P.plantid IN (" + PlantID + ") ";

        if (stime == "") SqlCommandText += "; SELECT S.plantno,S.item,ROW_NUMBER() OVER(ORDER BY cdatetime) No,";
        else SqlCommandText += "SELECT DISTINCT S.plantno,";

        SqlCommandText += "cdatetime,msg,emp,reason,rdatetime,logid,msg1 FROM (";

        if (change != "Y")
        {
            if (stime == "") SqlCommandText += "SELECT S.plantno,S.item,";
            else SqlCommandText += "SELECT DISTINCT S.plantno,";

            SqlCommandText += "REPLACE(CONVERT(nvarchar(16), L.cdatetime, 120),'-','/') cdatetime,L.msg,IIF(L.empno='','',E.empname+'/'+E.notesid) emp," +
                "L.reason,REPLACE(CONVERT(nvarchar(16), L.rdatetime, 120),'-','/') rdatetime,L.logid,L.msg1 " +
                "FROM @DT S " +
                "JOIN [VOC].[dbo].[VOC_MAIL_Log] L ON S.plantno=L.plantno AND L.msg1 LIKE CONCAT('%|',S.item,'|%') " +
                "LEFT JOIN [UTIDB].[dbo].[Employee] E On L.empno=E.empno ";

            if (stime == "")
                SqlCommandText += "WHERE CONVERT(nvarchar(10), L.CDATETIME, 111) BETWEEN @sdate AND @edate ";
            else
                SqlCommandText += "WHERE REPLACE(CONVERT(nvarchar(16), L.CDATETIME, 120),'-','/')=@stime ";

            SqlCommandText += (wheres.Trim().Length > 0 ? "And " + wheres : "");
            SqlCommandText += "UNION ";
        }

        if (stime == "") SqlCommandText += "SELECT S.plantno, '' item,";
        else SqlCommandText += "SELECT DISTINCT S.plantno,";

        SqlCommandText += "REPLACE(CONVERT(nvarchar(16), S.cdatetime, 120),'-','/') cdatetime,S.msg,IIF(S.empno='','',E.empname+'/'+E.notesid) emp," +
            "S.reason,REPLACE(CONVERT(nvarchar(16), S.rdatetime, 120),'-','/') rdatetime,S.logid,S.msg1 " +
            "FROM [VOC].[dbo].[VOC_MAIL_Log] S " +
            "LEFT JOIN [UTIDB].[dbo].[Employee] E On S.empno=E.empno ";

        if (stime == "")
            SqlCommandText += "WHERE CONVERT(nvarchar(10), S.CDATETIME, 111) BETWEEN @sdate AND @edate ";
        else
            SqlCommandText += "WHERE REPLACE(CONVERT(nvarchar(16), S.CDATETIME, 120),'-','/')=@stime ";

        if (plant != "") SqlCommandText += "AND S.plantno=@plant ";
        SqlCommandText += "AND S.msg LIKE '%改排水%') S ";

        SqlCommandText += "ORDER BY cdatetime ";
        SqlParameterAdd("@sdate", sdate);
        SqlParameterAdd("@edate", edate);
        SqlParameterAdd("@stime", stime);
        return SqlFillDT();
    }

    public DataTable List最新讀值資料(string plantno, string item)
    {
        SqlParameterClear();
        SqlCommandText = "Select W.plantno,W.item,W.rvalue,P.plantid,I.itemid " +
            "From [VOC].[dbo].[VOC_SPEC] S " +
            "Join [VOC].[dbo].[VOC_item] I On S.item=I.item " +
            "Join [VOC].[dbo].[VOC_plant] P On S.plantno=P.plantno " +
            "Join [VOC].[dbo].[VOC_SCADA_WEB] W On S.plantno=W.plantno And S.item=W.item " +
            "Where S.source=3 ";
        if (plantno != "")
        {
            SqlCommandText += "And S.plantno = @plantno ";
            SqlParameterAdd("@plantno", plantno);
        }
        if (item != "")
        {
            SqlCommandText += "And S.item = @item ";
            SqlParameterAdd("@item", item);
        }
        SqlCommandText += "Order By plantid,seqno ";
        return SqlFillDT();
    }

    public bool UpdateQA(Hashtable hrow, string prvalue)
    {
        try
        {
            SqlBeginTransaction();
            SqlParameterClear();
            SqlCommandText = "Select plantno From [VOC].[dbo].[VOC_plant] Where plantid=@plantid";
            SqlParameterAdd("@plantid", hrow["plant"]);
            string plantno = SqlExecuteScalarString();

            SqlParameterClear();
            SqlCommandText = "Select item From [VOC].[dbo].[VOC_item] Where itemid=@itemid";
            SqlParameterAdd("@itemid", hrow["item"]);
            string item = SqlExecuteScalarString();

            SqlParameterClear();
            SqlCommandText = "Update [VOC].[dbo].[VOC_SCADA_WEB] Set rvalue=@rvalue,cdatetime=@cdatetime " +
                "Where plantno=@plantno And item=@item";
            SqlParameterAdd("@plantno", plantno);
            SqlParameterAdd("@item", item);
            SqlParameterAdd("@rvalue", hrow["rvalue"]);
            SqlParameterAdd("@cdatetime", DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss.000"));
            SqlExecuteNonQuery();

            SqlParameterClear();
            SqlCommandText = "INSERT INTO [VOC].[dbo].[VOC_tranlog] " +
                "([empno],[logtype],[databefore],[dataafter],[cdatetime],[remark]) " +
                "VALUES (@empno,@logtype,@databefore,@dataafter,@cdatetime,@remark)";
            SqlParameterAdd("@empno", AppConfig.Sess_UserEmpNo);
            SqlParameterAdd("@logtype", "M");
            SqlParameterAdd("@databefore", plantno + "/" + item + "/" + prvalue);
            SqlParameterAdd("@dataafter", plantno + "/" + item + "/" + hrow["rvalue"]);
            SqlParameterAdd("@cdatetime", DateTime.Now);
            SqlParameterAdd("@remark", hrow["remark"]);
            SqlExecuteNonQuery();
            SqlCommit();
        }
        catch (Exception ex)
        {
            SqlRollback();
            _Exception = ex.Message;
            return false;
        }

        return true;
    }

    public bool Update異常原因(Hashtable hrow)
    {
        try
        {
            SqlBeginTransaction();
            SqlParameterClear();
            SqlCommandText = "Update [VOC].[dbo].[VOC_MAIL_Log] " +
                "Set empno=@empno,reason=@reason,rdatetime=@rdatetime Where logid=@logid";
            SqlParameterAdd("@empno", AppConfig.Sess_UserEmpNo);
            SqlParameterAdd("@reason", hrow["reason"].ToStringTrim());
            SqlParameterAdd("@rdatetime", DateTime.Now);
            SqlParameterAdd("@logid", hrow["logid"]);
            SqlExecuteNonQuery();
            SqlCommit();
        }
        catch (Exception ex)
        {
            SqlRollback();
            _Exception = ex.Message;
            return false;
        }
        return true;
    }

    public bool SendMail_異常原因回覆(Hashtable hrow)
    {
        try
        {
            string Albee = "Albee_Weng@aseglobal.com";
            string Bermy = "Bermy_Po@aseglobal.com";
            DataTable dtb, mailto, mailcc, phoneto, phonecc;
            int rcnt = 0, rows;
            string item, remark, source, emptycell;
            string sRed = "";
            string body = "", style, sColor, light, sdate;
            string[] ArrMsg, ArrMsg1, ArrColor;
            string url = "http://khfacsv01/VOC/";

            string plantno = hrow["plantno"].ToStringTrim();
            string reason = hrow["reason"].ToStringTrim().Replace("<", "&lt").Replace(">", "&gt");
            string cdatetime = hrow["cdatetime"].ToStringTrim();
            string cdatetime1 = hrow["cdatetime1"].ToStringTrim();
            string msg = hrow["msg"].ToStringTrim();
            string msg1 = hrow["msg1"].ToStringTrim();
            string msg2 = hrow["msg2"].ToStringTrim();
            Boolean rtn;

            dtb = GetData(plantno, cdatetime1);
            rows = dtb.Rows.Count;

            body = "<html><body><label>Dear Sir,<br />異常原因：<font style='color: Blue'><b>" + reason.Replace("\n", "<br />") + "</b></font></label><br /><br />" +
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

            foreach (DataRow row in dtb.Rows)
            {
                body += "<tr style='background-color: #FFFFFF; color: black; font-weight: bold; font-size: small;'>";
                if (rcnt == 0) body += "<td rowspan='" + rows + "' style='text-align: center'><strong>" + plantno + "</strong></td>";

                rcnt++;
                sdate = "";
                item = row["item"].ToString();
                emptycell = row["emptycell"].ToString();

                for (int i = 3; i < 14; i++)
                {
                    row[i] = row[i].ToString().Replace(",", "");

                    if (row[i].ToString() == "")
                        if (emptycell.IndexOf(i + ";") < 0) row[i] = "異常";

                    //統一數字欄位到小數二位, 第三位四捨五入; 導電度 & 日累積水量 四捨五入到整數
                    if (row[i].ToString() != "" && row[i].ToString() != "-" && row[i].ToString() != "N/A" &&
                        row[i].ToString() != "建置中" && row[i].ToString() != "斷訊" &&
                        row[i].ToString() != "異常" && row[i].ToString() != "保養中")
                    {
                        if (row["item"].ToString() == "導電度" || row["item"].ToString() == "日累積水量")
                            row[i] = ChangeData(row[i].ToString(), 0);
                        else row[i] = ChangeData(row[i].ToString(), 2);
                    }
                }

                ArrMsg = msg.Replace("；", ";").Split(';');
                for (int i = 0; i < ArrMsg.Length; i++)
                {
                    ArrMsg1 = ArrMsg[i].Replace("：", ":").Split(':');
                    for (int j = 0; j < ArrMsg1.Length; j++)
                    {
                        if (ArrMsg1[j] == item)
                        {
                            if (ArrMsg1[j + 1].IndexOf("保養中") > -1)
                            {
                                if (ArrMsg.Length > i + 1)
                                {
                                    if (ArrMsg[i + 1].IndexOf("從") > -1) sdate = ArrMsg[i + 1];
                                }
                            }
                        }
                    }
                }

                remark = row["remark"].ToString().Substring(0, row["remark"].ToString().IndexOf("|"));
                source = row["remark"].ToString().Substring(row["remark"].ToString().IndexOf("|") + 1, 1);
                emptycell = row["emptycell"].ToString();

                if (item.IndexOf("VOC") > -1)
                {
                    body += "<td style='text-align: center; background-color: YellowGreen;'><strong>" + item + "</strong></td>" +
                    "<td style='text-align: center; background-color: YellowGreen;'><strong>" + row["unit"] + "</strong></td>";
                }
                else if (source == "2") //CWMS
                {
                    body += "<td style='text-align: center; background-color: Orange;'><strong>" + item + "</strong></td>" +
                    "<td style='text-align: center; background-color: Orange;'><strong>" + row["unit"] + "</strong></td>";
                }
                else
                {
                    body += "<td style='text-align: center; background-color: DodgerBlue; color: White;'><strong>" + item + "</strong></td>" +
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

                using (dbVOC db = new dbVOC()) ArrColor = db.GetData(row, msg1, ref sRed);
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

                    body += style;

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
                if (sdate != "") body += (remark == "" ? "" : ";") + sdate;
                body += "</strong></td></tr>";
            }

            body += "</table><table style='border: black 1px solid'><tr style='font-weight: bold;'>" +
                "<td colspan='16' style='text-align: left'><a href='" + url + "'>進行查看</a>" +
                "</td></tr></table></body></html>";

            SmtpMessage sm = new SmtpMessage();
            string from = MTFlowBase.GetEmail(AppConfig.Sess_User員工ID);
            int idx = from.IndexOf("@");
            if (idx < 0) idx = from.Length;
            string fromname = from.Substring(0, idx).Replace("_", " ");
            sm.Message.From = new MailAddress(from, fromname);

            using (dbVOC db = new dbVOC())
            {
                mailto = db.GetMailList(sRed, plantno, "TO");
                mailcc = db.GetMailList(sRed, plantno, "CC");
            }

            foreach (DataRow mrow in mailto.Rows)
                sm.Message.To.Add(mrow["NotesID"].ToString().Replace(" ", "_") + "@aseglobal.com");

            foreach (DataRow mrow in mailcc.Rows)
                sm.Message.CC.Add(mrow["NotesID"].ToString().Replace(" ", "_") + "@aseglobal.com");

            if (plantno != "K14B" && msg.IndexOf("＞允收值") > -1)
            {
                using (dbVOC db = new dbVOC())
                    mailcc = db.GetMailList("水Alert", "K14B", "TO");
                foreach (DataRow mrow in mailcc.Rows)
                    sm.Message.CC.Add(mrow["NotesID"].ToString().Replace(" ", "_") + "@aseglobal.com");
            }

            //sm.Message.Bcc.Add(Albee);
            sm.Message.Bcc.Add(Bermy);

            sm.Message.Subject = string.Format("【異常原因回覆】「法遵平台」即時監控狀況 : {0}-{1} (Security C)", plantno, cdatetime);
            sm.Message.IsBodyHtml = true;
            sm.Message.Body = body;
            sm.Message.BodyEncoding = Encoding.UTF8;
            sm.Send(sm.Message);

            //if (sRed.IndexOf("OOS") > -1 || sRed.IndexOf("OOC") > -1 || sRed.IndexOf("斷訊") > -1)
            //{
            //    using (dbVOC db = new dbVOC())
            //    {
            //        msg = "【異常原因回覆】" + plantno + " " + cdatetime + " " + reason.Replace("&lt", "<").Replace("&gt", ">");

            //        phoneto = db.GetCellPhoneList(sRed, plantno, "TO");
            //        phonecc = db.GetCellPhoneList(sRed, plantno, "CC");

            //        foreach (DataRow mrow in phoneto.Rows)
            //        {
            //            rtn = SendSMS.SendSMSByCHTProxy(msg, mrow["CellPhone"].ToString(), 1);
            //            //db.InsertSMS(mrow, "SendSMS:" + (rtn == true ? "success" : "fail"));
            //            db.InsertSMS(mrow, msg, (rtn == true ? 1 : 0));
            //        }

            //        if (phoneto.Rows.Count > 0)
            //        {
            //            foreach (DataRow mrow in phonecc.Rows)
            //            {
            //                rtn = SendSMS.SendSMSByCHTProxy(msg, mrow["CellPhone"].ToString(), 1);
            //                //db.InsertSMS(mrow, "SendSMS:" + (rtn == true ? "success" : "fail"));
            //                db.InsertSMS(mrow, msg, (rtn == true ? 1 : 0));
            //            }
            //        }

            //        if (plantno != "K14B" && msg1.IndexOf("＞允收值") > -1)
            //        {
            //            phonecc = db.GetCellPhoneList("水Alert-K14B", "K14B", "TO");
            //            if (phoneto.Rows.Count > 0)
            //            {
            //                foreach (DataRow mrow in phonecc.Rows)
            //                {
            //                    rtn = SendSMS.SendSMSByCHTProxy(msg, mrow["CellPhone"].ToString(), 1);
            //                    //db.InsertSMS(mrow, "SendSMS:" + (rtn == true ? "success" : "fail"));
            //                    db.InsertSMS(mrow, msg, (rtn == true ? 1 : 0));
            //                }
            //            }
            //        }
            //    }
            //}
        }
        catch (Exception ex)
        {
            _Exception = ex.Message;
            return false;
        }
        return true;
    }

    public bool SendMail_異常原因回覆_雨水溝(Hashtable hrow)
    {
        try
        {
            string Albee = "Albee_Weng@aseglobal.com";
            string Bermy = "Bermy_Po@aseglobal.com";
            DataTable dtb, mailto, mailcc;
            int rcnt = 0, rows;
            string item, sRed = "", body = "", ArrColor, light, sdate;
            string[] ArrMsg, ArrMsg1;
            string url = "http://khfacsv01/VOC/RainGutter.aspx";

            string plantno = hrow["plantno"].ToStringTrim();
            string reason = hrow["reason"].ToStringTrim().Replace("<", "&lt").Replace(">", "&gt");
            string cdatetime = hrow["cdatetime"].ToStringTrim();
            string cdatetime1 = hrow["cdatetime1"].ToStringTrim();
            string msg = hrow["msg"].ToStringTrim();
            string msg1 = hrow["msg1"].ToStringTrim();

            int sflg = plantno == "K1" || plantno == "K9" ? 1 : 0;

            dtb = GetData雨水溝(plantno, cdatetime1);
            rows = dtb.Rows.Count;

            body = "<html><body><label>Dear Sir,<br />異常原因：<font style='color: Blue'><b>" + reason.Replace("\n", "<br />") + "</b></font></label><br /><br />" +
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

            foreach (DataRow row in dtb.Rows)
            {
                body += "<tr style='background-color: #FFFFFF; color: black; font-weight: bold; font-size: small;'>";
                if (rcnt == 0) body += "<td rowspan='" + rows + "' style='text-align: center'><strong>" + plantno + "</strong></td>";

                rcnt++;
                sdate = "";
                item = row["item"].ToString();

                ArrMsg = msg.Replace("；", ";").Split(';');
                for (int i = 0; i < ArrMsg.Length; i++)
                {
                    ArrMsg1 = ArrMsg[i].Replace("：", ":").Split(':');
                    for (int j = 0; j < ArrMsg1.Length; j++)
                    {
                        if (ArrMsg1[j] == item)
                        {
                            if (ArrMsg1[j + 1].IndexOf("保養中") > -1)
                            {
                                if (ArrMsg.Length > i + 1)
                                {
                                    if (ArrMsg[i + 1].IndexOf("從") > -1) sdate = ArrMsg[i + 1];
                                }
                            }
                        }
                    }
                }

                body += "<td style='text-align: center; background-color: DodgerBlue; color: White'><strong>" + row["item"] + "</strong></td>" +
                    "<td style='text-align: center'><strong>" + row["Sum24H"] + "</strong></td>" +
                    "<td style='text-align: center; background-color: Cornsilk";
                if (row["rvalue"].ToString() == "斷訊") body += "; color: Red; bordercolor: Black";
                body += "'><strong>" + row["rvalue"] + "</strong></td>";

                using (dbVOC db = new dbVOC()) ArrColor = db.GetData雨水溝預警(row, msg1, ref sRed);

                light = (ArrColor == "G" ? "Green" : (ArrColor == "O" ? "Orange" : "Red"));

                body += "<td style='text-align: center'><img src='file://khfacsv01/VOCimages$/Circle" + light + ".jpg'></td>" +
                    "<td style='text-align: center'><strong>";
                if (sdate != "") body += sdate;
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

            body += "</table><table style='border: black 1px solid' width='" + (sflg == 0 ? 600 : 900) + "px'><tr style='font-weight: bold;'>" +
                "<td colspan='" + (sflg == 0 ? 6 : 12) + "' style='text-align: left'><a href='" + url + "'>進行查看</a>" +
                "</td></tr></table></body></html>";

            SmtpMessage sm = new SmtpMessage();
            string from = MTFlowBase.GetEmail(AppConfig.Sess_User員工ID);
            int idx = from.IndexOf("@");
            if (idx < 0) idx = from.Length;
            string fromname = from.Substring(0, idx).Replace("_", " ");
            sm.Message.From = new MailAddress(from, fromname);

            using (dbVOC db = new dbVOC())
            {
                mailto = db.GetMailList(sRed, plantno, "TO");
                mailcc = db.GetMailList(sRed, plantno, "CC");
            }

            foreach (DataRow mrow in mailto.Rows)
                sm.Message.To.Add(mrow["NotesID"].ToString().Replace(" ", "_") + "@aseglobal.com");

            foreach (DataRow mrow in mailcc.Rows)
                sm.Message.CC.Add(mrow["NotesID"].ToString().Replace(" ", "_") + "@aseglobal.com");

            sm.Message.Bcc.Add(Albee);
            sm.Message.Bcc.Add(Bermy);

            sm.Message.Subject = string.Format("【異常原因回覆】「法遵平台-雨水溝預警」即時監控狀況 : {0}-{1} (Security C)", plantno, cdatetime);
            sm.Message.IsBodyHtml = true;
            sm.Message.Body = body;
            sm.Message.BodyEncoding = Encoding.UTF8;
            sm.Send(sm.Message);
        }
        catch (Exception ex)
        {
            _Exception = ex.Message;
            return false;
        }
        return true;
    }

    public bool SendMail_異常原因回覆_水質異常(Hashtable hrow)
    {
        try
        {
            string Albee = "Albee_Weng@aseglobal.com";
            string Bermy = "Bermy_Po@aseglobal.com";
            DataTable dtb, mailto, mailcc;
            int start, rcnt = 0, r;
            string item, cvalue, OOS, OOC, body, url1, sdate, edate;
            string[] Arritem, Arritem1;
            string url = "http://khfacsv01/VOC/WaterUrgent.aspx";

            string plantno = hrow["plantno"].ToStringTrim();
            string reason = hrow["reason"].ToStringTrim().Replace("<", "&lt").Replace(">", "&gt");
            string cdatetime = hrow["cdatetime"].ToStringTrim();
            sdate = edate = cdatetime.Substring(0, 10);
            string stime = cdatetime.Substring(0, 16);

            string msg = hrow["msg1"].ToStringTrim();

            dtb = GetData水質異常(plantno, cdatetime, msg);

            if (dtb.Rows.Count > 0)
            {
                start = msg.IndexOf("|");
                Arritem = msg.Substring(start).Replace("：", ":").Replace("；", ";").Split(';');
                rcnt = Arritem.Length - 1;

                body = "<html><body><label>Dear Sir,<br />異常原因：<font style='color: Blue'><b>" + reason.Replace("\n", "<br />") + "</b></font></label><br /><br />" +
                    "<table style='border: black 1px solid' width='450px'>" +
                    "<tr style='background-color: #CCFFFF; font-weight: bold; font-size: small;'>" +
                    "<td style='text-align: center'><strong>廠區</strong></td>" +
                    "<td style='text-align: center'><strong>項目</strong></td>" +
                    "<td style='text-align: center'><strong>OOS</strong></td>" +
                    "<td style='text-align: center'><strong>OOC</strong></td>" +
                    "<td style='text-align: center'><strong>最新讀值</strong></td></tr>" +
                    "<tr><td rowspan='" + rcnt + "' style='text-align: center; background-color: #FFFFFF;'><strong>K14B</strong></td>";

                r = 0;
                for (int i = 0; i < rcnt; i++)
                {
                    r++;
                    Arritem1 = Arritem[i].Split(':');
                    item = Arritem1[0].Replace("|", "");
                    cvalue = Arritem1[1];
                    OOS = GetSPEC("K14B", item, "OOS");
                    OOC = GetSPEC("K14B", item, "OOC");

                    body += "<td style='text-align: center; background-color: #FFFFFF;'><strong>" + item + "</strong></td>" +
                        "<td style='text-align: center; background-color: #FFFFFF;'><strong>" + OOS + "</strong></td>" +
                        "<td style='text-align: center; background-color: #FFFFFF;'><strong>" + OOC + "</strong></td>" +
                        "<td style='text-align: center; background-color: #FFFFFF;'><strong>" + cvalue + "</strong></td>" +
                        "</tr>";

                    if (r != rcnt) body += "<tr>";
                }

                url1 = "http://khfacsv01/VOC/VOCreason.aspx?plantno=" + plantno + "&sdate=" + sdate + "&edate=" + edate + "&stime=" + stime;
                body += "</table><table style='border: black 1px solid' width='450px'><tr style='font-weight: bold;'>" +
                    "<td colspan='5' style='text-align: left'>" +
                    //"<a href='" + url + "'>進行查看</a>&nbsp&nbsp&nbsp" +
                    "<a href='" + url1 + "'>異常原因回覆</a>" +
                    "</td></tr></table></body></html>";

                SmtpMessage sm = new SmtpMessage();
                string from = MTFlowBase.GetEmail(AppConfig.Sess_User員工ID);
                int idx = from.IndexOf("@");
                if (idx < 0) idx = from.Length;
                string fromname = from.Substring(0, idx).Replace("_", " ");
                sm.Message.From = new MailAddress(from, fromname);

                using (dbVOC db = new dbVOC())
                {
                    mailto = db.GetMailList("水質異常", plantno, "TO");
                    mailcc = db.GetMailList("水質異常", plantno, "CC");
                }

                foreach (DataRow mrow in mailto.Rows)
                    sm.Message.To.Add(mrow["NotesID"].ToString().Replace(" ", "_") + "@aseglobal.com");

                foreach (DataRow mrow in mailcc.Rows)
                    sm.Message.CC.Add(mrow["NotesID"].ToString().Replace(" ", "_") + "@aseglobal.com");

                if (plantno != "K14B")
                {
                    using (dbVOC db = new dbVOC())
                        mailcc = db.GetMailList("水質異常", "K14B", "TO");
                    foreach (DataRow mrow in mailcc.Rows)
                        sm.Message.CC.Add(mrow["NotesID"].ToString().Replace(" ", "_") + "@aseglobal.com");
                }

                sm.Message.To.Add(Bermy);
                sm.Message.To.Add("HankJH_Wang@aseglobal.com");
                sm.Message.To.Add("YG_Tsao@aseglobal.com");

                //sm.Message.Bcc.Add(Albee);
                //sm.Message.Bcc.Add(Bermy);

                if (sm.Message.To.Count == 0) return false;

                sm.Message.Subject = string.Format("【異常原因回覆】「法遵平台--中水放流管制」即時監控狀況 : {0}-{1} (Security C)", plantno, cdatetime);
                sm.Message.IsBodyHtml = true;
                sm.Message.Body = body;
                sm.Message.BodyEncoding = Encoding.UTF8;
                sm.Send(sm.Message);
            }
        }
        catch (Exception ex)
        {
            _Exception = ex.Message;
            return false;
        }
        return true;
    }

    public bool SendMail_異常原因回覆_改排水(Hashtable hrow)
    {
        try
        {
            string Albee = "Albee_Weng@aseglobal.com";
            string Bermy = "Bermy_Po@aseglobal.com";
            DataTable dtb, mailto, mailcc;
            int start, rcnt = 0, r;
            string item, cvalue, OOS, OOC, body, url1, sdate, edate;
            string[] ArrReason;
            string url = "http://khfacsv01/VOC/WaterUrgent.aspx";

            string plantno = hrow["plantno"].ToStringTrim();
            string reason = hrow["reason"].ToStringTrim().Replace("<", "&lt").Replace(">", "&gt");
            string cdatetime = hrow["cdatetime"].ToStringTrim();
            sdate = edate = cdatetime.Substring(0, 10);
            string stime = cdatetime.Substring(0, 16);

            string msg = hrow["msg1"].ToStringTrim();

            dtb = GetData水質異常(plantno, cdatetime, msg);

            if (dtb.Rows.Count > 0)
            {
                ArrReason = msg.Replace("：", ":").Split(':');

                body = "<html><body><label>Dear Sir,<br />異常原因：<font style='color: Blue'><b>" + reason.Replace("\n", "<br />") + "</b></font><br /><br />" +
                    "改排水原因：<font style='color: Red'><b>" + ArrReason[1] + "</b></font><br /><br /></label>";

                url1 = "http://khfacsv01/VOC/VOCreason.aspx?plantno=" + plantno + "&sdate=" + sdate + "&edate=" + edate + "&stime=" + stime + "&change=Y";
                body += "<table><tr style='font-weight: bold;'>" +
                    "<td style='text-align: left'>" +
                    //"<a href='" + url + "'>進行查看</a>&nbsp&nbsp&nbsp" +
                    "<a href='" + url1 + "'>異常原因回覆</a>" +
                    "</td></tr></table></body></html>";

                SmtpMessage sm = new SmtpMessage();
                string from = MTFlowBase.GetEmail(AppConfig.Sess_User員工ID);
                int idx = from.IndexOf("@");
                if (idx < 0) idx = from.Length;
                string fromname = from.Substring(0, idx).Replace("_", " ");
                sm.Message.From = new MailAddress(from, fromname);

                using (dbVOC db = new dbVOC())
                {
                    mailto = db.GetMailList("水質異常", plantno, "TO");
                    mailcc = db.GetMailList("水質異常", plantno, "CC");
                }

                foreach (DataRow mrow in mailto.Rows)
                    sm.Message.To.Add(mrow["NotesID"].ToString().Replace(" ", "_") + "@aseglobal.com");

                foreach (DataRow mrow in mailcc.Rows)
                    sm.Message.CC.Add(mrow["NotesID"].ToString().Replace(" ", "_") + "@aseglobal.com");

                if (plantno != "K14B")
                {
                    using (dbVOC db = new dbVOC())
                        mailcc = db.GetMailList("水質異常", "K14B", "TO");
                    foreach (DataRow mrow in mailcc.Rows)
                        sm.Message.CC.Add(mrow["NotesID"].ToString().Replace(" ", "_") + "@aseglobal.com");
                }

                sm.Message.To.Add(Bermy);
                sm.Message.To.Add("HankJH_Wang@aseglobal.com");
                sm.Message.To.Add("YG_Tsao@aseglobal.com");

                //sm.Message.Bcc.Add(Albee);
                //sm.Message.Bcc.Add(Bermy);

                if (sm.Message.To.Count == 0) return false;

                sm.Message.Subject = string.Format("【異常原因回覆】「法遵平台--中水放流管制」即時監控狀況 : {0}-{1} (Security C)", plantno, cdatetime);
                sm.Message.IsBodyHtml = true;
                sm.Message.Body = body;
                sm.Message.BodyEncoding = Encoding.UTF8;
                sm.Send(sm.Message);
            }
        }
        catch (Exception ex)
        {
            _Exception = ex.Message;
            return false;
        }
        return true;
    }

    public DataTable GetData(string plantno, string cdatetime)
    {
        SqlParameterClear();
        SqlCommandText = "Select S.plantno,Replace(Replace(S.item,'COD2','COD'),'pH1','pH') item,I.unit,S.LAW,H.OOS,H.OOC,H.alert1 alert,H.recv," +
            "H.OOS_HH,H.OOC_H,H.alert alert1,H.OOS_HH1,H.OOC_H1,Replace(Replace(Replace(Replace(H.rvalue,'N.D',0),'<0.05',0),'<0.02',0),'<0.01',0) rvalue," +
            "P.plantid,S.seqno,H.broken,concat(Iif(H.rvalue='N.D','N.D',null),Iif(H.rvalue='<0.05','<0.05',null),Iif(H.rvalue='<0.02','<0.02',null)," +
            "Iif(H.rvalue='<0.01','<0.01',null),'|',S.source) remark,E.emptycell " +
            "From [VOC].[dbo].[VOC_SPEC] S " +
            "Join [VOC].[dbo].[VOC_plant] P On S.plantno=P.plantno " +
            "Join [VOC].[dbo].[VOC_item] I On S.item=I.item " +
            "Join [VOC].[dbo].[VOC_SCADA_HIST] H On S.plantno=H.plantno And S.item=H.item " +
            "Left Join [VOC].[dbo].[VOC_EmptyCell] E On S.plantno=E.plantno And S.item=E.item " +
            "Where S.plantno=@plantno And H.cdatetime Between @sdatetime And @edatetime " +
            "Order By plantid,seqno ";
        SqlParameterAdd("@plantno", plantno);
        SqlParameterAdd("@sdatetime", cdatetime);
        SqlParameterAdd("@edatetime", Convert.ToDateTime(cdatetime).AddMinutes(5).ToString("yyyy/MM/dd HH:mm:ss"));
        return SqlFillDT();
    }

    public DataTable GetData雨水溝(string plantno, string cdatetime)
    {
        DateTime dt = Convert.ToDateTime(cdatetime);
        string ctime1 = dt.AddMinutes(-15).ToString("yyyy/MM/dd HH:mm:ss");
        string ctime2 = dt.AddMinutes(-30).ToString("yyyy/MM/dd HH:mm:ss");

        int sflg = plantno == "K1" || plantno == "K9" ? 1 : 0;

        SqlParameterClear();

        if (sflg == 0)
        {
            SqlCommandText = "Select W.plantno,W.item,H.rvalue,P.plantid,I.itemid,H.broken,Convert(nvarchar,TwentyFourHours) Sum24H " +
                "From [VOC].[dbo].[VOC_SCADA_WEB] W " +
                "Join [VOC].[dbo].[VOC_plant] P On W.plantno=P.plantno " +
                "Join [VOC].[dbo].[VOC_item] I On W.item=I.item " +
                "Join [VOC].[dbo].[VOC_SCADA_HIST] H On W.plantno=H.plantno And W.item=H.item " +
                "Left Join [PMS].[dbo].[Water_WindRainHistValue] On UpdateTime=@stime ";
        }
        else
        {
            SqlCommandText = "Select W.plantno,W.item,P.plantid,I.itemid,H.broken,Convert(nvarchar,TwentyFourHours) Sum24H," +
                "Iif(H.rvalue in ('斷訊','異常','保養中'),H.rvalue,Iif(value2 is null Or value3 is null,0,Iif(value2 is not null And value3 is not null " +
                "And Convert(float,H.rvalue)>Convert(float,value2) And Convert(float,value2)>Convert(float,value3),1,0))) rvalue," +
                "@stime datetime1,H.rvalue value1,@stime1 datetime2,value2,@stime2 datetime3,value3 " +
                "From [VOC].[dbo].[VOC_SCADA_WEB] W " +
                "Join [VOC].[dbo].[VOC_plant] P On W.plantno=P.plantno " +
                "Join [VOC].[dbo].[VOC_item] I On W.item=I.item " +
                "Join [VOC].[dbo].[VOC_SCADA_HIST] H On W.plantno=H.plantno And W.item=H.item " +
                "Left Join [PMS].[dbo].[Water_WindRainHistValue] On UpdateTime=@stime " +
                "Left Join (Select plantno,item,rvalue value2 From [VOC].[dbo].[VOC_SCADA_HIST] Where plantno=@plantno And item like '%雨水溝%' And cdatetime Between @stime1 And @etime1) W1 On W.plantno=W1.plantno And W.item=W1.item " +
                "Left Join (Select plantno,item,rvalue value3 From [VOC].[dbo].[VOC_SCADA_HIST] Where plantno=@plantno And item like '%雨水溝%' And cdatetime Between @stime2 And @etime2) W2 On W.plantno=W2.plantno And W.item=W2.item ";
        }

        SqlCommandText += "Where W.plantno=@plantno And W.item Like '%雨水溝%' And H.cdatetime Between @stime And @etime Order By plantid,itemid ";
        SqlParameterAdd("@plantno", plantno);
        SqlParameterAdd("@stime", cdatetime);
        SqlParameterAdd("@etime", Convert.ToDateTime(cdatetime).AddMinutes(5).ToString("yyyy/MM/dd HH:mm:ss"));
        SqlParameterAdd("@stime1", ctime1);
        SqlParameterAdd("@etime1", Convert.ToDateTime(ctime1).AddMinutes(5).ToString("yyyy/MM/dd HH:mm:ss"));
        SqlParameterAdd("@stime2", ctime2);
        SqlParameterAdd("@etime2", Convert.ToDateTime(ctime2).AddMinutes(5).ToString("yyyy/MM/dd HH:mm:ss"));
        return SqlFillDT();
    }

    public DataTable GetData水質異常(DateTime cdatetime)
    {
        SqlParameterClear();
        SqlCommandText = "Select T.plantno,T.item,OOS,OOC,CurrentValue cValue " +
            "From [VOC].[dbo].[VOC_SCADA_Tag] T " +
            "Join [VOC].[dbo].[VOC_SPEC] S On T.plantno=S.plantno " +
            "And Iif(T.item='COD','COD2',Iif(T.item='COD1','COD2',Iif(T.item='pH','pH1',Iif(T.item='pH2','pH1',T.item))))=S.item " +
            "Where T.plantno='K14B' And T.item Not in ('流量1','流量2') And cdatetime=@cdatetime " +
            "Order By item";
        SqlParameterAdd("@cdatetime", cdatetime.ToString("yyyy/MM/dd HH:mm:ss"));
        return SqlFillDT();
    }

    public DataTable GetData水質異常(string plantno, string cdatetime, string msg)
    {
        SqlParameterClear();
        SqlCommandText = "Select plantno,msg1 " +
            "From [VOC].[dbo].[VOC_MAIL_Log] " +
            "Where plantno=@plantno And cdatetime=@cdatetime And msg1=@msg";
        SqlParameterAdd("@plantno", plantno);
        SqlParameterAdd("@cdatetime", cdatetime);
        SqlParameterAdd("@msg", msg);
        return SqlFillDT();
    }

    public DataTable GetData水質廠區(int type)
    {
        SqlCommandText = "Select Distinct plantid,P.plantno " +
            "From [VOC].[dbo].[VOC_SCADA_Tag] T " +
            "Join [VOC].[dbo].[VOC_plant] P ON T.plantno=P.plantno ";
        if (type == 1) SqlCommandText += "Where T.plantno!='K14B' ";
        SqlCommandText += "Order By plantid";
        return SqlFillDT();
    }

    public DataTable List改排水原因()
    {
        SqlCommandText = "Select reasonid,reason From [VOC].[dbo].[VOC_reason]";
        return SqlFillDT();
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

    public string[] GetData(DataRow row, string msg, ref string sRed)
    {
        //紅燈條件：最新讀值>=OOS
        //橘燈條件：OOC<=最新讀值<OOS 或 SCADA與CWMS之管制值<>SPEC
        //黃燈條件：Alert<最新讀值<OOC
        //綠燈條件：正常狀態
        string[] ArrColor = { "White", "White", "White", "White", "White", "G" };
        string sPlant = row["plantno"].ToString();
        string sItem = row["item"].ToString();
        string sData, msg0;
        bool bWater = (sItem.IndexOf("pH") > -1 || sItem.IndexOf("Cu") > -1 || sItem.IndexOf("Ni") > -1 ||
            sItem.IndexOf("SS") > -1 || sItem.IndexOf("COD") > -1);
        int len, idx;

        if ((sItem.IndexOf("pH") < 0 && sItem != "溫度") || (sItem == "溫度" && sPlant != "K21"))
        {
            string sOOS = row["OOS"].ToString();
            string sOOC = row["OOC"].ToString();
            string sAlert = row["Alert"].ToString();
            string sRecv = row["Recv"].ToString();
            string sOOS_HH = row["OOS_HH"].ToString();
            string sOOC_H = row["OOC_H"].ToString();
            string sAlert1 = row["Alert1"].ToString();
            string sOOS_HH1 = row["OOS_HH1"].ToString();
            string sOOC_H1 = row["OOC_H1"].ToString();
            string sWEB = row["rvalue"].ToString();
            string sBroken = row["broken"].ToString();
            string sType = (sItem.IndexOf("VOC") > -1 ? "空" : "水");


            //if ((sOOS_HH == "-" || sOOS_HH == "N/A" || sOOS_HH == "建置中" || sOOS_HH == "斷訊" || sOOS_HH == "異常") &&
            //    (sOOC_H == "-" || sOOC_H == "N/A" || sOOC_H == "建置中" || sOOC_H == "斷訊" || sOOC_H == "異常") &&
            //    (sAlert1 == "-" || sAlert1 == "N/A" || sAlert1 == "建置中" || sAlert1 == "斷訊" || sAlert1 == "異常") && sWEB != "")
            if ((sOOS_HH == "-" || sOOS_HH == "N/A" || sOOS_HH == "建置中" || sOOS_HH == "異常") &&
                (sOOC_H == "-" || sOOC_H == "N/A" || sOOC_H == "建置中" || sOOC_H == "異常") &&
                (sAlert1 == "-" || sAlert1 == "N/A" || sAlert1 == "建置中" || sAlert1 == "異常") && sWEB != "")
            {
                if (sAlert != "" && sAlert != "-" && sAlert != "N/A" && MTDBbase.ToDecimal(sWEB) > MTDBbase.ToDecimal(sAlert) &&
                    MTDBbase.ToDecimal(sWEB) < MTDBbase.ToDecimal(sOOC) && sOOC != "-" && sOOC != "N/A")
                {
                    sData = sType + "Alert";
                    if (sRed.IndexOf(sData) < 0) sRed += (sRed == "" ? "" : ",") + sData;
                    ArrColor[5] = "Y";
                }

                if (sRecv != "" && sRecv != "-" && sRecv != "N/A" && MTDBbase.ToDecimal(sWEB) > MTDBbase.ToDecimal(sRecv))
                {
                    sData = sType + "Alert";
                    if (sRed.IndexOf(sData) < 0) sRed += (sRed == "" ? "" : ",") + sData;
                    ArrColor[5] = "Y";
                }

                //CWMS OOS_HH
                if (MTDBbase.ToDecimal(sOOS_HH1) != MTDBbase.ToDecimal(sOOS) && sOOS_HH1 != "" && sOOS_HH1 != "-" &&
                    //sOOS_HH1 != "N/A" && sOOS_HH1 != "建置中" && sOOS_HH1 != "斷訊" && sOOS_HH1 != "異常")
                    sOOS_HH1 != "N/A" && sOOS_HH1 != "建置中" && sOOS_HH1 != "異常")
                {
                    sData = sType + (sOOS_HH1 == "斷訊" ? "斷訊" : (sOOS_HH1 == "保養中" ? "保養中" : "管制值不"));
                    if (sRed.IndexOf(sData) < 0) sRed += (sRed == "" ? "" : ",") + sData;
                    if (sOOS_HH1 != "斷訊" && sOOS_HH1 != "保養中") ArrColor[3] = "LightPink";
                    if (sOOS_HH1 != "保養中") ArrColor[5] = "O";
                }

                //CWMS OOC_H
                if (MTDBbase.ToDecimal(sOOC_H1) != MTDBbase.ToDecimal(sOOC) && sOOC_H1 != "" && sOOC_H1 != "-" &&
                    //sOOC_H1 != "N/A" && sOOC_H1 != "建置中" && sOOC_H1 != "斷訊" && sOOC_H1 != "異常")
                    sOOC_H1 != "N/A" && sOOC_H1 != "建置中" && sOOC_H1 != "異常")
                {
                    sData = sType + (sOOC_H1 == "斷訊" ? "斷訊" : (sOOC_H1 == "保養中" ? "保養中" : "管制值不"));
                    if (sRed.IndexOf(sData) < 0) sRed += (sRed == "" ? "" : ",") + sData;
                    if (sOOC_H1 != "斷訊" && sOOC_H1 != "保養中") ArrColor[4] = "LightPink";
                    if (sOOC_H1 != "保養中") ArrColor[5] = "O";
                }

                if (MTDBbase.ToDecimal(sWEB) >= MTDBbase.ToDecimal(sOOC) && sOOC != "" && sOOC != "-" && sOOC != "N/A" &&
                    MTDBbase.ToDecimal(sWEB) < MTDBbase.ToDecimal(sOOS) && sOOS != "" && sOOS != "-" && sOOS != "N/A")
                {
                    if (bWater == true)
                    {
                        msg0 = "|" + sItem + "|：SPEC-OOC＜＝最新讀值＜SPEC-OOS";
                        len = msg0.Length;
                        idx = msg.IndexOf(msg0);
                        if (idx > -1)
                        {
                            len += idx;
                            sData = "水OOC" + (msg.Substring(len, 1) != "(" ? "" : msg.Substring(len + 1, 2));
                            if (sRed.IndexOf(sData) < 0) sRed += (sRed == "" ? "" : ",") + sData;
                        }
                    }
                    ArrColor[5] = "O";
                }

                if (MTDBbase.ToDecimal(sWEB) >= MTDBbase.ToDecimal(sOOS) && sOOS != "" && sOOS != "-" && sOOS != "N/A")
                {
                    if (bWater == true)
                    {
                        msg0 = "|" + sItem + "|：最新讀值＞＝SPEC-OOS";
                        len = msg0.Length;
                        idx = msg.IndexOf(msg0);
                        if (idx > -1)
                        {
                            len += idx;
                            sData = "水OOS" + (msg.Substring(len, 1) != "(" ? "" : msg.Substring(len + 1, 2));
                            if (sRed.IndexOf(sData) < 0) sRed += (sRed == "" ? "" : ",") + sData;
                        }
                    }
                    ArrColor[5] = "R";
                }
            }
            else
            {
                if (sAlert != "" && sAlert != "-" && sAlert != "N/A" && MTDBbase.ToDecimal(sWEB) > MTDBbase.ToDecimal(sAlert) &&
                    MTDBbase.ToDecimal(sWEB) < MTDBbase.ToDecimal(sOOC) && sOOC != "-" && sOOC != "N/A")
                {
                    sData = sType + "Alert";
                    if (sRed.IndexOf(sData) < 0) sRed += (sRed == "" ? "" : ",") + sData;
                    ArrColor[5] = "Y";
                }

                if (sRecv != "" && sRecv != "-" && sRecv != "N/A" && MTDBbase.ToDecimal(sWEB) > MTDBbase.ToDecimal(sRecv))
                {
                    sData = sType + "Alert";
                    if (sRed.IndexOf(sData) < 0) sRed += (sRed == "" ? "" : ",") + sData;
                    ArrColor[5] = "Y";
                }

                if (MTDBbase.ToDecimal(sAlert1) != MTDBbase.ToDecimal(sAlert) && sAlert1 != "" && sAlert1 != "-" &&
                    //sAlert1 != "N/A" && sAlert1 != "建置中" && sAlert1 != "斷訊" && sAlert1 != "異常")
                    sAlert1 != "N/A" && sAlert1 != "建置中" && sAlert1 != "異常")
                {
                    sData = sType + (sAlert1 == "斷訊" ? "斷訊" : (sAlert1 == "保養中" ? "保養中" : "管制值不"));
                    if (sRed.IndexOf(sData) < 0) sRed += (sRed == "" ? "" : ",") + sData;
                    if (sAlert1 != "斷訊" && sAlert1 != "保養中") ArrColor[2] = "LightPink";
                    if (sAlert1 != "保養中") ArrColor[5] = "O";
                }

                //SCADA OOS_HH
                if (MTDBbase.ToDecimal(sOOS_HH) != MTDBbase.ToDecimal(sOOS) && sOOS_HH != "" && sOOS_HH != "-" &&
                    //sOOS_HH != "N/A" && sOOS_HH != "建置中" && sOOS_HH != "斷訊" && sOOS_HH != "異常")
                    sOOS_HH != "N/A" && sOOS_HH != "建置中" && sOOS_HH != "異常")
                {
                    if (sItem.IndexOf("VOC") > -1 && MTDBbase.ToDecimal(sOOS_HH) < MTDBbase.ToDecimal(sOOS))
                    {

                    }
                    else
                    {
                        sData = sType + (sOOS_HH == "斷訊" ? "斷訊" : (sOOS_HH == "保養中" ? "保養中" : "管制值不"));
                        if (sRed.IndexOf(sData) < 0) sRed += (sRed == "" ? "" : ",") + sData;
                        if (sOOS_HH != "斷訊" && sOOS_HH != "保養中") ArrColor[0] = "LightPink";
                        if (sOOS_HH != "保養中") ArrColor[5] = "O";
                    }
                }

                //SCADA OOC_H
                if (MTDBbase.ToDecimal(sOOC_H) != MTDBbase.ToDecimal(sOOC) && sOOC_H != "" && sOOC_H != "-" &&
                    //sOOC_H != "N/A" && sOOC_H != "建置中" && sOOC_H != "斷訊" && sOOC_H != "異常")
                    sOOC_H != "N/A" && sOOC_H != "建置中" && sOOC_H != "異常")
                {
                    if (sItem.IndexOf("VOC") > -1 && MTDBbase.ToDecimal(sOOC_H) < MTDBbase.ToDecimal(sOOC))
                    {

                    }
                    else
                    {
                        sData = sType + (sOOC_H == "斷訊" ? "斷訊" : (sOOC_H == "保養中" ? "保養中" : "管制值不"));
                        if (sRed.IndexOf(sData) < 0) sRed += (sRed == "" ? "" : ",") + sData;
                        if (sOOC_H != "斷訊" && sOOC_H != "保養中") ArrColor[1] = "LightPink";
                        if (sOOC_H != "保養中") ArrColor[5] = "O";
                    }
                }

                //CWMS OOS_HH
                if (MTDBbase.ToDecimal(sOOS_HH1) != MTDBbase.ToDecimal(sOOS) && sOOS_HH1 != "" && sOOS_HH1 != "-" &&
                    sOOS_HH1 != "N/A" && sOOS_HH1 != "建置中" && sOOS_HH1 != "異常")
                {
                    sData = sType + (sOOS_HH1 == "斷訊" ? "斷訊" : (sOOS_HH1 == "保養中" ? "保養中" : "管制值不"));
                    if (sRed.IndexOf(sData) < 0) sRed += (sRed == "" ? "" : ",") + sData;
                    if (sOOS_HH1 != "斷訊" && sOOS_HH1 != "保養中") ArrColor[3] = "LightPink";
                    if (sOOS_HH1 != "保養中") ArrColor[5] = "O";
                }

                //CWMS OOC_H
                if (MTDBbase.ToDecimal(sOOC_H1) != MTDBbase.ToDecimal(sOOC) && sOOC_H1 != "" && sOOC_H1 != "-" &&
                    sOOC_H1 != "N/A" && sOOC_H1 != "建置中" && sOOC_H1 != "異常")
                {
                    sData = sType + (sOOC_H1 == "斷訊" ? "斷訊" : (sOOC_H1 == "保養中" ? "保養中" : "管制值不"));
                    if (sRed.IndexOf(sData) < 0) sRed += (sRed == "" ? "" : ",") + sData;
                    if (sOOC_H1 != "斷訊" && sOOC_H1 != "保養中") ArrColor[4] = "LightPink";
                    if (sOOC_H1 != "保養中") ArrColor[5] = "O";
                }

                if (sWEB == "")
                {
                    if (sOOS_HH == "" && sOOC_H == "" && sAlert1 == "")
                    {
                        if (sBroken == "0") //沒斷訊
                        {
                            sData = sType + "OOS";
                            if (sRed.IndexOf(sData) < 0) sRed += (sRed == "" ? "" : ",") + sData;
                            sData = sType + "OOC";
                            if (sRed.IndexOf(sData) < 0) sRed += (sRed == "" ? "" : ",") + sData;
                        }
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
                        if (bWater == true)
                        {
                            msg0 = "|" + sItem + "|：SPEC-OOC＜＝最新讀值＜SPEC-OOS";
                            len = msg0.Length;
                            idx = msg.IndexOf(msg0);
                            if (idx > -1)
                            {
                                len += idx;
                                sData = "水OOC" + (msg.Substring(len, 1) != "(" ? "" : msg.Substring(len + 1, 2));
                                if (sRed.IndexOf(sData) < 0) sRed += (sRed == "" ? "" : ",") + sData;
                            }
                        }
                        ArrColor[5] = "O";
                    }

                    if (MTDBbase.ToDecimal(sWEB) >= MTDBbase.ToDecimal(sOOS) && sOOS != "" && sOOS != "-" && sOOS != "N/A")
                    {
                        if (bWater == true)
                        {
                            msg0 = "|" + sItem + "|：最新讀值＞＝SPEC-OOS";
                            len = msg0.Length;
                            idx = msg.IndexOf(msg0);
                            if (idx > -1)
                            {
                                len += idx;
                                sData = "水OOS" + (msg.Substring(len, 1) != "(" ? "" : msg.Substring(len + 1, 2));
                                if (sRed.IndexOf(sData) < 0) sRed += (sRed == "" ? "" : ",") + sData;
                            }
                        }
                        ArrColor[5] = "R";
                    }
                }
            }
        }
        else
        {
            string sOOS = row["OOS"].ToString();
            string sOOC = row["OOC"].ToString();
            string sAlert = row["Alert"].ToString();
            string sRecv = row["Recv"].ToString();
            string sOOS_HH = row["OOS_HH"].ToString();
            string sOOC_H = row["OOC_H"].ToString();
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

            //if ((sOOS_HH == "-" || sOOS_HH == "N/A" || sOOS_HH == "建置中" || sOOS_HH == "斷訊" || sOOS_HH == "異常") &&
            //    (sOOC_H == "-" || sOOC_H == "N/A" || sOOC_H == "建置中" || sOOC_H == "斷訊" || sOOC_H == "異常") &&
            //    (sAlert1 == "-" || sAlert1 == "N/A" || sAlert1 == "建置中" || sAlert1 == "斷訊" || sAlert1 == "異常") && WEB != "")
            if ((sOOS_HH == "-" || sOOS_HH == "N/A" || sOOS_HH == "建置中" || sOOS_HH == "異常") &&
                (sOOC_H == "-" || sOOC_H == "N/A" || sOOC_H == "建置中" || sOOC_H == "異常") &&
                (sAlert1 == "-" || sAlert1 == "N/A" || sAlert1 == "建置中" || sAlert1 == "異常") && WEB != "")
            {
                if (sAlert != "-" && Alert.Length == 2 && OOC.Length == 2)
                {
                    if (MTDBbase.ToDecimal(WEB) > MTDBbase.ToDecimal(Alert[1]) &&
                        MTDBbase.ToDecimal(WEB) < MTDBbase.ToDecimal(OOC[1]))
                    {
                        sData = "水Alert";
                        if (sRed.IndexOf(sData) < 0) sRed += (sRed == "" ? "" : ",") + sData;
                        ArrColor[5] = "Y";
                    }
                }

                if (sRecv != "-" && Recv.Length == 2)
                {
                    if (MTDBbase.ToDecimal(WEB) > MTDBbase.ToDecimal(Recv[1]))
                    {
                        sData = "水Alert";
                        if (sRed.IndexOf(sData) < 0) sRed += (sRed == "" ? "" : ",") + sData;
                        ArrColor[5] = "Y";
                    }
                }

                //CWMS OOS_HH
                if (CheckData(OOS_HH1) != CheckData(OOS) && sOOS_HH1 != "" && sOOS_HH1 != "-" &&
                    sOOS_HH1 != "N/A" && sOOS_HH1 != "建置中" && sOOS_HH1 != "異常")
                {
                    sData = (sOOS_HH1 == "斷訊" ? "水斷訊" : (sOOS_HH1 == "保養中" ? "水保養中" : "水管制值不"));
                    if (sRed.IndexOf(sData) < 0) sRed += (sRed == "" ? "" : ",") + sData;
                    if (sOOS_HH1 != "斷訊" && sOOS_HH1 != "保養中") ArrColor[3] = "LightPink";
                    if (sOOS_HH1 != "保養中") ArrColor[5] = "O";
                }

                //CWMS OOC_H
                if (CheckData(OOC_H1) != CheckData(OOC) && sOOC_H1 != "" && sOOC_H1 != "-" &&
                    sOOC_H1 != "N/A" && sOOC_H1 != "建置中" && sOOC_H1 != "異常")
                {
                    sData = (sOOC_H1 == "斷訊" ? "水斷訊" : (sOOC_H1 == "保養中" ? "水保養中" : "水管制值不"));
                    if (sRed.IndexOf(sData) < 0) sRed += (sRed == "" ? "" : ",") + sData;
                    if (sOOC_H1 != "斷訊" && sOOC_H1 != "保養中") ArrColor[4] = "LightPink";
                    if (sOOC_H1 != "保養中") ArrColor[5] = "O";
                }

                if (OOC.Length == 2 && OOS.Length == 2)
                {
                    if (MTDBbase.ToDecimal(WEB) >= MTDBbase.ToDecimal(OOC[1]) && sOOC != "-" &&
                        MTDBbase.ToDecimal(WEB) < MTDBbase.ToDecimal(OOS[1]) && sOOS != "-")
                    {
                        if (bWater == true)
                        {
                            msg0 = "|" + sItem + "|：SPEC-OOC＜＝最新讀值＜SPEC-OOS";
                            len = msg0.Length;
                            idx = msg.IndexOf(msg0);
                            if (idx > -1)
                            {
                                len += idx;
                                sData = "水OOC" + (msg.Substring(len, 1) != "(" ? "" : msg.Substring(len + 1, 2));
                                if (sRed.IndexOf(sData) < 0) sRed += (sRed == "" ? "" : ",") + sData;
                            }
                        }
                        ArrColor[5] = "O";
                    }
                }

                if (OOS.Length == 2)
                {
                    if (MTDBbase.ToDecimal(WEB) >= MTDBbase.ToDecimal(OOS[1]) && sOOS != "-")
                    {
                        if (bWater == true)
                        {
                            msg0 = "|" + sItem + "|：最新讀值＞＝SPEC-OOS";
                            len = msg0.Length;
                            idx = msg.IndexOf(msg0);
                            if (idx > -1)
                            {
                                len += idx;
                                sData = "水OOS" + (msg.Substring(len, 1) != "(" ? "" : msg.Substring(len + 1, 2));
                                if (sRed.IndexOf(sData) < 0) sRed += (sRed == "" ? "" : ",") + sData;
                            }
                        }
                        ArrColor[5] = "R";
                    }
                }
            }
            else
            {
                if (CheckData(Alert1) != CheckData(Alert) && sAlert1 != "" && sAlert1 != "-" &&
                    //sAlert1 != "N/A" && sAlert1 != "建置中" && sAlert1 != "斷訊" && sAlert1 != "異常")
                    sAlert1 != "N/A" && sAlert1 != "建置中" && sAlert1 != "異常")
                {
                    sData = (sAlert1 == "斷訊" ? "水斷訊" : (sAlert1 == "保養中" ? "水保養中" : "水管制值不"));
                    if (sRed.IndexOf(sData) < 0) sRed += (sRed == "" ? "" : ",") + sData;
                    if (sAlert1 != "斷訊" && sAlert1 != "保養中") ArrColor[2] = "LightPink";
                    if (sAlert1 != "保養中") ArrColor[5] = "O";
                }

                //SCADA OOS_HH
                if (CheckData(OOS_HH) != CheckData(OOS) && sOOS_HH != "" && sOOS_HH != "-" &&
                    //sOOS_HH != "N/A" && sOOS_HH != "建置中" && sOOS_HH != "斷訊" && sOOS_HH != "異常")
                    sOOS_HH != "N/A" && sOOS_HH != "建置中" && sOOS_HH != "異常")
                {
                    sData = (sOOS_HH == "斷訊" ? "水斷訊" : (sOOS_HH == "保養中" ? "水保養中" : "水管制值不"));
                    if (sRed.IndexOf(sData) < 0) sRed += (sRed == "" ? "" : ",") + sData;
                    if (sOOS_HH != "斷訊" && sOOS_HH != "保養中") ArrColor[0] = "LightPink";
                    if (sOOS_HH != "保養中") ArrColor[5] = "O";
                }

                //SCADA OOC_H
                if (CheckData(OOC_H) != CheckData(OOC) && sOOC_H != "" && sOOC_H != "-" &&
                    //sOOC_H != "N/A" && sOOC_H != "建置中" && sOOC_H != "斷訊" && sOOC_H != "異常")
                    sOOC_H != "N/A" && sOOC_H != "建置中" && sOOC_H != "異常")
                {
                    sData = (sOOC_H == "斷訊" ? "水斷訊" : (sOOC_H == "保養中" ? "水保養中" : "水管制值不"));
                    if (sRed.IndexOf(sData) < 0) sRed += (sRed == "" ? "" : ",") + sData;
                    if (sOOC_H != "斷訊" && sOOC_H != "保養中") ArrColor[1] = "LightPink";
                    if (sOOC_H != "保養中") ArrColor[5] = "O";
                }

                //CWMS OOS_HH
                if (CheckData(OOS_HH1) != CheckData(OOS) && sOOS_HH1 != "" && sOOS_HH1 != "-" &&
                    sOOS_HH1 != "N/A" && sOOS_HH1 != "建置中" && sOOS_HH1 != "異常")
                {
                    sData = (sOOS_HH1 == "斷訊" ? "水斷訊" : (sOOS_HH1 == "保養中" ? "水保養中" : "水管制值不"));
                    if (sRed.IndexOf(sData) < 0) sRed += (sRed == "" ? "" : ",") + sData;
                    if (sOOS_HH1 != "斷訊" && sOOS_HH1 != "保養中") ArrColor[3] = "LightPink";
                    if (sOOS_HH1 != "保養中") ArrColor[5] = "O";
                }

                //CWMS OOC_H
                if (CheckData(OOC_H1) != CheckData(OOC) && sOOC_H1 != "" && sOOC_H1 != "-" &&
                    sOOC_H1 != "N/A" && sOOC_H1 != "建置中" && sOOC_H1 != "異常")
                {
                    sData = (sOOC_H1 == "斷訊" ? "水斷訊" : (sOOC_H1 == "保養中" ? "水保養中" : "水管制值不"));
                    if (sRed.IndexOf(sData) < 0) sRed += (sRed == "" ? "" : ",") + sData;
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
                            sData = "水Alert";
                            if (sRed.IndexOf(sData) < 0) sRed += (sRed == "" ? "" : ",") + sData;
                            ArrColor[5] = "Y";
                        }
                    }

                    if (sRecv != "-" && Recv.Length == 2)
                    {
                        if (MTDBbase.ToDecimal(WEB) > MTDBbase.ToDecimal(Recv[1]))
                        {
                            sData = "水Alert";
                            if (sRed.IndexOf(sData) < 0) sRed += (sRed == "" ? "" : ",") + sData;
                            ArrColor[5] = "Y";
                        }
                    }

                    if (OOC.Length == 2 && OOS.Length == 2)
                    {
                        if (MTDBbase.ToDecimal(WEB) >= MTDBbase.ToDecimal(OOC[1]) && sOOC != "-" &&
                            MTDBbase.ToDecimal(WEB) < MTDBbase.ToDecimal(OOS[1]) && sOOS != "-")
                        {
                            if (bWater == true)
                            {
                                msg0 = "|" + sItem + "|：SPEC-OOC＜＝最新讀值＜SPEC-OOS";
                                len = msg0.Length;
                                idx = msg.IndexOf(msg0);
                                if (idx > -1)
                                {
                                    len += idx;
                                    sData = "水OOC" + (msg.Substring(len, 1) != "(" ? "" : msg.Substring(len + 1, 2));
                                    if (sRed.IndexOf(sData) < 0) sRed += (sRed == "" ? "" : ",") + sData;
                                }
                            }
                            ArrColor[5] = "O";
                        }
                    }

                    if (OOS.Length == 2)
                    {
                        if (MTDBbase.ToDecimal(WEB) >= MTDBbase.ToDecimal(OOS[1]) && sOOS != "-")
                        {
                            if (bWater == true)
                            {
                                msg0 = "|" + sItem + "|：最新讀值＞＝SPEC-OOS";
                                len = msg0.Length;
                                idx = msg.IndexOf(msg0);
                                if (idx > -1)
                                {
                                    len += idx;
                                    sData = "水OOS" + (msg.Substring(len, 1) != "(" ? "" : msg.Substring(len + 1, 2));
                                    if (sRed.IndexOf(sData) < 0) sRed += (sRed == "" ? "" : ",") + sData;
                                }
                            }
                            ArrColor[5] = "R";
                        }
                    }
                }
            }
        }

        return ArrColor;
    }

    public string GetData雨水溝預警(DataRow row, string msg, ref string sRed)
    {
        //紅燈條件：最新讀值=1 且 24H累積雨量=0
        //橘燈條件：斷訊 或 異常
        //綠燈條件：正常狀態

        string ArrColor = "G";
        string sItem = row["item"].ToString();
        string rvalue = row["rvalue"].ToString();
        string sData;

        if (rvalue == "1" && row["Sum24H"].ToString() == "0.0")
        {
            sData = "雨水溝Alert";
            if (sRed.IndexOf(sData) < 0) sRed += (sRed == "" ? "" : ",") + sData;
            ArrColor = "R";
        }
        else if (rvalue == "斷訊" || rvalue == "保養中")
        {
            sData = "雨水溝" + rvalue;
            if (sRed.IndexOf(sData) < 0) sRed += (sRed == "" ? "" : ",") + sData;
            if (rvalue == "斷訊") ArrColor = "O";
        }

        return ArrColor;
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

    public DataTable GetMailList(string sRed, string plantno, string MailType)
    {
        int idx = -1;
        string wheres = "";
        string[] ArrRed = sRed.Split(',');
        for (int i = 0; i < ArrRed.Length; i++)
        {
            if (MailType == "TO")
                wheres += (wheres == "" ? "" : " Or ") + "(RptType='" + ArrRed[i] + "' And plantno='" + plantno + "')";
            else
            {
                idx = wheres.IndexOf(ArrRed[i]);
                if (idx < 0)
                    wheres += (wheres == "" ? "" : ",") + "'" + ArrRed[i] + "'";
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
        string[] ArrRed = DataRed.Split(',');
        for (int i = 0; i < ArrRed.Length; i++)
        {
            if (MailType == "TO")
                wheres += (wheres == "" ? "" : " Or ") + "(RptType='" + ArrRed[i] + "' And plantno='" + plantno + "')";
            else
            {
                idx = wheres.IndexOf(ArrRed[i]);
                if (idx < 0)
                    wheres += (wheres == "" ? "" : ",") + "'" + ArrRed[i] + "'";
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

    public DataTable Get部門名稱(string deptno)
    {
        SqlParameterClear();
        SqlCommandText = "Select Distinct DeptName " +
            "From [UTIDB].[dbo].[Employee] " +
            "Where DeptNo=@deptno And isLeave=0";
        SqlParameterAdd("@deptno", deptno);
        return SqlFillDT();
    }

    public bool InsertDeptList(Hashtable hrow)
    {
        try
        {
            string plantid = hrow["plant"].ToString();
            string deptno = hrow["deptno"].ToString();

            SqlBeginTransaction();
            SqlParameterClear();
            SqlCommandText = "Select plantno From [VOC].[dbo].[VOC_plant] Where plantid=@plantid";
            SqlParameterAdd("@plantid", plantid);
            string plantno = SqlExecuteScalarString();

            SqlParameterClear();
            SqlCommandText = "Select Count(*) From [VOC].[dbo].[VOC_dept] " +
                "Where plantid=@plantid And deptno=@deptno ";
            SqlParameterAdd("@plantid", plantid);
            SqlParameterAdd("@deptno", deptno);
            int cnt = SqlExecuteScalarInt32(0);
            if (cnt > 0)
                throw new Exception("此筆資料已存在部門資料內!");

            SqlParameterClear();
            SqlCommandText = "INSERT INTO [VOC].[dbo].[VOC_dept] " +
                "([plantid],[deptno],[cdatetime]) VALUES (@plantid,@deptno,@cdatetime);";
            SqlParameterAdd("@plantid", plantid);
            SqlParameterAdd("@deptno", deptno);
            SqlParameterAdd("@cdatetime", DateTime.Now);
            SqlExecuteNonQuery();

            SqlParameterClear();
            SqlCommandText = "INSERT INTO [VOC].[dbo].[VOC_tranlog] " +
                "([empno],[logtype],[databefore],[dataafter],[cdatetime],[remark]) " +
                "VALUES (@empno,@logtype,@databefore,@dataafter,@cdatetime,@remark)";
            SqlParameterAdd("@empno", AppConfig.Sess_UserEmpNo);
            SqlParameterAdd("@logtype", "I");
            SqlParameterAdd("@databefore", "");
            SqlParameterAdd("@dataafter", plantno + "/" + deptno + "/" + hrow["deptname"]);
            SqlParameterAdd("@cdatetime", DateTime.Now);
            SqlParameterAdd("@remark", hrow["remark"]);
            SqlExecuteNonQuery();
            SqlCommit();
        }
        catch (Exception ex)
        {
            SqlRollback();
            _Exception = ex.Message;
            return false;
        }

        return true;
    }

    public bool UpdateDeptList(Hashtable hrow, string pdeptno, string pdeptname)
    {
        try
        {
            string plantid = hrow["plant"].ToString();
            string deptno = hrow["deptno"].ToString();

            SqlBeginTransaction();
            SqlParameterClear();
            SqlCommandText = "Select plantno From [VOC].[dbo].[VOC_plant] Where plantid=@plantid";
            SqlParameterAdd("@plantid", plantid);
            string plantno = SqlExecuteScalarString();

            SqlParameterClear();
            SqlCommandText = "Update [VOC].[dbo].[VOC_dept] Set deptno=@deptno " +
                "Where plantid=@plantid And deptno=@pdeptno";
            SqlParameterAdd("@plantid", plantid);
            SqlParameterAdd("@pdeptno", pdeptno);
            SqlParameterAdd("@deptno", deptno);
            SqlExecuteNonQuery();

            SqlParameterClear();
            SqlCommandText = "INSERT INTO [VOC].[dbo].[VOC_tranlog] " +
                "([empno],[logtype],[databefore],[dataafter],[cdatetime],[remark]) " +
                "VALUES (@empno,@logtype,@databefore,@dataafter,@cdatetime,@remark)";
            SqlParameterAdd("@empno", AppConfig.Sess_UserEmpNo);
            SqlParameterAdd("@logtype", "M");
            SqlParameterAdd("@databefore", plantno + "/" + pdeptno + "/" + pdeptname);
            SqlParameterAdd("@dataafter", plantno + "/" + deptno + "/" + hrow["deptname"]);
            SqlParameterAdd("@cdatetime", DateTime.Now);
            SqlParameterAdd("@remark", hrow["remark"]);
            SqlExecuteNonQuery();
            SqlCommit();
        }
        catch (Exception ex)
        {
            SqlRollback();
            _Exception = ex.Message;
            return false;
        }

        return true;
    }

    public bool DeleteDeptList(Hashtable hrow)
    {
        try
        {
            string plantid = hrow["plant"].ToString();
            string deptno = hrow["deptno"].ToString();

            SqlBeginTransaction();
            SqlParameterClear();
            SqlCommandText = "Select plantno From [VOC].[dbo].[VOC_plant] Where plantid=@plantid";
            SqlParameterAdd("@plantid", plantid);
            string plantno = SqlExecuteScalarString();

            SqlParameterClear();
            SqlCommandText = "Delete From [VOC].[dbo].[VOC_dept] " +
                "Where plantid=@plantid And deptno=@deptno";
            SqlParameterAdd("@plantid", plantid);
            SqlParameterAdd("@deptno", deptno);
            SqlExecuteNonQuery();

            SqlParameterClear();
            SqlCommandText = "INSERT INTO [VOC].[dbo].[VOC_tranlog] " +
                "([empno],[logtype],[databefore],[dataafter],[cdatetime],[remark]) " +
                "VALUES (@empno,@logtype,@databefore,@dataafter,@cdatetime,@remark)";
            SqlParameterAdd("@empno", AppConfig.Sess_UserEmpNo);
            SqlParameterAdd("@logtype", "D");
            SqlParameterAdd("@databefore", plantno + "/" + deptno + "/" + hrow["deptname"]);
            SqlParameterAdd("@dataafter", "");
            SqlParameterAdd("@cdatetime", DateTime.Now);
            SqlParameterAdd("@remark", hrow["remark"]);
            SqlExecuteNonQuery();
            SqlCommit();
        }
        catch (Exception ex)
        {
            SqlRollback();
            _Exception = ex.Message;
            return false;
        }
        return true;
    }

    public int Check廠區(string plantno)
    {
        SqlParameterClear();
        SqlCommandText = "Select Count(*) From [VOC].[dbo].[VOC_plant] Where [plantno]=@plantno";
        SqlParameterAdd("@plantno", plantno);
        int cnt = SqlExecuteScalarInt32(0);
        if (cnt > 0) return 1; else return 0;
    }

    public int Check派送類型(string rpttype)
    {
        SqlParameterClear();
        SqlCommandText = "Select Count(*) From [VOC].[dbo].[VOC_Mail_Type] Where [RptType]=@rpttype";
        SqlParameterAdd("@rpttype", rpttype);
        int cnt = SqlExecuteScalarInt32(0);
        if (cnt > 0) return 1; else return 0;
    }

    public int Check工號(string empno)
    {
        SqlParameterClear();
        SqlCommandText = "Select Count(*) From [UTIDB].[dbo].[Employee] Where [EmpNo]=@empno And isLeave=0";
        SqlParameterAdd("@empno", empno);
        int cnt = SqlExecuteScalarInt32(0);
        if (cnt > 0) return 1; else return 0;
    }

    public int Check姓名(string empno, string empname)
    {
        SqlParameterClear();
        SqlCommandText = "Select Count(*) From [UTIDB].[dbo].[Employee] Where [EmpNo]=@empno And [EmpName]=@empname";
        SqlParameterAdd("@empno", empno);
        SqlParameterAdd("@empname", empname);
        int cnt = SqlExecuteScalarInt32(0);
        if (cnt > 0) return 1; else return 0;
    }

    public string GetNotesID(string empno)
    {
        SqlParameterClear();
        SqlCommandText = "Select NotesID From [UTIDB].[dbo].[Employee] Where [EmpNo]=@empno";
        SqlParameterAdd("@empno", empno);
        return SqlExecuteScalarString();
    }

    public int Check派送名單(string rpttype, string plantno, string empno, string action)
    {
        SqlParameterClear();
        SqlCommandText = "Select Count(*) From [VOC].[dbo].[VOC_Mail_List] Where [RptType]=@rpttype And [plantno]=@plantno And [EmpNo]=@empno";
        SqlParameterAdd("@rpttype", rpttype);
        SqlParameterAdd("@plantno", plantno);
        SqlParameterAdd("@empno", empno);
        int cnt = SqlExecuteScalarInt32(0);
        if ((cnt == 0 && action == "新增") || (cnt > 0 && action != "新增")) return 1; else return 0;
    }

    public bool UpdateMail(string[] ColName, string[] ColValue, string[] ColName1)
    {
        try
        {
            SqlBeginTransaction();

            string plantno = ColValue[0].ToString();
            string rtype = ColValue[1].ToString();
            string empno = ColValue[2].ToString();
            string empname = ColValue[3].ToString();
            string notesid = ColValue[4].ToString().Replace("_", " ");
            if (empno.IndexOf("群組") < 0 && empno.IndexOf("值班") < 0) notesid = GetNotesID(empno);
            string cphone = ColValue[5].ToString();
            if (cphone != "") cphone = (cphone.StartsWith("0") ? "" : "0") + cphone;
            string mtype = ColValue[6].ToString();
            string mail = ColValue[7].ToString();
            string sm = ColValue[8].ToString();
            string sgrp = ColValue[9].ToString();
            string action = ColValue[10].ToString();

            SqlParameterClear();
            SqlParameterAdd("@plantno", plantno);
            SqlParameterAdd("@rtype", rtype);
            SqlParameterAdd("@empno", empno);
            SqlParameterAdd("@empname", empname);
            SqlParameterAdd("@notesid", notesid);
            SqlParameterAdd("@cphone", cphone);
            SqlParameterAdd("@mtype", mtype);
            SqlParameterAdd("@mail", mail == "要" ? 1 : 0);
            SqlParameterAdd("@sm", sm == "要" ? 1 : 0);
            SqlParameterAdd("@sgrp", sgrp == "要" ? 1 : 0);

            if (action == "新增")
            {
                SqlCommandText = "INSERT INTO [VOC].[dbo].[VOC_Mail_List] " +
                    "(RptType,plantno,empno,empname,NotesID,MailType,CellPhone,SM,Mail,SignGrp,SM1,Mail1) " +
                    "VALUES(@rtype,@plantno,@empno,@empname,@notesid,@mtype,@cphone,@sm,@mail,@sgrp,@sm,@mail)";

            }
            else if (action == "修改")
            {
                SqlCommandText = "UPDATE [VOC].[dbo].[VOC_Mail_List] " +
                    "SET empname=@empname,NotesID=@notesid,MailType=@mtype,CellPhone=@cphone,SM=@sm,Mail=@mail,SignGrp=@sgrp,SM1=@sm,Mail1=@mail " +
                    "WHERE RptType=@rtype AND plantno=@plantno AND empno=@empno";
            }
            else
            {
                SqlCommandText = "DELETE FROM [VOC].[dbo].[VOC_Mail_List] WHERE RptType=@rtype AND plantno=@plantno AND empno=@empno";
            }

            SqlExecuteNonQuery();
            SqlCommit();
            return true;
        }
        catch (Exception ex)
        {
            SqlRollback();
            _Exception = ex.Message;
            return false;
        }
    }

    public DataTable ListTags(string plantno)
    {
        SqlParameterClear();
        SqlCommandText = "SELECT Tag,Description,plantno,item,TableName TNORA " +
            "FROM [VOC].[dbo].[VOC_SCADA_Tag] " +
            "Where plantno=@plantno And item is not null And IsActive=1";
        SqlParameterAdd("@plantno", plantno);
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

    public bool SendMail_水質異常通知(DateTime cdatetime)
    {
        try
        {
            string Albee = "Albee_Weng@aseglobal.com";
            string Bermy = "Bermy_Po@aseglobal.com";
            string Jeff = "Jeff_Liang@aseglobal.com";
            string url = "http://khfacsv01/VOC/WaterUrgent.aspx";
            string plantno, item, cvalue, body, sdate, edate, url1, msg, msg1;
            string DT = cdatetime.ToString("yyyy/MM/dd HH:mm");
            DateTime dt2 = Convert.ToDateTime(DT + ":00");
            sdate = edate = cdatetime.ToString("yyyy/MM/dd");
            string stime = cdatetime.ToString("yyyy/MM/dd HH:mm");
            DataTable dtb = GetData水質廠區(0);
            DataTable dtb1 = GetData水質異常(cdatetime);
            DataTable mailto, mailcc, phoneto, phonecc;
            int rcnt = dtb1.Rows.Count, r;
            bool rtn;

            if (rcnt > 0)
            {
                foreach (DataRow row in dtb.Rows)
                {
                    plantno = row["plantno"].ToString();

                    body = "<html><body><label>Dear Sir,<br />" +
                        "您好, <font style='color: Red'><b>中水水質異常</b></font>, 請回覆您所負責的 " + plantno + " 目前水質狀況, 謝謝!</label><br /><br />" +
                        "<table style='border: black 1px solid' width='450px'>" +
                        "<tr style='background-color: #CCFFFF; font-weight: bold; font-size: small;'>" +
                        "<td style='text-align: center'><strong>廠區</strong></td>" +
                        "<td style='text-align: center'><strong>項目</strong></td>" +
                        "<td style='text-align: center'><strong>OOS</strong></td>" +
                        "<td style='text-align: center'><strong>OOC</strong></td>" +
                        "<td style='text-align: center'><strong>最新讀值</strong></td></tr>" +
                        "<tr><td rowspan='" + rcnt + "' style='text-align: center; background-color: #FFFFFF;'><strong>K14B</strong></td>";

                    msg = msg1 = "中水水質異常，項目最新讀值-";
                    r = 0;

                    foreach (DataRow row1 in dtb1.Rows)
                    {
                        r++;
                        item = row1["item"].ToString();
                        cvalue = row1["cValue"].ToString();

                        //body += "<tr><td style='text-align: center; background-color: #FFFFFF;'><strong>K14B</strong></td>" +
                        body += "<td style='text-align: center; background-color: #FFFFFF;'><strong>" + item + "</strong></td>" +
                            "<td style='text-align: center; background-color: #FFFFFF;'><strong>" + row1["OOS"] + "</strong></td>" +
                            "<td style='text-align: center; background-color: #FFFFFF;'><strong>" + row1["OOC"] + "</strong></td>" +
                            "<td style='text-align: center; background-color: #FFFFFF;'><strong>" + cvalue + "</strong></td>" +
                            "</tr>";

                        if (r != rcnt) body += "<tr>";

                        msg += item + "：" + cvalue + "；";
                        msg1 += "|" + item + "|：" + cvalue + "；";
                    }

                    url1 = "http://khfacsv01/VOC/VOCreason.aspx?plantno=" + plantno + "&sdate=" + sdate + "&edate=" + edate + "&stime=" + stime;
                    body += "</table><table style='border: black 1px solid' width='450px'><tr style='font-weight: bold;'>" +
                        "<td colspan='5' style='text-align: left'>" +
                        //"<a href='" + url + "'>進行查看</a>&nbsp&nbsp&nbsp" +
                        "<a href='" + url1 + "'>異常原因回覆</a>" +
                        "</td></tr></table></body></html>";

                    SmtpMessage sm = new SmtpMessage();
                    sm.Message.From = new MailAddress(Jeff, "法遵平台");

                    mailto = GetMailList("水質異常", plantno, "TO");
                    mailcc = GetMailList("水質異常", plantno, "CC");

                    foreach (DataRow mrow in mailto.Rows) sm.Message.To.Add(mrow["NotesID"].ToString().Replace(" ", "_") + "@aseglobal.com");
                    foreach (DataRow mrow in mailcc.Rows) sm.Message.CC.Add(mrow["NotesID"].ToString().Replace(" ", "_") + "@aseglobal.com");

                    sm.Message.Bcc.Add(Albee);
                    sm.Message.Bcc.Add(Bermy);

                    if (sm.Message.To.Count == 0) return false;

                    sm.Message.Subject = string.Format("請確認「法遵平台-中水放流管制」即時監控狀況 : {0}-{1} (Security C)", plantno, DT);
                    sm.Message.IsBodyHtml = true;
                    sm.Message.Body = body;
                    sm.Message.BodyEncoding = Encoding.UTF8;
                    sm.Send(sm.Message);

                    using (dbVOC db = new dbVOC())
                    {
                        db.InsertMAIL(plantno, msg, msg1, dt2, msg1);

                        msg = "中水水質異常,請回覆" + plantno + "目前水質狀況,謝謝!";

                        phoneto = GetCellPhoneList("水質異常", plantno, "TO");
                        phonecc = GetCellPhoneList("水質異常", plantno, "CC");

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
        }
        catch (Exception ex)
        {
            _Exception = ex.Message;
            return false;
        }

        return true;
    }

    public bool SendMail_改排水通知(DateTime cdatetime, CheckBoxList plantlist, string reason)
    {
        try
        {
            string Albee = "Albee_Weng@aseglobal.com";
            string Bermy = "Bermy_Po@aseglobal.com";
            string Jeff = "Jeff_Liang@aseglobal.com";
            string url = "http://khfacsv01/VOC/WaterUrgent.aspx";
            string plantno, item, cvalue, body, sdate, edate, url1, msg, msg1;
            string[] Arrplant, Arrplant1;
            string DT = cdatetime.ToString("yyyy/MM/dd HH:mm");
            DateTime dt2 = Convert.ToDateTime(DT + ":00");
            sdate = edate = cdatetime.ToString("yyyy/MM/dd");
            string stime = cdatetime.ToString("yyyy/MM/dd HH:mm");

            string plant = "";
            for (int i = 0; i < plantlist.Items.Count; i++)
            {
                if (plantlist.Items[i].Selected == true)
                    plant += plantlist.Items[i].Text + ",";
            }

            Arrplant = plant.Split(',');
            int rcnt = Arrplant.Length - 1;

            DataTable mailto, mailcc, phoneto, phonecc;
            bool rtn;

            if (rcnt > 0)
            {
                for (int i = 0; i < rcnt; i++)
                {
                    plantno = Arrplant[i];

                    body = "<html><body><label>Dear Sir,<br />" +
                        "您好, 改排水原因：<font style='color: Red'><b>" + reason + "</b></font><br /><br />請回覆您所負責的 " + plantno + " 處理狀況, 謝謝!</label><br /><br />";

                    msg = msg1 = "改排水原因：" + reason;

                    url1 = "http://khfacsv01/VOC/VOCreason.aspx?plantno=" + plantno + "&sdate=" + sdate + "&edate=" + edate + "&stime=" + stime + "&change=Y";
                    body += "</table><table><tr style='font-weight: bold;'>" +
                        "<td style='text-align: left'>" +
                        //"<a href='" + url + "'>進行查看</a>&nbsp&nbsp&nbsp" +
                        "<a href='" + url1 + "'>異常原因回覆</a>" +
                        "</td></tr></table></body></html>";

                    SmtpMessage sm = new SmtpMessage();
                    sm.Message.From = new MailAddress(Jeff, "法遵平台");

                    mailto = GetMailList("水質異常", plantno, "TO");
                    mailcc = GetMailList("水質異常", plantno, "CC");

                    foreach (DataRow mrow in mailto.Rows) sm.Message.To.Add(mrow["NotesID"].ToString().Replace(" ", "_") + "@aseglobal.com");
                    foreach (DataRow mrow in mailcc.Rows) sm.Message.CC.Add(mrow["NotesID"].ToString().Replace(" ", "_") + "@aseglobal.com");

                    mailcc = GetMailList("水質異常", "K14B", "TO");
                    foreach (DataRow mrow in mailcc.Rows) sm.Message.CC.Add(mrow["NotesID"].ToString().Replace(" ", "_") + "@aseglobal.com");

                    sm.Message.Bcc.Add(Albee);
                    sm.Message.Bcc.Add(Bermy);

                    if (sm.Message.To.Count == 0) return false;

                    sm.Message.Subject = string.Format("請確認「法遵平台-中水放流管制」即時監控狀況 : {0}-{1} (Security C)", plantno, DT);
                    sm.Message.IsBodyHtml = true;
                    sm.Message.Body = body;
                    sm.Message.BodyEncoding = Encoding.UTF8;
                    sm.Send(sm.Message);

                    using (dbVOC db = new dbVOC())
                    {
                        db.InsertMAIL(plantno, msg, msg1, dt2, msg1);

                        msg = "改排水原因:" + reason + ",請回覆" + plantno + "處理狀況,謝謝!";

                        phoneto = GetCellPhoneList("水質異常", plantno, "TO");
                        phonecc = GetCellPhoneList("水質異常", plantno, "CC");

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

                        phonecc = GetCellPhoneList("水質異常", "K14B", "TO");

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
        }
        catch (Exception ex)
        {
            _Exception = ex.Message;
            return false;
        }

        return true;
    }

    public string GetSPEC(string plantno, string item, string type)
    {
        item = (item == "COD" ? "COD2" : (item == "COD1" ? "COD2" : (item == "pH" ? "pH1" : (item == "pH2" ? "pH1" : item))));
        SqlParameterClear();
        SqlCommandText = "Select " + type + " From [VOC].[dbo].[VOC_SPEC] Where plantno=@plantno And item=@item";
        SqlParameterAdd("@plantno", plantno);
        SqlParameterAdd("@item", item);
        return SqlExecuteScalarString();
    }
}