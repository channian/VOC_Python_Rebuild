using System;
using System.Collections;
using System.Collections.Generic;
using System.Data;
using System.Linq;
using System.Text;

namespace MTLibrary
{

    public class dbSignFlow : MTDBbase<dbSignFlow>
    {
        public dbSignFlow()
            : base((int)MTAppConfig.DataBaseCI.SignFlow)
        {

        }

        public enum 職稱ID
        {
            工程師 = 1,
            專案工程師 = 2,

            //Bermy start added on 2016/08/10 for "主任" & "主任工程師"
            主任 = 12,
            主任工程師 = 3,
            //Bermy end added on 2016/08/10 for "主任" & "主任工程師"

            //Bermy start added on 2018/11/26 for "專業技術副理" & "部副理" & "專業副理"
            專業技術副理 = 4,
            專業副理 = 31,
            部副理 = 10,
            //Bermy end added on 2018/11/26 for "專業技術副理" & "部副理" & "專業副理"

            處長 = 7,
            資深處長 = 8,
            廠長 = 20,
            資深廠長 = 21,

            //Bermy start added on 2018/11/26 for "副總經理" & "資深副總經理"
            副總經理 = 9,
            資深副總經理 = 30,
            //Bermy end added on 2018/11/26 for "副總經理" & "資深副總經理"
        };


        #region VL List
        public DataTable List簽核結果VL()
        {
            SqlParameterClear();
            SqlCommandText = "Select signactionid,signaction " +
                    "From [SignFlow].[dbo].[base_signaction] " +
                    "Order By signactionid ";
            return SqlFillDT();
        }

        //Bermy start added on 2016/08/04 to add parameter of "actstep" and modify SqlCommandText
        public DataTable List簽核結果VL(int actstep)
        {
            SqlParameterClear();
            SqlCommandText = "Select signactionid,signaction " +
                    "From [SignFlow].[dbo].[base_signaction] " +
                    "Where signaction <> '取消' ";
            if (actstep != 6) SqlCommandText = SqlCommandText + "And signaction <> '分享' ";  //actstep = 6 -> UTI_處長審核
            SqlCommandText = SqlCommandText + "Order By signactionid ";
            return SqlFillDT();
        }
        //Bermy end added on 2016/08/04 to add parameter of "actstep" and modify SqlCommandText

        public DataTable List簽核流程(int flowid)
        {
            SqlParameterClear();
            SqlCommandText = "Select FD.*,E.empname,signaction,S.signaction " +
                "From [SignFlow].[dbo].[base_flowd] FD " +
                "Join [SignFlow].[dbo].[base_emp] E On FD.empid=E.empid " +
                "left Join [SignFlow].[dbo].[base_signaction] S On FD.signactionid=S.signactionid " +
                "Where FD.flowid=@flowid " +
                " Order By FD.fstep ";
            SqlParameterAdd("@flowid", flowid);
            return SqlFillDT();
        }

        //Bermy start added on 2016/08/18 for approval history
        public DataTable List簽核流程(int fid, int fruleid)
        {
            string id = (fruleid == 1 ? "" : fruleid.ToString());
            SqlParameterClear();
            SqlCommandText = "Select E1.empname sendemp,FD.*,E.empname,signaction,S.signaction " +
                "From [AffectManage].[dbo].[affect_main] A " +
                "Join [SignFlow].[dbo].[base_flow] F on A.affectid=F.fid and F.fruleid=@fruleid " +
                "Join [SignFlow].[dbo].[base_flowd] FD on F.flowid=FD.flowid " +
                "Join [SignFlow].[dbo].[base_emp] E On FD.empid=E.empid " +
                "Join [SignFlow].[dbo].[base_emp] E1 On F.empid=E1.empid " +
                "left Join [SignFlow].[dbo].[base_signaction] S On FD.signactionid=S.signactionid " +
                "Where A.affectid=@fid " +
                "  and ((FD.flowid=A.flowid" + id + ") or (FD.flowid<>A.flowid" + id + " and FD.signtime is not null)) " +
                "Order By FD.flowid,FD.fstep ";
            SqlParameterAdd("@fid", fid);
            SqlParameterAdd("@fruleid", fruleid);
            return SqlFillDT();
        }
        //Bermy end added on 2016/08/18 for approval history

        //Bermy start added on 2018/11/07 for approval history
        public DataTable List簽核流程1(int fid, int fruleid)
        {
            SqlParameterClear();
            SqlCommandText = "Select FD.*,E.empname,signaction,S.signaction " +
                "From [SignFlow].[dbo].[base_flow] F " +
                "Join [SignFlow].[dbo].[base_flowd] FD on F.flowid=FD.flowid " +
                "Join [SignFlow].[dbo].[base_emp] E On FD.empid=E.empid " +
                "left Join [SignFlow].[dbo].[base_signaction] S On FD.signactionid=S.signactionid " +
                "Where F.fid=@fid And F.fruleid=@fruleid " +
                "And ((F.fstatusid = 8 And FD.signtime is not null) Or (F.fstatusid != 8)) " +
                "Order By FD.flowid,FD.fstep ";
            SqlParameterAdd("@fid", fid);
            SqlParameterAdd("@fruleid", fruleid);
            return SqlFillDT();
        }
        //Bermy end added on 2018/11/07 for approval history
        #endregion

        public int Get職稱id(string posname)
        {
            SqlParameterClear();
            SqlCommandText = "Select posid cnt From [SignFlow].[dbo].[base_pos] Where posname=@posname ";
            SqlParameterAdd("@posname", posname);
            int posid = SqlExecuteScalarInt32();
            if (posid <= 0)
            {
                SqlParameterClear();
                SqlCommandText = "INSERT INTO [SignFlow].[dbo].[base_pos]([posname]) Values(@posname); " +
                    "SELECT SCOPE_IDENTITY(); ";
                SqlParameterAdd("@posname", posname);
                posid = SqlExecuteScalarInt32();
            }
            return posid;
        }

        public int Get員工id(string empno)
        {
            SqlParameterClear();
            SqlCommandText = "Select empid cnt From [SignFlow].[dbo].[base_emp] Where empno=@empno ";
            SqlParameterAdd("@empno", empno);
            int empid = SqlExecuteScalarInt32();
            //displayname.description:姓名、mail、telephonenumber:分機、wwwhomepage:部門代碼、department:部門代碼+全名、title:職稱、manager:主管工號
            string[] datas = new string[] { "displayname", "mail", "telephonenumber", "wwwhomepage", "department", "title", "manager" };
            if (empid <= 0)
            {   //沒有員工ID的話就新增
                Hashtable hrow;
                hrow = new Hashtable();
                if (!MTDBbase.Get員工資訊(empno, datas, ref hrow))
                    throw new Exception("找尋員工資訊有誤!");
                int posid = Get職稱id(hrow["title"].ToString());
                SqlParameterClear();
                SqlCommandText = "INSERT INTO [SignFlow].[dbo].[base_emp] " +
                        "([empno],[empname],[email],[posid],[depno],[depname],[telephonenumber]) " +
                        "Values(@empno,@empname,@email,@posid,@depno,@depname,@telephonenumber); " +
                        "SELECT SCOPE_IDENTITY(); ";
                SqlParameterAdd("@empno", empno);
                SqlParameterAdd("@empname", hrow["displayname"] ?? DBNull.Value);
                SqlParameterAdd("@email", hrow["mail"] ?? DBNull.Value);
                SqlParameterAdd("@posid", posid);
                SqlParameterAdd("@depno", hrow["wwwhomepage"] ?? DBNull.Value);
                SqlParameterAdd("@depname", hrow["department"] ?? DBNull.Value);
                SqlParameterAdd("@telephonenumber", hrow["telephonenumber"] ?? DBNull.Value);
                empid = SqlExecuteScalarInt32();
            }
            return empid;
        }

        public int Get員工主管id(string empno)
        {
            string pempno = "";
            if (!MTDBbase.Get員工資訊(empno, "manager", ref pempno) || MTDBbase.IsNullOrEmpty(pempno))
                throw new Exception("找尋員工主管資訊有誤!");
            return Get員工id(pempno);
        }

        public int Get職稱By員工(int empid)
        {
            SqlParameterClear();
            SqlCommandText = "Select posid cnt From [SignFlow].[dbo].[base_emp] Where empid=@empid ";
            SqlParameterAdd("@empid", empid);
            return SqlExecuteScalarInt32();
        }

        public string GetEmail(int empid)
        {
            SqlParameterClear();
            SqlCommandText = "Select email cnt From [SignFlow].[dbo].[base_emp] Where empid=@empid ";
            SqlParameterAdd("@empid", empid);
            return SqlExecuteScalarString();
        }

        public DataTable Get員工資訊(int empid)
        {
            SqlParameterClear();
            SqlCommandText = "Select * From [SignFlow].[dbo].[base_emp] Where empid=@empid ";
            SqlParameterAdd("@empid", empid);
            return SqlFillDT();
        }

        public string Get員工主管Email(string empno, ref string pempno)
        {
            string pemail = "";
            if (!MTDBbase.Get員工資訊(empno, "manager", ref pempno) || MTDBbase.IsNullOrEmpty(pempno))
                throw new Exception("找尋員工主管資訊有誤!");
            MTDBbase.Get員工資訊(pempno, "mail", ref pemail);
            return pemail;
        }

        public int CreateNewFlow(int fruleid, int fid, string empno, int levelcnt, string hashkey, string showinfo)
        {
            try
            {
                SqlBeginTransaction();
                //Step1. 檢查有無此員工基本資料
                int empid = Get員工id(empno);
                int posid = Get職稱By員工(empid);
                SqlParameterClear();
                SqlCommandText = "Select flowurl From [SignFlow].[dbo].[base_flowrule] Where fruleid=@fruleid ";
                SqlParameterAdd("@fruleid", fruleid);
                string flowurl = SqlExecuteScalarString();
                //Step2. 建立簽核流程主檔
                SqlParameterClear();
                SqlCommandText = "INSERT INTO [SignFlow].[dbo].[base_flow]([fruleid],[actstep],[fstatusid],[fid],[signurl],[empid],[fstime],[showinfo]) " +
                        "Values(@fruleid,1,@fstatusid,@fid,@flowurl,@empid,@fstime,@showinfo); " +
                        "SELECT SCOPE_IDENTITY(); ";
                SqlParameterAdd("@fruleid", fruleid);
                SqlParameterAdd("@fstatusid", (int)MTFlowBase.FlowStatus.簽核中);
                SqlParameterAdd("@fid", fid);
                SqlParameterAdd("@flowurl", string.Format("{0}?{1}", flowurl, hashkey));
                SqlParameterAdd("@empid", empid);
                SqlParameterAdd("@fstime", DateTime.Now.ToString("yyyy/MM/dd HH:mm:ss"));
                SqlParameterAdd("@showinfo", showinfo);
                int flowid = SqlExecuteScalarInt32();

                //Step3. 依據要建立的簽核層數,新增往上的簽核人員
                string sempno = empno;
                int oempid = -1, sempid = -1, sposid = -1;
                for (int i = 1; i <= levelcnt; i++)
                {
                    //Bermy marked on 2016/08/09 for "UTI_TQM主管簽核流程" & "UTI_處長簽核流程"
                    //sempid = Get員工主管id(sempno);

                    //Bermy start added on 2016/08/09 for "UTI_TQM主管簽核流程" & "UTI_處長簽核流程"
                    if (fruleid == 3)   //UTI_TQM主管簽核流程
                    {
                        SqlParameterClear();
                        SqlCommandText = "Select B.empno From [AffectManage].[dbo].[affect_main] A " +
                            "Join [AffectManage].[dbo].[affect_main_type] B On A.affecttypeid=B.affecttypeid " +
                            "Where A.affectid=@fid ";
                        SqlParameterAdd("@fid", fid);
                        sempid = Get員工id(SqlExecuteScalarString());
                    }
                    else if (fruleid == 4)  //UTI_處長簽核流程
                    {
                        SqlParameterClear();
                        SqlCommandText = "Select configval From [AffectManage].[dbo].[sys_config] Where configkey='UTI_處長'";
                        sempid = Get員工id(SqlExecuteScalarString());
                    }
                    else
                    {
                        sempid = Get員工主管id(sempno);
                    }
                    //Bermy start added on 2016/08/09 for "UTI_TQM主管簽核流程" & "UTI_處長簽核流程"

                    if (sempid < 0)
                        continue;
                    sposid = Get職稱By員工(sempid);

                    if (fruleid == 1 || fruleid == 2) //異常管理_D4D5送簽 或 異常管理_D6D7送簽
                    {
                        //Bermy added on 2020/04/08 for 若員工的上二階主管是 副總，第二階就跳過
                        if (levelcnt == 2 && i == 2 &&
                            (sposid == (int)職稱ID.副總經理 || sposid == (int)職稱ID.資深副總經理))
                            continue;
                    }
                    else
                    {
                        //若員工的上二階主管是 廠處長 或 副總，第二階就跳過
                        if (levelcnt == 2 && i == 2 &&
                            (sposid == (int)職稱ID.處長 || sposid == (int)職稱ID.資深處長 || sposid == (int)職稱ID.廠長 || sposid == (int)職稱ID.資深廠長 ||
                             sposid == (int)職稱ID.副總經理 || sposid == (int)職稱ID.資深副總經理))
                            continue;
                    }

                    SqlParameterClear();
                    SqlCommandText = "INSERT INTO [SignFlow].[dbo].[base_flowd] " +
                            "([flowid],[fstep],[ftype],[empid],[posid]) " +
                            "Values(@flowid,@fstep,@ftype0,@empid,@posid) ";
                    SqlParameterAdd("@flowid", flowid);
                    SqlParameterAdd("@fstep", i);
                    SqlParameterAdd("@ftype0", (int)MTFlowBase.ReviewerType.人員);
                    SqlParameterAdd("@empid", sempid);
                    SqlParameterAdd("@posid", sposid);
                    SqlExecuteNonQuery();

                    SqlParameterClear();
                    SqlCommandText = "Select empno From [SignFlow].[dbo].[base_emp] Where empid=@empid ";
                    SqlParameterAdd("@empid", sempid);
                    sempno = SqlExecuteScalarString();
                    oempid = sempid;
                }

                //Bermy start added on 2020/05/12 for UTI_TQM主管簽核流程-增加查核者
                if (fruleid == 3)
                {
                    SqlParameterClear();
                    SqlCommandText = "Select Count(*) From [AffectManage].[dbo].[affect_main] " +
                        "Where affectid=@fid And actstep=5 ";   //actstep=5:第三階段主管簽核中
                    SqlParameterAdd("@fid", fid);
                    if (SqlExecuteScalarInt32(0) > 0)
                    {
                        SqlParameterClear();
                        SqlCommandText = "Select B.chkempno From [AffectManage].[dbo].[affect_main] A " +
                            "Join [AffectManage].[dbo].[affect_main_type] B On A.affecttypeid=B.affecttypeid " +
                            "Where A.affectid=@fid ";
                        SqlParameterAdd("@fid", fid);
                        string chkempno = SqlExecuteScalarString();
                        if (chkempno != "")
                        {
                            sempid = Get員工id(chkempno);
                            sposid = Get職稱By員工(sempid);
                            levelcnt++;
                            SqlParameterClear();
                            SqlCommandText = "INSERT INTO [SignFlow].[dbo].[base_flowd] " +
                                    "([flowid],[fstep],[ftype],[empid],[posid]) " +
                                    "Values(@flowid,@fstep,@ftype0,@empid,@posid) ";
                            SqlParameterAdd("@flowid", flowid);
                            SqlParameterAdd("@fstep", levelcnt);
                            SqlParameterAdd("@ftype0", (int)MTFlowBase.ReviewerType.人員);
                            SqlParameterAdd("@empid", sempid);
                            SqlParameterAdd("@posid", sposid);
                            SqlExecuteNonQuery();
                        }
                    }
                }
                //Bermy start added on 2020/05/12 for UTI_TQM主管簽核流程-增加查核者

                //Step4. 撈出內建流程(非上兩階以外的流程)
                SqlParameterClear();
                SqlCommandText = "Select * From [SignFlow].[dbo].[base_flowruled] Where fruleid=@fruleid Order By fstep ";
                SqlParameterAdd("@fruleid", fruleid);
                DataTable fdt = SqlFillDT();
                foreach (DataRow frow in fdt.Rows)
                {
                    levelcnt++;
                    SqlParameterClear();
                    SqlCommandText = "INSERT INTO [SignFlow].[dbo].[base_flowd] " +
                              "([flowid],[fstep],[ftype],[empid],[posid],[bcc]) " +
                              "Values(@flowid,@fstep,@ftype0,@empid,@posid,@bcc) ";
                    SqlParameterAdd("@flowid", flowid);
                    SqlParameterAdd("@fstep", levelcnt);
                    SqlParameterAdd("@ftype0", frow["ftype"]);
                    SqlParameterAdd("@empid", frow["empid"]);
                    SqlParameterAdd("@posid", frow["posid"]);
                    SqlParameterAdd("@bcc", frow["bcc"]);
                    SqlExecuteNonQuery();
                }

                SqlCommit();
                return flowid;
            }
            catch (Exception ex)
            {
                SqlRollback();
                throw new Exception(ex.Message);
            }
        }

        //Bermy start added on 2019/02/27 for 一階群組簽核
        public int CreateNewFlow(int fruleid, int fid, string empno, string plantno, string rtype, string hashkey, string showinfo)
        {
            try
            {
                SqlBeginTransaction();
                //Step1. 檢查有無此員工基本資料
                int empid = Get員工id(empno);
                int posid = Get職稱By員工(empid);
                SqlParameterClear();
                SqlCommandText = "Select flowurl From [SignFlow].[dbo].[base_flowrule] Where fruleid=@fruleid ";
                SqlParameterAdd("@fruleid", fruleid);
                string flowurl = SqlExecuteScalarString();
                //Step2. 建立簽核流程主檔
                SqlParameterClear();
                SqlCommandText = "INSERT INTO [SignFlow].[dbo].[base_flow]([fruleid],[actstep],[fstatusid],[fid],[signurl],[empid],[fstime],[showinfo]) " +
                        "Values(@fruleid,1,@fstatusid,@fid,@flowurl,@empid,@fstime,@showinfo); " +
                        "SELECT SCOPE_IDENTITY(); ";
                SqlParameterAdd("@fruleid", fruleid);
                SqlParameterAdd("@fstatusid", (int)MTFlowBase.FlowStatus.簽核中);
                SqlParameterAdd("@fid", fid);
                SqlParameterAdd("@flowurl", string.Format("{0}?{1}", flowurl, hashkey));
                SqlParameterAdd("@empid", empid);
                SqlParameterAdd("@fstime", DateTime.Now.ToString("yyyy/MM/dd HH:mm:ss"));
                SqlParameterAdd("@showinfo", showinfo);
                int flowid = SqlExecuteScalarInt32();

                //Step3. 依據要建立的簽核群組,新增簽核人員
                int sempid = -1, sposid = -1;

                DataTable dtb = Get簽核人員(plantno, rtype, empno);

                for (int i = 0; i < dtb.Rows.Count; i++)
                {
                    sempid = Get員工id(dtb.Rows[i]["empno"].ToString());
                    sposid = Get職稱By員工(sempid);

                    SqlParameterClear();
                    SqlCommandText = "INSERT INTO [SignFlow].[dbo].[base_flowd] " +
                            "([flowid],[fstep],[ftype],[empid],[posid]) " +
                            "Values(@flowid,@fstep,@ftype0,@empid,@posid) ";
                    SqlParameterAdd("@flowid", flowid);
                    SqlParameterAdd("@fstep", 1);
                    SqlParameterAdd("@ftype0", (int)MTFlowBase.ReviewerType.人員);
                    SqlParameterAdd("@empid", sempid);
                    SqlParameterAdd("@posid", sposid);
                    SqlExecuteNonQuery();
                }

                SqlCommit();
                return flowid;
            }
            catch (Exception ex)
            {
                SqlRollback();
                throw new Exception(ex.Message);
            }
        }
        //Bermy end added on 2019/02/27 for 一階群組簽核

        //Bermy start added on 2019/02/27 for 一階群組簽核人員
        public DataTable Get簽核人員(string plantno, string rtype, string empno)
        {
            SqlParameterClear();
            SqlCommandText = "Select Distinct M.empno " +
                "From [VOC].[dbo].[VOC_Mail_List] M " +
                "Join [UTIDB].[dbo].[Employee] E On M.empno=E.empno And E.isLeave=0 " +
                "Where M.plantno=@plantno And M.RptType in (" + @rtype + ") And M.empno!=@empno And M.SignGrp=1";
            SqlParameterAdd("@plantno", plantno);
            SqlParameterAdd("@rtype", rtype);
            SqlParameterAdd("@empno", empno);
            return SqlFillDT();
        }
        //Bermy end added on 2019/02/27 for 一階群組簽核人員

        //Bermy start added on 2019/04/26 for 執秘+一階多人+二階主管簽核(typeid=0,1,2) 或 二階主管簽核(typeid=3)
        public int CreateNewFlow(int fruleid, int fid, string empno, int plantid, int floorid, int cctvtypeid, int cctvareaid, int typeid, int levelcnt, int ChkFAC, string hashkey, string showinfo)
        {
            try
            {
                SqlBeginTransaction();
                //Step1. 檢查有無此員工基本資料
                int empid = Get員工id(empno);
                int posid = Get職稱By員工(empid);
                SqlParameterClear();
                SqlCommandText = "Select flowurl From [SignFlow].[dbo].[base_flowrule] Where fruleid=@fruleid ";
                SqlParameterAdd("@fruleid", fruleid);
                string flowurl = SqlExecuteScalarString();
                //Step2. 建立簽核流程主檔
                SqlParameterClear();
                SqlCommandText = "INSERT INTO [SignFlow].[dbo].[base_flow]([fruleid],[actstep],[fstatusid],[fid],[signurl],[empid],[fstime],[showinfo]) " +
                        "Values(@fruleid,1,@fstatusid,@fid,@flowurl,@empid,@fstime,@showinfo); " +
                        "SELECT SCOPE_IDENTITY(); ";
                SqlParameterAdd("@fruleid", fruleid);
                SqlParameterAdd("@fstatusid", (int)MTFlowBase.FlowStatus.簽核中);
                SqlParameterAdd("@fid", fid);
                SqlParameterAdd("@flowurl", string.Format("{0}?{1}", flowurl, hashkey));
                SqlParameterAdd("@empid", empid);
                SqlParameterAdd("@fstime", DateTime.Now.ToString("yyyy/MM/dd HH:mm:ss"));
                SqlParameterAdd("@showinfo", showinfo);
                int flowid = SqlExecuteScalarInt32();

                //Step3. 依據要建立的簽核群組,新增簽核人員
                int oempid = -1, sempid = -1, sposid = -1;
                DataTable dtb;
                int cnt;
                int fstep = 0;
                SqlParameterClear();
                SqlCommandText = "Select Count(*) " +
                    "From [SignFlow].[dbo].[base_flow] F " +
                    "Join [SignFlow].[dbo].[base_flowd] D On F.flowid=D.flowid " +
                    "Where F.fruleid=@fruleid And F.fid=@fid";
                SqlParameterAdd("@fruleid", fruleid);
                SqlParameterAdd("@fid", fid);
                int again = SqlExecuteScalarInt32(0);
                if (typeid < 3)
                {
                    dtb = Get簽核人員(plantid, floorid, cctvtypeid, cctvareaid, 0, ChkFAC, fruleid, fid, again);
                    cnt = dtb.Rows.Count;
                    if (cnt > 0) fstep++;
                    for (int i = 0; i < cnt; i++)
                    {
                        sempid = Get員工id(dtb.Rows[i]["empno"].ToString());
                        sposid = Get職稱By員工(sempid);

                        SqlParameterClear();
                        SqlCommandText = "INSERT INTO [SignFlow].[dbo].[base_flowd] " +
                                "([flowid],[fstep],[ftype],[empid],[posid]) " +
                                "Values(@flowid,@fstep,@ftype0,@empid,@posid) ";
                        SqlParameterAdd("@flowid", flowid);
                        SqlParameterAdd("@fstep", fstep);
                        SqlParameterAdd("@ftype0", (int)MTFlowBase.ReviewerType.人員);
                        SqlParameterAdd("@empid", sempid);
                        SqlParameterAdd("@posid", sposid);
                        SqlExecuteNonQuery();
                    }

                    dtb = Get簽核人員(plantid, floorid, cctvtypeid, cctvareaid, typeid, ChkFAC, fruleid, fid, again);
                    cnt = dtb.Rows.Count;
                    if (cnt > 0) fstep++;
                    for (int i = 0; i < cnt; i++)
                    {
                        sempid = Get員工id(dtb.Rows[i]["empno"].ToString());
                        sposid = Get職稱By員工(sempid);

                        SqlParameterClear();
                        SqlCommandText = "INSERT INTO [SignFlow].[dbo].[base_flowd] " +
                                "([flowid],[fstep],[ftype],[empid],[posid]) " +
                                "Values(@flowid,@fstep,@ftype0,@empid,@posid) ";
                        SqlParameterAdd("@flowid", flowid);
                        SqlParameterAdd("@fstep", fstep);
                        SqlParameterAdd("@ftype0", (int)MTFlowBase.ReviewerType.人員);
                        SqlParameterAdd("@empid", sempid);
                        SqlParameterAdd("@posid", sposid);
                        SqlExecuteNonQuery();
                    }
                }

                //Step3. 依據要建立的簽核層數,新增往上的簽核人員
                string sempno = empno;
                for (int i = 1; i <= levelcnt; i++)
                {
                    sempid = Get員工主管id(sempno);
                    if (sempid < 0) continue;
                    //if (i == 1 && sempid == 6859) sempid = 6780;    //Bermy added on 2019/08/26 for HR Barry Sir request
                    //if (i == 1 && sempid == 6859) sempid = 6787;    //Bermy added on 2019/12/11 for HR Hank request
                    //if (i == 1 && sempid == 6859) sempid = 7445;    //Bermy added on 2020/09/01 for HR Hank request
                    if (i == 1 && sempid == 6859) sempid = 9348;    //Bermy added on 2024/01/08 for HR Paja request
                    sposid = Get職稱By員工(sempid);

                    SqlParameterClear();
                    SqlCommandText = "INSERT INTO [SignFlow].[dbo].[base_flowd] " +
                            "([flowid],[fstep],[ftype],[empid],[posid]) " +
                            "Values(@flowid,@fstep,@ftype0,@empid,@posid) ";
                    SqlParameterAdd("@flowid", flowid);
                    SqlParameterAdd("@fstep", fstep + i);
                    SqlParameterAdd("@ftype0", (int)MTFlowBase.ReviewerType.人員);
                    SqlParameterAdd("@empid", sempid);
                    SqlParameterAdd("@posid", sposid);
                    SqlExecuteNonQuery();

                    SqlParameterClear();
                    SqlCommandText = "Select empno From [SignFlow].[dbo].[base_emp] Where empid=@empid ";
                    SqlParameterAdd("@empid", sempid);
                    sempno = SqlExecuteScalarString();
                    oempid = sempid;
                }

                SqlCommit();
                return flowid;
            }
            catch (Exception ex)
            {
                SqlRollback();
                throw new Exception(ex.Message);
            }
        }
        //Bermy end added on 2019/04/26 for 執秘+一階多人+二階主管簽核(typeid=0,1,2) 或 二階主管簽核(typeid=3)

        //Bermy start added on 2019/04/26 for 執秘+一階多人+二階主管簽核(typeid=0,1,2) 或 二階主管簽核(typeid=3)
        public DataTable Get簽核人員(int plantid, int floorid, int cctvtypeid, int cctvareaid, int typeid, int ChkFAC, int fruleid, int fid, int again)
        {
            SqlParameterClear();
            SqlCommandText = "";
            if (again > 0)
            {
                SqlCommandText += "DECLARE @empDT TABLE " +
                    "(empid int PRIMARY KEY); " +
                    "INSERT @empDT " +
                    "Select Distinct D.empid " +
                    "From [SignFlow].[dbo].[base_flow] F " +
                    "Join [SignFlow].[dbo].[base_flowd] D On F.flowid=D.flowid And (D.signactionid!=1 Or D.signactionid is null) " +
                    "Where F.fruleid=@fruleid And F.fid=@fid; ";
            }
            if (typeid == 0)    //執秘
            {
                SqlCommandText += "Select Distinct L.empno " +
                    "From [CCTV].[dbo].[CCTV_checkitem] I " +
                    "Join [CCTV].[dbo].[CCTV_sign_list] L On L.itemlist like '%' + I.itemno + '%' And L.dept='執秘' " +
                    "Join [UTIDB].[dbo].[Employee] E On L.empno=E.empno And E.isLeave=0 ";
            }
            else   //設備申裝前檢核表 OR 設備履歷
            {
                SqlCommandText += "Select Distinct L.empno " +
                    "From [CCTV].[dbo].[CCTV_checkitem] I " +
                    "Join [CCTV].[dbo].[CCTV_sign_list] L On L.itemlist like '%' + I.itemno + '%' And L.dept!='執秘' ";

                if (ChkFAC == 2)    //分樓層
                    SqlCommandText += "And L.dept!='FAC' ";

                SqlCommandText += "Join [UTIDB].[dbo].[Employee] E On L.empno=E.empno And E.isLeave=0 ";
            }
            if (again > 0)
            {
                SqlCommandText += "Join [SignFlow].[dbo].[base_emp] EP On E.empno=EP.empno " +
                    "Join @empDT D On EP.empid=D.empid ";
            }
            SqlCommandText += "Where I.cctvareaid=@cctvareaid And I.cctvtypeid=@cctvtypeid And L.plantid=@plantid ";
            if (typeid != 0)
            {
                if (ChkFAC == 2)
                {
                    SqlCommandText += "Union Select Distinct L.empno " +
                        "From [CCTV].[dbo].[CCTV_sign_list] L " +
                        "Join [UTIDB].[dbo].[Employee] E On L.empno=E.empno And E.isLeave=0 ";
                    if (again > 0)
                    {
                        SqlCommandText += "Join [SignFlow].[dbo].[base_emp] EP On E.empno=EP.empno " +
                            "Join @empDT D On EP.empid=D.empid ";
                    }
                    SqlCommandText += "Where L.plantid=@plantid And L.dept='FAC' And floorid Like @floorid ";
                }
                SqlCommandText += "Union Select Distinct L.empno " +
                    "From [CCTV].[dbo].[CCTV_sign_list] L " +
                    "Join [UTIDB].[dbo].[Employee] E On L.empno=E.empno And E.isLeave=0 ";
                if (again > 0)
                {
                    SqlCommandText += "Join [SignFlow].[dbo].[base_emp] EP On E.empno=EP.empno " +
                        "Join @empDT D On EP.empid=D.empid ";
                }
                SqlCommandText += "Where L.plantid=@plantid And L.dept='GMO' ";
            }
            if (typeid == 2)    //設備履歷
            {
                SqlCommandText += "Union Select Distinct L.empno " +
                    "From [CCTV].[dbo].[CCTV_sign_list] L " +
                    "Join [UTIDB].[dbo].[Employee] E On L.empno=E.empno And E.isLeave=0 ";
                if (again > 0)
                {
                    SqlCommandText += "Join [SignFlow].[dbo].[base_emp] EP On E.empno=EP.empno " +
                        "Join @empDT D On EP.empid=D.empid ";
                }
                SqlCommandText += "Where L.plantid=@plantid And L.dept='UTI' ";
            }
            SqlParameterAdd("@plantid", plantid);
            SqlParameterAdd("@floorid", "%|" + floorid.ToString() + "|%");
            SqlParameterAdd("@cctvtypeid", cctvtypeid);
            SqlParameterAdd("@cctvareaid", cctvareaid);
            SqlParameterAdd("@fruleid", fruleid);
            SqlParameterAdd("@fid", fid);
            return SqlFillDT();
        }
        //Bermy end added on 2019/04/26 for 執秘+一階多人+二階主管簽核(typeid=0,1,2) 或 二階主管簽核(typeid=3)

        public string GetSignUrl(int flowid)
        {
            SqlParameterClear();
            SqlCommandText = "Select signurl From [SignFlow].[dbo].[base_flow] Where flowid=@flowid ";
            SqlParameterAdd("@flowid", flowid);
            return SqlExecuteScalarString();
        }

        public MTFlowBase.FlowStatus GetFlowStatus(int flowid)
        {
            SqlParameterClear();
            SqlCommandText = "Select fstatusid From [SignFlow].[dbo].[base_flow] Where flowid=@flowid ";
            SqlParameterAdd("@flowid", flowid);
            int fstatusid = SqlExecuteScalarInt32(0);
            return (MTFlowBase.FlowStatus)fstatusid;
        }

        public DataTable GetNextStepEmail(int flowid, ref string bcc)
        {
            try
            {
                DataTable dtb = new DataTable();
                dtb.Columns.Add("empid", typeof(Int32));
                dtb.Columns.Add("email", typeof(String));
                SqlParameterClear();
                SqlCommandText = "Select FD.ftype,FD.posid,FD.empid,FD.bcc " +
                    "From [SignFlow].[dbo].[base_flow] F " +
                    "Join [SignFlow].[dbo].[base_flowd] FD ON F.flowid=FD.flowid AND F.actstep=FD.fstep " +
                    "Where F.flowid=@flowid ";
                SqlCommandText += "And FD.signtime is null ";   //Bermy added on 2019/05/08 for 多人簽核時取得未簽核人員
                SqlParameterAdd("@flowid", flowid);
                DataTable flowDT = SqlFillDT();
                //if (flowDT.Rows.Count > 0)  //Bermy marked on 2019/03/01 for 群組簽核
                for (int i = 0; i < flowDT.Rows.Count; i++)  //Bermy added on 2019/03/01 for 群組簽核
                {
                    SqlParameterClear();
                    //switch (MTDBbase.ToInt32(flowDT.Rows[0]["ftype"], -1))  //Bermy marked on 2019/03/01 for 群組簽核
                    switch (MTDBbase.ToInt32(flowDT.Rows[i]["ftype"], -1))  //Bermy added on 2019/03/01 for 群組簽核
                    {
                        //case (int)MTFlowBase.ReviewerType.職位:
                        //    SqlCommandText = "SELECT empid,email FROM [SignFlow].[dbo].[base_emp] WHERE posid=@posid ";
                        //    SqlParameterAdd("@posid", (int)flowDT.Rows[0]["posid"]);
                        //    break;
                        case (int)MTFlowBase.ReviewerType.人員:
                            SqlCommandText = "SELECT empid,email FROM [SignFlow].[dbo].[base_emp] WHERE empid=@empid ";
                            //SqlParameterAdd("@empid", (int)flowDT.Rows[0]["empid"]);    //Bermy marked on 2019/03/01 for 群組簽核
                            SqlParameterAdd("@empid", (int)flowDT.Rows[i]["empid"]);    //Bermy added on 2019/03/01 for 群組簽核
                            break;
                        //case (int)MTFlowBase.ReviewerType.任一:
                        //    SqlCommandText = "Select empid,email From [SignFlow].[dbo].[base_emp] Where posid=@posid OR empid=@empid  ";
                        //    SqlParameterAdd("@posid", MTDBbase.ToInt32(flowDT.Rows[0]["posid"], -1));
                        //    SqlParameterAdd("@empid", MTDBbase.ToInt32(flowDT.Rows[0]["empid"], -1));
                        //    break;
                        default:
                            SqlCommandText = "SELECT empid,email FROM [SignFlow].[dbo].[base_emp] WHERE 1=0 ";
                            break;
                    }
                    bcc = flowDT.Rows[0]["bcc"].ToString();
                    DataTable emailDT = SqlFillDT();
                    foreach (DataRow row in emailDT.Rows)
                        dtb.Rows.Add(row["empid"], row["email"]);
                }
                return dtb;
            }
            catch
            {
                return null;
            }
        }

        public DataTable GetAllStepEmail(int flowid, ref string bcc)
        {
            try
            {
                DataTable dtb = new DataTable();
                dtb.Columns.Add("empid", typeof(Int32));
                dtb.Columns.Add("email", typeof(String));
                // 查所有傳簽人員
                SqlParameterClear();

                //Bermy marked on 2019/03/01 for 群組簽核
                //SqlCommandText = "Select signempid From [SignFlow].[dbo].[base_flowd] Where flowid=@flowid ";

                //Bermy added on 2019/03/01 for 群組簽核
                SqlCommandText = "Select Iif(signempid is null,empid,signempid) signempid From [SignFlow].[dbo].[base_flowd] Where flowid=@flowid ";

                SqlParameterAdd("@flowid", flowid);
                DataTable flowDT = SqlFillDT();
                // 查提交人員
                SqlCommandText = "Select empid  From [SignFlow].[dbo].[base_flow]  Where flowid=@flowid  ";
                SqlParameterClear();
                SqlParameterAdd("@flowid", flowid);
                int fempid = SqlExecuteScalarInt32();
                if (fempid >= 0)
                    flowDT.Rows.Add(fempid);

                if (flowDT.Rows.Count > 0)
                {
                    string empids = "";
                    foreach (DataRow row in flowDT.Rows)
                    {
                        if (row["signempid"] != DBNull.Value)
                        {
                            if (empids.Length > 0) empids += ",";
                            empids += row["signempid"];
                        }
                    }
                    SqlParameterClear();
                    SqlCommandText = "SELECT Distinct empid,email FROM [SignFlow].[dbo].[base_emp] WHERE empid in (" + empids + ")";
                    DataTable emailDT = SqlFillDT();
                    foreach (DataRow row in emailDT.Rows)
                        dtb.Rows.Add(row["empid"], row["email"]);
                }
                return dtb;
            }
            catch
            {
                return null;
            }
        }

        //Bermy start added on 2020/09/25 for 品質異常統計平台:隔離警報申請通過後,知會廠區-樓層所屬QA窗口
        public DataTable GetEmailQA(int ccid)
        {
            SqlParameterClear();
            SqlCommandText = "SELECT DISTINCT M.NotesID " +
                "FROM [S1].[dbo].[fac_closectl] C " +
                "JOIN [S1].[dbo].[fac_closectl_taglist] L ON C.ccid=L.ccid " +
                "JOIN [SPC].[dbo].[SPC_Tag] T ON L.TagName=T.TagName " +
                "JOIN [S1].[dbo].[QA_emaillist] M ON C.plantid=M.plantid AND T.Location=M.Location " +
                "WHERE C.ccid=@ccid";
            SqlParameterAdd("@ccid", ccid);
            return SqlFillDT();
        }
        //Bermy end added on 2020/09/25 for 品質異常統計平台:隔離警報申請通過後,知會廠區-樓層所屬QA窗口

        #region Sign流程&寄送通知

        public bool Sign(Hashtable form, int PosID, int EmpID, string EmpName)
        {
            int flowid = MTDBbase.ToInt32(form["flowid"], -1);
            if (flowid < 0) return false;
            try
            {
                SqlBeginTransaction();
                MTFlowBase.SignAction act = (MTFlowBase.SignAction)form["signactionid"];
                string signmemo = form["signmemo"].ToString();
                // base_flow
                SqlParameterClear();
                SqlCommandText = "Select t2.* From [SignFlow].[dbo].[base_flow] t1 " +
                    "join [SignFlow].[dbo].[base_flowd] t2 On (t1.flowid=t2.flowid and t1.actstep=t2.fstep) " +
                    //"Where t1.flowid=@flowid";  //Bermy marked on 2019/03/01 for 群組簽核
                    "Where t1.flowid=@flowid And t2.empid=@empid";  //Bermy added on 2019/03/01 for 群組簽核
                SqlParameterAdd("@flowid", flowid);
                SqlParameterAdd("@empid", EmpID);
                //DataRow frow = SqlFillDT().Rows[0];   //Bermy marked on 2019/03/01 for 群組簽核
                DataTable frow = SqlFillDT();   //Bermy added on 2019/03/01 for 群組簽核
                // 檢查身份
                bool idpass = false;

                //Bermy start marked on 2019/03/01 for 群組簽核
                //bool ispos = MTDBbase.ToInt32(frow["posid"], -999) == PosID;
                //bool isemp = MTDBbase.ToInt32(frow["empid"], -999) == EmpID;

                //switch (MTDBbase.ToInt32(frow["ftype"], -1)) //0:全部 1:職務 2:員工 3:部門
                //Bermy end marked on 2019/03/01 for 群組簽核

                //Bermy start added on 2019/03/01 for 群組簽核
                bool ispos = false;
                bool isemp = false;

                if (frow.Rows.Count > 0)
                {
                    ispos = MTDBbase.ToInt32(frow.Rows[0]["posid"], -999) == PosID;
                    isemp = MTDBbase.ToInt32(frow.Rows[0]["empid"], -999) == EmpID;

                    switch (MTDBbase.ToInt32(frow.Rows[0]["ftype"], -1)) //0:全部 1:職務 2:員工 3:部門
                    //Bermy end added on 2019/03/01 for 群組簽核
                    {
                        case 0:
                            idpass = (ispos || isemp);
                            break;
                        case 1:
                            idpass = ispos;
                            break;
                        case 2:
                            idpass = isemp;
                            break;
                    }
                }   //Bermy added on 2019/03/01 for 群組簽核
                // SignAction
                if (!idpass)
                    throw new Exception("您不具備簽核資格");

                //int fstep = MTDBbase.ToInt32(frow["fstep"], -1);    //Bermy marked on 2019/03/01 for 群組簽核
                int fstep = MTDBbase.ToInt32(frow.Rows[0]["fstep"], -1);    //Bermy added on 2019/03/01 for 群組簽核
                SqlParameterClear();
                SqlCommandText =
                    "Update [SignFlow].[dbo].[base_flowd] Set signempid=@signempid,signempname=@signempname," +
                    "signtime=@signtime,signactionid=@signactionid,signmemo=@signmemo " +
                    "Where flowid=@flowid And fstep=@fstep And empid=@empid";
                SqlParameterAdd("@signempid", EmpID);
                SqlParameterAdd("@signempname", EmpName);
                SqlParameterAdd("@signtime", DateTime.Now.ToString("yyyy/MM/dd HH:mm:ss"));
                SqlParameterAdd("@signactionid", (int)act);
                SqlParameterAdd("@signmemo", signmemo);
                SqlParameterAdd("@flowid", flowid);
                SqlParameterAdd("@fstep", fstep);
                SqlParameterAdd("@empid", EmpID);
                SqlExecuteNonQuery();

                // get next fstep
                SqlParameterClear();
                SqlCommandText = "Select Min(fstep) From [SignFlow].[dbo].[base_flowd] Where flowid=@flowid and fstep>@fstep ";
                SqlParameterAdd("@flowid", flowid);
                SqlParameterAdd("@fstep", fstep);
                int nextfstep = SqlExecuteScalarInt32();
                // form db

                //Bermy marked on 2016/08/04 to cancel option of "取消"
                //if (nextfstep < 0 || act == MTFlowBase.SignAction.否決 || act == MTFlowBase.SignAction.取消)
                //Bermy added on 2016/08/04 to cancel option of "取消"
                if (nextfstep < 0 || act == MTFlowBase.SignAction.否決)

                {
                    SqlParameterClear();
                    SqlCommandText = "Update [SignFlow].[dbo].[base_flow] Set fetime=@fetime,actstep=NULL,fstatusid=@fstatusid Where flowid=@flowid ";
                    SqlParameterAdd("@flowid", flowid);
                    SqlParameterAdd("@fetime", DateTime.Now.ToString("yyyy/MM/dd HH:mm:ss"));
                    switch (act)
                    {
                        case MTFlowBase.SignAction.核准:
                            SqlParameterAdd("@fstatusid", (int)MTFlowBase.FlowStatus.核准);
                            break;

                        //Bermy start added on 2016/08/04 to add option of "分享"
                        case MTFlowBase.SignAction.分享:
                            SqlParameterAdd("@fstatusid", (int)MTFlowBase.FlowStatus.核准);
                            break;
                        //Bermy end added on 2016/08/04 to add option of "分享"

                        //Bermy start marked on 2016/08/04 to cancel option of "取消"
                        //case MTFlowBase.SignAction.取消:
                        //    SqlParameterAdd("@fstatusid", (int)MTFlowBase.FlowStatus.取消);
                        //    break;
                        //Bermy end marked on 2016/08/04 to cancel option of "取消"

                        case MTFlowBase.SignAction.否決:
                            SqlParameterAdd("@fstatusid", (int)MTFlowBase.FlowStatus.否決);
                            break;
                    }
                    SqlExecuteNonQuery();
                }
                else
                {
                    SqlParameterClear();
                    SqlCommandText = "Update [SignFlow].[dbo].[base_flow] Set actstep=@nextfstep,fstatusid=@fstatusid Where flowid=@flowid";
                    SqlParameterAdd("@flowid", flowid);
                    SqlParameterAdd("@nextfstep", nextfstep);
                    SqlParameterAdd("@fstatusid", (int)MTFlowBase.FlowStatus.簽核中);
                    SqlExecuteNonQuery();
                }

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

        //Bermy start added on 2019/04/26 for 一階多人+二階主管簽核
        public bool Sign1(Hashtable form, int PosID, int EmpID, string EmpName)
        {
            int flowid = MTDBbase.ToInt32(form["flowid"], -1);
            if (flowid < 0) return false;
            try
            {
                SqlBeginTransaction();
                MTFlowBase.SignAction act = (MTFlowBase.SignAction)form["signactionid"];
                string signmemo = form["signmemo"].ToString();
                // base_flow
                SqlParameterClear();
                SqlCommandText = "Select t2.* From [SignFlow].[dbo].[base_flow] t1 " +
                    "join [SignFlow].[dbo].[base_flowd] t2 On (t1.flowid=t2.flowid and t1.actstep=t2.fstep) " +
                    //"Where t1.flowid=@flowid";  //Bermy marked on 2019/03/01 for 群組簽核
                    "Where t1.flowid=@flowid And t2.empid=@empid";  //Bermy added on 2019/03/01 for 群組簽核
                SqlParameterAdd("@flowid", flowid);
                SqlParameterAdd("@empid", EmpID);
                //DataRow frow = SqlFillDT().Rows[0];   //Bermy marked on 2019/03/01 for 群組簽核
                DataTable frow = SqlFillDT();   //Bermy added on 2019/03/01 for 群組簽核
                // 檢查身份
                bool idpass = false;

                //Bermy start marked on 2019/03/01 for 群組簽核
                //bool ispos = MTDBbase.ToInt32(frow["posid"], -999) == PosID;
                //bool isemp = MTDBbase.ToInt32(frow["empid"], -999) == EmpID;

                //switch (MTDBbase.ToInt32(frow["ftype"], -1)) //0:全部 1:職務 2:員工 3:部門
                //Bermy end marked on 2019/03/01 for 群組簽核

                //Bermy start added on 2019/03/01 for 群組簽核
                bool ispos = false;
                bool isemp = false;

                if (frow.Rows.Count > 0)
                {
                    ispos = MTDBbase.ToInt32(frow.Rows[0]["posid"], -999) == PosID;
                    isemp = MTDBbase.ToInt32(frow.Rows[0]["empid"], -999) == EmpID;

                    switch (MTDBbase.ToInt32(frow.Rows[0]["ftype"], -1)) //0:全部 1:職務 2:員工 3:部門
                    //Bermy end added on 2019/03/01 for 群組簽核
                    {
                        case 0:
                            idpass = (ispos || isemp);
                            break;
                        case 1:
                            idpass = ispos;
                            break;
                        case 2:
                            idpass = isemp;
                            break;
                    }
                }   //Bermy added on 2019/03/01 for 群組簽核
                // SignAction
                if (!idpass)
                    throw new Exception("您不具備簽核資格");

                //int fstep = MTDBbase.ToInt32(frow["fstep"], -1);    //Bermy marked on 2019/03/01 for 群組簽核
                int fstep = MTDBbase.ToInt32(frow.Rows[0]["fstep"], -1);    //Bermy added on 2019/03/01 for 群組簽核
                SqlParameterClear();
                SqlCommandText =
                    "Update [SignFlow].[dbo].[base_flowd] Set signempid=@signempid,signempname=@signempname," +
                    "signtime=@signtime,signactionid=@signactionid,signmemo=@signmemo " +
                    "Where flowid=@flowid And fstep=@fstep And empid=@empid";
                SqlParameterAdd("@signempid", EmpID);
                SqlParameterAdd("@signempname", EmpName);
                SqlParameterAdd("@signtime", DateTime.Now.ToString("yyyy/MM/dd HH:mm:ss"));
                SqlParameterAdd("@signactionid", (int)act);
                SqlParameterAdd("@signmemo", signmemo);
                SqlParameterAdd("@flowid", flowid);
                SqlParameterAdd("@fstep", fstep);
                SqlParameterAdd("@empid", EmpID);
                SqlExecuteNonQuery();

                // get next fstep
                SqlParameterClear();
                SqlCommandText = "Select Min(fstep) From [SignFlow].[dbo].[base_flowd] Where flowid=@flowid and signtime is null ";
                SqlParameterAdd("@flowid", flowid);
                SqlParameterAdd("@fstep", fstep);
                int nextfstep = SqlExecuteScalarInt32();
                // form db

                //Bermy marked on 2016/08/04 to cancel option of "取消"
                //if (nextfstep < 0 || act == MTFlowBase.SignAction.否決 || act == MTFlowBase.SignAction.取消)
                //Bermy added on 2016/08/04 to cancel option of "取消"
                if (nextfstep < 0 || act == MTFlowBase.SignAction.否決)
                {
                    SqlParameterClear();
                    SqlCommandText = "Update [SignFlow].[dbo].[base_flow] Set fetime=@fetime,actstep=NULL,fstatusid=@fstatusid Where flowid=@flowid ";
                    SqlParameterAdd("@flowid", flowid);
                    SqlParameterAdd("@fetime", DateTime.Now.ToString("yyyy/MM/dd HH:mm:ss"));
                    switch (act)
                    {
                        case MTFlowBase.SignAction.核准:
                            SqlParameterAdd("@fstatusid", (int)MTFlowBase.FlowStatus.核准);
                            break;

                        //Bermy start added on 2016/08/04 to add option of "分享"
                        case MTFlowBase.SignAction.分享:
                            SqlParameterAdd("@fstatusid", (int)MTFlowBase.FlowStatus.核准);
                            break;
                        //Bermy end added on 2016/08/04 to add option of "分享"

                        //Bermy start marked on 2016/08/04 to cancel option of "取消"
                        //case MTFlowBase.SignAction.取消:
                        //    SqlParameterAdd("@fstatusid", (int)MTFlowBase.FlowStatus.取消);
                        //    break;
                        //Bermy end marked on 2016/08/04 to cancel option of "取消"

                        case MTFlowBase.SignAction.否決:
                            SqlParameterAdd("@fstatusid", (int)MTFlowBase.FlowStatus.否決);
                            break;
                    }
                    SqlExecuteNonQuery();
                }
                else
                {
                    SqlParameterClear();
                    SqlCommandText = "Update [SignFlow].[dbo].[base_flow] Set actstep=@nextfstep,fstatusid=@fstatusid Where flowid=@flowid";
                    SqlParameterAdd("@flowid", flowid);
                    SqlParameterAdd("@nextfstep", nextfstep);
                    SqlParameterAdd("@fstatusid", (int)MTFlowBase.FlowStatus.簽核中);
                    SqlExecuteNonQuery();
                }

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
        //Bermy end added on 2019/04/26 for 一階多人+二階主管簽核

        public string GetMsgtypeStr(int msgtypeid)
        {
            try
            {
                SqlParameterClear();
                SqlCommandText = "Select * From [SignFlow].[dbo].[base_messanger_msgtype] Order by msgtypeid";
                DataTable _msgtype = SqlFillDT();
                _msgtype.PrimaryKey = new DataColumn[] { _msgtype.Columns["msgtypeid"] };
                return _msgtype.Rows.Find(msgtypeid)["msgtype"].ToString();
            }
            catch
            {
                return null;
            }
        }

        public void SendSysMessage(MTFlowBase.MsgType msgtype, int toEmpid, string subject, string msg)
        {
            SqlParameterClear();
            SqlCommandText = "Insert into [SignFlow].[dbo].[base_messanger] (msgtypeid,msgtime,subject,msg,toempid,fromempid) " +
                "Values (@msgtypeid,@now,@subject,@msg,@toempid,NULL)";
            SqlParameterAdd("@msgtypeid", (int)msgtype);
            SqlParameterAdd("@now", DateTime.Now.ToString("yyyy/MM/dd HH:mm:ss"));
            SqlParameterAdd("@subject", subject);
            SqlParameterAdd("@msg", msg);
            SqlParameterAdd("@toempid", toEmpid);
            SqlExecuteNonQuery();
        }

        public bool SendMail通知(Hashtable row, int flowkeyid, int flowid, MTFlowBase.MsgType msgtype)
        {
            try
            {
                string substr = "";
                if (!string.IsNullOrWhiteSpace(row["ccno"] as string))
                    substr = row["ccno"].ToString();   //若有編號,主旨+show編號
                else if (!string.IsNullOrWhiteSpace(row["applyno"] as string))
                    substr = row["applyno"].ToString();
                else if (!string.IsNullOrWhiteSpace(row["affectno"] as string))
                    substr = row["affectno"].ToString();
                else if (!string.IsNullOrWhiteSpace(row["formno"] as string))
                    substr = "表單編號:" + row["formno"].ToString();  //PLC表單編號 Bermy added on 2018/08/23

                SqlParameterClear();
                SqlCommandText = "Select fstatusid From [SignFlow].[dbo].[base_flow] Where flowid=@flowid";
                SqlParameterAdd("@flowid", flowid);
                int cfresultid = MTDBbase.ToInt32(SqlExecuteScalar(), (int)MTFlowBase.FlowStatus.簽核中);
                if (cfresultid != (int)MTFlowBase.FlowStatus.簽核中)
                {
                    if (!Send簽核通知(flowid, flowkeyid, msgtype, substr, true))
                        throw new Exception("寄送簽核完成通知 失敗!" + MTDBbase.Errors.LastErrorMessage);
                }
                else
                {
                    if (!Send簽核通知(flowid, flowkeyid, msgtype, substr, false))
                        throw new Exception("寄送簽核通知 失敗!" + MTDBbase.Errors.LastErrorMessage);
                }
                return true;
            }
            catch (Exception ex)
            {
                MTDBbase.Errors.Add(ex.Message);
                return false;
            }
        }

        public bool Send簽核通知(int flowid, int sendid, MTFlowBase.MsgType msgtypeid, string substr, bool isFinished)
        {
            try
            {
                //檢查若base_flow的fid為NULL -> 將sendid填入fid
                SqlCommandText = "Select fid From [SignFlow].[dbo].[base_flow] Where flowid=@flowid";
                SqlParameterClear();
                SqlParameterAdd("@flowid", flowid);
                int fid = MTDBbase.ToInt32(SqlExecuteScalar(), -1);
                if (fid <= 0)
                {
                    SqlCommandText = "UPDATE [SignFlow].[dbo].[base_flow] SET fid=@sendid Where flowid=@flowid";
                    SqlParameterClear();
                    SqlParameterAdd("@flowid", flowid);
                    SqlParameterAdd("@sendid", sendid);
                    SqlExecuteNonQuery();
                }
                string url = MTFlowBase.GetSignUrl(flowid);
                string msgtype = MTFlowBase.GetMsgtypeStr((int)msgtypeid);
                url = url.Replace("~/", "");
                string subject = "";

                //簽核否決判斷 Bermy start added on 2018/08/23
                SqlParameterClear();
                SqlCommandText = "Select fstatusid From [SignFlow].[dbo].[base_flow] Where flowid=@flowid";
                SqlParameterAdd("@flowid", flowid);
                int resultid = MTDBbase.ToInt32(SqlExecuteScalar(), -1);
                string result = (resultid == (int)MTFlowBase.FlowStatus.否決 ? "退件" : (isFinished ? "完成" : ""));
                //簽核否決判斷 Bermy end added on 2018/08/23

                //寄送信件標題新增(Security C) Bermy start added on 2018/08/23
                if (!string.IsNullOrWhiteSpace(substr))
                    subject = string.Format("{0}{1}通知 [{2}] (Security C)", msgtype, result, substr);
                else
                    subject = string.Format("{0}{1}通知 (Security C)", msgtype, result);
                //寄送信件標題新增(Security C) Bermy end added on 2018/08/23

                string bodyhtml = "<!DOCTYPE html PUBLIC \" -//W3C//DTD XHTML 1.0 Transitional//EN\"><html><body>";
                bodyhtml += "<table cellpadding='1' border='0'>";
                SqlParameterClear();
                SqlCommandText = "SELECT F.flowid,F.fstime,F.fid,R.flowrule,E.empname,F.showinfo,E.email  " +
                                 "FROM [SignFlow].[dbo].[base_flow] F  " +
                                 "JOIN [SignFlow].[dbo].[base_flowrule] R ON F.fruleid=R.fruleid  " +
                                 "JOIN [SignFlow].[dbo].[base_emp] E ON F.empid=E.empid  " +
                                 "WHERE F.flowid=@flowid ";
                SqlParameterAdd("@flowid", flowid);
                DataTable fdt = SqlFillDT();
                string fromstr = "";
                if (fdt.Rows.Count > 0)
                {
                    //內文定義, 讓收件人清楚了解信件重點 Bermy start added on 2018/08/23
                    bodyhtml += string.Format("<tr><td>Dear Sir,</td></tr>");
                    if (!isFinished)
                        bodyhtml += string.Format("<tr><td>您好, 以下文件待您簽核, 請儘速處理, 謝謝!</td></tr><br />");
                    else
                        bodyhtml += string.Format("<tr><td>您好, 以下文件已簽核" + result + ", 請知悉!</td></tr><br />");
                    //內文定義, 讓收件人清楚了解信件重點 Bermy end added on 2018/08/23

                    bodyhtml += string.Format("<tr><td bgcolor='#CCFFCC' style='width: 100px' width='100px'>表單類別</td><td style='width: 400px' width='400px'>{0}</td></tr>", fdt.Rows[0]["flowrule"]);
                    bodyhtml += string.Format("<tr><td bgcolor='#CCFFFF'>表單內容摘要</td><td>{0}</td></tr>", fdt.Rows[0]["showinfo"]);
                    bodyhtml += string.Format("<tr><td bgcolor='#CCFFCC'>提交時間</td><td>{0:yyyy/MM/dd HH:mm:ss}</td></tr>", fdt.Rows[0]["fstime"]);
                    bodyhtml += string.Format("<tr><td bgcolor='#CCFFFF'>提交簽核人員</td><td>{0}</td></tr>", fdt.Rows[0]["empname"]);
                    fromstr = fdt.Rows[0]["email"].ToString();
                }

                if (!isFinished)
                    bodyhtml += string.Format("<tr><td colspan='2' >{0}</td></tr>", "<a href='" + @url + "'>進行簽核</a>");
                //新增"進行查看"的網頁連結 Bermy start added on 2018/08/23
                else
                {
                    url = url.Replace("SignLimitControl","MyApply").Replace("Sign", msgtype.IndexOf("異常管理平台") > -1 ? "Mdf" : "").Replace("Control","MyApply");
                    if (fdt.Rows[0]["showinfo"].ToString().IndexOf("表單狀態:廢除") > -1) url.Replace("CCTVchecklist", "CCTVchecklistDel");
                    bodyhtml += string.Format("<tr><td colspan='2' >{0}</td></tr>", "<a href='" + @url + "'>進行查看</a>");
                }
                //新增"進行查看"的網頁連結 Bermy end added on 2018/08/23
                bodyhtml += "</table></body></html>";

                string bcc = "";
                DataTable dtb;
                if (isFinished)
                    dtb = MTFlowBase.GetAllStepEmail(flowid, ref bcc);
                else
                    dtb = MTFlowBase.GetNextStepEmail(flowid, ref bcc);
                List<string> mailtos = new List<string>();
                foreach (DataRow row in dtb.Rows)
                {
                    MTFlowBase.SendSysMessage(msgtypeid, Convert.ToInt32(row["empid"]), msgtype + "通知", "<a href='" + @url + "'>進行簽核</a>" + bodyhtml);
                    if (string.IsNullOrWhiteSpace(row["email"].ToString())) continue;
                    mailtos.Add(row["email"].ToString());
                }

                //Bermy start added on 2020/09/25 for 品質異常統計平台:隔離警報申請通過後,知會廠區-樓層所屬QA窗口
                if (isFinished && result == "完成" && msgtype.IndexOf("品質異常統計") > -1)
                {
                    DataTable dtbQA = GetEmailQA(sendid);
                    foreach (DataRow row in dtbQA.Rows)
                    {
                        if (string.IsNullOrWhiteSpace(row["NotesID"].ToString())) continue;
                        mailtos.Add(row["NotesID"].ToString().Replace(" ", "_") + "@aseglobal.com");
                    }
                }
                //Bermy end added on 2020/09/25 for 品質異常統計平台:隔離警報申請通過後,知會廠區-樓層所屬QA窗口

                if (!SendMail.寄送Mail通知(subject, bodyhtml, mailtos, fromstr, bcc))
                    throw new Exception("寄送Mail通知 失敗!" + MTDBbase.Errors.LastErrorMessage);

                return true;
            }
            catch (Exception ex)
            {
                MTDBbase.Errors.Add(ex.Message);
                return false;
            }
        }

        #endregion



        #region --- Exception Log ---

        public void SysLogE(Exception exx, string requestPath = null)
        {
            if (exx == null) return;
            try
            {
                SqlParameterClear();
                SqlCommandText = "Insert into [SignFlow].[dbo].[sys_aploge]  " +
                        "(logtime, logsrc, logtype, logmsg, logtrace, loginmsg, logintrace) " +
                        "Values (@now,@logsrc, @logtype, @logmsg,@logtrace, @loginmsg,@logintrace)";
                SqlParameterAdd("@now", DateTime.Now.ToString("yyyy/MM/dd HH:mm:ss"));
                SqlParameterAdd("@logsrc", requestPath ?? "");
                string tname = exx.GetType().FullName;
                if (String.Compare(tname, "System.Exception", StringComparison.OrdinalIgnoreCase) == 0)
                    SqlParameterAdd("@logtype", null);
                else
                    SqlParameterAdd("@logtype", tname);
                SqlParameterAdd("@logmsg", MTDBbase.StringTruncate(exx.Message, 4000));
                SqlParameterAdd("@logtrace", MTDBbase.StringTruncate(exx.StackTrace, 4000));
                if (exx.InnerException != null)
                {
                    SqlParameterAdd("@loginmsg", MTDBbase.StringTruncate(exx.Message, 4000));
                    SqlParameterAdd("@logintrace", MTDBbase.StringTruncate(exx.StackTrace, 4000));
                }
                SqlExecuteNonQuery();
            }
            catch (Exception ex)
            {
                string msg = String.Format("發生錯誤的網頁:{0}\n錯誤訊息:{1}\n堆疊內容:\n{2}\n",
                    requestPath, exx.Message, exx.StackTrace);
                msg += String.Format("發生錯誤的網頁:{0}\n錯誤訊息:{1}\n堆疊內容:\n{2}\n",
                    requestPath, ex.Message, ex.StackTrace);
                MTDBbase.SysLogFile(msg);

                if (exx.InnerException != null)
                {
                    msg = String.Format("\t***內層錯誤訊息:{0}\n\t***堆疊內容:\n{1}\n",
                       exx.InnerException.Message, exx.InnerException.StackTrace);
                    MTDBbase.SysLogFile(msg);
                }
            }
        }

        #endregion


    }
}
