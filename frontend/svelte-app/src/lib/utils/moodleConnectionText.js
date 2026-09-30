const en = {
    title: 'Your Moodle', connectedIntro: 'Your connected account and courses.', disconnectedIntro: 'No Moodle account connected.',
    connected: 'Connected', inactive: 'Stored connection is inactive', account: 'You are connected as', storedAccount: 'Stored account',
    versionUnknown: 'Moodle version unavailable', disconnect: 'Disconnect Moodle', connectTo: 'Connect to', connect: 'Connect Moodle',
    connecting: 'Connecting…', disconnected: 'Moodle disconnected.', loading: 'Loading Moodle settings…',
    disabled: 'The Moodle connector is disabled. Your organization administrator can enable it.',
    inactiveHelp: 'Disconnect this inactive account before connecting again.',
    courses: 'Your courses', teacher: 'You are a teacher', student: 'You are a student', other: 'Other or unavailable roles',
    courseCount: n => `${n} ${n === 1 ? 'course' : 'courses'}`,
    noTeacher: 'No courses with a teacher role.', noStudent: 'No courses with a student role.',
    noCourses: 'No enrolled courses were returned by Moodle.', unknownRole: 'Role unavailable', noRole: 'No role returned',
    loadingCourses: 'Reading your Moodle courses…', coursesError: 'Could not load your Moodle version and courses. Your saved connection has been kept.',
    retry: 'Try again', qrIntro: 'Use a fresh Moodle login QR code to connect your account.',
    steps: ['Open your profile in Moodle.', 'Display the QR code for automatic mobile login and take a screenshot.', 'Upload it here within about three minutes.'],
    qrLabel: 'QR code image', formats: 'PNG, JPEG or WebP · up to 5 MiB', imageTooLarge: 'Select a QR image smaller than 5 MiB.',
    alternative: 'Use a passport or token instead', method: 'Connection method', passport: 'QR passport', token: 'Mobile-service token',
    passportHelp: 'Paste the moodlemobile:// address from a fresh login QR code.', tokenHelp: 'Paste the mobile-service token for your own Moodle account.',
    advanced: 'Advanced mode', advancedHelp: 'Show the exact command alongside the explanation when LAMB LEGATUS asks for approval. Applies to all your conversations.',
    saved: 'Preference saved.'
};
const es = {
    title: 'Tu Moodle', connectedIntro: 'Tu cuenta conectada y tus cursos.', disconnectedIntro: 'No hay ninguna cuenta de Moodle conectada.',
    connected: 'Conectado', inactive: 'La conexión guardada está inactiva', account: 'Estás conectado como', storedAccount: 'Cuenta guardada',
    versionUnknown: 'Versión de Moodle no disponible', disconnect: 'Desconectar Moodle', connectTo: 'Conectar a', connect: 'Conectar Moodle',
    connecting: 'Conectando…', disconnected: 'Moodle desconectado.', loading: 'Cargando la configuración de Moodle…',
    disabled: 'El conector de Moodle está desactivado. El administrador de tu organización puede activarlo.', inactiveHelp: 'Desconecta esta cuenta inactiva antes de volver a conectar.',
    courses: 'Tus cursos', teacher: 'Eres docente', student: 'Eres estudiante', other: 'Otros roles o roles no disponibles',
    courseCount: n => `${n} ${n === 1 ? 'curso' : 'cursos'}`, noTeacher: 'No hay cursos con rol docente.', noStudent: 'No hay cursos con rol de estudiante.',
    noCourses: 'Moodle no ha devuelto cursos matriculados.', unknownRole: 'Rol no disponible', noRole: 'No se ha devuelto ningún rol',
    loadingCourses: 'Leyendo tus cursos de Moodle…', coursesError: 'No se han podido cargar la versión de Moodle y tus cursos. Se ha conservado tu conexión.', retry: 'Reintentar',
    qrIntro: 'Usa un código QR de acceso a Moodle recién generado para conectar tu cuenta.',
    steps: ['Abre tu perfil en Moodle.', 'Muestra el código QR de acceso automático desde el móvil y haz una captura de pantalla.', 'Súbela aquí en unos tres minutos.'],
    qrLabel: 'Imagen del código QR', formats: 'PNG, JPEG o WebP · hasta 5 MiB', imageTooLarge: 'Selecciona una imagen QR de menos de 5 MiB.',
    alternative: 'Usar un pasaporte o token', method: 'Método de conexión', passport: 'Pasaporte QR', token: 'Token del servicio móvil',
    passportHelp: 'Pega la dirección moodlemobile:// de un código QR de acceso recién generado.', tokenHelp: 'Pega el token del servicio móvil de tu propia cuenta de Moodle.',
    advanced: 'Modo avanzado', advancedHelp: 'Mostrar el comando exacto junto a la explicación cuando LAMB LEGATUS pide aprobación. Se aplica a todas tus conversaciones.', saved: 'Preferencia guardada.'
};
const ca = {
    title: 'El teu Moodle', connectedIntro: 'El teu compte connectat i els teus cursos.', disconnectedIntro: 'No hi ha cap compte de Moodle connectat.',
    connected: 'Connectat', inactive: 'La connexió desada està inactiva', account: 'Estàs connectat com a', storedAccount: 'Compte desat',
    versionUnknown: 'Versió de Moodle no disponible', disconnect: 'Desconnecta Moodle', connectTo: 'Connecta amb', connect: 'Connecta Moodle',
    connecting: 'Connectant…', disconnected: 'Moodle desconnectat.', loading: 'Carregant la configuració de Moodle…',
    disabled: 'El connector de Moodle està desactivat. L’administrador de la teva organització el pot activar.', inactiveHelp: 'Desconnecta aquest compte inactiu abans de tornar a connectar.',
    courses: 'Els teus cursos', teacher: 'Ets docent', student: 'Ets estudiant', other: 'Altres rols o rols no disponibles',
    courseCount: n => `${n} ${n === 1 ? 'curs' : 'cursos'}`, noTeacher: 'No hi ha cursos amb rol docent.', noStudent: 'No hi ha cursos amb rol d’estudiant.',
    noCourses: 'Moodle no ha retornat cursos matriculats.', unknownRole: 'Rol no disponible', noRole: 'No s’ha retornat cap rol',
    loadingCourses: 'Llegint els teus cursos de Moodle…', coursesError: 'No s’han pogut carregar la versió de Moodle i els teus cursos. S’ha conservat la connexió.', retry: 'Torna-ho a provar',
    qrIntro: 'Fes servir un codi QR d’accés a Moodle acabat de generar per connectar el teu compte.',
    steps: ['Obre el teu perfil a Moodle.', 'Mostra el codi QR d’accés automàtic des del mòbil i fes una captura de pantalla.', 'Puja-la aquí en uns tres minuts.'],
    qrLabel: 'Imatge del codi QR', formats: 'PNG, JPEG o WebP · fins a 5 MiB', imageTooLarge: 'Selecciona una imatge QR de menys de 5 MiB.',
    alternative: 'Fes servir un passaport o token', method: 'Mètode de connexió', passport: 'Passaport QR', token: 'Token del servei mòbil',
    passportHelp: 'Enganxa l’adreça moodlemobile:// d’un codi QR d’accés acabat de generar.', tokenHelp: 'Enganxa el token del servei mòbil del teu compte de Moodle.',
    advanced: 'Mode avançat', advancedHelp: 'Mostra l’ordre exacta al costat de l’explicació quan LAMB LEGATUS demana aprovació. S’aplica a totes les teves converses.', saved: 'Preferència desada.'
};
const eu = {
    title: 'Zure Moodle', connectedIntro: 'Konektatutako kontua eta zure ikastaroak.', disconnectedIntro: 'Ez dago Moodle konturik konektatuta.',
    connected: 'Konektatuta', inactive: 'Gordetako konexioa ez dago aktibo', account: 'Kontu honekin konektatuta zaude:', storedAccount: 'Gordetako kontua',
    versionUnknown: 'Moodle bertsioa ez dago erabilgarri', disconnect: 'Deskonektatu Moodle', connectTo: 'Konektatu hona:', connect: 'Konektatu Moodle',
    connecting: 'Konektatzen…', disconnected: 'Moodle deskonektatuta.', loading: 'Moodle ezarpenak kargatzen…',
    disabled: 'Moodle konektorea desgaituta dago. Zure erakundeko administratzaileak gaitu dezake.', inactiveHelp: 'Deskonektatu kontu inaktibo hau berriro konektatu aurretik.',
    courses: 'Zure ikastaroak', teacher: 'Irakaslea zara', student: 'Ikaslea zara', other: 'Beste rolak edo erabilgarri ez dauden rolak',
    courseCount: n => `${n} ikastaro`, noTeacher: 'Ez dago irakasle-rola duen ikastarorik.', noStudent: 'Ez dago ikasle-rola duen ikastarorik.',
    noCourses: 'Moodle-k ez du matrikulatutako ikastarorik itzuli.', unknownRole: 'Rola ez dago erabilgarri', noRole: 'Ez da rolik itzuli',
    loadingCourses: 'Zure Moodle ikastaroak irakurtzen…', coursesError: 'Ezin izan dira Moodle bertsioa eta zure ikastaroak kargatu. Konexioa gorde da.', retry: 'Saiatu berriro',
    qrIntro: 'Erabili Moodleko saioa hasteko QR kode berri bat zure kontua konektatzeko.',
    steps: ['Ireki zure profila Moodlen.', 'Erakutsi mugikorreko saio-hasiera automatikorako QR kodea eta egin pantaila-argazki bat.', 'Igo hemen hiru minutu inguru igaro baino lehen.'],
    qrLabel: 'QR kodearen irudia', formats: 'PNG, JPEG edo WebP · gehienez 5 MiB', imageTooLarge: 'Hautatu 5 MiB baino txikiagoa den QR irudi bat.',
    alternative: 'Erabili pasaportea edo tokena', method: 'Konexio-metodoa', passport: 'QR pasaportea', token: 'Mugikorreko zerbitzuaren tokena',
    passportHelp: 'Itsatsi saioa hasteko QR kode berri baten moodlemobile:// helbidea.', tokenHelp: 'Itsatsi zure Moodle kontuaren mugikorreko zerbitzuaren tokena.',
    advanced: 'Modu aurreratua', advancedHelp: 'Erakutsi komando zehatza azalpenarekin batera LAMB LEGATUSek onarpena eskatzen duenean. Zure elkarrizketa guztiei aplikatzen zaie.', saved: 'Ezarpena gordeta.'
};
export const moodleConnectionText = locale => ({en, es, ca, eu}[locale] || en);

export function courseGroups(courses = []) {
    const groups = {teacher: [], student: [], other: []};
    for (const course of courses) {
        const roles = course.my_roles_status === 'available' ? (course.my_roles || []) : [];
        const teacher = roles.some(role => ['teacher', 'editingteacher'].includes(role.shortname));
        const student = roles.some(role => role.shortname === 'student');
        if (teacher) groups.teacher.push(course);
        if (student) groups.student.push(course);
        if (!teacher && !student) groups.other.push(course);
    }
    return groups;
}
