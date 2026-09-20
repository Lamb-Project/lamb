import { beforeEach, expect, it, vi } from 'vitest';
import { render, screen, cleanup } from '@testing-library/svelte';
vi.mock('$lib/services/moodleService', () => ({moodleResult:vi.fn()}));
import { moodleResult } from '$lib/services/moodleService';
import MoodleEvidence from './MoodleEvidence.svelte';
const id='11111111-1111-4111-8111-111111111111';
const fixture=()=>({result_id:id,base_url:'https://moodle.test/campus',snapshot:{
    coverage:{complete:false,posts_found:1,requested_courses:2,courses:{ok:1,excluded:1},meaning:'Partial coverage'},
    window:{since:'2026-09-01T00:00:00Z',until:'2026-10-01T00:00:00Z'},completed_at:'2026-09-19T12:00:00Z',limitations:['New posts only'],
    courses:[{id:1,name:'Synthetic course',status:'ok',forums:[]},{id:2,name:'Other',status:'excluded',forums:[]}],
    posts:[{id:1000,discussion_id:100,course_id:1,timecreated:1790000000,subject_text:'Question',message_text:'<img src="https://evil.test" onerror="alert(1)">'}]}});
beforeEach(()=>{cleanup();vi.resetAllMocks();moodleResult.mockResolvedValue(fixture());});
it('shows deterministic coverage and escapes source text, with site-prefix-safe links',async()=>{
    render(MoodleEvidence,{resultId:id});
    expect(await screen.findByLabelText('Coverage')).toHaveTextContent('1 of 2 requested courses fully checked');
    expect(screen.getByText(/<img src=/)).toBeInTheDocument();
    expect(document.querySelector('img')).toBeNull();
    const link=screen.getByRole('link',{name:'Open post in Moodle'});
    expect(link).toHaveAttribute('href','https://moodle.test/campus/mod/forum/discuss.php?d=100#p1000');
    expect(link).toHaveAttribute('target','_blank');
    expect(document.querySelector('[data-aac-resource="moodle-result"]')).toHaveAttribute('data-aac-id',id);
});
it('does not mark denied evidence as a loaded navigation destination',async()=>{
    moodleResult.mockRejectedValue(new Error('Moodle evidence is unavailable or expired'));
    render(MoodleEvidence,{resultId:id});
    await screen.findByRole('alert');
    expect(document.querySelector('[data-aac-resource]')).toBeNull();
});

it('shows saved progress and cumulative counts without calling a paused run complete',async()=>{
    const data=fixture();data.snapshot.run={can_continue:true,step:1,step_limit:12};
    Object.assign(data.snapshot.coverage,{posts_found:155,discussions_checked:155,remaining_courses:2});
    moodleResult.mockResolvedValue(data);render(MoodleEvidence,{resultId:id});
    const coverage=await screen.findByLabelText('Coverage');
    expect(coverage).toHaveTextContent('Check paused. Progress is saved.');
    expect(coverage).toHaveTextContent('155 discussions checked');
    expect(coverage).toHaveTextContent('2 still to finish');
    expect(coverage).not.toHaveTextContent('Complete coverage');
});
it('distinguishes terminal gaps from resumable work',async()=>{
    const data=fixture();data.snapshot.run={can_continue:false,step:12,step_limit:12};
    moodleResult.mockResolvedValue(data);render(MoodleEvidence,{resultId:id});
    const coverage=await screen.findByLabelText('Coverage');
    expect(coverage).toHaveTextContent('Check finished with gaps.');
    expect(coverage).not.toHaveTextContent('Ask LAMB AGENT to continue');
});
