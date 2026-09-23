"""Bounded cohort attempt aggregation, independent of collection/authorization.

The caller must supply an exhausted, permission-checked current population and
attempt source. No API or recipe may expose this until that collector exists.
Raw attempt marks are not final gradebook grades or evidence of learning.
"""
from collections import Counter,defaultdict
from decimal import Decimal
from .grades import _number,_percentile

POLICIES={'first_finished','latest_finished','best_scored_finished','all_finished'}
STATES={'inprogress','overdue','finished','abandoned'}


def _summary(values):
    values=sorted(values)
    return {'n':len(values),'mean':float(sum(values)/len(values)) if values else None,
        **{key:float(_percentile(values,p)) if values else None
           for key,p in [('q1',Decimal('.25')),('median',Decimal('.5')),('q3',Decimal('.75'))]}}


def summarize_attempts(records,students,*,quiz_id,maximum,policy,pass_percent=None):
    if policy not in POLICIES:raise ValueError('Use an explicit finished-attempt policy')
    if type(quiz_id) is not int or quiz_id<1:raise ValueError('Invalid quiz ID')
    if (not isinstance(students,(list,set,tuple)) or len(students)>1000
            or any(type(user) is not int or user<1 for user in students)
            or len(set(students))!=len(students)):
        raise ValueError('Invalid complete quiz population')
    if not isinstance(records,list) or len(records)>10000:raise ValueError('Attempt limit exceeded')
    maximum=_number(maximum)
    if maximum<=0:raise ValueError('Quiz raw maximum must be positive')
    threshold=_number(pass_percent) if pass_percent is not None else None
    if threshold is not None and not 0<=threshold<=100:raise ValueError('Invalid pass threshold')
    students=set(students);seen=set();ordinals=set();by_user=defaultdict(list)
    states=Counter({state:0 for state in STATES});excluded=Counter()
    for row in records:
        if not isinstance(row,dict):raise ValueError('Invalid attempt record')
        for key in ('id','quiz','userid','attempt'):
            if type(row.get(key)) is not int or row[key]<1:raise ValueError('Invalid attempt identity')
        if row['quiz']!=quiz_id or row['id'] in seen:raise ValueError('Duplicate or foreign quiz attempt')
        seen.add(row['id'])
        if type(row.get('preview')) is not bool:raise ValueError('Unknown preview status')
        if row['preview']:
            excluded['preview']+=1;continue
        if row['userid'] not in students:
            excluded['outside_population']+=1;continue
        ordinal=(row['userid'],row['attempt'])
        if ordinal in ordinals:raise ValueError('Duplicate user attempt number')
        ordinals.add(ordinal)
        state=row.get('state')
        if state not in STATES:raise ValueError('Unknown quiz attempt state')
        states[state]+=1
        if state!='finished':continue
        start,finish=row.get('timestart'),row.get('timefinish')
        if type(start) is not int or type(finish) is not int or not 0<start<=finish:
            raise ValueError('Invalid finished-attempt clock')
        mark=_number(row['sumgrades']) if row.get('sumgrades') is not None else None
        if mark is not None and not 0<=mark<=maximum:
            raise ValueError('Raw quiz mark outside supported range')
        by_user[row['userid']].append({'ordinal':row['attempt'],'score':mark*100/maximum if mark is not None else None,
            'duration':Decimal(finish-start),'start':start,'finish':finish})
    selected=[];deltas=[];gaps=[];ungraded_pairs=0
    for attempts in by_user.values():
        attempts.sort(key=lambda row:row['ordinal'])
        if policy=='all_finished':chosen=attempts
        elif policy=='first_finished':chosen=attempts[:1]
        elif policy=='latest_finished':chosen=attempts[-1:]
        else:
            scored=[row for row in attempts if row['score'] is not None]
            chosen=[max(scored,key=lambda row:(row['score'],-row['ordinal']))] if scored else attempts[:1]
        selected.extend(chosen)
        exact={row['ordinal']:row for row in attempts}
        if 1 in exact and 2 in exact:
            first,second=exact[1],exact[2]
            if second['start']<first['finish']:raise ValueError('Overlapping first/second attempts')
            if first['score'] is None or second['score'] is None:ungraded_pairs+=1
            else:
                deltas.append(second['score']-first['score'])
                gaps.append(Decimal(second['start']-first['finish']))
    scores=[row['score'] for row in selected if row['score'] is not None]
    bins=[0]*10
    for score in scores:bins[min(int(score//10),9)]+=1
    histogram=Counter(len(by_user.get(user,[])) for user in students)
    passed=sum(score>=threshold for score in scores) if threshold is not None else None
    ungraded_finished=sum(row['score'] is None for attempts in by_user.values() for row in attempts)
    return {'attempt_policy':policy,'population_students':len(students),'source_records':len(records),
        'excluded':dict(excluded),'attempt_states':dict(states),'students_with_finished_attempt':len(by_user),
        'finished_attempt_histogram':[{'attempts':count,'students':histogram[count]} for count in sorted(histogram)],
        'selected_attempts':len(selected),'ungraded_selected_attempts':len(selected)-len(scores),
        'ungraded_finished_attempts':ungraded_finished,
        'best_selection_complete':not ungraded_finished if policy=='best_scored_finished' else None,
        'score_percent':_summary(scores),'score_bins':[{'lower':i*10,'upper':(i+1)*10,
            'upper_inclusive':i==9,'attempts':count} for i,count in enumerate(bins)],
        'elapsed_seconds':_summary([row['duration'] for row in selected]),
        'pass_percent':float(threshold) if threshold is not None else None,'passing_selected_attempts':passed,
        'pass_rate_scored_attempts':passed/len(scores) if threshold is not None and scores else None,
        'retry_1_to_2':{'score_change_percentage_points':_summary(deltas),
            'between_attempt_seconds':_summary(gaps),'ungraded_pairs':ungraded_pairs,
            'improved':sum(delta>0 for delta in deltas),'unchanged':sum(delta==0 for delta in deltas),
            'decreased':sum(delta<0 for delta in deltas)},
        'limitations':['Current population, not historical enrolment.',
            'Finished-attempt presence is not Moodle course or activity completion.',
            'Raw scores are not final gradebook marks or evidence of learning.',
            'Elapsed attempt duration is not study time.',
            'Best-scored selection uses observed marks only; an ungraded attempt may change the best result.',
            'Retry deltas use actual attempt numbers 1 and 2 with observed marks, not the first two available records.',
            'Question variants, randomized content and comparability were not collected.']}
