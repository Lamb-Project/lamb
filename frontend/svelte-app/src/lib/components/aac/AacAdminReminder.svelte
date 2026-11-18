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
        en: ['Please set your organization’s Moodle URL.', 'LTI access currently continues without checking the organization’s LMS origin. Set it to restrict access to your Moodle. The global whitelist still applies.', 'Set Moodle URL'],
        es: ['Configura la URL de Moodle de tu organización.', 'El acceso LTI continúa sin comprobar el origen del LMS de la organización. Configúralo para restringir el acceso a tu Moodle. La lista global de permitidos sigue aplicándose.', 'Configurar URL de Moodle'],
        ca: ['Configura l’URL de Moodle de la teva organització.', 'L’accés LTI continua sense comprovar l’origen de l’LMS de l’organització. Configura’l per restringir l’accés al teu Moodle. La llista global de llocs permesos continua aplicant-se.', 'Configurar l’URL de Moodle'],
        eu: ['Konfiguratu zure erakundearen Moodle URLa.', 'LTI sarbideak erakundearen LMS jatorria egiaztatu gabe jarraitzen du. Konfiguratu zure Moodlera mugatzeko. Baimendutako guneen zerrenda globala aplikatzen da.', 'Konfiguratu Moodle URLa']
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
