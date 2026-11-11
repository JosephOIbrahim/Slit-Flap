' DEPARTURES silent launcher - double-click to start the board with no console window.
' If the board is already running, it just opens the browser (handled by the CLI).
' Startup errors are appended to launcher.log in the data folder:
' %DEPARTURES_HOME% if set, otherwise %USERPROFILE%\.departures
Option Explicit
Dim fso, sh, here, dataDir
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")
here = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = here

dataDir = sh.ExpandEnvironmentStrings("%DEPARTURES_HOME%")
If dataDir = "%DEPARTURES_HOME%" Or dataDir = "" Then
    dataDir = sh.ExpandEnvironmentStrings("%USERPROFILE%") & "\.departures"
End If
EnsureFolder dataDir

' Full path to the .bat (works even where cmd doesn't search the current folder).
' cmd /c strips the outer pair of quotes, leaving: "<bat>" 2>> "<log>"
sh.Environment("PROCESS")("DEPARTURES_SILENT") = "1"
sh.Run "cmd /c """"" & here & "\departures.bat"" 2>> """ & dataDir & "\launcher.log""""", 0, False

Sub EnsureFolder(path)
    If path <> "" And Not fso.FolderExists(path) Then
        EnsureFolder fso.GetParentFolderName(path)
        fso.CreateFolder path
    End If
End Sub
