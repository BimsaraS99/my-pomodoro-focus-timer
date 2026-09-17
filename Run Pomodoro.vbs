' Double-click to run the timer with no console window.
' Works if Python is installed. (No build required.)
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = scriptDir
sh.Run "pythonw """ & scriptDir & "\pomodoro.pyw""", 0, False
