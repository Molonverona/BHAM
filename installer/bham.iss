; Script generated for Inno Setup (Windows Installer for BHAM)
; Builds professional Windows setup executable

#define MyAppName "BHAM - BACS Help Auto Mapper"
#define MyAppVersion "1.2.0"
#define MyAppPublisher "BACS Help"
#define MyAppURL "https://github.com/Molonverona/BHAM"
#define MyAppExeName "bham.exe"
; Deve coincidere con WINDOWS_FIREWALL_RULE_NAME in core/system_requirements.py
#define MyFirewallRule "BHAM - BACS Help Auto Mapper"
#define MyAppPort "8765"

[Setup]
AppId={{C28D7B24-8FA9-4B52-87F9-5B26E86D8B09}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\BHAM
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=..\LICENSE
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist-installer
OutputBaseFilename=bham-windows-x64-installer-v{#MyAppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible
; Windows 8.1 e successivi, coerente con le dichiarazioni di bham.exe.manifest
MinVersion=6.3
; Aggiornamento sopra una versione precedente: chiude l'istanza in esecuzione
; tramite Restart Manager invece di fallire con "file in uso".
CloseApplications=yes
RestartApplications=no
SetupMutex=BhamSetupMutex,Global\BhamSetupMutex
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
VersionInfoVersion={#MyAppVersion}
VersionInfoProductVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} Setup

[Languages]
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
; Senza questa regola BHAM risponde solo su localhost: tablet e smartphone di
; cantiere (pairing via QR code) vengono bloccati da Windows Firewall.
Name: "firewall"; Description: "Consenti l'accesso da tablet e smartphone sulla rete LAN (porta {#MyAppPort}/TCP)"; GroupDescription: "Rete e collaudo di campo:"; Check: IsAdminInstallMode

[Files]
Source: "..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "verifica-installazione.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion isreadme
Source: "..\MANUALE_UTENTE.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
; Diagnostica di campo senza dover aprire un prompt a mano. Punta a uno script
; wrapper invece di comporre "cmd /k" con percorsi fra apici annidati: la
; differenza e' verificabile, mentre il quoting annidato compila ma puo'
; rompersi solo a runtime.
Name: "{group}\Verifica installazione (diagnostica)"; Filename: "{app}\verifica-installazione.bat"; IconFilename: "{app}\{#MyAppExeName}"; Comment: "Verifica preflight e motori di protocollo di BHAM"
Name: "{group}\Manuale Utente"; Filename: "{app}\MANUALE_UTENTE.md"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Regola firewall in ingresso per la console web di collaudo (solo se l'utente
; ha accettato il task e l'installazione e' elevata). Una voce di sezione Inno
; Setup deve stare su una sola riga.
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall add rule name=""{#MyFirewallRule}"" dir=in action=allow program=""{app}\{#MyAppExeName}"" enable=yes profile=private,domain protocol=TCP localport={#MyAppPort}"; StatusMsg: "Configurazione di Windows Firewall per l'accesso LAN..."; Flags: runhidden waituntilterminated; Tasks: firewall
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""{#MyFirewallRule}"""; Flags: runhidden waituntilterminated; RunOnceId: "DelBhamFirewallRule"
