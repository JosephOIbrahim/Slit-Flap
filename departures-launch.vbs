' DEPARTURES silent launcher - double-click to start the board with no console window.
' If the board is already up, it opens it in the browser instead of starting another.
' Startup errors are appended to launcher.log in the data folder:
' %DEPARTURES_HOME% if set, otherwise %USERPROFILE%\.departures
' A running board keeps launcher.log open, so a launch that can't open it
' writes to a log of its own, launcher-YYYYMMDD-HHMMSS.log, in the same folder.
Option Explicit
' The browser opens localhost, as the CLI does. The check asks 127.0.0.1, where
' the server listens: asking localhost tries ::1 first, which costs Windows ~2s.
Const BOARD_URL = "http://localhost:4040"
Const PROBE_URL = "http://127.0.0.1:4040/api/session"

Dim fso, sh, here, dataDir, logPath
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")
here = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = here

If BoardIsUp(PROBE_URL) Then
    OpenBoard BOARD_URL
    WScript.Quit 0
End If

dataDir = sh.ExpandEnvironmentStrings("%DEPARTURES_HOME%")
If dataDir = "%DEPARTURES_HOME%" Or dataDir = "" Then
    dataDir = sh.ExpandEnvironmentStrings("%USERPROFILE%") & "\.departures"
End If
EnsureFolder dataDir

logPath = dataDir & "\launcher.log"
If Not StartLog(logPath) Then
    logPath = FreshLog(dataDir)
    If Not StartLog(logPath) Then logPath = ""
End If

' Full path to the .bat (works even where cmd doesn't search the current folder).
' cmd /c strips the outer pair of quotes, leaving: "<bat>" 2>> "<log>"
sh.Environment("PROCESS")("DEPARTURES_SILENT") = "1"
If logPath = "" Then
    sh.Run "cmd /c """"" & here & "\departures.bat""""", 0, False   ' no log can be opened: start anyway
Else
    sh.Run "cmd /c """"" & here & "\departures.bat"" 2>> """ & logPath & """""", 0, False
End If


' True when a DEPARTURES board answers at url (the same check the CLI makes).
Function BoardIsUp(url)
    Dim http
    BoardIsUp = False
    On Error Resume Next
    Set http = CreateObject("MSXML2.ServerXMLHTTP.6.0")
    http.setTimeouts 1000, 1000, 1000, 1000
    http.open "GET", url, False
    http.send
    If Err.Number = 0 Then
        If http.status = 200 And InStr(http.responseText, "startedAt") > 0 Then BoardIsUp = True
    End If
    Err.Clear
    On Error GoTo 0
End Function

Sub OpenBoard(url)
    sh.Run url, 1, False
End Sub

' Appends a launch marker to path. False when it can't be opened for writing,
' for example while a board started from here still holds it.
Function StartLog(path)
    Dim f
    On Error Resume Next
    Set f = fso.OpenTextFile(path, 8, True)
    If Err.Number = 0 Then
        f.WriteLine "--- launch " & Now
        f.Close
    End If
    StartLog = (Err.Number = 0)
    Err.Clear
    On Error GoTo 0
End Function

' A log of this launch's own: launcher-YYYYMMDD-HHMMSS.log, or -2, -3... if taken.
Function FreshLog(folder)
    Dim stamp, path, n
    stamp = Year(Now) & Pad(Month(Now)) & Pad(Day(Now)) & "-" & Pad(Hour(Now)) & Pad(Minute(Now)) & Pad(Second(Now))
    path = folder & "\launcher-" & stamp & ".log"
    n = 2
    Do While fso.FileExists(path)
        path = folder & "\launcher-" & stamp & "-" & n & ".log"
        n = n + 1
    Loop
    FreshLog = path
End Function

Function Pad(n)
    Pad = Right("0" & n, 2)
End Function

Sub EnsureFolder(path)
    If path <> "" And Not fso.FolderExists(path) Then
        EnsureFolder fso.GetParentFolderName(path)
        fso.CreateFolder path
    End If
End Sub
