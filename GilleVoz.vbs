' GilleVoz sem janela de console (uso diario).
' Para ver erros na tela, use iniciar.bat.
Option Explicit

Dim fso, sh, pasta, python, comando

Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")

' Pasta onde este .vbs esta (a raiz do projeto)
pasta = fso.GetParentFolderName(WScript.ScriptFullName)
python = pasta & "\.venv\Scripts\pythonw.exe"

If Not fso.FileExists(python) Then
    MsgBox "O GilleVoz ainda nao foi instalado." & vbCrLf & _
           "Rode setup.bat (na pasta do projeto) primeiro.", vbExclamation, "GilleVoz"
    WScript.Quit 1
End If

' Pasta de trabalho = raiz do projeto (o caminho tem espaco, por isso as aspas)
sh.CurrentDirectory = pasta
comando = """" & python & """ -m gillevoz"

' 0 = sem janela; False = nao espera o app terminar
sh.Run comando, 0, False
