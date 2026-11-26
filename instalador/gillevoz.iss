; Instalador do GilleVoz (DESENHO-V2 §12). Montado por instalador\montar.ps1, que antes prepara:
;   ..\ui\dist\win-unpacked\  Electron empacotado (electron-builder, alvo dir)
;   cache\python\            Python 3.12 embutível (zip extraído)
;   cache\motor\             pacote gillevoz + requirements.txt sem pytest
;   cache\get-pip.py
; Layout instalado (o mesmo que ui/src/main/motor.ts resolverPython espera):
;   {app}\app\GilleVoz.exe   {app}\python\pythonw.exe   {app}\motor\gillevoz\

#ifndef Versao
  #define Versao "2.0.0"
#endif

[Setup]
AppId=br.gillezin.gillevoz
AppName=GilleVoz
AppVersion={#Versao}
AppVerName=GilleVoz {#Versao}
AppPublisher=Gillezin
; Só o usuário atual, sem pedir administrador.
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\GilleVoz
; Pasta fixa: o desinstalador apaga {app}\python e {app}\motor inteiras (com as bibliotecas do pip).
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableReadyPage=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=saida
OutputBaseFilename=GilleVoz-Setup
SetupIconFile=icone.ico
UninstallDisplayIcon={app}\app\GilleVoz.exe
UninstallDisplayName=GilleVoz
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
; Quem fecha o GilleVoz antes de instalar é o encerrar.ps1 (PrepareToInstall).
CloseApplications=no

[Languages]
Name: "ptbr"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "atalhodesktop"; Description: "Atalho na Área de Trabalho"; Flags: unchecked
Name: "iniciarwindows"; Description: "Iniciar com o Windows"; Flags: unchecked

[InstallDelete]
; Atualização: tira arquivos que sumiram da versão nova (python\ fica, com as bibliotecas já baixadas).
Type: filesandordirs; Name: "{app}\app"
Type: filesandordirs; Name: "{app}\motor"

[Files]
Source: "..\ui\dist\win-unpacked\*"; DestDir: "{app}\app"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "cache\python\*"; DestDir: "{app}\python"; Excludes: "python312._pth"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "cache\python\python312._pth"; DestDir: "{app}\python"; Flags: ignoreversion; AfterInstall: AjustarPth
Source: "cache\motor\*"; DestDir: "{app}\motor"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "cache\get-pip.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "pos_instalacao.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "encerrar.ps1"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\GilleVoz"; Filename: "{app}\app\GilleVoz.exe"; WorkingDir: "{app}\app"; AppUserModelID: "com.gillevoz.app"
Name: "{autoprograms}\Reparar GilleVoz"; Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\pos_instalacao.ps1"""; WorkingDir: "{app}"; IconFilename: "{app}\app\GilleVoz.exe"; Comment: "Reinstala as bibliotecas do motor e o modelo de voz"
Name: "{autodesktop}\GilleVoz"; Filename: "{app}\app\GilleVoz.exe"; WorkingDir: "{app}\app"; AppUserModelID: "com.gillevoz.app"; Tasks: atalhodesktop

[Registry]
; Mesmo nome e mesmo valor que o Electron grava em "Iniciar com o Windows" no Hub
; (app.setLoginItemSettings com name 'GilleVoz': o caminho do exe entre aspas, sem argumentos).
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "GilleVoz"; ValueData: """{app}\app\GilleVoz.exe"""; Tasks: iniciarwindows; Flags: uninsdeletevalue

[Run]
; A pós-instalação (pos_instalacao.ps1) roda no CurStepChanged, para o instalador saber se deu certo.
Filename: "{app}\app\GilleVoz.exe"; Description: "Abrir o GilleVoz"; Flags: postinstall nowait skipifsilent; Check: PosInstalacaoOk

[UninstallRun]
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\encerrar.ps1"" -Pasta ""{app}"""; Flags: runhidden waituntilterminated; RunOnceId: "EncerrarGilleVoz"

[UninstallDelete]
; O que o pip e o Python criaram depois da instalação. %APPDATA%\GilleVoz (dados do usuário) NÃO é apagada.
Type: filesandordirs; Name: "{app}\python"
Type: filesandordirs; Name: "{app}\motor"
Type: filesandordirs; Name: "{app}\app"
Type: dirifempty; Name: "{app}"
; Cache interno do Chromium da interface (não são dados do usuário; ver ui/src/main/index.ts).
Type: filesandordirs; Name: "{localappdata}\GilleVoz"

[Code]
const
  CHAVE_RUN = 'Software\Microsoft\Windows\CurrentVersion\Run';
  CHAVE_APROVADOS = 'Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run';

function PowerShell: String;
begin
  Result := ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe');
end;

{ Antes de copiar os arquivos: fecha o GilleVoz que estiver aberto (v2 e v1). }
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Codigo: Integer;
begin
  ExtractTemporaryFile('encerrar.ps1');
  Exec(PowerShell, '-NoProfile -ExecutionPolicy Bypass -File "' + ExpandConstant('{tmp}\encerrar.ps1') +
    '" -Pasta "' + ExpandConstant('{app}') + '" -V1', '', SW_HIDE, ewWaitUntilTerminated, Codigo);
  Result := '';
end;

{ python312._pth: liga o "import site" (para o pip e o site-packages) e acrescenta ..\motor
  (o ._pth ignora PYTHONPATH e a pasta atual, então o pacote gillevoz precisa estar listado). }
procedure AjustarPth;
var
  Arquivo: String;
  Linhas: TArrayOfString;
  I, N: Integer;
  TemMotor: Boolean;
begin
  Arquivo := ExpandConstant('{app}\python\python312._pth');
  if not LoadStringsFromFile(Arquivo, Linhas) then
    RaiseException('Não consegui ler ' + Arquivo);
  TemMotor := False;
  N := GetArrayLength(Linhas);
  for I := 0 to N - 1 do
  begin
    if Trim(Linhas[I]) = '#import site' then
      Linhas[I] := 'import site';
    if Trim(Linhas[I]) = '..\motor' then
      TemMotor := True;
  end;
  if not TemMotor then
  begin
    SetArrayLength(Linhas, N + 1);
    Linhas[N] := '..\motor';
  end;
  if not SaveStringsToFile(Arquivo, Linhas, False) then
    RaiseException('Não consegui gravar ' + Arquivo);
end;

var
  PosInstalacaoCodigo: Integer;

{ Depois de copiar os arquivos: pos_instalacao.ps1 numa janela visível (pip, bibliotecas, modelo).
  Se falhar, a opção "Abrir o GilleVoz" some da última tela e o aviso manda rodar o "Reparar GilleVoz". }
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep <> ssPostInstall then
    Exit;
  WizardForm.StatusLabel.Caption := 'Instalando as bibliotecas do motor e o modelo de voz (pode demorar)...';
  if not Exec(PowerShell, '-NoProfile -ExecutionPolicy Bypass -File "' +
      ExpandConstant('{app}\pos_instalacao.ps1') + '"', ExpandConstant('{app}'), SW_SHOWNORMAL,
      ewWaitUntilTerminated, PosInstalacaoCodigo) then
    PosInstalacaoCodigo := -1;
  Log('pos_instalacao.ps1 terminou com código ' + IntToStr(PosInstalacaoCodigo));
  if PosInstalacaoCodigo <> 0 then
    SuppressibleMsgBox('A preparação do motor de voz não terminou (código ' + IntToStr(PosInstalacaoCodigo) +
      ').' + #13#10#13#10 + 'Rode "Reparar GilleVoz" no Menu Iniciar (precisa de internet).',
      mbError, MB_OK, IDOK);
end;

function PosInstalacaoOk: Boolean;
begin
  Result := PosInstalacaoCodigo = 0;
end;

{ Desinstalar: tira o "Iniciar com o Windows" mesmo que tenha sido ligado pelo Hub (não pela tarefa),
  mas só se a entrada for desta instalação. }
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Valor: String;
begin
  if CurUninstallStep <> usPostUninstall then
    Exit;
  if RegQueryStringValue(HKCU, CHAVE_RUN, 'GilleVoz', Valor) and
     (Pos(Lowercase(ExpandConstant('{app}')), Lowercase(Valor)) > 0) then
  begin
    RegDeleteValue(HKCU, CHAVE_RUN, 'GilleVoz');
    RegDeleteValue(HKCU, CHAVE_APROVADOS, 'GilleVoz');
  end;
end;
