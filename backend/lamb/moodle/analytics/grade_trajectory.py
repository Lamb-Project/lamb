"""Pure explicit-learner trajectory over dated, authorized private evidence.

The caller must establish assessment date provenance and learner/item authority.
Stored grade modification clocks are deliberately not accepted as chronology.
"""
from datetime import datetime
from collections import Counter
from .assessment_comparison import summarize_assessment
from .gradebook_state import integer, decimal

DATE_BASES={'stored_course_default_due','explicit_instructor_date'}


def trajectory(evidence, student_id, *, rolling_window=3, edge_window=2):
    integer(student_id,1)
    if (not isinstance(evidence,list) or not 2<=len(evidence)<=20
            or type(rolling_window) is not int or not 2<=rolling_window<=10
            or type(edge_window) is not int or not 1<=edge_window<=10):
        raise ValueError('Use 2–20 dated assessments and bounded trajectory windows')
    rows=[];scopes=set();ids=set()
    for entry in evidence:
        if not isinstance(entry,dict) or not {'assessment_at','date_basis','cursor','students'}<=entry.keys():
            raise ValueError('Dated assessment evidence required')
        date=entry['assessment_at']
        if (not isinstance(date,str) or len(date)>64 or not isinstance(entry['date_basis'],str)
                or entry['date_basis'] not in DATE_BASES):
            raise ValueError('Explicit assessment date provenance required')
        when=datetime.fromisoformat(date)
        if when.utcoffset() is None:
            raise ValueError('Assessment date needs an explicit timezone offset')
        cursor=entry['cursor'];students=entry['students']
        summary=summarize_assessment(cursor,students)
        identity=summary['grade_item_id']
        if identity in ids:raise ValueError('Duplicate trajectory assessment')
        ids.add(identity);scopes.add((summary['course_id'],summary['group_id']))
        record=next((r for r in cursor['records'] if r['userid']==student_id),None)
        score=None
        if student_id not in students:status='outside_target_population'
        elif record is None:status='no_grade_record'
        elif record['excluded']!=0:status='excluded_grade'
        elif record['finalgrade'] is None:status='null_final_grade'
        elif summary['comparison_status']!='available':status='unavailable_score'
        else:
            low,high=(decimal(cursor['item'][k]) for k in ('grademin','grademax'))
            score=float((decimal(record['finalgrade'])-low)*100/(high-low));status='available'
        rows.append(dict(grade_item_id=identity,name=cursor['item'].get('name',''),
            assessment_at=date,date_basis=entry['date_basis'],timestamp=when.timestamp(),
            score_pct=score,class_median_pct=summary['metrics']['median_pct'],
            class_valid_n=summary['metrics']['valid_n'],status=status,
            unavailable_reasons=summary['unavailable_reasons'],rolling_mean_pct=None))
    if len(scopes)!=1:raise ValueError('Trajectory requires one course and group')
    rows.sort(key=lambda r:(r['timestamp'],r['grade_item_id']))
    dates=Counter(r['timestamp'] for r in rows)
    for row in rows:row['chronology_tied']=dates[row['timestamp']]>1
    # No rolling-window compression across missing/excluded/stale assessments.
    for i in range(rolling_window-1,len(rows)):
        selected=rows[i-rolling_window+1:i+1]
        window=[r['score_pct'] for r in selected]
        if all(v is not None for v in window) and not any(r['chronology_tied'] for r in selected):
            rows[i]['rolling_mean_pct']=sum(window)/rolling_window
    valid=[r for r in rows if r['score_pct'] is not None]
    distinct_scored_dates=len({r['timestamp'] for r in valid})
    slope=None
    if len(valid)>=3 and distinct_scored_dates>=3:
        x=[(r['timestamp']-valid[0]['timestamp'])/86400 for r in valid]
        y=[r['score_pct'] for r in valid];mx=sum(x)/len(x);my=sum(y)/len(y)
        slope=sum((a-mx)*(b-my) for a,b in zip(x,y))/sum((a-mx)**2 for a in x)
    change=None
    # Fixed nonoverlapping chronological edge windows, not cherry-picked valid grades.
    if len(rows)>=2*edge_window:
        early=[r['score_pct'] for r in rows[:edge_window]]
        recent=[r['score_pct'] for r in rows[-edge_window:]]
        if (all(v is not None for v in early+recent)
                and not any(r['chronology_tied'] for r in rows[:edge_window]+rows[-edge_window:])):
            change=(sum(recent)-sum(early))/edge_window
    for row in rows:row.pop('timestamp')
    course,group=scopes.pop()
    return dict(course_id=course,group_id=group,student_id=student_id,rows=rows,
        rolling_window=rolling_window,edge_window=edge_window,valid_assessments=len(valid),
        distinct_scored_dates=distinct_scored_dates,
        slope_percentage_points_per_day=slope,early_to_recent_change_percentage_points=change,
        limitations=[
            'Descriptive scores across different assessments, not ability, motivation or learning growth.',
            'Assessment schedule dates are not submission, grading or feedback timestamps.',
            'Class medians use each item target population; populations may differ.',
            'Rolling means require every score in the fixed window; gaps are not imputed.',
            'Equal instants are tied, even with different offsets. ID sorting is display-only; tied windows have no rolling or edge-change estimate.',
            'OLS slope uses available scores and requires three distinct dates; missingness can bias it.',
            'Edge change compares fixed early/recent windows only when both are fully scored.'])
