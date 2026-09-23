<script>
    let {data} = $props();
    let page = $state(0);
    const words = {
        en:['Student','Incoming peers','Outgoing peers','Unique peers','Replies received','Replies sent','No observed peer interaction','Unknown','Yes','No','Previous','Next','Incomplete public evidence','Reply author → parent author. Arrow weight is reply count. Circular positions follow IDs, not importance.','Graph omitted for size or density; the degree table remains exact.','Creation window [start, end), exclusive end','Names were not collected; identifiers are Moodle IDs.','No rows'],
        es:['Estudiante','Pares entrantes','Pares salientes','Pares distintos','Respuestas recibidas','Respuestas enviadas','Sin interacción observada con pares','Desconocido','Sí','No','Anterior','Siguiente','Evidencia pública incompleta','Autor de respuesta → autor del mensaje padre. El peso cuenta respuestas. Posiciones circulares por identificador, no importancia.','Grafo omitido por tamaño o densidad; la tabla de grados sigue siendo exacta.','Intervalo de creación [inicio, fin), fin excluido','No se han recogido nombres; los identificadores son de Moodle.','Sin filas'],
        ca:['Estudiant','Companys entrants','Companys sortints','Companys diferents','Respostes rebudes','Respostes enviades','Sense interacció observada amb companys','Desconegut','Sí','No','Anterior','Següent','Evidència pública incompleta','Autor de resposta → autor del missatge pare. El pes compta respostes. Posicions circulars per identificador, no importància.','Graf omès per mida o densitat; la taula de graus continua sent exacta.','Interval de creació [inici, fi), fi exclòs','No s’han recollit noms; els identificadors són de Moodle.','Sense files'],
        eu:['Ikaslea','Sarrerako ikaskideak','Irteerako ikaskideak','Ikaskide desberdinak','Jasotako erantzunak','Bidalitako erantzunak','Ikaskideekin behatutako interakziorik gabe','Ezezaguna','Bai','Ez','Aurrekoa','Hurrengoa','Ebidentzia publiko osatugabea','Erantzunaren egilea → jatorrizko mezuaren egilea. Pisuak erantzunak zenbatzen ditu. Kokapen zirkularra IDaren arabera, ez garrantziaren arabera.','Grafoa tamainagatik edo dentsitateagatik ezkutatuta; gradu-taula zehatza da.','Sortze-tartea [hasiera, amaiera), amaiera kanpo','Ez da izenik bildu; identifikatzaileak Moodlekoak dira.','Errenkadarik ez']
    };
    const t = $derived(words[data.language] || words.en);
    const rows = $derived(data.rows.slice(page*50,(page+1)*50));
    const pages = $derived(Math.max(1,Math.ceil(data.rows.length/50)));
    // Never sample the graph. Large/dense evidence stays an exact degree table.
    const showGraph = $derived(data.network.edges_included && data.rows.length>0 && data.rows.length<=30 && data.network.edges.length<=100);
    const nodes = $derived(data.rows.map((row,i)=>{
        const angle=2*Math.PI*i/data.rows.length-Math.PI/2;
        return {...row,x:450+340*Math.cos(angle),y:450+340*Math.sin(angle),
            lx:450+375*Math.cos(angle),ly:450+375*Math.sin(angle)};
    }));
    const paths = $derived.by(()=>{
        if(!showGraph)return [];
        const lookup=new Map(nodes.map(row=>[row.student_id,row]));
        return data.network.edges.map(edge=>{
            const a=lookup.get(edge.source_student_id),b=lookup.get(edge.target_student_id);
            const dx=b.x-a.x,dy=b.y-a.y,len=Math.hypot(dx,dy),ux=dx/len,uy=dy/len;
            return {...edge,path:`M ${a.x+ux*14} ${a.y+uy*14} Q ${(a.x+b.x)/2-uy*22} ${(a.y+b.y)/2+ux*22} ${b.x-ux*19} ${b.y-uy*19}`};
        });
    });
    const markerId = $derived(`peer-arrow-${data.collection_run_id || data.forum_id}`);
    function stamp(value) {
        return new Intl.DateTimeFormat(data.language || 'en',{timeZone:data.timezone,
            year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',
            timeZoneName:'longOffset',hourCycle:'h23'}).format(new Date(value*1000));
    }
    $effect(()=>{void data;page=0;});
</script>

<section data-forum-network aria-label={data.title}>
    <h3>{data.title}</h3>
    <p>{t[15]}: {stamp(data.metrics.window.since)} → {stamp(data.metrics.window.until)} · {data.timezone}</p>
    <p>{t[16]}</p>
    <p class="caption">{data.caption}</p>
    {#if !data.coverage.complete}<p role="status">{t[12]}</p>{/if}
    {#if showGraph}
        <p>{t[13]}</p>
        <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
        <div class="scroll" role="region" tabindex="0" aria-label={t[13]}>
            <svg viewBox="0 0 900 900" role="img" aria-label={t[13]}>
                <defs><marker id={markerId} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#526a82" /></marker></defs>
                {#each paths as edge}
                    <path data-peer-edge d={edge.path} fill="none" stroke="#526a82" stroke-width={Math.min(5,1+Math.log2(edge.replies))} marker-end={`url(#${markerId})`}>
                        <title>#{edge.source_student_id} → #{edge.target_student_id}: {edge.replies}</title>
                    </path>
                {/each}
                {#each nodes as node}
                    <circle data-peer-node cx={node.x} cy={node.y} r="12" fill="#2463a1"><title>{node.name}: {t[3]} {node.unique_peers}</title></circle>
                    <text x={node.lx} y={node.ly} text-anchor="middle" dominant-baseline="middle">#{node.student_id}</text>
                {/each}
            </svg>
        </div>
    {:else if data.rows.length}<p data-network-table-reason>{t[14]}</p>{/if}
    {#if !data.rows.length}<p role="status">{t[17]}</p>{:else}
        <nav aria-label={data.title}>
            <button onclick={()=>page--} disabled={page===0}>{t[10]}</button>
            <span aria-live="polite">{page+1} / {pages} · {page*50+1}–{Math.min((page+1)*50,data.rows.length)} / {data.rows.length}</span>
            <button onclick={()=>page++} disabled={page+1>=pages}>{t[11]}</button>
        </nav>
        <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
        <div class="scroll" role="region" tabindex="0" aria-label={data.title}>
            <table><caption>{data.title}</caption><thead><tr>{#each t.slice(0,7) as title}<th scope="col">{title}</th>{/each}</tr></thead>
                <tbody>{#each rows as row}<tr><th scope="row">{row.name}</th>
                    <td>{row.in_degree}</td><td>{row.out_degree}</td><td>{row.unique_peers}</td>
                    <td>{row.incoming_replies}</td><td>{row.outgoing_replies}</td>
                    <td>{row.no_observed_peer_interaction===null?t[7]:row.no_observed_peer_interaction?t[8]:t[9]}</td>
                </tr>{/each}</tbody>
            </table>
        </div>
    {/if}
</section>
<style>
    h3 {font-size:1.15rem;font-weight:600;}
    p {margin:10px 0;}
    .caption {border-left:3px solid #2463a1;padding:8px 12px;}
    .scroll {max-width:100%;overflow:auto;}
    svg {width:100%;min-width:760px;max-height:900px;}
    text {font-size:14px;fill:#17314b;}
    table {width:100%;min-width:900px;border-collapse:collapse;font-size:.9rem;}
    caption {text-align:left;font-weight:600;padding:8px;}
    th,td {padding:10px;border-bottom:1px solid #d6e0ea;text-align:left;min-width:105px;}
    th:first-child {min-width:160px;}
    nav {display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin:16px 0;}
    button {border:1px solid #2463a1;border-radius:6px;padding:8px 14px;color:#2463a1;}
    button:disabled {opacity:.5;}
    :focus-visible {outline:3px solid #2463a1;outline-offset:3px;}
</style>
