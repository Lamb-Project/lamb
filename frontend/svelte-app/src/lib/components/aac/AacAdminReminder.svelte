<script>
    import { onMount } from 'svelte';
    import { base } from '$app/paths';
    import { locale } from '$lib/i18n';
    import { apiJson } from '$lib/services/apiClient';
    import { user } from '$lib/stores/userStore';
    import { sidebarOpen, sidebarMobile } from '$lib/stores/aacStore.svelte';

    /** @typedef {{ id: string, settings_path: string }} Reminder */
    /** @type {Reminder | null} */
    let reminder = $state(null);
    let refresh = $state(0);
    /** @type {Record<string, string[]>} */
    const text = {
        en: ['You can lock your organization to your LMS.', 'This organization accepts LTI launches from any LMS installation that holds the credentials. Locking it to the installation you use is optional and takes one click. Any system whitelist still applies.', 'Open the LMS lock'],
        es: ['Puedes bloquear tu organización a tu LMS.', 'Esta organización acepta lanzamientos LTI de cualquier instalación de LMS que tenga las credenciales. Bloquearla a la instalación que usas es opcional y se hace con un clic. La lista de instalaciones permitidas del sistema se sigue aplicando.', 'Abrir el bloqueo del LMS'],
        ca: ['Pots bloquejar la teva organització al teu LMS.', 'Aquesta organització accepta llançaments LTI de qualsevol instal·lació d’LMS que tingui les credencials. Bloquejar-la a la instal·lació que fas servir és opcional i es fa amb un clic. La llista d’instal·lacions permeses del sistema es continua aplicant.', 'Obre el bloqueig de l’LMS'],
        eu: ['Zure erakundea zure LMSra blokea dezakezu.', 'Erakunde honek kredentzialak dituen edozein LMS instalazioren LTI abiarazteak onartzen ditu. Erabiltzen duzun instalaziora blokeatzea aukerakoa da eta klik bakarrarekin egiten da. Sistemaren baimendutako instalazioen zerrenda aplikatzen da oraindik.', 'Ireki LMS blokeoa']
    };
    let labels = $derived(text[$locale || 'en'] || text.en);
    $effect(() => {
        const token = $user.token;
        const open = $sidebarOpen;
        refresh;
        reminder = null;
        if (!token || !open) return;
        const controller = new AbortController();
        apiJson('/aac/admin-reminders', { token, signal: controller.signal })
            .then(data => {
                if (!controller.signal.aborted) reminder = data.reminders.find((/** @type {Reminder} */ item) => item.id === 'lms_origin_unset') || null;
            })
            .catch(() => { /* Retry on panel reopen, focus or a settings save. */ });
        return () => controller.abort();
    });
    function check() { refresh += 1; }
    onMount(() => {
        window.addEventListener('lamb-lti-access-changed', check);
        return () => window.removeEventListener('lamb-lti-access-changed', check);
    });
</script>

<svelte:window onfocus={check} />
{#if reminder}
    <section class="reminder" aria-label="LAMB LEGATUS reminder" data-aac-reminder="lms-origin">
        <strong>{labels[0]}</strong>
        <p>{labels[1]}</p>
        <a href={`${base}${reminder.settings_path}`} data-sveltekit-reload onclick={() => { if ($sidebarMobile) sidebarOpen.set(false); }}>{labels[2]}</a>
    </section>
{/if}

<style>
    .reminder { flex-shrink: 0; margin: 8px 12px; padding: 12px; border: 1px solid #c6d6e5; border-radius: 8px; background: #f4f8fb; color: #173f64; font-size: 13px; line-height: 1.5; }
    p { margin: 4px 0 8px; }
    a { font-weight: 600; text-decoration: underline; }
</style>
