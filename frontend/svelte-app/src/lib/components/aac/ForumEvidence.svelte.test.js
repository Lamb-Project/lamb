import {beforeEach,expect,it} from 'vitest';
import {render,screen,cleanup,fireEvent} from '@testing-library/svelte';
import ForumEvidence from './ForumEvidence.svelte';
beforeEach(cleanup);
const data={title:'Forum',language:'en',timezone:'Europe/Madrid',recipe:{id:'forum-participation'},
    caption:'Counts are not learning.',metrics:{window:{since:1761350400,until:1761526800}},coverage:{complete:true},
    rows:Array.from({length:101},(_,i)=>({name:`Student #${i+1}`,value:100-i,posts:100-i,replies:2,discussions_started:1,active_local_days:3}))};
it.each(['en','es','ca','eu'])('renders exact learner columns in %s',language=>{
    const {container}=render(ForumEvidence,{data:{...data,language}});
    expect(container.querySelectorAll('tbody tr')).toHaveLength(50);
    expect([...container.querySelector('tbody tr').children].map(cell=>cell.textContent)).toEqual(['Student #1','100','2','1','3']);
    expect(container.querySelector('[role="region"]')).toHaveAttribute('tabindex','0');
});
it('pages to exact zero without losing rows',async()=>{
    const {container}=render(ForumEvidence,{data});
    expect(screen.getByRole('button',{name:'Previous'})).toBeDisabled();
    await fireEvent.click(screen.getByRole('button',{name:'Next'}));
    expect(container.querySelector('tbody th').textContent).toBe('Student #51');
    await fireEvent.click(screen.getByRole('button',{name:'Next'}));
    expect(container.querySelectorAll('tbody tr')).toHaveLength(1);
    expect(container.querySelector('tbody td').textContent).toBe('0');
    expect(screen.getByRole('button',{name:'Next'})).toBeDisabled();
});
it('keeps unknown reply status and missing clocks distinct from zero',()=>{
    const {container}=render(ForumEvidence,{data:{...data,recipe:{id:'forum-discussions'},coverage:{complete:false},
        rows:[{name:'Discussion #1',observed_public_replies_as_of:0,public_thread_complete:false,
            last_observed_public_post_at:null,seconds_since_last_observed_public_post:null,no_observed_public_replies:null}]}});
    const cells=[...container.querySelector('tbody tr').children].map(cell=>cell.textContent);
    expect(cells.slice(2)).toEqual(['Unknown','Unknown','Unknown']);
    expect(screen.getByRole('status').textContent).toBe('Incomplete public evidence');
});
