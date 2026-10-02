(function(global){
  function nowTs(){ return Date.now(); }
  function clone(x){ return JSON.parse(JSON.stringify(x)); }
  function later(a,b){
    if(!a) return b; if(!b) return a;
    const delta=Number(a.ts||0)-Number(b.ts||0);
    return delta ? (delta>0?a:b) : (JSON.stringify(a)>=JSON.stringify(b)?a:b);
  }

  function emptyState(){
    return {
      version: 1,
      device_id: "",
      updated_at: 0,
      sets: { saved:{}, read:{}, watchlist:{} },
      blobs: { learning:{value:null,ts:0}, ui_prefs:{value:null,ts:0}, personalize:{value:null,ts:0}, mode:{value:null,ts:0} }
    };
  }

  function normalize(s){
    const out = emptyState();
    if(!s || typeof s!=="object") return out;
    out.version = 1;
    out.device_id = String(s.device_id||"");
    out.updated_at = Number(s.updated_at||0);
    for(const k of ["saved","read","watchlist"]){
      if(s.sets && s.sets[k] && typeof s.sets[k]==="object"){
        for(const [id,v] of Object.entries(s.sets[k])){
          if(["__proto__","constructor","prototype"].includes(id)||!v||typeof v!=="object") continue;
          out.sets[k][id] = {present:!!v.present, ts:Number(v.ts||0)};
        }
      }
    }
    for(const k of ["learning","ui_prefs","personalize","mode"]){
      const v=s.blobs?.[k];
      if(v && typeof v==="object"){
        out.blobs[k]={value:v.value??null,ts:Number(v.ts||0)};
      }
    }
    return out;
  }

  function merge(a,b){
    a=normalize(a); b=normalize(b);
    const out=emptyState();
    out.device_id = b.device_id || a.device_id;
    for(const k of ["saved","read","watchlist"]){
      const ids=new Set([...Object.keys(a.sets[k]),...Object.keys(b.sets[k])]);
      for(const id of ids){
        out.sets[k][id]=clone(later(a.sets[k][id],b.sets[k][id]));
      }
    }
    for(const k of ["learning","ui_prefs","personalize","mode"]){
      out.blobs[k]=clone(later(a.blobs[k],b.blobs[k]));
    }
    out.updated_at=Math.max(a.updated_at,b.updated_at,nowTs());
    return out;
  }

  function touchSet(state,collection,key,present,ts){
    const out=normalize(state);
    if(!out.sets[collection]) throw new Error("unknown collection");
    out.sets[collection][String(key)]={present:!!present,ts:Number(ts||nowTs())};
    out.updated_at=Number(ts||nowTs());
    return out;
  }

  function touchBlob(state,name,value,ts){
    const out=normalize(state);
    if(!out.blobs[name]) throw new Error("unknown blob");
    out.blobs[name]={value:clone(value),ts:Number(ts||nowTs())};
    out.updated_at=Number(ts||nowTs());
    return out;
  }

  function presentKeys(map){
    return Object.entries(map||{}).filter(([,v])=>v?.present).map(([k])=>k);
  }

  const api={emptyState,normalize,merge,touchSet,touchBlob,presentKeys};
  if(typeof module!=="undefined" && module.exports) module.exports=api;
  global.AIBriefSyncCore=api;
})(typeof window!=="undefined"?window:globalThis);
