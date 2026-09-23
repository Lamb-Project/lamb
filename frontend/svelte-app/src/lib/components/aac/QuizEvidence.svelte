<script>
    let { metrics, language = 'en' } = $props();
    const messages = {
        en: ['Attempts and retries', 'Scored pairs (attempts 1 and 2)', 'Mean score change (percentage points)', 'Median gap between attempts (seconds)', 'Pairs missing marks', 'Finished attempts per current student', 'Finished attempts', 'Students', 'Unavailable', 'Only actual finished attempts 1 and 2 with both marks are compared. Questions may differ. Score change does not establish learning; the gap is not study time.'],
        es: ['Intentos y repeticiones', 'Pares con puntuación (intentos 1 y 2)', 'Cambio medio de puntuación (puntos porcentuales)', 'Intervalo mediano entre intentos (segundos)', 'Pares con puntuaciones ausentes', 'Intentos finalizados por estudiante actual', 'Intentos finalizados', 'Estudiantes', 'No disponible', 'Solo se comparan los intentos reales 1 y 2 finalizados y con ambas puntuaciones. Las preguntas pueden variar. El cambio de puntuación no demuestra aprendizaje; el intervalo no es tiempo de estudio.'],
        ca: ['Intents i repeticions', 'Parelles amb puntuació (intents 1 i 2)', 'Canvi mitjà de puntuació (punts percentuals)', 'Mediana de l’interval entre intents (segons)', 'Parelles amb puntuacions absents', 'Intents finalitzats per estudiant actual', 'Intents finalitzats', 'Estudiants', 'No disponible', 'Només es comparen els intents reals 1 i 2 finalitzats i amb totes dues puntuacions. Les preguntes poden variar. El canvi de puntuació no demostra aprenentatge; l’interval no és temps d’estudi.'],
        eu: ['Saiakerak eta errepikapenak', 'Puntuazioa duten bikoteak (1. eta 2. saiakerak)', 'Batez besteko puntuazio-aldaketa (ehuneko-puntuak)', 'Saiakeren arteko tartearen mediana (segundoak)', 'Puntuazioak falta dituzten bikoteak', 'Amaitutako saiakerak uneko ikasleko', 'Amaitutako saiakerak', 'Ikasleak', 'Ez dago eskuragarri', 'Benetako 1. eta 2. saiakera amaituak bakarrik alderatzen dira, bi puntuazioak daudenean. Galderak desberdinak izan daitezke. Puntuazio-aldaketak ez du ikaskuntza frogatzen; tartea ez da ikasteko denbora.']
    };
    const text = $derived(messages[language] || messages.en);
    const pair = $derived(metrics?.retry_1_to_2);
    const values = $derived([pair?.score_change_percentage_points?.n,
        pair?.score_change_percentage_points?.mean, pair?.between_attempt_seconds?.median, pair?.ungraded_pairs]);
    function number(value) {
        return typeof value === 'number' && Number.isFinite(value)
            ? new Intl.NumberFormat(language, {maximumFractionDigits: 4}).format(value) : text[8];
    }
</script>

<section data-quiz-evidence aria-label={text[0]}>
    <h4>{text[0]}</h4>
    <dl>
        {#each values as value, index}
            <div><dt>{text[index + 1]}</dt><dd>{number(value)}</dd></div>
        {/each}
    </dl>
    <p>{text[9]}</p>
    {#if Array.isArray(metrics?.finished_attempt_histogram)}
        <details>
            <summary>{text[5]}</summary>
            <table>
                <caption>{text[5]}</caption>
                <thead><tr><th scope="col">{text[6]}</th><th scope="col">{text[7]}</th></tr></thead>
                <tbody>{#each metrics.finished_attempt_histogram as row}
                    <tr><th scope="row">{number(row.attempts)}</th><td>{number(row.students)}</td></tr>
                {/each}</tbody>
            </table>
        </details>
    {/if}
</section>

<style>
    section { margin:16px 0; border-top:1px solid #d6e0ea; padding-top:12px; }
    h4, summary { font-weight:600; }
    dl { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; margin:12px 0; }
    dt, p { font-size:.85rem; color:#53677b; }
    dd { margin:0; font-weight:600; }
    p { margin:10px 0; }
    summary { cursor:pointer; padding:8px 0; }
    table { width:100%; border-collapse:collapse; font-size:.9rem; }
    th, td { text-align:left; border-bottom:1px solid #d6e0ea; padding:8px; }
    caption { text-align:left; padding:8px; }
    :focus-visible { outline:3px solid #2463a1; outline-offset:3px; }
    @media(max-width:600px) { dl { grid-template-columns:repeat(2,minmax(0,1fr)); } }
</style>
