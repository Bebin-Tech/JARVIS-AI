import test from 'node:test';
import assert from 'node:assert/strict';
import {handle} from '../server/cloud.js';
const post = (body, headers={}) => new Request('https://jarvis.test/api/chat',{method:'POST',headers:{'Content-Type':'application/json',...headers},body:JSON.stringify(body)});
test('cloud endpoints validate requests and isolate desktop features', async()=>{
  assert.equal((await handle(new Request('https://jarvis.test/api/index?route=health'))).status,200);
  assert.equal((await handle(post({text:'x'},{origin:'https://evil.test'}))).status,403);
  assert.equal((await handle(post({text:''}))).status,422);
  assert.equal((await handle(post({text:'x',history:[{role:'system',content:'bad'}]}))).status,422);
  assert.equal((await handle(post({text:'x',tools_enabled:true}))).status,422);
  assert.equal((await handle(new Request('https://jarvis.test/api/tools',{method:'POST'}))).status,404);
});
test('request identity stays server-side, real results and errors are preserved',async()=>{
  const originalFetch=globalThis.fetch;
  const headers={'x-vercel-oidc-token':'unit-test-identity'};
  try {
    globalThis.fetch=async (url,init)=>{
      assert.equal(url,'https://ai-gateway.vercel.sh/v1/chat/completions');
      assert.equal(init.headers.Authorization,'Bearer unit-test-identity');
      assert.equal(JSON.parse(init.body).messages.at(-1).content,'17 plus 25');
      return Response.json({choices:[{message:{content:'42'}}]});
    };
    const reply=await (await handle(post({text:'17 plus 25',history:[]},headers))).json();
    assert.equal(reply.text,'42');assert.equal(JSON.stringify(reply).includes('unit-test-identity'),false);
    globalThis.fetch=async()=>Response.json({error:{code:'customer_verification_required'}},{status:402});
    const response=await handle(post({text:'hello'},headers));
    assert.equal(response.status,503);assert.match((await response.json()).detail,/verification/);
  } finally { globalThis.fetch=originalFetch; }
});
