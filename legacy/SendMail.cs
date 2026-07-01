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

namespace MTLibrary
{
    public class SendMail
    {

        public static bool 寄送Mail通知(string subject, string body, List<string> mailtos, string from = "", string bccs = "")
        {
            try
            {
                SmtpMessage sm = new SmtpMessage();
                if (!MTDBbase.IsNullOrEmpty(from))
                {
                    int idx = from.IndexOf("@");
                    if (idx < 0)
                        idx = from.Length;
                    string fromname = from.Substring(0, idx).Replace("_", " ");
                    sm.Message.From = new MailAddress(from, fromname);
                }
                else
                    sm.Message.From = new MailAddress("Albee_Weng@global.com", "Albee Weng");

                foreach (string tomail in mailtos)
                    sm.Message.To.Add(tomail);

                //if (DateTime.Now <= ChingDueday)
                //    sm.Message.Bcc.Add(Wanching);
                //sm.Message.Bcc.Add(Albee);
                //sm.Message.Bcc.Add(UJ);
                //sm.Message.Bcc.Add(Bermy);  //Bermy added on 2018/08/17
                if (!MTDBbase.IsNullOrEmpty(bccs))
                {
                    string[] bcc = bccs.Split(',');
                    foreach (string bcc0 in bcc)
                        sm.Message.Bcc.Add(bcc0);
                }
                sm.Message.Subject = subject;
                sm.Message.IsBodyHtml = true;
                sm.Message.Body = body;
                sm.Message.BodyEncoding = Encoding.UTF8;
                sm.Send(sm.Message);
                return true;
            }
            catch (Exception ex)
            {
                MTDBbase.Errors.Add(ex.Message);
                return false;
            }
        }
    }
}
