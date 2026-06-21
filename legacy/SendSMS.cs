using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using SNSCOMSERVER;

public class SendSMS
{
    public static int SMSTryTimes;

    static SendSMS()
    {
        try
        {
            SMSTryTimes = 6;
        }
        catch (Exception)
        {
            SMSTryTimes = 2;
        }

    }

    public static bool SendSMSByCHTProxy(string Message, string Phone, byte Seq)
    {
        return SendSMSByCHT(Message, Phone, Seq);
    }

    public static bool SendSMSByCHT(String Message, String Phone, byte Seq)
    {
        if (string.IsNullOrEmpty(Phone))
        {
            return false;
        }

        try
        {
            //抓取長度限制
            int LengthLimit = 70;
            if (SMSSpliter.CheckStringInAscii(Message))
            {
                //LengthLimit = int.Parse(System.Configuration.ConfigurationManager.AppSettings["MsgLengthAllAscii"].ToString());
                LengthLimit = int.Parse("160");
            }
            else
            {
                //LengthLimit = int.Parse(System.Configuration.ConfigurationManager.AppSettings["MsgLengthNoAscii"].ToString());
                LengthLimit = int.Parse("70");
            }

            //檢查是否超過長度 => 分割傳送or單筆傳送
            if (SMSSpliter.isLondMessage(Message, LengthLimit))
            {
                List<byte[]> msgList = SMSSpliter.SplitStringForComboMessage(Message, LengthLimit, Seq);

                for (int i = 0; i < msgList.Count; i++)
                {
                    Message = Encoding.BigEndianUnicode.GetString(msgList[i]);
                    SendComboSMSByAPI(msgList[i], Phone);
                    System.Threading.Thread.Sleep(25);
                }
            }
            else
            {
                SendSMSByAPI(Message, Phone);
            }
        }
        catch (Exception)
        {
            return false;
        }

        return true;
    }

    /// <summary>
    /// CHT 傳送簡訊API，發送長簡訊
    /// </summary>        
    /// <param name="message">訊息內容被拆成長簡訊格式</param>
    /// <returns></returns>
    private static bool SendComboSMSByAPI(byte[] message, String Phone)
    {

        try
        {
            SNSCOMSERVER.SnsComObject m_sns = new SnsComObject();

            //int loginRes = m_sns.Login(
            //    System.Configuration.ConfigurationManager.AppSettings["SNSIP"].ToString(),
            //    int.Parse(System.Configuration.ConfigurationManager.AppSettings["SNSPort"].ToString()),
            //    System.Configuration.ConfigurationManager.AppSettings["SNSUser"].ToString(),
            //    System.Configuration.ConfigurationManager.AppSettings["SNSPassword"].ToString());

            int loginRes = m_sns.Login("203.66.172.133", int.Parse("8001"), "11307", "11307");

            switch (loginRes)
            {
                case -1:
                    throw new Exception(m_sns.RespMessage + " 無法連線 SNS");
                case 0:
                    int nResult = m_sns.SubmitComboMessage(Phone, message);
                    switch (nResult)
                    {
                        case -1:
                            throw new Exception("請重新連線：" + m_sns.RespMessage + ", 傳送通道發生錯誤");
                        case 0:
                            break;
                        default:
                            break;
                    }
                    break;
                case 1:
                    throw new Exception(m_sns.RespMessage + " 帳號/密碼輸入錯誤");
                default:
                    throw new Exception("[" + loginRes + "] " + m_sns.RespMessage + " 請參考 SNS 文件");
            }

            return true;
        }
        catch (Exception ex)
        {
            throw ex;
        }
    }

    private static bool SendSMSByAPI(String message, String Phone)
    {

        try
        {
            SNSCOMSERVER.SnsComObject m_sns = new SnsComObject();

            //int loginRes = m_sns.Login(
            //    System.Configuration.ConfigurationManager.AppSettings["SNSIP"].ToString(),
            //    int.Parse(System.Configuration.ConfigurationManager.AppSettings["SNSPort"].ToString()),
            //    System.Configuration.ConfigurationManager.AppSettings["SNSUser"].ToString(),
            //    System.Configuration.ConfigurationManager.AppSettings["SNSPassword"].ToString());

            int loginRes = m_sns.Login("203.66.172.133", int.Parse("8001"), "11307", "11307");

            switch (loginRes)
            {
                case -1:
                    throw new Exception(m_sns.RespMessage + " 無法連線 SNS");
                case 0:
                    int nResult = m_sns.SubmitMessage(Phone, message);
                    switch (nResult)
                    {
                        case -1:
                            throw new Exception("請重新連線：" + m_sns.RespMessage + ", 傳送通道發生錯誤");
                        case 0:
                            break;
                        default:
                            break;
                    }
                    break;
                case 1:
                    throw new Exception(m_sns.RespMessage + " 帳號/密碼輸入錯誤");

                default:
                    throw new Exception("[" + loginRes + "] " + m_sns.RespMessage + " 請參考 SNS 文件");
            }

            return true;
        }
        catch (Exception ex)
        {
            throw ex;
        }
    }
}

/// <summary>
/// 將Message分開的class
/// </summary>
public class SMSSpliter
{
    /// <summary>
    /// SplitStringForComboMessage 支持長簡訊 ucs2 修改header
    /// </summary>
    public static Boolean isLondMessage(string strValue, int Len)
    {
        if (String.IsNullOrEmpty(strValue)) return false;
        if (strValue.Length < Len) return false;
        return true;
    }

    /// <summary>
    /// SplitStringForComboMessage 支持長簡訊 ucs2 修改header
    /// </summary>
    /// <param name="strValue"></param>
    /// <param name="Len"></param>
    /// <returns></returns>
    public static List<byte[]> SplitStringForComboMessage(string strValue, int Len, byte Seq)
    {
        if (String.IsNullOrEmpty(strValue)) return null;

        //轉成ucs2
        Encoding enc = Encoding.BigEndianUnicode;
        byte[] intermediate = enc.GetBytes(strValue);

        //算出要分成幾封 for header
        decimal total_msg_cnt = Math.Ceiling((decimal)intermediate.Length / 134);

        //用LINQ切割成 List<byte[]> 處理 header
        int current_length = 0;
        int this_msg_seq = 0;
        var result = intermediate.Aggregate(new List<List<byte>>(), (container, x) =>
        {
            if (container.Count == 0 || current_length >= 133)
            {
                this_msg_seq++;
                // 前三碼(503為辨認碼，第四碼為序號，第五碼
                container.Add(new List<byte>() { 5, 0, 3, Seq, (Byte)total_msg_cnt, (Byte)this_msg_seq, x });
                current_length = 0;
            }
            else
            {
                current_length++;
                container.Last().Add(x);
            }
            return container;
        })
        .Select(lst => lst.ToArray());

        return result.ToList();
    }

    /// <summary>
    /// 將字串拆開成固定長度
    /// </summary>
    /// <param name="strValue">Message will be spilt</param>
    /// <param name="Len">Message spilt to length Len</param>
    /// <returns>Splited Message</returns>
    public static string[] SplitStringIntoSetOfChars(string strValue, int Len)
    {
        double input = strValue.Length;
        double min = Len;
        double res = Math.Ceiling(input / min);
        string[] array = new string[Convert.ToInt32(res)];

        if (!string.IsNullOrEmpty(strValue))
        {
            try
            {
                for (int k = 0; k < array.Length; k++)
                {
                    if (Len > strValue.Length) array[k] = strValue;
                    else
                    {
                        array[k] = strValue.Substring(0, Len);
                        strValue = strValue.Substring(Len);
                    }
                }
                return array;
            }
            catch (Exception ex)
            {
                string[] array2 = { strValue };
                return array2;
            }
        }
        else
        {
            return null;
        }
    }

    /// <summary>
    /// Check Message have not Ascii char
    /// </summary>
    /// <param name="target">Message to check</param>
    /// <returns>true: all Ascii, false: have no Ascii char</returns>
    public static Boolean CheckStringInAscii(String target)
    {
        char[] CharArr = target.ToCharArray();
        for (int i = 0; i < CharArr.Length; i++)
        {
            if (Convert.ToInt32(CharArr[i]) > 255)
            {
                return false;
            }
        }
        return true;
    }
}