#define MyAppName "CAMGOZ"
#define MyAppVersion "0.13.0"
#define MyAppPublisher "CAMGOZ"
#define MyAppExeName "CAMGOZ.exe"

[Setup]
AppId={{7B91E4B2-9B32-4D4D-A8C8-5C8C6D7F0130}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\CAMGOZ
DefaultGroupName=CAMGOZ
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=CAMGOZ_Setup
SetupIconFile=assets\CAMGOZ.ico
WizardImageFile=assets\CAMGOZ_WizardImage.bmp
WizardSmallImageFile=assets\CAMGOZ_WizardSmallImage.bmp
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayIcon={app}\{#MyAppExeName}
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[Tasks]
Name: "desktopicon"; Description: "Masaüstü kısayolu oluştur"; GroupDescription: "Ek kısayollar:"; Flags: unchecked

[Files]
Source: "dist\CAMGOZ\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\CAMGOZ"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\CAMGOZ"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "CAMGOZ uygulamasını başlat"; Flags: postinstall nowait skipifsilent

[UninstallDelete]
; Bilerek AppData\CAMGOZ silinmiyor. Kullanıcı veritabanı korunur.
