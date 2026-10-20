import {it,expect} from 'vitest';
import {sidebarSize} from './aacLayout';
it('keeps both desktop panes usable and falls back to a mobile panel',()=>{
 for(const w of [920,1000,1500,2500])for(const ratio of [-1,.25,.35,.55,2,NaN]){
  const s=sidebarSize(w,ratio);expect(s.mobile).toBe(false);expect(s.width).toBeGreaterThanOrEqual(360);expect(w-s.width).toBeGreaterThanOrEqual(560);expect(s.width/w).toBeGreaterThanOrEqual(.25);expect(s.width/w).toBeLessThanOrEqual(.55);
 }
 expect(sidebarSize(390)).toMatchObject({mobile:true,width:390});
});
