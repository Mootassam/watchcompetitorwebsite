; RivalRadar installer — ships the official, digitally signed Python runtime (Python Software
; Foundation) with the app, so Windows Smart App Control can verify what it runs.
; Build: powershell -ExecutionPolicy Bypass -File build.ps1   (stages build_embed\ then runs ISCC)

#define MyAppName "RivalRadar"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "RivalRadar"

[Setup]
AppId={{F7A4C9E2-3B1D-4E6A-9C5F-RIVALRADAR001}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DisableProgramGroupPage=yes
DisableDirPage=auto
OutputDir=installer_output
OutputBaseFilename=RivalRadar-Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible
SetupIconFile=rivalradar.ico
UninstallDisplayIcon={app}\app\rivalradar.ico
UninstallDisplayName={#MyAppName}
CloseApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; Flags: checkedonce

[InstallDelete]
; replace program files cleanly on every upgrade
Type: filesandordirs; Name: "{app}\app"
Type: filesandordirs; Name: "{app}\runtime"

[Files]
Source: "build_embed\runtime\*"; DestDir: "{app}\runtime"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "build_embed\app\*"; DestDir: "{app}\app"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\runtime\pythonw.exe"; Parameters: """{app}\app\server.py"""; WorkingDir: "{app}\app"; IconFilename: "{app}\app\rivalradar.ico"; Comment: "Competitor intelligence & website-change monitor"
Name: "{userdesktop}\{#MyAppName}"; Filename: "{app}\runtime\pythonw.exe"; Parameters: """{app}\app\server.py"""; WorkingDir: "{app}\app"; IconFilename: "{app}\app\rivalradar.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\runtime\pythonw.exe"; Parameters: """{app}\app\server.py"""; WorkingDir: "{app}\app"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[Code]
{ Close a running RivalRadar so its files can be replaced or removed: python/pythonw started
  from the install folder or the data folder. Only those processes are touched. }
procedure StopRivalRadar();
var
  Rc: Integer;
  Cmd, AppDir, DataDir: String;
begin
  AppDir := Lowercase(ExpandConstant('{app}'));
  DataDir := Lowercase(ExpandConstant('{localappdata}\RivalRadar'));
  Cmd := '-NoProfile -ExecutionPolicy Bypass -Command "Get-Process python,pythonw -ErrorAction SilentlyContinue | ' +
         'Where-Object { $_.Path -and ($_.Path.ToLower().StartsWith(''' + AppDir + ''') -or $_.Path.ToLower().StartsWith(''' + DataDir + ''')) } | ' +
         'Stop-Process -Force -ErrorAction SilentlyContinue; Start-Sleep -Milliseconds 900"';
  Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'), Cmd, '', SW_HIDE, ewWaitUntilTerminated, Rc);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  StopRivalRadar();
  Result := '';
end;

function InitializeUninstall(): Boolean;
begin
  StopRivalRadar();
  Result := True;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    DataDir := ExpandConstant('{localappdata}\RivalRadar');
    if DirExists(DataDir) and not UninstallSilent() then
      if MsgBox('Also delete your RivalRadar data?' + #13#10 + #13#10 +
                'This permanently removes your tracked competitors, change history, snapshots and settings from this computer.' + #13#10 + #13#10 +
                'Choose No to keep them (they come back if you reinstall).',
                mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
        DelTree(DataDir, True, True, True);
  end;
end;

[UninstallDelete]
Type: filesandordirs; Name: "{app}\app"
Type: filesandordirs; Name: "{app}\runtime"
Type: dirifempty; Name: "{app}"
