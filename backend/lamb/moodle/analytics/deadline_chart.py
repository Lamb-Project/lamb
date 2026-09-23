"""Code-owned bounded calendar and density specification, with no external data."""
def calendar_spec(snapshot):
    events=snapshot['events'];weeks=snapshot['weekly'];labels=snapshot['calendar_labels']
    if len(events)>300 or len(weeks)>54:
        raise ValueError('Calendar mark limit exceeded')
    values=[]
    for event in events:
        if (event.get('kind') not in {'opens','due','closes'} or type(event.get('timestamp')) is not int
                or type(event.get('cmid')) is not int or not isinstance(event.get('local'),str)):
            raise ValueError('Invalid calendar event')
        values.append({'activity':f"{event['name']} (#{event['cmid']})",'date':event['local'],
            'kind':labels[event['kind']],'timestamp':event['timestamp']})
    if any(type(w.get('deadlines')) is not int or w['deadlines']<0 for w in weeks):
        raise ValueError('Invalid weekly deadline counts')
    # Ordinal offset-bearing labels prevent the SVG renderer's host timezone
    # from silently converting local times. Spacing is categorical, not duration.
    dates=list(dict.fromkeys(e['date'] for e in sorted(values,key=lambda e:e['timestamp'])))
    return {'vconcat':[
        {'width':600,'height':max(80,24*len({e['activity'] for e in values})),
         'title':labels['timeline'],'data':{'values':values},'mark':{'type':'point','filled':True,'size':80},
         'encoding':{'x':{'field':'date','type':'ordinal','sort':dates,'title':None,
                          'axis':{'labelAngle':-45,'labelOverlap':True}},
                     'y':{'field':'activity','type':'nominal','title':labels['activity'],'axis':{'labelLimit':200}},
                     'color':{'field':'kind','type':'nominal','title':None},
                     'shape':{'field':'kind','type':'nominal','title':None}}},
        {'width':600,'height':160,'title':labels['weekly'],'data':{'values':weeks},'mark':'bar',
         'encoding':{'x':{'field':'week_start','type':'ordinal','sort':None,'title':labels['week'],
                          'axis':{'labelAngle':-45,'labelOverlap':True}},
                     'y':{'field':'deadlines','type':'quantitative','title':labels['metric'],
                          'axis':{'tickMinStep':1},'scale':{'zero':True}}}}
    ],'resolve':{'scale':{'x':'independent'}},'config':{'font':'sans-serif'}}
