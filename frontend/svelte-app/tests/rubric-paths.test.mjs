import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';

// Exercise the service boundary: apiFetch owns base-URL resolution.
test('rubric services pass API-relative paths to the central client', async () => {
 const source=await fs.readFile(new URL('../src/lib/services/rubricService.js',import.meta.url),'utf8');
 const requests=[];
 globalThis.localStorage={getItem:()=> 'synthetic-token'};
 globalThis.__rubricFetch=async(path,options)=>{
  requests.push({path,method:options?.method||'GET'});
  assert.ok(path.startsWith('/rubrics'),path);
  assert.ok(!path.includes('/creator/'),path);
  return {ok:true,json:async()=>({rubrics:[],total:0,rubricId:'example'})};
 };
 try {
  const rewritten=source.replace(/^import .*;\r?\n/gm,'');
  const code="const browser=true; const apiFetch=globalThis.__rubricFetch; const getApiUrl=p=>'/creator'+p;\n"+rewritten;
  const service=await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'));
  await service.fetchRubrics();
  await service.fetchRubric('example');
  await service.fetchAccessibleRubrics();
  assert.deepEqual(requests.map(r=>r.path.split('?')[0]),['/rubrics','/rubrics/example','/rubrics/accessible']);
 }finally{delete globalThis.__rubricFetch;delete globalThis.localStorage;}
});
