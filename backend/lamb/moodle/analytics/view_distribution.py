"""Bounded integer histograms for recorded views or observed active days.

Keep observed zero separate. Positive bins are equally wide integer intervals;
binning changes the display only, not the exact histogram or its statistics.
"""
from math import ceil
from .resource_text import present_resource

TEXT={
    'en':('Recorded views per student','Observed active days per student','Students','Median',
        'Current students with zero recorded views are included. Zero is separate; positive bins are inclusive integer ranges. Active days mean local dates with a recorded course, resource or chapter view, not all participation. Quartiles use linear interpolation at (n-1)*p. '),
    'es':('Visitas registradas por estudiante','Días activos observados por estudiante','Estudiantes','Mediana',
        'Se incluyen estudiantes actuales con cero visitas registradas. El cero se separa; los intervalos positivos incluyen ambos extremos enteros. Los días activos son fechas locales con visitas al curso, recursos o capítulos, no toda la participación. Los cuartiles usan interpolación lineal en (n-1)*p. '),
    'ca':('Visites registrades per estudiant','Dies actius observats per estudiant','Estudiants','Mediana',
        'S’inclouen estudiants actuals amb zero visites registrades. El zero se separa; els intervals positius inclouen tots dos extrems enters. Els dies actius són dates locals amb visites al curs, recursos o capítols, no tota la participació. Els quartils fan servir interpolació lineal a (n-1)*p. '),
    'eu':('Erregistratutako bisitak ikasleko','Behatutako egun aktiboak ikasleko','Ikasleak','Mediana',
        'Erregistratutako bisitarik gabeko uneko ikasleak sartzen dira. Zeroa bereizita dago; tarte positiboek bi mutur osoak barne hartzen dituzte. Egun aktiboak ikastaroko, baliabideetako edo kapituluetako bisitak dituzten tokiko datak dira, ez parte-hartze osoa. Kuartilek interpolazio lineala erabiltzen dute (n-1)*p posizioan. '),
}


def present_distribution(language,timezone,data):
    views,days,students,median,caption=TEXT[language]
    fields=present_resource(language,timezone,data)
    fields.pop('resource_columns')
    distribution=data['distribution']
    fields.update(title=views if data['distribution_metric']=='student_view_counts' else days,
        metric_label=students,view_kind='metric-bars-v1',caption=caption+fields['caption'],
        summary_statistics=[{'label':label,'value':distribution[key]}
            for label,key in [(median,'median'),('Q1','q1'),('Q3','q3'),('IQR','iqr')]])
    return fields


def display_bins(distribution, *, positive_bins=20):
    if type(positive_bins) is not int or not 1 <= positive_bins <= 50:
        raise ValueError('Invalid distribution bin limit')
    histogram=distribution['histogram']
    population=distribution['population_students']
    if type(population) is not int or not 0 <= population <= 1000:
        raise ValueError('Invalid distribution population')
    seen=set();total=0
    for row in histogram:
        value,count=row.get('value'),row.get('students')
        if (type(value) is not int or not 0 <= value <= 20000 or value in seen
                or type(count) is not int or count <= 0):
            raise ValueError('Invalid exact distribution histogram')
        seen.add(value);total+=count
    if total!=population:
        raise ValueError('Distribution population mismatch')
    if not population:return []
    counts={row['value']:row['students'] for row in histogram}
    maximum=max(counts)
    width=max(1,ceil(maximum/positive_bins))
    rows=[{'lower':0,'upper':0,'students':counts.get(0,0)}]
    for lower in range(1,maximum+1,width):
        upper=min(maximum,lower+width-1)
        rows.append({'lower':lower,'upper':upper,
            'students':sum(count for value,count in counts.items() if lower<=value<=upper)})
    return rows
