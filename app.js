
let issue=null, sourceConfig=null, archiveIndex=[], health=null, sourceHealth=null, basePrefs=null, weekly=null, learningCfg=null, signals=null, syncCfg=null;
let todayNews=null;
const translationStates=new Map();
let activeFilter="全部";
let searchText="";
let readingMode=localStorage.getItem("ai-brief-mode")||"10min";
let personalize=localStorage.getItem("ai-brief-personalize")!=="false";

const saved=new Set(JSON.parse(localStorage.getItem("ai-brief-saved")||"[]"));
const hidden=new Set(JSON.parse(localStorage.getItem("ai-brief-hidden")||"[]"));
const readSet=new Set(JSON.parse(localStorage.getItem("ai-brief-read")||"[]"));

function blankProfile(){
  return {version:1,interactions:0,categories:{},sources:{},keywords:{},updated_at:null};
}
function getProfile(){
  try{
    const p=JSON.parse(localStorage.getItem("ai-brief-learning")||"null");
    return p&&typeof p==="object"?p:blankProfile();
  }catch(e){return blankProfile()}
}
function saveProfile(p){
  p.updated_at=new Date().toISOString();
  localStorage.setItem("ai-brief-learning",JSON.stringify(p));
  try{window.AIBriefSync.touchBlob("learning",p)}catch(e){}
}
function clamp(n,lo,hi){return Math.max(lo,Math.min(hi,n))}
function esc(s){return String(s??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[m]))}

async function loadJSON(path){
  const r=await fetch(path,{cache:"no-store"});
  if(!r.ok) throw new Error(path);
  return await r.json();
}
async function loadIssue(){
  const path=readingMode==="5min"?"./data/latest_5min.json":"./data/latest_10min.json";
  try{return await loadJSON(path)}catch(e){return await loadJSON("./data/latest.json")}
}
async function boot(){
  try{
    [issue,sourceConfig,archiveIndex,basePrefs,learningCfg] = await Promise.all([
      loadIssue(),
      loadJSON("./config/sources.json"),
      loadJSON("./data/archive/index.json"),
      loadJSON("./config/preferences.json"),
      loadJSON("./config/learning.json")
    ]);
    try{todayNews=await loadJSON("./data/today.json")}catch(e){todayNews=null}
    try{health=await loadJSON("./data/health.json")}catch(e){health=null}
    try{weekly=await loadJSON("./data/weekly.json")}catch(e){weekly=null}
    try{sourceHealth=await loadJSON("./data/source_health.json")}catch(e){sourceHealth=null}
    try{signals=await loadJSON("./data/signals.json")}catch(e){signals=null}
    try{syncCfg=await window.AIBriefSync.init()}catch(e){syncCfg={enabled:false}}
    await reloadPersonalState();
    renderAll();
  }catch(e){
    document.querySelector("main").innerHTML=`<div class="empty">直接双击 HTML 时，浏览器可能阻止读取日报数据。<br><br>Windows 用户请双击项目里的 <b>启动日报.bat</b>。</div>`;
  }
}

function fmtDate(d){
  const x=new Date(d+"T00:00:00+08:00");
  return `${x.getFullYear()} 年 ${x.getMonth()+1} 月 ${x.getDate()} 日`;
}
function badgeClass(s){return ["必看","必须处理","建议看","重点","建议试用","报名提醒","今晚截止"].includes(s)?"badge hot":"badge"}

function tokenize(text){
  const stop=new Set((learningCfg?.keyword_learning?.stopwords||[]).map(x=>x.toLowerCase()));
  const out=[];
  const zh=(text.match(/[\u4e00-\u9fff]{2,8}/g)||[]);
  const en=(text.toLowerCase().match(/[a-z][a-z0-9\-]{2,}/g)||[]);
  for(const t of [...zh,...en]){
    const v=t.trim().toLowerCase();
    if(!stop.has(v) && v.length>1) out.push(v);
  }
  return [...new Set(out)].slice(0,12);
}
function interactionWeight(kind){
  return learningCfg?.interaction_weights?.[kind] ?? 0;
}
function learnFrom(item,kind){
  const w=interactionWeight(kind);
  if(!w) return;
  const p=getProfile();
  p.interactions=(p.interactions||0)+1;
  const cat=item.category||"未分类";
  const src=item.source||"未知来源";
  const cl=learningCfg?.score_limits?.category||[-20,20];
  const sl=learningCfg?.score_limits?.source||[-15,15];
  const kl=learningCfg?.score_limits?.keyword||[-12,12];
  p.categories[cat]=clamp((p.categories[cat]||0)+w,cl[0],cl[1]);
  p.sources[src]=clamp((p.sources[src]||0)+w*.75,sl[0],sl[1]);
  tokenize([item.title,item.summary,item.why].join(" ")).forEach(k=>{
    p.keywords[k]=clamp((p.keywords[k]||0)+w*.35,kl[0],kl[1]);
  });
  const maxK=learningCfg?.keyword_learning?.max_keywords||80;
  const entries=Object.entries(p.keywords).sort((a,b)=>Math.abs(b[1])-Math.abs(a[1])).slice(0,maxK);
  p.keywords=Object.fromEntries(entries);
  saveProfile(p);
  try{window.AIBriefSync.touchBlob('learning',p)}catch(e){}
}
function personalBoost(item){
  if(!personalize) return 0;
  const p=getProfile();
  let s=(p.categories[item.category||""]||0)+(p.sources[item.source||""]||0);
  for(const k of tokenize([item.title,item.summary,item.why].join(" "))) s+=(p.keywords[k]||0);
  return s;
}
function withPersonalScore(item){
  return {...item,_personalBoost:personalBoost(item),_displayScore:(item.score||0)+personalBoost(item)};
}
function sortPersonal(items){
  const arr=items.map(withPersonalScore);
  if(!personalize) return arr;
  return arr.sort((a,b)=>(b._displayScore||0)-(a._displayScore||0));
}
function saveToggle(item){
  const id=item.id;
  if(saved.has(id)){
    saved.delete(id);
  }else{
    saved.add(id);
    learnFrom(item,"save");
  }
  localStorage.setItem("ai-brief-saved",JSON.stringify([...saved]));
  try{window.AIBriefSync.touchSet("saved",id,saved.has(id))}catch(e){}
  renderAll();
}
function hideItem(item){
  hidden.add(item.id);
  localStorage.setItem("ai-brief-hidden",JSON.stringify([...hidden]));
  learnFrom(item,"hide");
  renderAll();
}
function clearHidden(){hidden.clear();localStorage.setItem("ai-brief-hidden","[]");renderAll()}
function markRead(item){
  if(!readSet.has(item.id)){
    readSet.add(item.id);
    localStorage.setItem("ai-brief-read",JSON.stringify([...readSet]));
    try{window.AIBriefSync.touchSet("read",item.id,true)}catch(e){}
    learnFrom(item,"open_source");
  }
}
function feedback(item,kind){
  learnFrom(item,kind);
  const key="ai-brief-feedback-"+item.id;
  localStorage.setItem(key,kind);
  renderAll();
}
function currentFeedback(id){return localStorage.getItem("ai-brief-feedback-"+id)||""}

function eventAvailable(x, now=new Date()){
  if(x.category!=="论坛 / 展会") return true;
  const parts=new Intl.DateTimeFormat("en",{timeZone:"Asia/Shanghai",year:"numeric",month:"2-digit",day:"2-digit"}).formatToParts(now);
  const get=t=>parts.find(p=>p.type===t).value;
  const today=`${get("year")}-${get("month")}-${get("day")}`;
  if(!/^\d{4}-\d{2}-\d{2}$/.test(x.event_date||"")||x.event_date<today) return false;
  if(x.deadline){
    let raw=x.deadline.replace("T24:00:00","T23:59:59");
    if(!/(Z|[+-]\d{2}:?\d{2})$/.test(raw)) raw+="+08:00";
    const end=new Date(raw);
    if(!Number.isFinite(end.getTime())||end<=now) return false;
  }
  return true;
}
function countdown(x){
  if(!x.deadline) return "";
  let raw=x.deadline.replace("T24:00:00","T23:59:59");
  const d=new Date(raw), now=new Date(), diff=d-now;
  if(diff<=0) return `<span class="deadline ended">已截止</span>`;
  const hours=Math.floor(diff/3600000), mins=Math.floor((diff%3600000)/60000);
  if(hours<36) return `<span class="deadline">距截止约 ${hours} 小时 ${mins} 分</span>`;
  return `<span class="deadline">截止 ${d.toLocaleString("zh-CN",{month:"numeric",day:"numeric",hour:"2-digit",minute:"2-digit"})}</span>`;
}
function sourceLink(x){
  if(!x.url || x.url==="#") return "";
  return `<a class="source-link" href="${esc(x.url)}" target="_blank" rel="noopener" onclick='markRead(${esc(JSON.stringify(x))})'>原始来源 ↗</a>`;
}
function matchesSearch(x){
  if(!searchText) return true;
  const t=[x.title,x.summary,x.why,x.source,x.category,x.action].join(" ").toLowerCase();
  return t.includes(searchText.toLowerCase());
}
function actionChip(x){return x.action?`<span class="action-chip">${esc(x.action)}</span>`:""}
function altSources(x){
  if(!x.alternatives||!x.alternatives.length) return "";
  return `<details class="alts"><summary>同题其他来源 ${x.alternatives.length}</summary>${x.alternatives.map(a=>`<a href="${esc(a.url)}" target="_blank" rel="noopener">${esc(a.source)} ↗</a>`).join("")}</details>`;
}
function dateBadge(x){
  const label=x.date_label||x.published_at||"日期待确认";
  const cls=x.date_confidence==="unknown"?"date-unknown":"";
  return `<span class="${cls}">${esc(label)}</span>`;
}
function feedbackBar(x){
  const fb=currentFeedback(x.id);
  const j=esc(JSON.stringify(x));
  return `<div class="feedback-bar">
    <span>这条对你：</span>
    <button class="${fb==="useful"?"active":""}" onclick='feedback(${j},"useful")'>有用</button>
    <button class="${fb==="not_interested"?"active":""}" onclick='feedback(${j},"not_interested")'>没兴趣</button>
    ${translationLink(x)}
    ${personalize && Math.abs(x._personalBoost||0)>.5?`<span class="personal-note">为你调整 ${x._personalBoost>0?"+":""}${x._personalBoost.toFixed(1)}</span>`:""}
  </div>`;
}
function translationLink(x){
  if(!window.AIBriefTranslate.hasForeign([x.title,x.summary].join(" ")))return "";
  const state=translationStates.get(x.id)||{};
  return `<button class="translate-btn" ${state.loading?"disabled":""} aria-pressed="${!!state.show}" onclick='toggleTranslation(${esc(JSON.stringify(x))})'>${state.loading?"翻译中…":state.show?"显示原文":"翻译"}</button>`;
}
async function toggleTranslation(item){
  const state=translationStates.get(item.id)||{};
  if(state.loading)return;
  if(state.show){state.show=false;translationStates.set(item.id,state);renderAll();return;}
  if(state.zh){state.show=true;translationStates.set(item.id,state);renderAll();return;}
  state.loading=true;state.error="";translationStates.set(item.id,state);renderAll();
  try{state.zh=await window.AIBriefTranslate.article(item);state.show=true;}
  catch(e){state.error=e.name==="AbortError"?"翻译超时，请重试。":e.message;}
  finally{state.loading=false;renderAll();}
}
function chineseFocus(x){
  const value=x.why||"";
  if((value.match(/[A-Za-z]/g)||[]).length<=2*(value.match(/[\u4e00-\u9fff]/g)||[]).length)return value;
  return "中文关注重点暂未生成；具体变化请查看原文。";
}
function newsImage(x){
  if(!x.image||!/^https:\/\//i.test(x.image)) return "";
  return `<figure class="news-image"><img src="${esc(x.image)}" alt="${esc(x.title)} · 来源配图" loading="lazy" decoding="async" referrerpolicy="no-referrer" onerror="this.closest('figure').hidden=true"><figcaption>来源配图 · ${esc(x.source)}</figcaption></figure>`;
}
function card(raw){
  const x=withPersonalScore(raw);
  if(!eventAvailable(x)||hidden.has(x.id)||!matchesSearch(x)) return "";
  const translation=translationStates.get(x.id)||{};
  const shown=translation.show&&translation.zh?{...x,...translation.zh}:x;
  const read=readSet.has(x.id);
  const j=esc(JSON.stringify(x));
  return `<article class="card ${read?"is-read":""}" data-article-id="${esc(x.id)}">
    <div class="card-tools">
      <button class="save" onclick='saveToggle(${j})' title="收藏">${saved.has(x.id)?"★":"☆"}</button>
      <button class="hidebtn" onclick='hideItem(${j})' title="今天不看">×</button>
    </div>
    <div class="meta"><span class="${badgeClass(x.tier||x.status)}">${esc(x.tier||x.status||"")}</span><span>${esc(x.category||"")}</span>${x.resurfaced?'<span class="badge">重要更新</span>':""}${countdown(x)}</div>
    ${newsImage(x)}
    <h4>${esc(shown.title)}</h4>
    <div class="meta"><span>${esc(x.source)}</span>${dateBadge(x)}${x.location?`<span>${esc(x.location)}</span>`:""}</div>
    <div class="brief-parts">
      <div><b>发生了什么</b><p>${esc(shown.summary)}</p></div>
      <div><b>关注重点</b><p>${esc(chineseFocus(x))}</p></div>
    </div>
    ${altSources(x)}
    ${feedbackBar(x)}
    ${translation.error?`<p class="translation-error" role="status">${esc(translation.error)}</p>`:""}
    <div class="card-foot">${actionChip(x)}${sourceLink(x)}</div>
  </article>`;
}
function allItems(){return [...issue.top3,...issue.sections.flatMap(s=>s.items.map(x=>({...x,category:x.category||s.name})))];}

function renderMode(){
  document.getElementById("mode5").classList.toggle("active",readingMode==="5min");
  document.getElementById("mode10").classList.toggle("active",readingMode==="10min");
  document.getElementById("personalizeBtn").classList.toggle("active",personalize);
  document.getElementById("personalizeBtn").textContent=personalize?"为你排序 ✓":"为你排序";
}
async function setMode(mode){
  readingMode=mode; localStorage.setItem("ai-brief-mode",mode);
  try{window.AIBriefSync.touchBlob("mode",mode)}catch(e){}
  issue=await loadIssue(); renderAll();
}
function togglePersonalize(){
  personalize=!personalize;
  localStorage.setItem("ai-brief-personalize",String(personalize));
  try{window.AIBriefSync.touchBlob("personalize",personalize)}catch(e){}
  renderAll();
}
function renderHealth(){
  const el=document.getElementById("healthPill");
  if(!el) return;
  if(!health){el.textContent="未读取到更新状态";el.className="health-pill warn";return}
  const ok=health.status==="ok" && Number(health.candidate_count)>0;
  el.className="health-pill "+(ok?"ok":"warn");
  el.textContent=ok
    ? `已更新 · ${health.candidate_count||0} 条高质量候选 · ${health.error_count||0} 个源失败`
    : `更新降级 · 已保留上一期`;
}
function renderToday(){
  document.getElementById("issueDate").textContent=fmtDate(issue.date);
  document.getElementById("edition").textContent=issue.edition;
  document.getElementById("readTime").textContent=`约 ${issue.reading_minutes} 分钟读完`;
  const parts=new Intl.DateTimeFormat("en",{timeZone:"Asia/Shanghai",year:"numeric",month:"2-digit",day:"2-digit"}).formatToParts(new Date());
  const get=t=>parts.find(p=>p.type===t).value,today=`${get("year")}-${get("month")}-${get("day")}`;
  const candidates=todayNews?.date===today?todayNews.items:allItems();
  const published=[...new Map(candidates.filter(x=>x.published_at===today&&["high","medium"].includes(x.date_confidence)&&!/^(Community Articles|Research Overview|Research|Explore models|Skip to main content|Global Affairs)$/i.test(x.title.trim())&&eventAvailable(x)).map(x=>[x.id,x])).values()];
  document.getElementById("headline").textContent=published.length?`今日发布 · ${published.length} 条消息`:"暂未收录今日发布的消息";
  document.getElementById("note").textContent="按上海日期统计，只计入发布日期已确认的消息。";
  document.getElementById("todayMessages").innerHTML=published.map(x=>`<a href="${esc(x.url)}" target="_blank" rel="noopener"><span>${esc(x.zh?.title||x.title)}</span><small>${esc(x.source)} · ${esc(x.published_at)}</small></a>`).join("");
  document.getElementById("updateStamp").textContent="数据日期 "+issue.date;

  const topItems=sortPersonal(issue.top3);
  const topHtml=topItems.map(x=>card(x)).join("");
  document.getElementById("top3").innerHTML=topHtml||`<div class="empty">当前条件下没有头版内容。</div>`;

  const cats=["全部",...issue.sections.map(s=>s.name)];
  document.getElementById("filters").innerHTML=cats.map(c=>`<button class="${c===activeFilter?"active":""}" onclick="setFilter('${c}')">${c}</button>`).join("");
  const secs=issue.sections.filter(s=>activeFilter==="全部"||s.name===activeFilter);
  document.getElementById("sections").innerHTML=secs.map(s=>{
    const items=sortPersonal(s.items.map(x=>({...x,category:x.category||s.name})));
    const content=items.map(x=>card(x)).join("");
    return `<section class="section-block">
      <div class="section-head"><span>${s.icon}</span><h3>${esc(s.name)}</h3><span class="meta">${s.items.length} 条</span></div>
      <div class="item-list">${content||`<div class="empty">今天这个栏目没有需要你花时间看的内容。</div>`}</div>
    </section>`;
  }).join("");
}
function setFilter(c){activeFilter=c;renderToday()}
function renderEvents(){
  const sec=issue.sections.find(s=>s.name==="论坛 / 展会");
  let arr=[...issue.top3.filter(x=>x.category==="论坛 / 展会"),...(sec?sec.items:[])];
  arr=sortPersonal(arr.filter(x=>eventAvailable({...x,category:"论坛 / 展会"}))).sort((a,b)=>{
    const preferred=basePrefs?.event_cities||["上海","杭州"];
    const localA=preferred.includes(a.location),localB=preferred.includes(b.location);
    if(localA!==localB)return localA?-1:1;
    if(a.deadline&&b.deadline) return String(a.deadline).localeCompare(String(b.deadline));
    if(a.deadline) return -1;if(b.deadline) return 1;
    return (a.event_date||"9999").localeCompare(b.event_date||"9999");
  });
  document.getElementById("eventCards").innerHTML=arr.map(x=>card({...x,category:"论坛 / 展会"})).join("")||`<div class="empty">当前没有值得提醒的活动。</div>`;
}
function renderSaved(){
  const arr=sortPersonal(allItems().filter(x=>saved.has(x.id)));
  document.getElementById("savedCards").innerHTML=arr.map(x=>card(x)).join("")||`<div class="empty">还没有收藏。</div>`;
}
function renderArchive(){
  document.getElementById("archiveList").innerHTML=archiveIndex.map(x=>{
    const link=x.html?`<a class="source-link" href="${esc(x.html)}" target="_blank">独立日报 ↗</a>`:"";
    return `<div class="archive-row"><b>${esc(x.date)}</b> · ${esc(x.edition)}<br><span class="meta">${esc(x.title)}</span><br>${link}</div>`;
  }).join("");
}
function renderSources(){
  document.getElementById("sourceList").innerHTML=sourceConfig.sources.map(x=>`<div class="source">
    <div><a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.name)}</a><br><span class="meta">${esc(x.category.join(" · "))}</span></div>
    <div>${esc(x.region)}</div><div class="meta">${esc(x.type)} · P${x.priority}</div>
  </div>`).join("");
}
function renderSourceHealth(){
  const summary=document.getElementById("sourceHealthSummary"), list=document.getElementById("sourceHealthList");
  if(!sourceHealth||!sourceHealth.sources){summary.innerHTML="";list.innerHTML=`<div class="empty">首次自动更新后会显示每个来源的抓取健康状态。</div>`;return}
  const rows=sourceHealth.sources;
  const ok=rows.filter(x=>x.status==="ok").length,bad=rows.length-ok,zero=rows.filter(x=>x.status==="ok"&&!x.candidate_count).length;
  summary.innerHTML=`<div><b>${ok}</b><span>正常</span></div><div><b>${bad}</b><span>失败</span></div><div><b>${zero}</b><span>本次无候选</span></div>`;
  list.innerHTML=rows.map(x=>`<div class="source-health-row">
    <div><b>${esc(x.source)}</b><br><span class="meta">${x.candidate_count||0} 条候选 · ${x.elapsed_ms||0} ms</span></div>
    <div class="${x.status==="ok"?"status-ok":"status-bad"}">${x.status==="ok"?"正常":"失败"}</div>
    <div class="meta">${esc(x.error||"")}</div>
  </div>`).join("");
}
function renderWeekly(){
  const el=document.getElementById("weeklyCards");
  if(!weekly||!weekly.items||!weekly.items.length){el.innerHTML=`<div class="empty">积累几天日报后，这里会自动生成一周回顾。</div>`;return}
  const items=sortPersonal(weekly.items);
  el.innerHTML=`<div class="weekly-intro">${esc(weekly.headline||"")}</div>`+items.map(x=>card(x)).join("");
}
function rankEntries(obj,limit=8){
  return Object.entries(obj||{}).sort((a,b)=>b[1]-a[1]).slice(0,limit);
}
function renderLearning(){
  const p=getProfile();
  const stats=document.getElementById("learningStats");
  const profile=document.getElementById("learningProfile");
  stats.innerHTML=`
    <div><b>${p.interactions||0}</b><span>次学习信号</span></div>
    <div><b>${Object.keys(p.categories||{}).length}</b><span>个已学习栏目</span></div>
    <div><b>${Object.keys(p.sources||{}).length}</b><span>个已学习来源</span></div>
    <div><b>${Object.keys(p.keywords||{}).length}</b><span>个关键词</span></div>`;

  const cats=rankEntries(p.categories,8);
  const srcs=rankEntries(p.sources,8);
  const kws=rankEntries(p.keywords,12);
  const bars=(arr,empty)=>arr.length?arr.map(([name,v])=>`
    <div class="learn-row"><span>${esc(name)}</span><div class="learn-track"><i style="width:${Math.min(100,Math.abs(v)*5)}%" class="${v<0?"neg":""}"></i></div><b>${v>0?"+":""}${v.toFixed(1)}</b></div>`).join(""):`<div class="empty small">${empty}</div>`;

  profile.innerHTML=`
    <div class="learning-columns">
      <section class="learn-card"><h3>栏目倾向</h3>${bars(cats,"还没学到栏目偏好。")}</section>
      <section class="learn-card"><h3>来源倾向</h3>${bars(srcs,"还没学到来源偏好。")}</section>
      <section class="learn-card"><h3>关键词倾向</h3>${bars(kws,"点几次“有用 / 没兴趣”后会出现。")}</section>
    </div>
    <p class="privacy-note">隐私：学习数据默认保存在当前设备；启用并登录云同步后会同步到你的账号。</p>`;
}
function exportProfile(){
  const blob=new Blob([JSON.stringify(getProfile(),null,2)],{type:"application/json"});
  const a=document.createElement("a");a.href=URL.createObjectURL(blob);a.download="AI前沿日报_我的偏好.json";a.click();URL.revokeObjectURL(a.href);
}
function importProfile(file){
  const r=new FileReader();
  r.onload=()=>{
    try{
      const p=JSON.parse(r.result);
      if(!p||typeof p!=="object") throw new Error();
      const merged={...blankProfile(),...p}; saveProfile(merged); try{window.AIBriefSync.touchBlob("learning",merged)}catch(e){}
      renderAll();
    }catch(e){alert("偏好文件无法读取。")}
  };
  r.readAsText(file);
}
function resetLearning(){
  if(!confirm("确定重置日报对你的学习结果吗？收藏不会删除。")) return;
  saveProfile(blankProfile());
  for(const k of Object.keys(localStorage)){
    if(k.startsWith("ai-brief-feedback-")) localStorage.removeItem(k);
  }
  renderAll();
}
function getLocalPrefs(){return JSON.parse(localStorage.getItem("ai-brief-ui-prefs")||"{}")}
function setUIPref(key,value){const p=getLocalPrefs();p[key]=value;localStorage.setItem("ai-brief-ui-prefs",JSON.stringify(p));try{window.AIBriefSync.touchBlob("ui_prefs",p)}catch(e){}applyUIPrefs();renderSettings()}
function applyUIPrefs(){
  const p=getLocalPrefs();
  document.body.classList.toggle("compact",!!p.compact);
  document.body.classList.toggle("large-type",!!p.largeType);
  document.body.classList.toggle("dark",!!p.dark);
  document.body.classList.toggle("dim-read",p.dimRead!==false);
}
function renderSettings(){
  const p=getLocalPrefs();
  document.getElementById("settingsPanel").innerHTML=`
    <div class="setting-card"><h3>阅读模式</h3>
      <label><input type="checkbox" ${p.compact?"checked":""} onchange="setUIPref('compact',this.checked)"> 紧凑模式</label>
      <label><input type="checkbox" ${p.largeType?"checked":""} onchange="setUIPref('largeType',this.checked)"> 大字号</label>
      <label><input type="checkbox" ${p.dark?"checked":""} onchange="setUIPref('dark',this.checked)"> 深色模式</label>
      <label><input type="checkbox" ${p.dimRead!==false?"checked":""} onchange="setUIPref('dimRead',this.checked)"> 淡化已读条目</label>
    </div>
    <div class="setting-card"><h3>今日过滤</h3>
      <p>你点过“×”的条目只会在今天隐藏。</p>
      <button class="ghost" onclick="clearHidden()">恢复所有隐藏条目</button>
    </div>
    <div class="setting-card"><h3>个性化排序</h3>
      <p>“为你排序”开启后，只改变同一期日报里的先后顺序，不会偷偷把官方抓取结果删除。</p>
      <p>学习数据默认只存在当前浏览器。</p>
    </div>`;
}
function copyBrief(){
  let lines=[`AI 前沿日报｜${issue.date}`,issue.headline,""];
  sortPersonal(issue.top3).forEach((x,i)=>{
    lines.push(`${i+1}. ${x.title}`);
    lines.push(`发生了什么：${x.summary}`);
    lines.push(`关注重点：${x.why}`);
    if(x.action) lines.push(`建议：${x.action}`);
    if(x.url) lines.push(x.url);
    lines.push("");
  });
  navigator.clipboard.writeText(lines.join("\n")).then(()=>{
    const b=document.getElementById("copyBtn");const old=b.textContent;b.textContent="已复制";setTimeout(()=>b.textContent=old,1200);
  }).catch(()=>{});
}

function getWatchlist(){
  try{return JSON.parse(localStorage.getItem("ai-brief-watchlist")||"[]")}catch(e){return []}
}
function saveWatchlist(arr){
  const next=[...new Set(arr.map(x=>x.trim()).filter(Boolean))].slice(0,30);
  const prev=getWatchlist();
  localStorage.setItem("ai-brief-watchlist",JSON.stringify(next));
  try{
    const p=new Set(prev), n=new Set(next);
    for(const v of new Set([...p,...n])) window.AIBriefSync.touchSet("watchlist",v,n.has(v));
  }catch(e){}
}
function addWatch(){
  const input=document.getElementById("watchInput");
  const v=(input.value||"").trim();
  if(!v) return;
  const arr=getWatchlist(); arr.push(v); saveWatchlist(arr); input.value=""; renderSignals();
}
function removeWatch(v){
  saveWatchlist(getWatchlist().filter(x=>x!==v)); renderSignals();
}
function watchMatches(){
  const keys=getWatchlist();
  if(!keys.length) return [];
  const rows=allItems();
  const out=[];
  for(const x of rows){
    const t=[x.title,x.summary,x.why,x.source,x.category].join(" ").toLowerCase();
    const matched=keys.filter(k=>t.includes(k.toLowerCase()));
    if(matched.length) out.push({...x,_watchMatched:matched});
  }
  return out;
}
function renderSignals(){
  const urgentEl=document.getElementById("urgentSignals");
  const statusEl=document.getElementById("trendStatus");
  const topicsEl=document.getElementById("trendTopics");
  const tagsEl=document.getElementById("watchTags");
  const matchesEl=document.getElementById("watchMatches");

  const urgent=(signals?.urgent||[]).filter(x=>new Date(x.deadline)>new Date() && eventAvailable({...x,event_date:x.event_date||allItems().find(i=>i.id===x.id)?.event_date}));
  if(urgent.length){
    urgentEl.innerHTML=`<div class="urgent-box"><div class="kicker">URGENT</div><h3>今天需要处理</h3>${urgent.map(x=>`
      <div class="urgent-row"><div><b>${esc(x.title)}</b><br><span class="meta">${esc(x.source)} · 约 ${x.hours_left} 小时后截止</span></div>
      <a class="source-link" href="${esc(x.url)}" target="_blank">去看 ↗</a></div>`).join("")}</div>`;
  }else{
    urgentEl.innerHTML="";
  }

  if(!signals){
    statusEl.innerHTML=`<div class="empty">还没有趋势数据。</div>`; topicsEl.innerHTML="";
  }else if(!signals.enough_history){
    statusEl.innerHTML=`<div class="trend-wait"><b>趋势样本积累中</b><p>${esc(signals.message)}</p>
      <div class="sample-meter"><i style="width:${Math.min(100,(signals.history_days/signals.minimum_days_needed)*100)}%"></i></div>
      <span>${signals.history_days} / ${signals.minimum_days_needed} 天</span></div>`;
    topicsEl.innerHTML="";
  }else{
    statusEl.innerHTML=`<div class="trend-note">${esc(signals.message)}</div>`;
    const topics=signals.topics||[];
    topicsEl.innerHTML=topics.length?`<div class="trend-grid">${topics.map(x=>`
      <article class="trend-card">
        <div class="trend-head"><h3>${esc(x.topic)}</h3><span class="trend-dir ${x.direction==="升温"?"up":x.direction==="降温"?"down":""}">${esc(x.direction)}</span></div>
        <div class="trend-strength"><i style="width:${x.strength}%"></i></div>
        <div class="trend-metrics">
          <span><b>${x.mentions}</b> 次出现</span>
          <span><b>${x.unique_days}</b> 天</span>
          <span><b>${x.sources}</b> 个来源</span>
          <span>速度 ×${x.velocity_ratio}</span>
        </div>
      </article>`).join("")}</div>`:`<div class="empty">最近没有达到“趋势”阈值的主题。</div>`;
  }

  const watch=getWatchlist();
  tagsEl.innerHTML=watch.length?watch.map(v=>`<span class="watch-tag">${esc(v)} <button onclick='removeWatch(${esc(JSON.stringify(v))})'>×</button></span>`).join(""):`<span class="meta">还没有观察词。</span>`;
  const matches=watchMatches();
  matchesEl.innerHTML=matches.length?`<div class="watch-match-head">今天命中 ${matches.length} 条</div>`+
    matches.map(x=>`<div class="watch-match"><div><b>${esc(x.title)}</b><br><span class="meta">命中：${x._watchMatched.map(esc).join(" · ")}</span></div>${sourceLink(x)}</div>`).join("")
    : (watch.length?`<div class="empty small">今天没有命中你的观察词。</div>`:"");
}


async function renderSync(){
  const status=document.getElementById("syncStatus");
  const auth=document.getElementById("syncAuth");
  const details=document.getElementById("syncDetails");
  if(!status||!auth||!details) return;

  const cfg=syncCfg||{enabled:false};
  const sess=window.AIBriefSync?.session?.();

  if(!cfg.enabled){
    status.innerHTML=`<div class="sync-card warn"><b>云同步尚未启用</b><p>当前所有收藏、已读、观察词和学习偏好都只保存在本机。项目已经把同步层搭好，配置 Supabase 后即可启用。</p></div>`;
    auth.innerHTML="";
    details.innerHTML=`<div class="sync-card"><h3>已经准备好的部分</h3>
      <p>离线优先、本地数据不丢失、冲突合并、跨设备收藏/已读/观察词/学习偏好同步、断网回退。</p>
      <p class="meta">配置文件：<code>config/sync.json</code> · 数据库脚本：<code>db/supabase_schema.sql</code></p></div>`;
    return;
  }

  status.innerHTML=`<div class="sync-card ok"><b>云同步已配置</b><p>${sess?.user?.email?`当前账号：${esc(sess.user.email)}`:"尚未登录"}</p></div>`;

  if(!sess?.access_token){
    auth.innerHTML=`<div class="sync-auth-grid">
      <div class="sync-card"><h3>登录</h3><input id="syncLoginEmail" type="email" placeholder="邮箱"><input id="syncLoginPass" type="password" placeholder="密码">
        <button id="syncLoginBtn" class="ghost">登录并同步</button></div>
      <div class="sync-card"><h3>首次使用</h3><input id="syncSignupEmail" type="email" placeholder="邮箱"><input id="syncSignupPass" type="password" placeholder="密码（至少6位）">
        <button id="syncSignupBtn" class="ghost">创建同步账号</button></div>
    </div>`;
    details.innerHTML=`<div class="sync-card"><p>账号只用于同步你的日报偏好数据。日报正文和抓取内容仍然是公开静态数据。</p></div>`;
    setTimeout(()=>{
      const lb=document.getElementById("syncLoginBtn"), sb=document.getElementById("syncSignupBtn");
      if(lb) lb.onclick=syncLogin;
      if(sb) sb.onclick=syncSignup;
    },0);
  }else{
    auth.innerHTML="";
    details.innerHTML=`<div class="sync-card"><h3>同步控制</h3>
      <div class="sync-actions"><button id="syncNowBtn" class="ghost">立即同步</button><button id="syncLogoutBtn" class="ghost">退出同步账号</button></div>
      <div id="syncResult" class="meta">自动同步：${cfg.autoSync?"开启":"关闭"} · 本地设备ID：${esc(localStorage.getItem("ai-brief-device-id")||"")}</div>
      <p class="meta">同步失败时不会覆盖本地数据；恢复网络后可再次同步。</p></div>`;
    setTimeout(()=>{
      document.getElementById("syncNowBtn").onclick=syncNow;
      document.getElementById("syncLogoutBtn").onclick=()=>{window.AIBriefSync.signOut();renderSync()};
    },0);
  }
}
async function syncLogin(){
  const email=document.getElementById("syncLoginEmail").value.trim();
  const password=document.getElementById("syncLoginPass").value;
  const btn=document.getElementById("syncLoginBtn");
  btn.disabled=true;btn.textContent="登录中…";
  try{
    await window.AIBriefSync.signIn(syncCfg,email,password);
    await window.AIBriefSync.syncNow();
    location.reload();
  }catch(e){
    btn.disabled=false;btn.textContent="登录并同步";alert(e.message||"登录失败");
  }
}
async function syncSignup(){
  const email=document.getElementById("syncSignupEmail").value.trim();
  const password=document.getElementById("syncSignupPass").value;
  const btn=document.getElementById("syncSignupBtn");
  btn.disabled=true;btn.textContent="创建中…";
  try{
    const data=await window.AIBriefSync.signUp(syncCfg,email,password);
    if(data.access_token){await window.AIBriefSync.syncNow();location.reload()}
    else{btn.disabled=false;btn.textContent="创建同步账号";alert("账号已创建。若项目要求邮箱确认，请先完成邮箱确认后再登录。")}
  }catch(e){
    btn.disabled=false;btn.textContent="创建同步账号";alert(e.message||"注册失败");
  }
}
async function syncNow(){
  const el=document.getElementById("syncResult");
  if(el) el.textContent="正在同步…";
  try{
    await window.AIBriefSync.syncNow();
    if(el) el.textContent="同步完成："+new Date().toLocaleTimeString("zh-CN");
    setTimeout(()=>location.reload(),500);
  }catch(e){
    if(el) el.textContent="同步失败："+(e.message||"未知错误")+"；本地数据未受影响。";
  }
}
async function reloadPersonalState(){
  saved.clear();readSet.clear();hidden.clear();
  for(const id of JSON.parse(localStorage.getItem("ai-brief-hidden")||"[]")) hidden.add(id);
  for(const id of JSON.parse(localStorage.getItem("ai-brief-saved")||"[]")) saved.add(id);
  for(const id of JSON.parse(localStorage.getItem("ai-brief-read")||"[]")) readSet.add(id);
  readingMode=localStorage.getItem("ai-brief-mode")||"10min";
  personalize=localStorage.getItem("ai-brief-personalize")!=="false";
  if(issue){issue=await loadIssue();renderAll()}
}
window.addEventListener("ai-brief-synced",()=>reloadPersonalState().catch(()=>{}));

function renderAll(){
  applyUIPrefs();renderMode();renderHealth();renderToday();renderEvents();renderSaved();
  renderArchive();renderSources();renderSourceHealth();renderWeekly();renderSignals();renderLearning();renderSettings();renderSync();
}

document.querySelectorAll(".tabs button").forEach(b=>b.onclick=()=>{
  document.querySelectorAll(".tabs button").forEach(x=>x.classList.remove("active"));b.classList.add("active");
  document.querySelectorAll(".view").forEach(v=>v.classList.remove("active"));
  document.getElementById(b.dataset.view+"View").classList.add("active");
});
document.getElementById("refreshBtn").onclick=()=>location.reload();
document.getElementById("printBtn").onclick=()=>window.print();
document.getElementById("copyBtn").onclick=copyBrief;
document.getElementById("mode5").onclick=()=>setMode("5min");
document.getElementById("mode10").onclick=()=>setMode("10min");
document.getElementById("personalizeBtn").onclick=togglePersonalize;
document.getElementById("exportProfileBtn").onclick=exportProfile;
document.getElementById("importProfileInput").addEventListener("change",e=>{if(e.target.files[0]) importProfile(e.target.files[0])});
document.getElementById("resetLearningBtn").onclick=resetLearning;
document.getElementById("searchInput").addEventListener("input",e=>{searchText=e.target.value.trim();renderToday();renderEvents();renderSaved();});
if("serviceWorker" in navigator){navigator.serviceWorker.register("./sw.js").catch(()=>{})}
boot();

document.getElementById("addWatchBtn").onclick=addWatch;
document.getElementById("watchInput").addEventListener("keydown",e=>{if(e.key==="Enter") addWatch();});

setInterval(()=>{if(issue){renderToday();renderEvents();renderSignals();}},60000);
window.addEventListener("focus",()=>{if(issue){renderToday();renderEvents();renderSignals();}});

