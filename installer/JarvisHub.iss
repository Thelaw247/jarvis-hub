; Builds JarvisHub-Setup.exe from the PyInstaller folder in dist\JarvisHub.
; Run by .github/workflows/release.yml, or by hand:  iscc /DAppVersion=0.1.0 installer\JarvisHub.iss
#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif

[Setup]
AppId={{3F0B7C52-9D1E-4E0A-8B6F-2A7C5D9E41B3}
AppName=Jarvis Hub
AppVersion={#AppVersion}
AppPublisher=Thelaw247
DefaultDirName={autopf}\Jarvis Hub
DisableProgramGroupPage=yes
; installs for the current user, so no administrator password is needed
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=JarvisHub-Setup
SetupIconFile=..\ui\icons\app.ico
UninstallDisplayIcon={app}\JarvisHub.exe
UninstallDisplayName=Jarvis Hub
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Tasks]
Name: "desktopicon"; Description: "Put a shortcut on the desktop"; GroupDescription: "Shortcuts:"

[Files]
Source: "..\dist\JarvisHub\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{autoprograms}\Jarvis Hub"; Filename: "{app}\JarvisHub.exe"
Name: "{autoprograms}\Jarvis Hub (ambient screen)"; Filename: "{app}\JarvisHub.exe"; Parameters: "--ambient"
Name: "{autoprograms}\Jarvis Hub (strip)"; Filename: "{app}\JarvisHub.exe"; Parameters: "--strip"
Name: "{autodesktop}\Jarvis Hub"; Filename: "{app}\JarvisHub.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\JarvisHub.exe"; Description: "Open Jarvis Hub now"; Flags: nowait postinstall skipifsilent
