import {beforeEach, expect, it} from 'vitest';
import {render, screen, cleanup, fireEvent} from '@testing-library/svelte';
import QuizEvidence from './QuizEvidence.svelte';
beforeEach(cleanup);
const metrics = {
    retry_1_to_2: {score_change_percentage_points: {n: 1, mean: 100},
        between_attempt_seconds: {median: 500}, ungraded_pairs: 0},
    finished_attempt_histogram: [{attempts: 0, students: 1}, {attempts: 1, students: 1}, {attempts: 3, students: 1}]
};
it.each(['en','es','ca','eu'])('renders exact paired evidence and zero-attempt population in %s', async language => {
    const {container} = render(QuizEvidence, {metrics, language});
    expect([...container.querySelectorAll('dd')].map(node=>node.textContent)).toEqual(['1','100','500','0']);
    const detail = container.querySelector('details');
    expect(detail.open).toBe(false);
    await fireEvent.click(container.querySelector('summary'));
    expect([...container.querySelectorAll('tbody tr')].map(row=>[...row.children].map(cell=>cell.textContent)))
        .toEqual([['0','1'],['1','1'],['3','1']]);
    expect(container.querySelector('section')).toHaveAttribute('aria-label');
});
it('keeps absent or null evidence unavailable, never zero', () => {
    const {container} = render(QuizEvidence, {metrics: {retry_1_to_2: {
        score_change_percentage_points: {n: 0, mean: null}, between_attempt_seconds: {median: null}}}});
    expect([...container.querySelectorAll('dd')].map(node=>node.textContent))
        .toEqual(['0','Unavailable','Unavailable','Unavailable']);
    expect(screen.queryByRole('table')).toBeNull();
    expect(screen.getByText(/Score change does not establish learning/)).toBeInTheDocument();
});
