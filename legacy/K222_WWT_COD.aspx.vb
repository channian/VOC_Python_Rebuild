Imports System.Data.OleDb
Imports System.Web.Configuration
Imports System.Drawing
Imports System.IO
Imports System.Data.SqlClient
Imports System.Data

Partial Class K222_WWT_K222_WWT_COD
    Inherits System.Web.UI.Page

    Dim ParameterScope As String = "K222-BF"
    Dim ParameterSubScope As String = "WWT"

    Dim Shows_H(2) As Double
    Dim Shows_L(2) As Double
    Dim Shows(2) As Label
    Protected Sub Page_Load(ByVal sender As Object, ByVal e As System.EventArgs) Handles Me.Load
        If Not User.Identity.IsAuthenticated Then
            GetLiveValue()
        Else
            If Not IsPostBack Then  'First time execution
                GetLiveValue()
                TimerGetData.Enabled = True
            End If
        End If

    End Sub

    Private Sub GetLiveValue()
        Try
            Shows(0) = K222_BF_WWWT_T703_COD703_PV
            Shows(1) = K222_BF_WWWT_T702_MAXII_COD
            Dim TagNames As String = ""
            Dim NodeName As String = WebConfigurationManager.AppSettings("K222_WWTNodeName")
            For i As Integer = 0 To 1
                TagNames &= "tagname='" & NodeName & "." & Shows(i).ID & ".F_CV' OR "
            Next

            TagNames = TagNames.Substring(0, TagNames.Length - 4)


            Dim SQL As String
            SQL = "SET SamplingMode = CurrentValue ; "
            SQL &= "SELECT tagname,value,quality FROM iHRawData WHERE "
            SQL &= TagNames

            Using cnn As New OleDbConnection(WebConfigurationManager.ConnectionStrings("K222iHConnectionString").ConnectionString)
                cnn.Open()
                Dim cmd As OleDbCommand = cnn.CreateCommand
                cmd.CommandText = SQL
                Dim dr As OleDbDataReader = cmd.ExecuteReader
                If dr.HasRows Then
                    Dim NewAlarm As Boolean = False
                    Dim Pvv As String
                    ReadiniSetting()
                    While dr.Read
                        If Not dr.IsDBNull(0) Then
                            For i As Integer = 0 To Shows.Length - 1
                                If dr.GetString(0).Trim.ToUpper = (NodeName & "." & Shows(i).ID & ".F_CV").ToUpper Then
                                    Pvv = If(dr.IsDBNull(1), "###", CType(dr.GetValue(1), Double).ToString("0.0"))
                                    Shows(i).Text = Pvv
                                    If dr.GetString(2) <> "Good NonSpecific" Then
                                        Pvv = "###"
                                        Shows(i).Text = Pvv
                                    End If
                                    If i >= 0 And i <= 1 Then
                                        If CheckNewAlarm(Shows(i), Shows(i).ID, Pvv, Shows_H(i), Shows_L(i)) Then
                                            NewAlarm = True
                                        End If
                                    End If
                                    Exit For
                                End If
                            Next
                        End If
                    End While
                    If NewAlarm Then
                        LabelMusic1.Text = "<embed src='../../Images/11113151140.mp3' autostart='true' repeat='true' loop='true' height='43px' > </embed>"
                        'ButtonStopMusic.Visible = True
                        UpdatePanel2.Update()
                    End If
                End If
            End Using
            LabelReadMessage.Text = ""
        Catch ex As Exception
            LabelReadMessage.Text = "讀取 IHistorian 失敗!!<br/>" & ex.Message
            LabelReadMessage.Focus()
        End Try
    End Sub

    Private Sub TimerGetData_Tick(ByVal sender As Object, ByVal e As System.EventArgs) Handles TimerGetData.Tick
        TimerGetData.Enabled = False
        GetLiveValue()
        TimerGetData.Enabled = True
    End Sub

    Private Function CheckNewAlarm(ByRef lab As System.Web.UI.WebControls.Label, ByVal SessionName As String, ByVal PV As String, ByVal H As Double, ByVal L As Double) As Boolean
        Dim Result, NewAlarm As Boolean
        'NewAlarm = False
        'If Session(SessionName) Is Nothing Then
        '    Session(SessionName) = False
        'End If
        'Result = Tag_Alarm(lab, PV, H, L)
        'NewAlarm = Not CBool(Session(SessionName)) AndAlso Result
        'Session(SessionName) = Result
        'Return NewAlarm
        Result = Tag_Alarm(lab, PV, H, L)
        Return Result
    End Function

    Private Function Tag_Alarm(ByRef lab As System.Web.UI.WebControls.Label, ByVal PV As String, ByVal H As Double, ByVal L As Double) As Boolean
        Try
            If PV <> "###" Then
                Dim P As Double = CType(PV, Double)
                If H = Double.NaN AndAlso L = Double.NaN Then
                    lab.BackColor = Nothing
                ElseIf H = Double.NaN Then
                    If P < L Then
                        lab.BackColor = Color.Red
                        Return True
                    Else
                        lab.BackColor = Nothing
                    End If
                ElseIf L = Double.NaN Then
                    If P > H Then
                        lab.BackColor = Color.Red
                        Return True
                    Else
                        lab.BackColor = Nothing
                    End If
                Else
                    If P > H OrElse P < L Then
                        lab.BackColor = Color.Red
                        Return True
                    Else
                        lab.BackColor = Nothing
                    End If
                End If
            Else
                lab.BackColor = Color.Red
            End If
            Return False
        Catch ex As Exception
            Return False
        End Try
    End Function

    'Protected Sub ButtonStopMusic_Click(ByVal sender As Object, ByVal e As System.EventArgs) Handles ButtonStopMusic.Click
    '    LabelMusic.Text = ""
    '    ButtonStopMusic.Visible = False
    'End Sub

    Private Sub ReadiniSetting()
        Try
            For i As Integer = 0 To Shows.Length - 1
                Shows_L(i) = Double.NaN
                Shows_H(i) = Double.NaN
            Next
            Using cnn As New SqlConnection(WebConfigurationManager.ConnectionStrings("AseLaiSecurityConnectionString").ConnectionString)
                cnn.Open()
                Dim cmd As SqlCommand = cnn.CreateCommand
                cmd.CommandText = "SELECT [ItemTag],[ItemValue],[ItemName] FROM [Parameter] WHERE " & _
                    "[Scope]='" & ParameterScope & "' AND [SubScope]='" & ParameterSubScope & "'"


                Dim dr As SqlDataReader = cmd.ExecuteReader
                If dr.HasRows Then
                    While dr.Read
                        Select Case dr.GetString(0)

                            Case "SamplingTime"
                                TimerGetData.Interval = CInt(dr.GetDouble(1))
                            Case "T703_COD_L"
                                Shows_L(0) = dr.GetDouble(1)
                                K222_BF_WWWT_T703_COD703_PV_L.Text = Shows_L(0).ToString("0.0")
                                K222_BF_WWWT_T702_MAXII_COD_L.Text = Shows_L(0).ToString("0.0")
                            Case "T703_COD_H"
                                Shows_H(0) = dr.GetDouble(1)
                                K222_BF_WWWT_T703_COD703_PV_H.Text = Shows_H(0).ToString("0.0")
                                K222_BF_WWWT_T702_MAXII_COD_H.Text = Shows_H(0).ToString("0.0")
                        End Select
                    End While
                Else
                    Throw New Exception("沒有資料!")
                End If
            End Using
        Catch ex As Exception
            Throw New Exception("找不到參數設定值!" & ex.Message)
        End Try
    End Sub
End Class
