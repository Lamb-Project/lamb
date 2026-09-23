<script>
    let { data } = $props();
    const translations = {
        en: {
            columns: ['Assessment','Target students','Valid grades','Minimum %','Q1 %','Median %','Q3 %','Maximum %','IQR (points)','Pass / valid grades','Pass %','Missing / nonexcluded students','Missing %','Excluded grades','Status'],
            legend: 'Normalized final grades (0–100%). Dot: median; box: Q1–Q3; line: minimum–maximum, not Tukey whiskers or a confidence interval.',
            unavailable: 'Unavailable', available: 'Available', empty: 'No assessments', noGrades: 'No valid grades',
            stale_final_grades: 'Stale final grades', non_numeric_grade_type: 'Non-numeric grade type', invalid_numeric_range: 'Invalid numeric range',
            table: 'Exact saved values', partial: 'Some assessments cannot be compared.',
            denominator: 'Pass rates use valid nonexcluded grades. Missing-grade rates use nonexcluded target students. Missing grades are not missing submissions. A dash means unavailable, not zero.'
        },
        es: {
            columns: ['Evaluación','Estudiantes destinatarios','Notas válidas','Mínimo %','Q1 %','Mediana %','Q3 %','Máximo %','RIC (puntos)','Aprobados / notas válidas','Aprobados %','Sin nota / estudiantes no excluidos','Sin nota %','Notas excluidas','Estado'],
            legend: 'Notas finales normalizadas (0–100%). Punto: mediana; caja: Q1–Q3; línea: mínimo–máximo, no bigotes de Tukey ni intervalo de confianza.',
            unavailable: 'No disponible', available: 'Disponible', empty: 'Sin evaluaciones', noGrades: 'Sin notas válidas',
            stale_final_grades: 'Notas finales desactualizadas', non_numeric_grade_type: 'Tipo de nota no numérico', invalid_numeric_range: 'Rango numérico no válido',
            table: 'Valores guardados exactos', partial: 'Algunas evaluaciones no se pueden comparar.',
            denominator: 'Los porcentajes de aprobados usan notas válidas no excluidas. Los porcentajes sin nota usan estudiantes destinatarios no excluidos. Sin nota no significa sin entrega. Un guion indica que no está disponible, no cero.'
        },
        ca: {
            columns: ['Avaluació','Estudiants destinataris','Notes vàlides','Mínim %','Q1 %','Mediana %','Q3 %','Màxim %','RIQ (punts)','Aprovats / notes vàlides','Aprovats %','Sense nota / estudiants no exclosos','Sense nota %','Notes excloses','Estat'],
            legend: 'Notes finals normalitzades (0–100%). Punt: mediana; caixa: Q1–Q3; línia: mínim–màxim, no bigotis de Tukey ni interval de confiança.',
            unavailable: 'No disponible', available: 'Disponible', empty: 'Sense avaluacions', noGrades: 'Sense notes vàlides',
            stale_final_grades: 'Notes finals desactualitzades', non_numeric_grade_type: 'Tipus de nota no numèric', invalid_numeric_range: 'Rang numèric no vàlid',
            table: 'Valors desats exactes', partial: 'Algunes avaluacions no es poden comparar.',
            denominator: 'Els percentatges d’aprovats usen notes vàlides no excloses. Els percentatges sense nota usen estudiants destinataris no exclosos. Sense nota no significa sense lliurament. Un guió indica que no està disponible, no zero.'
        },
        eu: {
            columns: ['Ebaluazioa','Helburuko ikasleak','Baliozko notak','Gutxienekoa %','Q1 %','Mediana %','Q3 %','Gehienekoa %','Kuartil arteko tartea (puntuak)','Gaindituak / baliozko notak','Gaindituak %','Notarik gabe / baztertu gabeko ikasleak','Notarik gabe %','Baztertutako notak','Egoera'],
            legend: 'Azken nota normalizatuak (0–100%). Puntua: mediana; kutxa: Q1–Q3; lerroa: gutxienekoa–gehienekoa, ez Tukey biboteak edo konfiantza-tartea.',
            unavailable: 'Ez dago erabilgarri', available: 'Erabilgarri', empty: 'Ez dago ebaluaziorik', noGrades: 'Ez dago baliozko notarik',
            stale_final_grades: 'Azken nota zaharkituak', non_numeric_grade_type: 'Zenbakizkoa ez den nota mota', invalid_numeric_range: 'Zenbakizko tarte baliogabea',
            table: 'Gordetako balio zehatzak', partial: 'Ebaluazio batzuk ezin dira konparatu.',
            denominator: 'Gaindituen ehunekoek baztertu gabeko baliozko notak erabiltzen dituzte. Notarik gabekoen ehunekoek baztertu gabeko helburuko ikasleak erabiltzen dituzte. Notarik ez izateak ez du esan nahi entregarik ez dagoenik. Marrak erabilgarri ez dagoela esan nahi du, ez zero.'
        }
    };
    const text = $derived(translations[data.language] || translations.en);
    const keys = ['population_n','valid_n','min_pct','q1_pct','median_pct','q3_pct','max_pct','iqr_pct'];
    const value = n => typeof n === 'number' && Number.isFinite(n) ? String(n) : '–';
    const ratio = (n,d) => n == null || d == null ? '–' : `${n} / ${d}`;
    const drawable = row => row.comparison_status === 'available' && row.metrics.valid_n > 0 &&
        ['min_pct','q1_pct','median_pct','q3_pct','max_pct'].every(k => Number.isFinite(row.metrics[k]) && row.metrics[k] >= 0 && row.metrics[k] <= 100);
    const status = row => row.comparison_status !== 'available'
        ? (row.unavailable_reasons || []).map(reason => text[reason] || text.unavailable).join('; ') || text.unavailable
        : row.metrics.valid_n ? text.available : text.noGrades;
</script>

<section data-assessment-comparison>
    <h4>{data.title}</h4>
    <p>{data.caption}</p>
    {#if !data.rows.length}<p role="status">{text.empty}</p>
    {:else}
        {#if !data.coverage.complete}<p role="status">{text.partial}</p>{/if}
        <p>{text.legend}</p>
        <ul class="plots">
            {#each data.rows as row}
                <li><strong>{row.name}</strong>
                    {#if drawable(row)}
                        <svg viewBox="0 0 440 65" role="img" aria-label={`${row.name}: ${text.columns[5]} ${value(row.metrics.median_pct)}`}>
                            <title>{row.name}: Q1 {value(row.metrics.q1_pct)}, {text.columns[5]} {value(row.metrics.median_pct)}, Q3 {value(row.metrics.q3_pct)}</title>
                            {#each [0,25,50,75,100] as tick}
                                <line x1={20+tick*4} x2={20+tick*4} y1="6" y2="38" class="grid" />
                                <text x={20+tick*4} y="57" text-anchor="middle">{tick}</text>
                            {/each}
                            <line data-extrema x1={20+row.metrics.min_pct*4} x2={20+row.metrics.max_pct*4} y1="22" y2="22" class="extent" />
                            <rect data-iqr x={20+row.metrics.q1_pct*4} y="12" width={(row.metrics.q3_pct-row.metrics.q1_pct)*4} height="20" />
                            <circle data-median cx={20+row.metrics.median_pct*4} cy="22" r="5" />
                        </svg>
                    {:else}<p>{status(row)}</p>{/if}
                </li>
            {/each}
        </ul>
        <p>{text.denominator}</p>
        <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
        <div class="table-scroll" role="region" tabindex="0" aria-label={text.table}>
            <table><caption>{text.table}</caption>
                <thead><tr>{#each text.columns as label}<th scope="col">{label}</th>{/each}</tr></thead>
                <tbody>{#each data.rows as row}<tr>
                    <th scope="row">{row.name}</th>
                    {#each keys as key}<td>{value(row.metrics[key])}</td>{/each}
                    <td>{ratio(row.metrics.pass_n,row.metrics.pass_denominator_n)}</td><td>{value(row.metrics.pass_rate_pct)}</td>
                    <td>{ratio(row.metrics.missing_n,row.metrics.nonexcluded_population_n)}</td><td>{value(row.metrics.missing_grade_rate_pct)}</td>
                    <td>{value(row.metrics.excluded_n)}</td><td>{status(row)}</td>
                </tr>{/each}</tbody>
            </table>
        </div>
    {/if}
</section>
<style>
    h4 {font-size:1.1rem;font-weight:600;}
    p {margin:12px 0;}
    .plots {list-style:none;padding:0;margin:18px 0;}
    .plots li {margin-bottom:14px;}
    svg {display:block;width:100%;max-width:700px;height:auto;overflow:visible;}
    .grid {stroke:#d6e0ea;stroke-width:1;}
    .extent {stroke:#172b40;stroke-width:2;}
    rect {fill:#b7d4ee;stroke:#2463a1;}
    circle {fill:#172b40;}
    text {font-size:12px;fill:#172b40;}
    .table-scroll {max-width:100%;overflow:auto;}
    table {border-collapse:collapse;min-width:1500px;font-size:.9rem;}
    th,td {padding:10px 8px;border-bottom:1px solid #d6e0ea;text-align:left;min-width:90px;overflow-wrap:normal;word-break:normal;}
    th:first-child {min-width:180px;}
    caption {text-align:left;font-weight:600;padding:8px;}
    :focus-visible {outline:3px solid #2463a1;outline-offset:3px;}
</style>
