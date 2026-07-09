<%@ Page Title="" Language="VB" MasterPageFile="~/Menu.master" AutoEventWireup="false" CodeFile="K222_WWT_COD.aspx.vb" Inherits="K222_WWT_K222_WWT_COD" %>

<asp:Content ID="Content1" ContentPlaceHolderID="head" Runat="Server">
    <style type="text/css">
        .ppWDIW
        {
            position: absolute;
            top: 200px;
            left: 450px;
            z-index: 2;
        }
        .ppWDIW div
        {
            background-color: Black;
            text-align: left;
            width: 660px;
        }
    </style>
</asp:Content>
<asp:Content ID="Content2" ContentPlaceHolderID="ContentPlaceHolder1" Runat="Server">
    <div align="center">
        <asp:Label ID="Label53" runat="server" Text="K222 廢水處理COD 即時" BackColor="#66FF33"
            BorderStyle="Inset" Font-Bold="True" Font-Size="XX-Large" BorderColor="#0066FF"></asp:Label>          
    </div>
    
    <asp:ScriptManager ID="ScriptManager1" runat="server">    </asp:ScriptManager>
    <asp:UpdatePanel ID="UpdatePanel1" runat="server" UpdateMode="Conditional">
        <ContentTemplate>
                   <asp:Panel runat="server" ID="plRegionDiv" Width="800" Height="500">
                <div>
                    <asp:Panel ID="plWDIW" runat="server" CssClass='ppWDIW'>
                    <%--放流池預警COD--%>
                        <asp:Panel ID="Panel1" runat="server" BorderColor="#333399" BorderStyle="Outset">
                            <div align="center">
                                <div style="background-color: LightGreen">
                                    <asp:Label ID="Label2" runat="server" Text="放流池預警COD" Font-Bold="True" Font-Size="Large"></asp:Label>
                                    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
                                    <asp:Label ID="K222_BF_WWWT_T702_MAXII_COD" runat="server" Font-Bold="True" ForeColor="Blue" Font-Size="Large">Reading</asp:Label>
                                    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
                                    <asp:Label ID="Label6" runat="server" Text="pH" Font-Size="Large" ></asp:Label>&nbsp;&nbsp;&nbsp;&nbsp;
                                    <asp:Label ID="Label8" runat="server" Text="L" Font-Bold="true" Font-Size="Large"></asp:Label>&nbsp;                                    
                                    <asp:Label ID="K222_BF_WWWT_T702_MAXII_COD_L" runat="server" Font-Bold="True" ForeColor="Blue" Font-Size="Large">Reading</asp:Label> 
                                    <asp:Label ID="Label10" runat="server" Text="H" Font-Bold="true" Font-Size="Large"></asp:Label>&nbsp;
                                    <asp:Label ID="K222_BF_WWWT_T702_MAXII_COD_H" runat="server" Font-Bold="True" ForeColor="Blue" Font-Size="Large">Reading</asp:Label>
                                </div>
                            </div>
                        </asp:Panel>
                        <%--放流池COD--%>
                        <asp:Panel ID="Panel2" runat="server" BorderColor="#333399" BorderStyle="Outset">
                            <div align="center">
                                <div style="background-color: LightGreen">
                                    <asp:Label ID="Label1" runat="server" Text="放流池COD" Font-Bold="True" Font-Size="Large"></asp:Label>
                                    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
                                    <asp:Label ID="K222_BF_WWWT_T703_COD703_PV" runat="server" Font-Bold="True" ForeColor="Blue" Font-Size="Large">Reading</asp:Label>
                                    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
                                    <asp:Label ID="Label4" runat="server" Text="pH" Font-Size="Large" ></asp:Label>&nbsp;&nbsp;&nbsp;&nbsp;
                                    <asp:Label ID="Label5" runat="server" Text="L" Font-Bold="true" Font-Size="Large"></asp:Label>&nbsp;                                    
                                    <asp:Label ID="K222_BF_WWWT_T703_COD703_PV_L" runat="server" Font-Bold="True" ForeColor="Blue" Font-Size="Large">Reading</asp:Label> 
                                    <asp:Label ID="Label7" runat="server" Text="H" Font-Bold="true" Font-Size="Large"></asp:Label>&nbsp;
                                    <asp:Label ID="K222_BF_WWWT_T703_COD703_PV_H" runat="server" Font-Bold="True" ForeColor="Blue" Font-Size="Large">Reading</asp:Label>
                                </div>
                            </div>
                        </asp:Panel>
                    </asp:Panel>
                </div>
            </asp:Panel>
            <asp:Timer ID="TimerGetData" runat="server" Interval="5000" Enabled="true">
            </asp:Timer>
            <asp:Label ID="LabelReadMessage" runat="server" ForeColor="#FF3300"></asp:Label>
        </ContentTemplate>
    </asp:UpdatePanel>
   <br />
    <br />
    <br />
    <br />
    <br />
    <br />
    <asp:Label ID="Label70" runat="server" Text=" 畫面每5分鐘更新一次近一小時數據" BackColor="Yellow"
             Font-Bold="True" Font-Size="Medium"></asp:Label>   
    <br />
    <br />
    <%--警報發聲--%>
    <asp:UpdatePanel ID="UpdatePanel2" runat="server" UpdateMode="Conditional">
        <ContentTemplate>
            <asp:Label ID="LabelMusic1" runat="server"></asp:Label>
        </ContentTemplate>
    </asp:UpdatePanel>
</asp:Content>

