// Three isolated device runtimes using the production sync client.
const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
const root=path.join(__dirname,'..');
const rows=new Map();let outage=false,cloudFailure=false,hold=null;
function device(){
 const store=new Map(),events=[];
 const ctx={console,crypto:{randomUUID:()=>Math.random().toString()},Date,JSON,Number,String,Object,Set,Math,
  localStorage:{getItem:k=>store.get(k)??null,setItem:(k,v)=>store.set(k,String(v)),removeItem:k=>store.delete(k)},
  setTimeout:()=>1,clearTimeout(){},setInterval(){},CustomEvent:class{constructor(type){this.type=type}},
  dispatchEvent:e=>events.push(e.type),addEventListener(){},
  fetch:async(url,opts={})=>{
   if(outage) throw Error('network offline');
   if(cloudFailure && url.includes('/rest/'))return {ok:false,status:500,json:async()=>({})};
   const body=JSON.parse(opts.body||'{}');let data;
   if(url.includes('grant_type=password')) data={access_token:body.email,refresh_token:body.email,user:{id:body.email}};
   else if(url.includes('rpc/')){
    if(hold){const fn=hold;hold=null;await fn()}
    const owner=opts.headers.Authorization.slice(7),row=rows.get(owner);
    if((row?.revision||0)!==body.p_revision)data={ok:false};
    else{const revision=body.p_revision+1;rows.set(owner,{state:body.p_state,revision});data={ok:true,revision}}
   }else if(url.includes('/rest/')) data=rows.has(opts.headers.Authorization.slice(7))?[rows.get(opts.headers.Authorization.slice(7))]:[];
   else data={enabled:true,autoSync:false,supabaseUrl:'https://mock.invalid',anonKey:'public'};
   return {ok:true,status:200,json:async()=>structuredClone(data)};
  }};
 ctx.window=ctx;vm.createContext(ctx);
 for(const f of ['sync-core.js','sync.js'])vm.runInContext(fs.readFileSync(path.join(root,f),'utf8'),ctx);
 return ctx.AIBriefSync;
}
(async()=>{
 const pc=device(),phone=device(),pad=device();const cfg=await pc.config();
 for(const d of [pc,phone,pad]){await d.init();await d.signIn(cfg,'alice','password')}
 pc.touchSet('saved','A',true);phone.touchSet('saved','B',true);pad.touchSet('watchlist','Godot',true);
 await Promise.all([pc.syncNow(),phone.syncNow(),pad.syncNow()]);
 for(const d of [pc,phone,pad]){await d.syncNow();assert.deepEqual(Object.keys(d.meta().sets.saved).sort(),['A','B']);assert.equal(d.meta().sets.watchlist.Godot.present,true)}
 phone.touchSet('read','A',true);phone.touchBlob('mode','5min');phone.touchBlob('learning',{categories:{AI:5}});
 await phone.syncNow();await pc.syncNow();assert.equal(pc.meta().sets.read.A.present,true);assert.equal(pc.meta().blobs.mode.value,'5min');assert.equal(pc.meta().blobs.learning.value.categories.AI,5);
 const fresh=device();await fresh.init();await fresh.signIn(cfg,'alice','password');await fresh.syncNow();assert.equal(fresh.meta().blobs.mode.value,'5min');assert.equal(fresh.meta().blobs.learning.value.categories.AI,5);
 cloudFailure=true;pc.touchSet('saved','server-failure',true);await assert.rejects(pc.syncNow());assert.equal(pc.meta().sets.saved['server-failure'].present,true);cloudFailure=false;await pc.syncNow();
 outage=true;pad.touchSet('saved','offline',true);await assert.rejects(pad.syncNow());assert.equal(pad.meta().sets.saved.offline.present,true);
 outage=false;await pad.syncNow();await pc.syncNow();assert.equal(pc.meta().sets.saved.offline.present,true);
 hold=async()=>{pc.touchSet('saved','during-upload',true)};await pc.syncNow();assert.equal(pc.meta().sets.saved['during-upload'].present,true);await pc.syncNow();
 await pc.signIn(cfg,'bob','password');assert.equal(Object.keys(pc.meta().sets.saved).length,0);await pc.syncNow();assert.equal(Object.keys(rows.get('bob').state.sets.saved).length,0);
 pc.signOut();await pc.signIn(cfg,'alice','password');assert.equal(pc.meta().sets.saved.A.present,true);
 const C=require('../sync-core');let a=C.touchSet(C.emptyState(),'saved','tie',true,100),b=C.touchSet(C.emptyState(),'saved','tie',false,100);
 assert.deepEqual(C.merge(a,b).sets,C.merge(b,a).sets);
 console.log('sync integration passed: concurrent devices, read/watch/learning/mode, offline/cloud failure, in-flight edits, account isolation, deterministic conflicts');
})().catch(e=>{console.error(e);process.exitCode=1});
