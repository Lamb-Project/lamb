const en = {
    platform: 'Your computer', prepare: 'Prepare local command', preparing: 'Preparing…',
    command: 'Local connection command', run: 'Run the command on your computer',
    help: 'Copy the command, open a terminal on the computer and network where you generated the QR, paste it and press Enter. Run it immediately: the QR expires about three minutes after generation.',
    macHelp: 'macOS: use Terminal. Requires curl and Python 3.',
    linuxHelp: 'Linux: requires curl, Python 3 and wl-clipboard (Wayland) or xclip/xsel (X11). Use a desktop terminal.',
    windowsHelp: 'Windows: use PowerShell with curl.exe and Set-Clipboard available.',
    copy: 'Copy command', copied: 'Command copied. Run it in your terminal.',
    manualCopy: 'Automatic copy is unavailable. Select and copy the complete command above.',
    private: 'This command contains your single-use login passport. Do not share it. After connecting, clear it from terminal history and replace the token in your clipboard.',
    paste: 'Paste the token and connect', tokenHelp: 'After the terminal confirms the token was copied, paste it here. You can also use an existing mobile-service token for your account.'
};
const es = {
    platform: 'Tu ordenador', prepare: 'Preparar comando local', preparing: 'Preparando…',
    command: 'Comando de conexión local', run: 'Ejecuta el comando en tu ordenador',
    help: 'Copia el comando, abre un terminal en el ordenador y la red donde generaste el QR, pégalo y pulsa Intro. Ejecútalo enseguida: el QR caduca unos tres minutos después de generarlo.',
    macHelp: 'macOS: usa Terminal. Necesitas curl y Python 3.',
    linuxHelp: 'Linux: necesitas curl, Python 3 y wl-clipboard (Wayland) o xclip/xsel (X11). Usa un terminal de escritorio.',
    windowsHelp: 'Windows: usa PowerShell con curl.exe y Set-Clipboard disponibles.',
    copy: 'Copiar comando', copied: 'Comando copiado. Ejecútalo en tu terminal.',
    manualCopy: 'No se puede copiar automáticamente. Selecciona y copia el comando completo de arriba.',
    private: 'El comando contiene tu pasaporte de acceso de un solo uso. No lo compartas. Tras conectar, bórralo del historial del terminal y sustituye el token del portapapeles.',
    paste: 'Pega el token y conecta', tokenHelp: 'Cuando el terminal confirme que ha copiado el token, pégalo aquí. También puedes usar un token existente del servicio móvil de tu cuenta.'
};
const ca = {
    platform: 'El teu ordinador', prepare: 'Prepara l’ordre local', preparing: 'Preparant…',
    command: 'Ordre de connexió local', run: 'Executa l’ordre al teu ordinador',
    help: 'Copia l’ordre, obre un terminal a l’ordinador i la xarxa on has generat el QR, enganxa-la i prem Retorn. Executa-la de seguida: el QR caduca uns tres minuts després de generar-lo.',
    macHelp: 'macOS: fes servir Terminal. Calen curl i Python 3.',
    linuxHelp: 'Linux: calen curl, Python 3 i wl-clipboard (Wayland) o xclip/xsel (X11). Fes servir un terminal d’escriptori.',
    windowsHelp: 'Windows: fes servir PowerShell amb curl.exe i Set-Clipboard disponibles.',
    copy: 'Copia l’ordre', copied: 'Ordre copiada. Executa-la al terminal.',
    manualCopy: 'No es pot copiar automàticament. Selecciona i copia tota l’ordre de dalt.',
    private: 'L’ordre conté el teu passaport d’accés d’un sol ús. No el comparteixis. Després de connectar, esborra’l de l’historial del terminal i substitueix el token del porta-retalls.',
    paste: 'Enganxa el token i connecta', tokenHelp: 'Quan el terminal confirmi que ha copiat el token, enganxa’l aquí. També pots fer servir un token existent del servei mòbil del teu compte.'
};
const eu = {
    platform: 'Zure ordenagailua', prepare: 'Prestatu komando lokala', preparing: 'Prestatzen…',
    command: 'Konexio lokalaren komandoa', run: 'Exekutatu komandoa zure ordenagailuan',
    help: 'Kopiatu komandoa eta itsatsi QR kodea sortu duzun ordenagailuko terminalean, sare berean. Sakatu Enter berehala: QR kodea sortu eta hiru minutu ingurura iraungitzen da.',
    macHelp: 'macOS: erabili Terminal. curl eta Python 3 behar dira.',
    linuxHelp: 'Linux: curl, Python 3 eta wl-clipboard (Wayland) edo xclip/xsel (X11) behar dira. Erabili mahaigaineko terminala.',
    windowsHelp: 'Windows: erabili PowerShell, curl.exe eta Set-Clipboard erabilgarri dituela.',
    copy: 'Kopiatu komandoa', copied: 'Komandoa kopiatuta. Exekutatu terminalean.',
    manualCopy: 'Ezin da automatikoki kopiatu. Hautatu eta kopiatu goiko komando osoa.',
    private: 'Komandoak erabilera bakarreko pasaportea dauka. Ez partekatu. Konektatu ondoren, ezabatu terminalaren historiatik eta ordeztu arbeleko tokena.',
    paste: 'Itsatsi tokena eta konektatu', tokenHelp: 'Terminalak tokena kopiatu dela baieztatzen duenean, itsatsi hemen. Zure kontuaren mugikorreko zerbitzuaren token bat ere erabil dezakezu.'
};
export const qrCommandText = locale => ({en, es, ca, eu}[locale] || en);
