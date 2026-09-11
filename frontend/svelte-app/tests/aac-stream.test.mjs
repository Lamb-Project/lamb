import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
const source=(await fs.readFile(new URL('../src/lib/services/aacService.js',import.meta.url),'utf8')).replace("import { apiFetch, apiJson } from '$lib/services/apiClient';",'const apiFetch=(...a)=>globalThis.mockFetch(...a); const apiJson=apiFetch;');
const {sendMessageStream}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
async function run(parts,{status=200,signal,fail}={}) {
 const chunks=[],errors=[],done=[],statuses=[];let cancelled=false;
 globalThis.mockFetch=async()=>new Response(new ReadableStream({start(c){for(const p of parts)c.enqueue(p); if(fail)c.error(fail);else c.close();},cancel(){cancelled=true;}}),{status});
 await sendMessageStream('s','hi',x=>chunks.push(x),x=>done.push(x),x=>errors.push(x),x=>statuses.push(x),signal);
 return {chunks,errors,done,statuses,cancelled};
}
const enc=s=>new TextEncoder().encode(s);
test('byte-fragmented Unicode and CRLF SSE, status, stats',async()=>{
 const bytes=enc('data: {"status":"thinking"}\r\n\r\ndata: {"content":"Sí 日本語"}\n\ndata: {"done":true,"stats":{"tool_calls":2}}\n\ndata: [DONE]\n\n');
 const r=await run([...bytes].map(x=>new Uint8Array([x])));
 assert.equal(r.chunks.join(''),'Sí 日本語');assert.equal(r.done[0].tool_calls,2);assert.equal(r.statuses[0].status,'thinking');assert.deepEqual(r.errors,[]);
});
test('last frame without newline is consumed',async()=>{assert.equal((await run([enc('data:{"content":"last"}\ndata:[DONE]')])).chunks.join(''),'last');});
test('premature EOF is an error, partial content retained',async()=>{const r=await run([enc('data: {"content":"partial"}\n')]);assert.deepEqual(r.chunks,['partial']);assert.match(r.errors[0],/interrupted/);});
test('server error is delivered once',async()=>{const r=await run([enc('data: {"error":"provider failed"}\n')]);assert.deepEqual(r.errors,['provider failed']);});
test('malformed event does not eat later content',async()=>{const r=await run([enc('data: broken\ndata: {"content":"ok"}\ndata: [DONE]\n')]);assert.deepEqual(r.chunks,['ok']);});
test('HTTP failure detail',async()=>{assert.deepEqual((await run([enc('{"detail":"forbidden"}')],{status:403})).errors,['forbidden']);});
test('HTTP non-JSON failure',async()=>{assert.deepEqual((await run([enc('bad gateway')],{status:502})).errors,['HTTP 502']);});
test('abort is quiet',async()=>{const controller=new AbortController();controller.abort();assert.deepEqual((await run([],{signal:controller.signal})).errors,[]);});
test('reader failure propagates to terminal',async()=>{await assert.rejects(run([],{fail:new Error('network lost')}),/network lost/);});
test('callback failure is not swallowed as JSON error',async()=>{globalThis.mockFetch=async()=>new Response('data: {"content":"x"}\n');await assert.rejects(sendMessageStream('s','x',()=>{throw new Error('render failed');}),/render failed/);});
test('retry works after failed request',async()=>{await run([enc('oops')],{status:500});assert.deepEqual((await run([enc('data: {"content":"recovered"}\ndata: [DONE]\n')])).chunks,['recovered']);});
