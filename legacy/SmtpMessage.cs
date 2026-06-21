using System;
using System.Collections.Generic;
using System.Linq;
using System.Net.Mail;
using System.Web;

public class SmtpMessage : SmtpClient
{
    public MailMessage Message;
    public SmtpMessage()
    {
        Message = new MailMessage();
        //Host = "FTC-S1.kh.asegroup.com"; //"10.10.51.62";
        Host = "10.12.10.31"; //IT mail server

        //伺服器:  khaddc03.kh.asegroup.com
        //FTC-S1.kh.asegroup.com
    }
}