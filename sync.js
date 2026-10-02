(function(){
  const C=window.AIBriefSyncCore;
  if(!C) throw new Error("sync-core.js missing");

  const META_KEY="ai-brief-sync-meta";
  const SESSION_KEY="ai-brief-sync-session";
  const DEVICE_KEY="ai-brief-device-id";

  function uid(){
    let id=localStorage.getItem(DEVICE_KEY);
    if(!id){
      id=(crypto.randomUUID?crypto.randomUUID():("dev-"+Date.now()+"-"+Math.random().toString(16).slice(2)));
      localStorage.setItem(DEVICE_KEY,id);
    }
    return id;
  }
  function readJSON(key, fallback){
    try{const v=JSON.parse(localStorage.getItem(key)||"null"); return v??fallback}catch(e){return fallback}
  }
  function writeJSON(key,v){localStorage.setItem(key,JSON.stringify(v))}
  function meta(){
    const s=C.normalize(readJSON(META_KEY,C.emptyState()));
    s.device_id=uid();
    return s;
  }
  function saveMeta(s){s.device_id=uid();s.updated_at=Date.now();writeJSON(META_KEY,s)}
  function session(){return readJSON(SESSION_KEY,null)}
  function saveSession(s){s?writeJSON(SESSION_KEY,s):localStorage.removeItem(SESSION_KEY)}

  async function loadConfig(){
    try{
      const r=await fetch("./config/sync.json",{cache:"no-store"});
      if(!r.ok) throw new Error();
      return await r.json();
    }catch(e){
      return {enabled:false,provider:"supabase",autoSync:false,privacy:{}};
    }
  }

  function bootstrapFromLocal(){
    let s=meta();
    const t=Date.now()-1000;
    if(!Object.keys(s.sets.saved).length){
      for(const id of readJSON("ai-brief-saved",[])) s=C.touchSet(s,"saved",id,true,t);
    }
    if(!Object.keys(s.sets.read).length){
      for(const id of readJSON("ai-brief-read",[])) s=C.touchSet(s,"read",id,true,t);
    }
    if(!Object.keys(s.sets.watchlist).length){
      for(const id of readJSON("ai-brief-watchlist",[])) s=C.touchSet(s,"watchlist",id,true,t);
    }
    if(!s.blobs.learning.value){
      const p=readJSON("ai-brief-learning",null);
      s=C.touchBlob(s,"learning",p,p?.interactions?t:0);
      if(!p?.interactions) s.blobs.learning.ts=0;
    }
    if(!s.blobs.ui_prefs.value){
      const p=readJSON("ai-brief-ui-prefs",{});
      s=C.touchBlob(s,"ui_prefs",p,t);if(!Object.keys(p).length)s.blobs.ui_prefs.ts=0;
    }
    if(s.blobs.personalize.value===null){
      const v=localStorage.getItem("ai-brief-personalize")!=="false";
      s=C.touchBlob(s,"personalize",v,t);if(v)s.blobs.personalize.ts=0;
    }
    if(s.blobs.mode.value===null){
      const v=localStorage.getItem("ai-brief-mode")||"10min";
      s=C.touchBlob(s,"mode",v,t);if(v==="10min")s.blobs.mode.ts=0;
    }
    saveMeta(s);
  }

  function applyToLocal(s){
    s=C.normalize(s);
    writeJSON("ai-brief-saved",C.presentKeys(s.sets.saved));
    writeJSON("ai-brief-read",C.presentKeys(s.sets.read));
    writeJSON("ai-brief-watchlist",C.presentKeys(s.sets.watchlist));
    writeJSON("ai-brief-learning",s.blobs.learning.value);
    writeJSON("ai-brief-ui-prefs",s.blobs.ui_prefs.value||{});
    localStorage.setItem("ai-brief-personalize",String(s.blobs.personalize.value!==false));
    localStorage.setItem("ai-brief-mode",String(s.blobs.mode.value||"10min"));
    saveMeta(s);
  }

  function headers(cfg, token){
    const h={"apikey":cfg.anonKey,"Content-Type":"application/json"};
    if(token) h["Authorization"]="Bearer "+token;
    return h;
  }

  async function signUp(cfg,email,password){
    const r=await fetch(cfg.supabaseUrl.replace(/\/$/,"")+"/auth/v1/signup",{
      method:"POST",headers:headers(cfg),body:JSON.stringify({email,password})
    });
    const data=await r.json();
    if(!r.ok) throw new Error(data?.msg||data?.message||"注册失败");
    if(data.access_token){bindAccount(data.user.id);saveSession(data);}
    return data;
  }

  async function signIn(cfg,email,password){
    const r=await fetch(cfg.supabaseUrl.replace(/\/$/,"")+"/auth/v1/token?grant_type=password",{
      method:"POST",headers:headers(cfg),body:JSON.stringify({email,password})
    });
    const data=await r.json();
    if(!r.ok) throw new Error(data?.error_description||data?.msg||"登录失败");
    bindAccount(data.user.id);saveSession(data);
    return data;
  }

  async function refresh(cfg){
    const s=session();
    if(!s?.refresh_token) return null;
    const r=await fetch(cfg.supabaseUrl.replace(/\/$/,"")+"/auth/v1/token?grant_type=refresh_token",{
      method:"POST",headers:headers(cfg),body:JSON.stringify({refresh_token:s.refresh_token})
    });
    const data=await r.json();
    if(!r.ok) return null;
    saveSession(data); return data;
  }

  async function remoteRead(cfg){
    let s=session(); if(!s?.access_token) throw new Error("未登录");
    const userId=s.user?.id; if(!userId) throw new Error("缺少用户ID");
    let url=cfg.supabaseUrl.replace(/\/$/,"")+"/rest/v1/ai_brief_sync_state?user_id=eq."+encodeURIComponent(userId)+"&select=state,revision,updated_at";
    let r=await fetch(url,{headers:{...headers(cfg,s.access_token),"Accept":"application/json"}});
    if(r.status===401){s=await refresh(cfg); if(!s) throw new Error("登录已过期"); r=await fetch(url,{headers:{...headers(cfg,s.access_token),"Accept":"application/json"}})}
    if(!r.ok) throw new Error("读取云端失败");
    const arr=await r.json();
    return arr[0]||null;
  }

  async function remoteWrite(cfg,state,revision){
    const sess=session(); if(!sess?.access_token) throw new Error("未登录");
    const r=await fetch(cfg.supabaseUrl.replace(/\/$/,"")+"/rest/v1/rpc/ai_brief_compare_and_swap",{
      method:"POST",headers:headers(cfg,sess.access_token),
      body:JSON.stringify({p_state:state,p_revision:revision})
    });
    if(!r.ok) throw new Error("写入云端失败："+r.status);
    return await r.json();
  }
  let activeSync=null, generation=0;
  async function syncNow(cfg){
    if(activeSync){await activeSync;return syncNow(cfg)}
    if(!cfg?.enabled) throw new Error("云同步尚未配置");
    const owner=session()?.user?.id, epoch=generation;
    if(!owner) throw new Error("未登录");
    const check=()=>{if(epoch!==generation||session()?.user?.id!==owner) throw new Error("账号已切换")};
    activeSync=(async()=>{
      bootstrapFromLocal();
      for(let attempt=0;attempt<5;attempt++){
        const remote=await remoteRead(cfg);check();
        const merged=C.merge(meta(),remote?.state||C.emptyState());
        const result=await remoteWrite(cfg,merged,remote?.revision||0);check();
        if(!result.ok) continue;
        const current=meta();
        const dirty=JSON.stringify(current.sets)!==JSON.stringify(merged.sets)||JSON.stringify(current.blobs)!==JSON.stringify(merged.blobs);
        applyToLocal(C.merge(merged,current));
        window.dispatchEvent(new CustomEvent("ai-brief-synced"));
        if(dirty) schedule();
        return {ok:true,revision:result.revision};
      }
      throw new Error("同步冲突，请重试；本地修改已保留");
    })();
    try{return await activeSync}finally{activeSync=null}
  }
  function bindAccount(id){
    const old=localStorage.getItem("ai-brief-sync-owner");
    if(old===id) return;
    generation++;
    if(old) writeJSON("ai-brief-account-"+old,meta());
    if(old || localStorage.getItem("ai-brief-has-account")){
      const state=readJSON("ai-brief-account-"+id,C.emptyState());
      applyToLocal(state);
      for(const key of Object.keys(localStorage)) if(key.startsWith("ai-brief-feedback-")||key==="ai-brief-hidden") localStorage.removeItem(key);
    }
    localStorage.setItem("ai-brief-sync-owner",id);
    localStorage.setItem("ai-brief-has-account","true");
    window.dispatchEvent(new CustomEvent("ai-brief-synced"));
  }
  function signOut(){
    const old=localStorage.getItem("ai-brief-sync-owner");
    if(old) writeJSON("ai-brief-account-"+old,meta());
    generation++;clearTimeout(timer);saveSession(null);
    localStorage.removeItem("ai-brief-sync-owner");applyToLocal(C.emptyState());
    window.dispatchEvent(new CustomEvent("ai-brief-synced"));
  }

  function touchSet(collection,key,present){
    let s=meta();
    s=C.touchSet(s,collection,key,present,Date.now());
    saveMeta(s);
    schedule();
  }
  function touchBlob(name,value){
    let s=meta();
    s=C.touchBlob(s,name,value,Date.now());
    saveMeta(s);
    schedule();
  }

  let cfgCache=null, timer=null;
  async function config(){ if(!cfgCache) cfgCache=await loadConfig(); return cfgCache; }
  async function schedule(){
    const cfg=await config();
    if(!cfg.enabled || !cfg.autoSync || !session()?.access_token) return;
    clearTimeout(timer);
    timer=setTimeout(()=>syncNow(cfg).then(()=>window.dispatchEvent(new CustomEvent("ai-brief-synced"))).catch(()=>{}),1200);
  }

  async function init(){
    bootstrapFromLocal();
    const cfg=await config();
    if(cfg.enabled && cfg.autoSync && session()?.access_token){
      try{await syncNow(cfg)}catch(e){}
    }
    if(cfg.enabled && cfg.autoSync){
      setInterval(()=>schedule(),Math.max(15,Number(cfg.syncIntervalSeconds)||120)*1000);
      window.addEventListener("online",schedule);
      window.addEventListener("focus",schedule);
    }
    return cfg;
  }

  window.AIBriefSync={
    init,config,session,signUp,signIn,signOut,syncNow:async()=>syncNow(await config()),
    touchSet,touchBlob,applyToLocal,meta
  };
})();
