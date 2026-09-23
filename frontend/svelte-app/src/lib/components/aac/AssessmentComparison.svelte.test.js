import {beforeEach,expect,it} from 'vitest';
import {render,screen,cleanup} from '@testing-library/svelte';
import AssessmentComparison from './AssessmentComparison.svelte';
beforeEach(cleanup);
const row = {name:'Assessment #42',comparison_status:'available',unavailable_reasons:[],metrics:{
    population_n:6,valid_n:4,min_pct:0,q1_pct:25,median_pct:50,q3_pct:75,max_pct:100,iqr_pct:50,
    pass_n:2,pass_denominator_n:4,pass_rate_pct:50,missing_n:1,nonexcluded_population_n:5,
    missing_grade_rate_pct:20,excluded_n:1}};
const data = {title:'Comparison',language:'en',caption:'Saved final grades only.',coverage:{complete:true},rows:[row]};
it.each(['en','es','ca','eu'])('renders exact statistics and normalized coordinates in %s',language=>{
    const {container}=render(AssessmentComparison,{data:{...data,language}});
    expect(container.querySelector('[data-median]')).toHaveAttribute('cx','220');
    expect(container.querySelector('[data-iqr]')).toHaveAttribute('x','120');
    expect(container.querySelector('[data-iqr]')).toHaveAttribute('width','200');
    expect([...container.querySelector('tbody tr').children].slice(1,14).map(c=>c.textContent))
        .toEqual(['6','4','0','25','50','75','100','50','2 / 4','50','1 / 5','20','1']);
    expect(screen.getByRole('region')).toHaveAttribute('tabindex','0');
    expect(screen.getAllByRole('columnheader')).toHaveLength(15);
});
it('retains unavailable assessments without invented zero scores',()=>{
    const stale={...row,name:'Stale item',comparison_status:'unavailable',unavailable_reasons:['stale_final_grades'],
        metrics:{...row.metrics,valid_n:0,min_pct:null,q1_pct:null,median_pct:null,q3_pct:null,max_pct:null,iqr_pct:null,pass_n:null,pass_denominator_n:null,pass_rate_pct:null}};
    const {container}=render(AssessmentComparison,{data:{...data,coverage:{complete:false},rows:[row,stale]}});
    expect(screen.getAllByRole('img')).toHaveLength(1);
    expect(container.querySelectorAll('tbody tr')).toHaveLength(2);
    expect(container.querySelectorAll('tbody tr')[1].children[5].textContent).toBe('–');
    expect(screen.getAllByText('Stale final grades')).toHaveLength(2);
});
it('renders all twenty items without sampling or truncation',()=>{
    const {container}=render(AssessmentComparison,{data:{...data,rows:Array.from({length:20},(_,i)=>({...row,name:`Assessment #${i}`}))}});
    expect(container.querySelectorAll('tbody tr')).toHaveLength(20);
    expect(screen.getAllByRole('img')).toHaveLength(20);
});
it('distinguishes empty population from a real zero score',()=>{
    const {container}=render(AssessmentComparison,{data:{...data,rows:[{...row,metrics:{...row.metrics,valid_n:0,median_pct:null}}]}});
    expect(container.querySelector('svg')).toBeNull();
    expect(screen.getAllByText('No valid grades')).toHaveLength(2);
});
it('renders the empty state',()=>{
    render(AssessmentComparison,{data:{...data,rows:[]}});
    expect(screen.getByRole('status')).toHaveTextContent('No assessments');
    expect(screen.queryByRole('table')).toBeNull();
});
