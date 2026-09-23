import {beforeEach,expect,it} from 'vitest';
import {render,screen,cleanup,fireEvent} from '@testing-library/svelte';
import ForumNetwork from './ForumNetwork.svelte';
beforeEach(cleanup);
const row=i=>({student_id:i,name:`Student #${i}`,in_degree:1,out_degree:1,unique_peers:1,
    incoming_replies:2,outgoing_replies:3,no_observed_peer_interaction:false});
const data={title:'Peer network',language:'en',timezone:'Europe/Madrid',forum_id:8,
    collection_run_id:'fixed-run',caption:'Position is not learning or social value.',
    metrics:{window:{since:1761350400,until:1761526800}},coverage:{complete:true},
    rows:[row(1),row(2)],network:{edges_included:true,edges:[
        {source_student_id:1,target_student_id:2,replies:3},
        {source_student_id:2,target_student_id:1,replies:2}]}};
it.each(['en','es','ca','eu'])('renders exact peer metrics and directed graph in %s',language=>{
    const {container}=render(ForumNetwork,{data:{...data,language}});
    expect(container.querySelectorAll('[data-peer-node]')).toHaveLength(2);
    expect(container.querySelectorAll('[data-peer-edge]')).toHaveLength(2);
    expect(container.querySelector('[data-peer-edge] title').textContent).toBe('#1 → #2: 3');
    const cells=[...container.querySelector('tbody tr').children].map(c=>c.textContent);
    expect(cells.slice(0,6)).toEqual(['Student #1','1','1','1','2','3']);
    expect(container.querySelector('svg')).toHaveAttribute('role','img');
});
it.each([31,51,500])('uses exact table without a sampled graph for %s students',count=>{
    const {container}=render(ForumNetwork,{data:{...data,rows:Array.from({length:count},(_,i)=>row(i+1))}});
    expect(container.querySelector('svg')).toBeNull();
    expect(container.querySelector('[data-network-table-reason]')).not.toBeNull();
    expect(container.querySelectorAll('tbody tr')).toHaveLength(Math.min(count,50));
});
it('uses a table for dense evidence even with few students',()=>{
    const {container}=render(ForumNetwork,{data:{...data,network:{edges_included:true,edges:Array(101).fill(data.network.edges[0])}}});
    expect(container.querySelector('svg')).toBeNull();
    expect(container.querySelectorAll('tbody tr')).toHaveLength(2);
});
it('paginates all 500 rows and returns to first page',async()=>{
    const rows=Array.from({length:500},(_,i)=>row(i+1));
    const {container}=render(ForumNetwork,{data:{...data,rows,network:{edges_included:false,edges:[]}}});
    expect(screen.getByRole('button',{name:'Previous'})).toBeDisabled();
    for(let p=1;p<10;p++)await fireEvent.click(screen.getByRole('button',{name:'Next'}));
    expect(container.querySelector('tbody th').textContent).toBe('Student #451');
    expect(screen.getByRole('button',{name:'Next'})).toBeDisabled();
    for(let p=9;p>0;p--)await fireEvent.click(screen.getByRole('button',{name:'Previous'}));
    expect(container.querySelector('tbody th').textContent).toBe('Student #1');
});
it('retains unknown flags under incomplete coverage',()=>{
    const {container}=render(ForumNetwork,{data:{...data,coverage:{complete:false},rows:[{...row(1),no_observed_peer_interaction:null}],network:{edges_included:true,edges:[]}}});
    expect(screen.getByRole('status').textContent).toBe('Incomplete public evidence');
    expect(container.querySelector('tbody td:last-child').textContent).toBe('Unknown');
});
it('shows an empty state without a graph or navigation',()=>{
    const {container}=render(ForumNetwork,{data:{...data,rows:[],network:{edges_included:true,edges:[]}}});
    expect(screen.getByRole('status').textContent).toBe('No rows');
    expect(container.querySelector('svg')).toBeNull();
    expect(container.querySelector('nav')).toBeNull();
});
