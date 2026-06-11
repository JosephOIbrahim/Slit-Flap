' DEPARTURES silent launcher — double-click to start the board with no console window.
' If the board is already running, it just opens the browser (handled by the CLI).
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = fso.GetParentFolderName(WScript.ScriptFullName)
sh.Run "cmd /c departures.bat", 0, False
