/* Public news only; no account or preference data is sent. */
(function(root){
  const encoder=new TextEncoder();
  function chunks(text){const out=[];let part="";for(const c of String(text)){if(encoder.encode(part+c).length>480){out.push(part);part="";}part+=c;}if(part)out.push(part);return out;}
  function language(text){if(/[\u3040-\u30ff]/.test(text))return "ja";if(/[\uac00-\ud7af]/.test(text))return "ko";return "en";}
  function hasForeign(text){return /[A-Za-z]{3,}|[\u3040-\u30ff]|[\uac00-\ud7af]/.test(text||"");}
  function isChinese(text){return /[\u4e00-\u9fff]/.test(text||"");}
  async function text(value){
    if(!hasForeign(value)||isChinese(value))return value;
    const key="ai-brief-translation-v1:"+value;
    try{const cached=localStorage.getItem(key);if(cached)return cached;}catch(e){}
    if(!navigator.onLine)throw Error("当前离线，尚无这条新闻的中文缓存。联网后重试。");
    let result=[];
    for(const part of chunks(value)){
      const control=new AbortController(),timer=setTimeout(()=>control.abort(),15000);
      try{
        const url="https://api.mymemory.translated.net/get?"+new URLSearchParams({q:part,langpair:language(value)+"|zh-CN"});
        const response=await fetch(url,{signal:control.signal,credentials:"omit",referrerPolicy:"no-referrer"});
        if(!response.ok)throw Error("翻译服务暂时不可用，请稍后重试。");
        const data=await response.json(),translated=data.responseData?.translatedText;
        if(Number(data.responseStatus)!==200||data.quotaFinished||!translated||!isChinese(translated))throw Error("翻译服务繁忙或额度已用完，请稍后重试。");
        const el=document.createElement("textarea");el.innerHTML=translated;result.push(el.value);
      }finally{clearTimeout(timer);}
    }
    const translated=result.join("");try{localStorage.setItem(key,translated);}catch(e){}return translated;
  }
  async function article(item){
    if(item.zh?.title&&item.zh?.summary)return item.zh;
    return {title:await text(item.title),summary:await text(item.summary)};
  }
  root.AIBriefTranslate={chunks,language,hasForeign,text,article};
})(window);

