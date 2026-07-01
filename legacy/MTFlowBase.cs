using System;
using System.Collections;
using System.Collections.Generic;
using System.Data;
using System.Data.SqlClient;
using System.Linq;
using System.Text;

namespace MTLibrary
{
    public class MTFlowBase
    {
        public static string _Exception;
        public MTFlowBase()
        {
            DbSession.SetConnectionString(DbSession.ServerType.SQLServer, @"Data Source=KHTWXAR;Persist Security Info=True;User ID=SignFlow;Password=sasignflow;", (int)MTAppConfig.DataBaseCI.SignFlow);    //我是使用 SignFlow
        }

        public enum FlowStatus
        {
            待簽核 = 0,
            簽核中 = 1,
            核准 = 7,
            否決 = 8,
            取消 = 12,
        };

        public enum SignAction
        {
            核准 = 1,
            //取消 = 8,   //Bermy marked on 2016/08/04 to cancel option of "取消"
            否決 = 9,
            分享 = 10,    //Bermy added on 2016/08/04 to add option of "分享"
        };

        public enum ReviewerType
        {
            //任一 = 0,
            //職位 = 1,
            人員 = 2,
            //類別 = 3,
        }

        public static int Proc建立簽核流程(int fruleid, int fid, string empno, int levelcnt, string hashkey, string showinfo)
        {
            int flowid = -1;
            try
            {
                using (dbSignFlow db = new dbSignFlow())
                    flowid = db.CreateNewFlow(fruleid, fid, empno, levelcnt, hashkey, showinfo);

                return flowid;
            }
            catch (Exception ex)
            {
                _Exception = ex.Message;
                throw new Exception(ex.Message);
            }
        }

        //Bermy start added on 2019/02/27 for 一階群組簽核
        public static int Proc建立簽核流程(int fruleid, int fid, string empno, string plantno, string rtype, string hashkey, string showinfo)
        {
            int flowid = -1;
            try
            {
                using (dbSignFlow db = new dbSignFlow())
                    flowid = db.CreateNewFlow(fruleid, fid, empno, plantno, rtype, hashkey, showinfo);

                return flowid;
            }
            catch (Exception ex)
            {
                _Exception = ex.Message;
                throw new Exception(ex.Message);
            }
        }
        //Bermy end added on 2019/02/27 for 一階群組簽核

        //Bermy start added on 2019/04/26 for 一階多人+二階主管簽核(typeid=1,2) 或 二階主管簽核(typeid=3)
        public static int Proc建立簽核流程(int fruleid, int fid, string empno, int plantid, int floorid, int cctvtypeid, int cctvareaid, int typeid, int levelcnt, int ChkFAC, string hashkey, string showinfo)
        {
            int flowid = -1;
            try
            {
                using (dbSignFlow db = new dbSignFlow())
                    flowid = db.CreateNewFlow(fruleid, fid, empno, plantid, floorid, cctvtypeid, cctvareaid, typeid, levelcnt, ChkFAC, hashkey, showinfo);

                return flowid;
            }
            catch (Exception ex)
            {
                _Exception = ex.Message;
                throw new Exception(ex.Message);
            }
        }
        //Bermy end added on 2019/04/26 for 一階多人+二階主管簽核(typeid=1,2) 或 二階主管簽核(typeid=3)

        public static string Get員工主管Email(string empno, ref string pempno)
        {
            using (dbSignFlow db = new dbSignFlow())
                return db.Get員工主管Email(empno, ref pempno);
        }

        public static string GetEmail(int empid)
        {
            using (dbSignFlow db = new dbSignFlow())
                return db.GetEmail(empid);
        }

        public static DataTable GetNextStepEmail(int flowid, ref string bcc)
        {
            using (dbSignFlow db = new dbSignFlow())
                return db.GetNextStepEmail(flowid, ref bcc);
        }

        public static DataTable GetAllStepEmail(int flowid, ref string bcc)
        {
            using (dbSignFlow db = new dbSignFlow())
                return db.GetAllStepEmail(flowid, ref bcc);
        }

        public static string GetSignUrl(int flowid)
        {
            using (dbSignFlow db = new dbSignFlow())
                return db.GetSignUrl(flowid);
        }

        public static DataTable List簽核結果VL()
        {
            using (dbSignFlow db = new dbSignFlow())
                return db.List簽核結果VL();
        }

        //Bermy start added on 2016/08/04 for "分享" of "UTI_處長簽核流程"
        public static DataTable List簽核結果VL(int actstep)
        {
            using (dbSignFlow db = new dbSignFlow())
                return db.List簽核結果VL(actstep);
        }
        //Bermy end added on 2016/08/04 for "分享" of "UTI_處長簽核流程"

        public static DataTable List簽核流程(int flowid)
        {
            using (dbSignFlow db = new dbSignFlow())
                return db.List簽核流程(flowid);
        }

        //Bermy start added on 2016/08/18 for approval history
        public static DataTable List簽核流程(int fid, int fruleid)
        {
            using (dbSignFlow db = new dbSignFlow())
                return db.List簽核流程(fid, fruleid);
        }
        //Bermy end added on 2016/08/18 for approval history

        //Bermy start added on 2016/08/18 for approval history
        public static DataTable List簽核流程1(int fid, int fruleid)
        {
            using (dbSignFlow db = new dbSignFlow())
                return db.List簽核流程1(fid, fruleid);
        }
        //Bermy end added on 2016/08/18 for approval history

        public static bool Sign(Hashtable form, int PosID, int EmpID, string EmpName)
        {
            using (dbSignFlow db = new dbSignFlow())
            {
                bool isOK = db.Sign(form, PosID, EmpID, EmpName);
                if (!isOK)
                    _Exception = db._Exception;
                return isOK;
            }
        }

        //Bermy start added on 2019/04/26 for 一階多人+二階主管簽核
        public static bool Sign1(Hashtable form, int PosID, int EmpID, string EmpName)
        {
            using (dbSignFlow db = new dbSignFlow())
            {
                bool isOK = db.Sign1(form, PosID, EmpID, EmpName);
                if (!isOK)
                    _Exception = db._Exception;
                return isOK;
            }
        }
        //Bermy end added on 2019/04/26 for 一階多人+二階主管簽核(typeid=1,2) 或 二階主管簽核(typeid=3)

        public static FlowStatus GetFlowStatus(int flowid)
        {
            using (dbSignFlow db = new dbSignFlow())
                return db.GetFlowStatus(flowid);
        }

        public static string GetMsgtypeStr(int msgtypeid)
        {
            using (dbSignFlow db = new dbSignFlow())
                return db.GetMsgtypeStr(msgtypeid);
        }


        public enum MsgType
        {
            圖資管理簽核訊息 = 1,
            品質異常統計簽核訊息 = 2,
            異常管理平台簽核訊息 = 3,
            異常管理平台訊息_需填寫D6D7 = 4,
            廠務PLC程式備份簽核 = 5,
            法遵平台簽核 = 6,
            T廠CCTV設備履歷簽核 = 7,
            T廠CCTV設備申裝前檢核表簽核 = 8,
            T廠既設CCTV設備履歷簽核 = 9,
            T廠CCTV設備故障叫修處理 = 10,
            T廠CCTV設備故障完修簽核 = 11,
        };

        public static void SendSysMessage(MsgType msgtype, int toEmpid, string subject, string msg)
        {
            using (dbSignFlow db = new dbSignFlow())
                db.SendSysMessage(msgtype, toEmpid, subject, msg);
        }
        public static bool SendMail通知(Hashtable row, int flowkeyid, int flowid, MTFlowBase.MsgType msgtype)
        {
            using (dbSignFlow db = new dbSignFlow())
                return db.SendMail通知(row, flowkeyid, flowid, msgtype);
        }
    }
}
