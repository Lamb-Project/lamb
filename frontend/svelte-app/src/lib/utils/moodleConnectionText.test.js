import {expect,it} from 'vitest';
import {courseGroups,moodleConnectionText} from './moodleConnectionText';
it('groups exact reported roles, preserves unknowns and supports dual roles',()=>{
 const rows=[['teacher'],['editingteacher'],['student'],['manager'],['custom_teacher'],['teacher','student'],[]].map((roles,id)=>({id,my_roles_status:'available',my_roles:roles.map(shortname=>({shortname}))}));
 rows.push({id:7,my_roles_status:'unavailable',my_roles:[{shortname:'teacher'}]});
 const result=courseGroups(rows);
 expect(result.teacher.map(c=>c.id)).toEqual([0,1,5]);expect(result.student.map(c=>c.id)).toEqual([2,5]);expect(result.other.map(c=>c.id)).toEqual([3,4,6,7]);
});
it('all interface languages provide the complete connection flow',()=>{
 const keys=Object.keys(moodleConnectionText('en')).sort();
 for(const locale of ['en','es','ca','eu']){const text=moodleConnectionText(locale);expect(Object.keys(text).sort()).toEqual(keys);expect(text.steps).toHaveLength(3);expect(text.courseCount(2)).toContain('2');}
});
