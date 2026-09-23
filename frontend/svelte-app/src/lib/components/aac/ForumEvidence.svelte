<script>
    let {data} = $props();
    let page = $state(0);
    const labels = {
        en:['Student','Posts','Replies','Discussions started','Active local days','Discussion','Public replies through snapshot','Last public post','Age at snapshot (seconds)','No observed public replies','Unknown','Yes','No','Previous','Next','Incomplete public evidence','Creation window [start, end), exclusive end','No rows','Names were not collected; identifiers are Moodle IDs.'],
        es:['Estudiante','Publicaciones','Respuestas','Discusiones iniciadas','Días locales activos','Discusión','Respuestas públicas hasta la captura','Última publicación pública','Antigüedad en la captura (segundos)','Sin respuestas públicas observadas','Desconocido','Sí','No','Anterior','Siguiente','Evidencia pública incompleta','Intervalo de creación [inicio, fin), fin excluido','Sin filas','No se han recogido nombres; los identificadores son de Moodle.'],
        ca:['Estudiant','Publicacions','Respostes','Discussions iniciades','Dies locals actius','Discussió','Respostes públiques fins a la captura','Última publicació pública','Antiguitat a la captura (segons)','Sense respostes públiques observades','Desconegut','Sí','No','Anterior','Següent','Evidència pública incompleta','Interval de creació [inici, fi), fi exclòs','Sense files','No s’han recollit noms; els identificadors són de Moodle.'],
        eu:['Ikaslea','Mezuak','Erantzunak','Hasitako eztabaidak','Tokiko egun aktiboak','Eztabaida','Argazkira arteko erantzun publikoak','Azken mezu publikoa','Argazkiko antzinatasuna (segundoak)','Behatutako erantzun publikorik gabe','Ezezaguna','Bai','Ez','Aurrekoa','Hurrengoa','Ebidentzia publiko osatugabea','Sortze-tartea [hasiera, amaiera), amaiera kanpo','Errenkadarik ez','Ez da izenik bildu; identifikatzaileak Moodlekoak dira.']
    };
    const t = $derived(labels[data.language] || labels.en);
    const learner = $derived(data.recipe.id === 'forum-participation');
    const rows = $derived(data.rows.slice(page*50,(page+1)*50));
    const pages = $derived(Math.max(1,Math.ceil(data.rows.length/50)));
    const max = $derived(Math.max(1,...data.rows.map(row=>row.value || 0)));
    const columns = $derived(learner ? t.slice(0,5) : [t[5],t[6],t[7],t[8],t[9]]);
    function stamp(value) {
        if (value === null || value === undefined) return t[10];
        return new Intl.DateTimeFormat(data.language || 'en', {timeZone:data.timezone,
            year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',
            timeZoneName:'longOffset',hourCycle:'h23'}).format(new Date(value*1000));
    }
    $effect(() => { void data; page=0; });
</script>

<section aria-label={data.title} data-forum-evidence>
    <h3>{data.title}</h3>
    <p>{t[16]}: {stamp(data.metrics.window.since)} → {stamp(data.metrics.window.until)} · {data.timezone}</p>
    <p>{t[18]}</p>
    {#if !data.coverage.complete}<p role="status">{t[15]}</p>{/if}
    <p class="caption">{data.caption}</p>
    {#if !data.rows.length}<p role="status">{t[17]}</p>{:else}
        <nav aria-label={data.title}>
            <button onclick={()=>page--} disabled={page===0}>{t[13]}</button>
            <span aria-live="polite">{page+1} / {pages} · {page*50+1}–{Math.min((page+1)*50,data.rows.length)} / {data.rows.length}</span>
            <button onclick={()=>page++} disabled={page+1>=pages}>{t[14]}</button>
        </nav>
        <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
        <div class="scroll" tabindex="0" role="region" aria-label={data.title}>
            <table><caption>{data.title}</caption>
                <thead><tr>{#each columns as column}<th scope="col">{column}</th>{/each}</tr></thead>
                <tbody>{#each rows as row}
                    <tr><th scope="row">{row.name}</th>
                    {#if learner}
                        <td>{row.posts}<span class="bar" aria-hidden="true" style:width={`${100*row.posts/max}%`}></span></td>
                        <td>{row.replies}</td><td>{row.discussions_started}</td><td>{row.active_local_days}</td>
                    {:else}
                        <td>{row.observed_public_replies_as_of}{#if !row.public_thread_complete}<br />{t[15]}{/if}</td>
                        <td>{stamp(row.last_observed_public_post_at)}</td>
                        <td>{row.seconds_since_last_observed_public_post ?? t[10]}</td>
                        <td>{row.no_observed_public_replies === null ? t[10] : row.no_observed_public_replies ? t[11] : t[12]}</td>
                    {/if}</tr>
                {/each}</tbody>
            </table>
        </div>
    {/if}
</section>
<style>
    h3 {font-size:1.15rem;font-weight:600;}
    p {margin:10px 0;}
    .caption {border-left:3px solid #2463a1;padding:8px 12px;}
    nav {display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin:16px 0;}
    button {border:1px solid #2463a1;border-radius:6px;padding:8px 14px;color:#2463a1;}
    button:disabled {opacity:.5;}
    .scroll {overflow:auto;max-width:100%;}
    table {width:100%;min-width:760px;border-collapse:collapse;font-size:.9rem;}
    th,td {padding:10px;border-bottom:1px solid #d6e0ea;text-align:left;min-width:100px;}
    th:first-child {min-width:160px;}
    caption {text-align:left;font-weight:600;padding:8px;}
    .bar {display:block;height:6px;background:#2463a1;min-width:0;margin-top:4px;}
    :focus-visible {outline:3px solid #2463a1;outline-offset:3px;}
</style>
