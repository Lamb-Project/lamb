import { describe, it, expect } from 'vitest';
import { groupActivities } from './activities';

describe('activity course grouping', () => {
  it('separates identical course identifiers across LMS installations and LTI deployments', () => {
    const rows = ['lms-a', 'lms-b', 'deployment-c'].map((scope, i) => ({ id: i + 1, lms_scope: scope, context_id: '101', context_title: 'Databases' }));
    expect(groupActivities(rows)).toHaveLength(3);
    expect(groupActivities([...rows, { ...rows[0], id: 4 }])[0].activities).toHaveLength(2);
  });
  it('does not combine unverifiable legacy courses by title', () => {
    expect(groupActivities([{ id: 1, context_title: 'Databases' }, { id: 2, context_title: 'Databases' }])).toHaveLength(2);
  });
});
