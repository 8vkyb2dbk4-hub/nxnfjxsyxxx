"""
AI 前沿日报 v6 - 长期稳定版

新增质量机制：
1. 不再把“抓不到发布日期”自动当成今天，避免旧闻伪装成新闻。
2. 识别 JSON-LD / time 标签 / meta 中的发布时间，并记录 date_confidence。
3. 标题模糊去重 + URL 规范化 + 同题聚类。
4. 跨日 seen history：最近看过的同一条，默认不重复推送。
5. 如果检测到“正式上线 / 新增 / 更新 / 延期 / 报名截止”等实质变化，可重新出现。
6. 软文词降权、低信息条目过滤。
7. 论坛日期校验，过去活动不再混进“未来活动”。
8. 每个来源记录健康状态，方便发现长期失效的信息源。
"""
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse, parse_qsl, urlencode
from difflib import SequenceMatcher
from concurrent.futures import ThreadPoolExecutor
import requests, json, re, hashlib, datetime, time, html, os, sys

try:
    from bs4 import BeautifulSoup
except Exception:
    BeautifulSoup = None

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"scripts"))
try:
    import summarizer
except Exception:
    summarizer = None
try:
    import trends as trend_engine
except Exception:
    trend_engine = None

TZ = datetime.timezone(datetime.timedelta(hours=8))
NOW = datetime.datetime.now(TZ)
TODAY = NOW.date()
UA = {"User-Agent":"Mozilla/5.0 (compatible; Creator-AI-Brief/6.0; personal reader)"}

CATEGORY_KWS = {
    "艺术":["craft","ceramic","textile","embroidery","weaving","sculpture","paper art","art magazine","手工","艺术刊物","陶艺","刺绣","编织","雕塑","版画","纸艺","纤维艺术"],
    "AI 绘画":["image","illustration","art","diffusion","flux","图像","绘画","美术","设计","视觉","reference image","upscale","角色一致性","参考图","局部编辑"],
    "AI 影视":["video","film","audio","voice","music","speech","dub","视频","影视","动画","语音","配音","音乐","音效","lip","镜头","首尾帧"],
    "游戏与 3D":["game","gaming","3d","unity","unreal","godot","npc","游戏","三维","建模","动作","贴图","关卡"],
    "Agent / 编程":["agent","coding","code","developer","mcp","workflow","automation","智能体","编程","代码","自动化","codex"],
    "论坛 / 展会":["forum","conference","workshop","event","registration","deadline","论坛","会议","讲座","活动","报名","征稿","大会","工作坊","展会","展览","特展","临展","公共教育"],
    "新模型 / 开源":["model","open source","release","benchmark","research","模型","开源","发布","论文","研究","multimodal","多模态"]
}
AI_KWS = ["AI","artificial intelligence","model","agent","LLM","multimodal","人工智能","大模型","模型","智能体","生成","多模态","开源"]
EVENT_KWS = ["报名","截止","论坛","会议","工作坊","讲座","大会","registration","deadline","conference","workshop"]

TRACKING_PARAMS = {
    "utm_source","utm_medium","utm_campaign","utm_term","utm_content",
    "gclid","fbclid","mc_cid","mc_eid","ref","source"
}

def jload(path, default):
    try: return json.loads(path.read_text(encoding="utf-8"))
    except Exception: return default

def clean(s):
    return re.sub(r"\s+"," ",(s or "")).strip()

def norm_title(s):
    s = clean(s).lower()
    s = re.sub(r"[【】\[\]（）()“”\"'‘’：:，,。.!！?？\-—_|/\\]", "", s)
    s = re.sub(r"\s+","",s)
    return s

def hid(s):
    return hashlib.sha1(s.encode("utf-8","ignore")).hexdigest()[:14]

def canonical_url(url):
    try:
        p = urlparse(url)
        pairs = [(k,v) for k,v in parse_qsl(p.query, keep_blank_values=True) if k.lower() not in TRACKING_PARAMS]
        path = re.sub(r"/+","/",p.path or "/")
        if path != "/" and path.endswith("/"): path = path[:-1]
        return urlunparse((p.scheme.lower(), p.netloc.lower(), path, "", urlencode(pairs), ""))
    except Exception:
        return url

def get(url, timeout=16):
    r=requests.get(url,headers=UA,timeout=timeout)
    r.raise_for_status()
    if r.encoding is None or r.encoding.lower() in ("iso-8859-1","ascii"):r.encoding=r.apparent_encoding
    return r

def product_match(text,word):
    word=word.lower();text=text.lower()
    if word.isascii():return bool(re.search(r"(?<![a-z0-9])"+re.escape(word)+r"(?![a-z0-9])",text))
    return word in text

def classify(text, hinted=None):
    t=text.lower(); scores={}
    if "论坛 / 展会" in (hinted or []) and any(k.lower() in t for k in EVENT_KWS):return "论坛 / 展会"
    focus=jload(ROOT/"config/preferences.json",{}).get("focus_products",{})
    for cat,words in focus.items():
        if any(product_match(t,k) for k in words):return cat
    for cat,kws in CATEGORY_KWS.items():
        scores[cat]=sum(1 for k in kws if k.lower() in t)
    for cat in hinted or []:
        if cat in scores: scores[cat]+=2
    return max(scores,key=scores.get) if max(scores.values() or [0])>0 else "新模型 / 开源"

def source_reliability(src):
    typ=src.get("type","")
    if any(k in typ for k in ["官方","高校","实验室","研究机构"]): return 10
    if any(k in typ for k in ["大会","学术会议","图形学大会"]): return 9
    if any(k in typ for k in ["开源社区","开发平台"]): return 8
    return 6

def parse_isoish(value):
    if not value: return None
    value = clean(str(value))
    m = re.search(r"(20\d{2})[-/年](\d{1,2})[-/月](\d{1,2})", value)
    if m:
        try: return datetime.date(int(m.group(1)),int(m.group(2)),int(m.group(3))).isoformat()
        except: pass
    m = re.search(r"(20\d{2})(\d{2})(\d{2})", value)
    if m:
        try: return datetime.date(int(m.group(1)),int(m.group(2)),int(m.group(3))).isoformat()
        except: pass
    return None

def article_meta(url):
    if BeautifulSoup is None:
        return {"desc":"","published":"","date_confidence":"unknown","body":""}
    try:
        r=get(url,14)
        soup=BeautifulSoup(r.text,"html.parser")
        image=""
        for attrs in ({"property":"og:image"},{"name":"twitter:image"}):
            tag=soup.find("meta",attrs=attrs)
            if tag and tag.get("content"):
                candidate=urljoin(url,tag["content"])
                if urlparse(candidate).scheme=="https": image=candidate; break
        desc=""
        for attrs in ({"name":"description"},{"property":"og:description"},{"name":"twitter:description"}):
            m=soup.find("meta",attrs=attrs)
            if m and m.get("content"):
                desc=clean(m["content"]); break
        if len(desc)<35:
            paras=[clean(p.get_text(" ",strip=True)) for p in soup.find_all("p")]
            paras=[p for p in paras if 40<=len(p)<=500]
            if paras: desc=paras[0]

        published=""
        confidence="unknown"

        # 1) JSON-LD
        for s in soup.find_all("script", type="application/ld+json"):
            raw=s.string or s.get_text()
            if not raw: continue
            try:
                obj=json.loads(raw)
                objs=obj if isinstance(obj,list) else [obj]
                stack=list(objs)
                while stack:
                    cur=stack.pop()
                    if isinstance(cur,dict):
                        for key in ("datePublished","uploadDate"):
                            if cur.get(key):
                                d=parse_isoish(cur.get(key))
                                if d:
                                    published=d; confidence="high"; break
                        if published: break
                        stack.extend(v for v in cur.values() if isinstance(v,(dict,list)))
                    elif isinstance(cur,list):
                        stack.extend(cur)
                if published: break
            except Exception:
                pass

        # 2) meta
        if not published:
            for attrs in (
                {"property":"article:published_time"},
                {"name":"date"},
                {"name":"publishdate"},
                {"name":"pubdate"},
                {"itemprop":"datePublished"}
            ):
                m=soup.find("meta",attrs=attrs)
                if m and m.get("content"):
                    d=parse_isoish(m.get("content"))
                    if d:
                        published=d; confidence="high"; break

        # 3) time tag
        if not published:
            for t in soup.find_all("time"):
                d=parse_isoish(t.get("datetime") or t.get_text(" ",strip=True))
                if d:
                    published=d; confidence="medium"; break

        # 4) visible page text near common labels
        body=clean(soup.get_text(" ",strip=True))[:18000]
        if not published:
            m=re.search(r"(?:发布时间|发布日期|发布于)[：:\s]*(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})", body)
            if m:
                try:
                    published=datetime.date(int(m.group(1)),int(m.group(2)),int(m.group(3))).isoformat()
                    confidence="medium"
                except: pass

        return {"desc":desc[:500],"published":published,"date_confidence":confidence,"body":body,"image":image,"headings":[clean(h.get_text(" ",strip=True)) for h in soup.find_all(["h1","h2"])]}
    except Exception:
        return {"desc":"","published":"","date_confidence":"unknown","body":""}

def score_item(title, desc, src, cat, prefs, quality, date_confidence):
    text=(title+" "+desc).lower()
    s=src.get("category_priorities",{}).get(cat,src.get("priority",3))*9 + source_reliability(src)*2
    s+=prefs.get("category_weights",{}).get(cat,5)*3
    if src.get("name") in prefs.get("must_watch_sources",[]): s+=16

    if cat=="AI 影视":
        rule=prefs.get("video_keyword_boost",{})
        hits=sum(any(alias.lower() in text for alias in aliases) for aliases in rule.get("concepts",{}).values())
        s+=min(hits*rule.get("per_concept",8),rule.get("max_boost",40))
    focus=prefs.get("focus_products",{}).get(cat,[])
    if any(product_match(text,k) for k in focus):s+=24
    for kw in prefs.get("boost_keywords",[]):
        if kw.lower() in text: s+=6
    for kw in prefs.get("downrank_keywords",[]):
        if kw.lower() in text: s-=8
    for kw in quality.get("promotion_downrank_keywords",[]):
        if kw.lower() in text: s-=12

    s+=min(sum(1 for k in AI_KWS if k.lower() in text)*2,12)
    if cat=="论坛 / 展会":
        if any(product_match(text,k) for k in prefs.get("game_event_keywords",[])):s+=18
        s+=min(sum(1 for k in EVENT_KWS if k.lower() in text)*3,15)
        for city in prefs.get("event_cities",[]):
            if city.lower() in text: s+=12

    if date_confidence=="unknown":
        s-=quality.get("unknown_date_policy",{}).get("score_penalty",18)
    return s

def list_links(src):
    if src.get("collector")=="x_api":
        from x_updates import fetch
        return fetch(src)
    if src.get("collector")=="single_article":
        return [{"title":src["name"],"url":src["url"]}]
    if BeautifulSoup is None: return []
    r=get(src["url"])
    soup=BeautifulSoup(r.text,"html.parser")
    if src.get("collector")=="sniec":
        rows=[]
        for heading in soup.find_all(["h4","h3"]):
            anchor=heading.find("a",href=True)
            if not anchor: continue
            node=heading
            for _ in range(4):
                node=node.parent
                if node is None:break
                match=re.search(r"(20\d{2}/\d{2}/\d{2})\s*-\s*(20\d{2}/\d{2}/\d{2})",node.get_text(" ",strip=True))
                if match:
                    rows.append({"title":clean(anchor.get_text(" ",strip=True)),"url":urljoin(src["url"],anchor["href"]),"event_date":match[1].replace("/","-"),"event_end_date":match[2].replace("/","-"),"location":"上海"});break
        return rows
    if src.get("collector")=="dated_changelog":
        from product_updates import parse_changelog
        return parse_changelog(soup,src)
    rows=[]
    for article_url in src.get("wechat_article_urls",[]):
        if urlparse(article_url).netloc=="mp.weixin.qq.com":
            rows.append({"title":src["name"]+" · 公众号公开活动通知","url":article_url})
    trigger = AI_KWS + EVENT_KWS + sum(CATEGORY_KWS.values(),[]) + sum(jload(ROOT/"config/preferences.json",{}).get("focus_products",{}).values(),[])
    seen=set()
    for a in soup.find_all("a",href=True):
        title=clean(a.get_text(" ",strip=True))
        if not 8<=len(title)<=180: continue
        if not src.get("force_category") and not any(k.lower() in title.lower() for k in trigger): continue
        url=canonical_url(urljoin(src["url"],a["href"]))
        if urlparse(url).scheme not in ("http","https"): continue
        if src.get("article_url_pattern") and not re.search(src["article_url_pattern"],url): continue
        if src.get("force_category")=="艺术" and urlparse(url).netloc!=urlparse(src["url"]).netloc: continue
        k=url if src.get("force_category")=="艺术" else (norm_title(title),url)
        if k in seen: continue
        seen.add(k)
        rows.append({"title":title,"url":url,"listing_date":parse_isoish(title)})
    return rows[:70]

def extract_deadline(text):
    patterns=[
        r"报名截止(?:时间)?[：:\s]*(20\d{2})?[-/年]?(\d{1,2})[-/月](\d{1,2})日?(?:\s*([0-9]{1,2})[:：]([0-9]{2}))?",
        r"截止(?:至|时间)?[：:\s]*(20\d{2})?[-/年]?(\d{1,2})[-/月](\d{1,2})日?(?:\s*([0-9]{1,2})[:：]([0-9]{2}))?"
    ]
    for pat in patterns:
        m=re.search(pat,text,re.I)
        if not m: continue
        try:
            year=int(m.group(1) or TODAY.year)
            month,day=int(m.group(2)),int(m.group(3))
            hh,mm=int(m.group(4) or 23),int(m.group(5) or 59)
            dt=datetime.datetime(year,month,day,hh,mm,tzinfo=TZ)
            return dt.isoformat()
        except: pass
    return None

def extract_event_date(text):
    # 先匹配带年份
    m=re.search(r"(20\d{2})[-/年](\d{1,2})[-/月](\d{1,2})日?", text)
    if m:
        try: return datetime.date(int(m.group(1)),int(m.group(2)),int(m.group(3))).isoformat()
        except: pass
    # 再匹配月日，且必须接近“会议/活动”等上下文
    for m in re.finditer(r"(\d{1,2})月(\d{1,2})日", text):
        start=max(0,m.start()-30); end=min(len(text),m.end()+40)
        ctx=text[start:end]
        if not any(k in ctx for k in ["活动","论坛","会议","讲座","大会","工作坊","举办","召开","时间"]):
            continue
        try:
            d=datetime.date(TODAY.year,int(m.group(1)),int(m.group(2)))
            return d.isoformat()
        except: pass
    return None

def is_material_update(text, quality):
    t=text.lower()
    return any(k.lower() in t for k in quality.get("material_update_keywords",[]))

def tier(score, deadline=None):
    if deadline:
        try:
            dl=datetime.datetime.fromisoformat(deadline)
            if 0 < (dl-NOW).total_seconds() < 36*3600: return "必须处理"
        except: pass
    if score>=115: return "必看"
    if score>=90: return "建议看"
    return "有空再看"

def action(cat, score, deadline=None):
    if deadline:
        try:
            dl=datetime.datetime.fromisoformat(deadline)
            if 0 < (dl-NOW).total_seconds() < 36*3600: return "今天决定是否报名"
        except: pass
    if score>=115: return "今天看"
    if score>=90: return "建议收藏"
    if cat in ("AI 绘画","AI 影视","游戏与 3D","Agent / 编程"): return "有空试一下"
    return "扫一眼即可"

def focus_points(title, desc):
    sentences=[clean(v) for v in re.split(r"(?<=[。！？.!?])\s+|[\n]",desc or "") if clean(v)]
    updates=[v for v in sentences if re.search(r"新增|更新|发布|推出|升级|支持|开放|改进|提升|修复|new|introduc|launch|releas|updat|improv|support|now |increase",v,re.I)]
    if updates:
        return "更新重点："+" ".join(updates[:2])[:260]
    if sentences:
        return "关注内容："+sentences[0][:220]+"（原文未明确列出版本变化。）"
    return "关注主题："+clean(title)+"；具体能力与更新细节需查看原文。"

def summary(title,desc):
    if desc and len(desc)>=35:
        return desc[:230].rstrip("。；;,. ")+"。"
    return f"官方来源出现与“{title[:46]}”相关的新条目，完整内容需进入原始来源确认。"

def title_similarity(a,b):
    a,b=norm_title(a),norm_title(b)
    if not a or not b: return 0
    if a in b or b in a:
        return min(len(a),len(b))/max(len(a),len(b))
    return SequenceMatcher(None,a,b).ratio()

def choose_primary(cluster):
    def key(x):
        return (
            x.get("source_reliability",0),
            x.get("date_confidence")=="high",
            x.get("score",0)
        )
    primary=max(cluster,key=key)
    alts=[{"source":x.get("source"),"url":x.get("url")} for x in cluster if x is not primary][:4]
    primary["alternatives"]=alts
    return primary

def cluster_duplicates(rows, threshold):
    clusters=[]
    for x in sorted(rows,key=lambda z:z["score"],reverse=True):
        placed=False
        for c in clusters:
            if canonical_url(x["url"])==canonical_url(c[0]["url"]) or title_similarity(x["title"],c[0]["title"])>=threshold:
                c.append(x); placed=True; break
        if not placed: clusters.append([x])
    return [choose_primary(c) for c in clusters]

def load_seen():
    data=jload(ROOT/"data/seen_items.json",{"items":[]})
    return data.get("items",[])

def suppress_recent_seen(rows, quality):
    days=quality.get("duplicate_detection",{}).get("cross_day_suppression_days",10)
    seen=load_seen()
    out=[]
    for x in rows:
        if x.get("category")=="论坛 / 展会" and event_is_valid(x,quality):
            out.append(x);continue
        suppress=False
        for s in seen:
            try:
                seen_date=datetime.date.fromisoformat(s["last_seen"])
            except:
                continue
            if (TODAY-seen_date).days>days: continue
            same=(canonical_url(x["url"])==canonical_url(s.get("url",""))) or title_similarity(x["title"],s.get("title",""))>=0.86
            if same:
                if x.get("material_update"):
                    x["resurfaced"]=True
                else:
                    suppress=True
                break
        if not suppress: out.append(x)
    return out

def update_seen(rows):
    data=jload(ROOT/"data/seen_items.json",{"items":[]})
    items=data.get("items",[])
    by_key={}
    for s in items:
        key=canonical_url(s.get("url","")) or norm_title(s.get("title",""))
        by_key[key]=s
    for x in rows:
        key=canonical_url(x.get("url","")) or norm_title(x.get("title",""))
        by_key[key]={
            "title":x.get("title",""),
            "url":x.get("url",""),
            "last_seen":TODAY.isoformat(),
            "content_hash":hid((x.get("title","")+"|"+x.get("summary",""))),
            "source":x.get("source","")
        }
    kept=[]
    for s in by_key.values():
        try:
            if (TODAY-datetime.date.fromisoformat(s["last_seen"])).days<=60:
                kept.append(s)
        except:
            kept.append(s)
    (ROOT/"data/seen_items.json").write_text(json.dumps({"items":kept[-1200:]},ensure_ascii=False,indent=2),encoding="utf-8")

def within_freshness(x, quality):
    cat=x.get("category","")
    if cat=="论坛 / 展会" and x.get("event_end_date") and event_is_valid(x,quality): return True
    days=quality.get("freshness_days",{}).get(cat, quality.get("freshness_days",{}).get("default",21))
    if not x.get("published_at"):
        min_p=quality.get("unknown_date_policy",{}).get("allow_if_source_priority_at_least",5)
        return x.get("source_priority",0)>=min_p
    try:
        d=datetime.date.fromisoformat(x["published_at"][:10])
        age=(TODAY-d).days
        return -1<=age<=days
    except:
        return False

def extract_event_city(text):
    # Venue evidence only: an organizer's city is not the event location.
    matches=re.finditer(r"(?:地点|地址|举办地|会场|location|venue)\s*[:：]?\s*([^。；;\n]{1,100})",text,re.I)
    for match in matches:
        for city,alias in [("上海","shanghai"),("杭州","hangzhou"),("北京","beijing"),("深圳","shenzhen"),("广州","guangzhou")]:
            if city in match.group(1) or alias in match.group(1).lower(): return city
    return ""

def event_is_valid(x, quality):
    if x.get("category")!="论坛 / 展会": return True
    if x.get("registration_status") in ["closed","full","cancelled"]:return False
    try:
        start=datetime.date.fromisoformat(x.get("event_date") or "")
        event=datetime.date.fromisoformat(x.get("event_end_date") or x.get("event_date") or "")
        if event<start or event<TODAY: return False
        if x.get("deadline"):
            deadline=datetime.datetime.fromisoformat(str(x["deadline"]).replace("T24:00:00","T23:59:59"))
            if deadline.tzinfo is None: deadline=deadline.replace(tzinfo=TZ)
            if deadline<=datetime.datetime.now(TZ): return False
        return start<=TODAY or (start-TODAY).days<=quality.get("event_validation",{}).get("max_future_days",180)
    except (ValueError,TypeError):
        return False

def collect(source_filter=None):
    cfg=jload(ROOT/"config/sources.json",{"sources":[]})
    prefs=jload(ROOT/"config/preferences.json",{})
    quality=jload(ROOT/"config/quality.json",{})
    rows=[]; errors=[]; health=[]
    runtime=jload(ROOT/"config/runtime.json",{}).get("fetch",{})
    max_articles=max(1,min(70,int(runtime.get("max_articles_per_source",40))))
    article_workers=max(1,min(8,int(runtime.get("article_workers",4))))
    source_workers=max(1,min(8,int(runtime.get("source_workers",6))))
    def collect_source(src):
        rows=[]; errors=[]; health=[]
        started=time.time(); count=0; err=""
        try:
            bases=list_links(src)[:max_articles]
            with ThreadPoolExecutor(max_workers=article_workers) as pool:
                metas=list(pool.map(lambda base:({"desc":base["summary"],"published":base["published_at"],"body":base["summary"],"date_confidence":"high","image":""} if src.get("collector")=="x_api" else article_meta(base["url"])),bases))
            for base,meta in zip(bases,metas):
                desc,pub,body=meta["desc"],meta["published"],meta["body"]
                if base.get("published_at"):
                    desc,pub,body=base["summary"],base["published_at"],base["summary"];meta["date_confidence"]="high"
                if src.get("collector")=="sniec":
                    prefix=base["title"].rstrip(". …")
                    base["title"]=next((h for h in meta.get("headings",[]) if h.startswith(prefix)),base["title"])
                if src.get("focus_update_only") and not base.get("published_at"):
                    if base.get("listing_date") and not pub:pub=base["listing_date"];meta["date_confidence"]="medium"
                    if not pub:continue
                    headings=meta.get("headings",[])
                    if headings and not re.fullmatch(r"Change Log|Changelog|Documentation",headings[0],re.I):base["title"]=headings[0]
                    if re.fullmatch(r"this documentation|learn more|read more|change log|changelog|documentation",base["title"],re.I):continue
                    if not re.search(r"update|release|launch|introduc|announc|available|model|engine|version|新增|更新|发布|上线|模型|引擎|升级|\d+\.\d+",base["title"]+" "+desc,re.I):continue
                text=base["title"]+" "+desc+" "+body[:4000]
                cat=src.get("force_category") or classify(text,src.get("category"))
                dl=extract_deadline(text) if cat=="论坛 / 展会" else None
                ev=base.get("event_date") or (extract_event_date(text) if cat=="论坛 / 展会" else None)
                sc=score_item(base["title"],desc,src,cat,prefs,quality,meta["date_confidence"])
                if dl:
                    try:
                        if datetime.datetime.fromisoformat(dl)>=NOW: sc+=24
                    except: pass
                if cat=="论坛 / 展会":
                    city=extract_event_city(text)
                    if city in prefs.get("event_cities",[]): sc+=24
                    elif city: sc-=18
                material=is_material_update(text,quality)
                item={
                    "id":hid(base["url"]),"title":base["title"],"url":base["url"],
                    "image":meta.get("image",""),"image_source":base["url"],
                    "summary":summary(base["title"],desc),"why":focus_points(base["title"],desc),
                    "action":action(cat,sc,dl),"tier":tier(sc,dl),
                    "source":src.get("name","未知来源"),
                    "source_type":src.get("type",""),
                    "source_priority":src.get("category_priorities",{}).get(cat,src.get("priority",3)),
                    "source_reliability":source_reliability(src),
                    "published_at":pub,
                    "date_confidence":meta["date_confidence"],
                    "date_label":pub or quality.get("unknown_date_policy",{}).get("display_label","日期待确认"),
                    "category":cat,"status":tier(sc,dl),
                    "deadline":dl,"event_date":ev,"event_end_date":base.get("event_end_date"),
                    "location":(base.get("location") or extract_event_city(text)) if cat=="论坛 / 展会" else "",
                    "score":sc,
                    "material_update":material
                }
                if src.get("library_source"):
                    from public_classes import lecture_details
                    details=lecture_details(text,src.get("city"))
                    if not details:continue
                    item.update(details)
                if src.get("game_event_source"):
                    item.update(event_kind="游戏行业",participation_mode="线下",registration="报名资格与名额以官方通知为准",registration_status="check",action="查看游戏活动与报名")
                if src.get("collector")=="sniec":
                    item.update(summary=f"官方场馆日程：{ev} 至 {base.get('event_end_date')}，地点为上海新国际博览中心。参观票务及资格请查看主办方通知。",why="关注展会主题、举办日期与观众报名要求；票务或专业观众资格以官方通知为准。",image="",published_at="",date_confidence="unknown",date_label="场馆官方日程")
                if summarizer and summarizer.configured() and sc>=90:
                    item=summarizer.rewrite(item)
                rows.append(item); count+=1
            status="ok"
        except Exception as e:
            status="error"; err=f"{type(e).__name__}: {e}"
            errors.append({"source":src.get("name","未知来源"),"error":err})
        health.append({
            "source":src.get("name","未知来源"),
            "url":src.get("url",""),
            "status":status,
            "candidate_count":count,
            "elapsed_ms":int((time.time()-started)*1000),
            "error":err,
            "checked_at":NOW.isoformat(timespec="seconds")
        })
        return rows,errors,health

    with ThreadPoolExecutor(max_workers=source_workers) as pool:
        for source_rows,source_errors,source_health in pool.map(collect_source,[s for s in cfg.get("sources",[]) if source_filter is None or source_filter(s)]):
            rows.extend(source_rows);errors.extend(source_errors);health.extend(source_health)

    import category_news
    category_news.refresh(ROOT,rows,TODAY,errors)

    # 基础过滤
    min_title=quality.get("minimum_content",{}).get("title_chars",8)
    rows=[x for x in rows if len(x.get("title",""))>=min_title]
    rows=[x for x in rows if within_freshness(x,quality)]
    rows=[x for x in rows if event_is_valid(x,quality)]

    # 同题聚类：保留更可靠的一手来源
    threshold=quality.get("duplicate_detection",{}).get("title_similarity_threshold",0.84)
    rows=cluster_duplicates(rows,threshold)

    # 跨日去重
    rows=suppress_recent_seen(rows,quality)
    rows=sorted(rows,key=lambda z:z["score"],reverse=True)

    return rows,errors,prefs,quality,len(cfg.get("sources",[])),health

def build_mode(rows,prefs,mode):
    rt=jload(ROOT/"config/runtime.json",{})
    m=rt.get("brief_modes",{}).get(mode,{"top":3,"per_section":5,"min_score":72})
    pool=[x for x in rows if x["score"]>=m["min_score"]]
    pool.sort(key=lambda z:z["score"],reverse=True)
    top=[]; seen=set()
    for x in pool:
        if len(top)>=m["top"]: break
        if x["category"] not in seen or len(top)>=2:
            top.append(x); seen.add(x["category"])
    top_ids={x["id"] for x in top}
    cats=[("艺术","◈"),("AI 绘画","✦"),("AI 影视","▶"),("游戏与 3D","◆"),("Agent / 编程","⌘"),("新模型 / 开源","◎"),("论坛 / 展会","◉")]
    sections=[]
    for cat,icon in cats:
        items=[x for x in pool if x["category"]==cat and x["id"] not in top_ids][:m["per_section"]]
        sections.append({"name":cat,"icon":icon,"items":items})
    hi=sum(1 for x in pool if x.get("tier") in ("必看","必须处理"))
    return {
        "date":TODAY.isoformat(),
        "edition":f"AUTO-{TODAY.strftime('%Y%m%d')}-{mode}",
        "reading_minutes":5 if mode=="5min" else 10,
        "headline":f"今天筛出 {hi} 条高优先级 AI 信息",
        "note":f"{mode} 模式：优先一手来源；发布日期不确定的内容会降权；最近重复出现的旧条目默认不再推送。",
        "top3":top,"sections":sections
    }

def issue_to_html(issue):
    cards=[]
    def one(x,h="h3"):
        alts=""
        if x.get("alternatives"):
            alts="<p class='meta'>同题其他来源："+ " · ".join(html.escape(a.get("source","")) for a in x["alternatives"]) +"</p>"
        return f"""<article><div class="tag">{html.escape(x.get('tier',''))}</div>
        <{h}>{html.escape(x.get('title',''))}</{h}>
        <p><b>发生了什么：</b>{html.escape(x.get('summary',''))}</p>
        <p><b>关注重点：</b>{html.escape(x.get('why',''))}</p>
        <p><b>建议动作：</b>{html.escape(x.get('action',''))}</p>
        <p class="meta">{html.escape(x.get('source',''))} · {html.escape(x.get('date_label',''))} · <a href="{html.escape(x.get('url',''))}">原始来源</a></p>{alts}</article>"""
    for i,x in enumerate(issue.get("top3",[]),1):
        cards.append(one(x,"h2"))
    for sec in issue.get("sections",[]):
        if not sec.get("items"): continue
        cards.append(f"<h2 class='sec'>{html.escape(sec['name'])}</h2>")
        cards.extend(one(x,"h3") for x in sec["items"])
    return f"""<!doctype html><html lang="zh-CN"><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>AI前沿日报 {issue['date']}</title>
    <style>body{{max-width:820px;margin:auto;padding:24px 16px;background:#f5f0e7;color:#20201e;font-family:-apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif}}
    h1{{font:700 52px Georgia,serif;border-bottom:4px double #20201e;padding-bottom:10px}} article{{padding:16px 0;border-bottom:1px solid #cfc7ba}}
    p{{line-height:1.7}}.meta{{font-size:12px;color:#777167}}.tag{{display:inline-block;border:1px solid #aaa;border-radius:999px;padding:3px 7px;font-size:11px}}
    a{{color:#17324d}}.sec{{margin-top:34px;border-top:1px solid #20201e;padding-top:8px}}</style>
    <body><h1>AI 前沿日报</h1><p>{issue['date']} · 约 {issue['reading_minutes']} 分钟</p><h2>{html.escape(issue['headline'])}</h2>{''.join(cards)}</body></html>"""

def write_ics(rows):
    events=[]
    for x in rows:
        if x.get("category")!="论坛 / 展会" or not event_is_valid(x,{}): continue
        try:
            d=datetime.date.fromisoformat(x["event_date"])
            if (d-TODAY).days>180: continue
            end=datetime.date.fromisoformat(x.get("event_end_date") or x["event_date"])+datetime.timedelta(days=1)
        except: continue
        events.append("\n".join([
            "BEGIN:VEVENT",
            f"UID:{x['id']}@ai-brief",
            f"DTSTAMP:{NOW.astimezone(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
            f"DTSTART;VALUE=DATE:{d.strftime('%Y%m%d')}",
            f"DTEND;VALUE=DATE:{end.strftime('%Y%m%d')}",
            f"SUMMARY:{x.get('title','').replace(',', '，')}",
            f"DESCRIPTION:{(x.get('summary','')+' '+x.get('url','')).replace(chr(10),' ')}",
            f"LOCATION:{x.get('location','')}",
            "END:VEVENT"
        ]))
    ics="BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//AI Frontier Daily//CN\nCALSCALE:GREGORIAN\n"+("\n".join(events))+"\nEND:VCALENDAR\n"
    (ROOT/"data/events.ics").write_text(ics,encoding="utf-8")

def build_weekly():
    entries=[]
    for p in sorted((ROOT/"data/archive").glob("20??-??-??.json"),reverse=True)[:7]:
        obj=jload(p,{})
        if not isinstance(obj,dict): continue
        entries.extend(obj.get("top3",[]))
    # 再次同题聚类
    q=jload(ROOT/"config/quality.json",{})
    entries=cluster_duplicates(entries,q.get("duplicate_detection",{}).get("title_similarity_threshold",0.84)) if entries else []
    top=sorted(entries,key=lambda x:x.get("score",0),reverse=True)[:8]
    (ROOT/"data/weekly.json").write_text(json.dumps({
        "generated_at":NOW.isoformat(timespec="seconds"),
        "range_days":7,
        "headline":"过去一周真正值得记住的 AI 变化",
        "items":top
    },ensure_ascii=False,indent=2),encoding="utf-8")

def published_today(rows):
    return [dict(x) for x in rows if x.get("published_at")==TODAY.isoformat()
            and x.get("date_confidence") in ("high","medium") and event_is_valid(x,{})
            and not re.fullmatch(r"Community Articles|Research Overview|Research|Explore models|Skip to main content|Global Affairs",x.get("title",""),re.I)]

def write_all(issue5,issue10,rows,errors,source_count,health):
    from translation_pipeline import prepare
    selected=issue5.get("top3",[])+[x for sec in issue5.get("sections",[]) for x in sec["items"]]+issue10.get("top3",[])+[x for sec in issue10.get("sections",[]) for x in sec["items"]]
    today_items=published_today(rows)
    prepare(selected+today_items)
    (ROOT/"data/today.json").write_text(json.dumps({"date":TODAY.isoformat(),"items":today_items},ensure_ascii=False,indent=2),encoding="utf-8")
    data=ROOT/"data"; editions=ROOT/"editions"; editions.mkdir(exist_ok=True)
    (data/"latest_5min.json").write_text(json.dumps(issue5,ensure_ascii=False,indent=2),encoding="utf-8")
    (data/"latest_10min.json").write_text(json.dumps(issue10,ensure_ascii=False,indent=2),encoding="utf-8")
    (data/"latest.json").write_text(json.dumps(issue10,ensure_ascii=False,indent=2),encoding="utf-8")
    (data/"archive"/f"{TODAY.isoformat()}.json").write_text(json.dumps(issue10,ensure_ascii=False,indent=2),encoding="utf-8")
    (editions/f"{TODAY.isoformat()}.html").write_text(issue_to_html(issue10),encoding="utf-8")
    (data/"source_health.json").write_text(json.dumps({"generated_at":NOW.isoformat(timespec="seconds"),"sources":health},ensure_ascii=False,indent=2),encoding="utf-8")

    idxp=data/"archive/index.json"; idx=jload(idxp,[])
    idx=[x for x in idx if x.get("date")!=TODAY.isoformat()]
    idx.insert(0,{"date":TODAY.isoformat(),"edition":issue10["edition"],"title":issue10["headline"],"html":f"./editions/{TODAY.isoformat()}.html"})
    idxp.write_text(json.dumps(idx[:120],ensure_ascii=False,indent=2),encoding="utf-8")

    write_ics(rows+jload(ROOT/"data/exhibitions.json",{}).get("items",[])+jload(ROOT/"data/public_classes.json",{}).get("items",[])); build_weekly()
    health_summary={
        "updated_at":NOW.isoformat(timespec="seconds"),
        "source_count":source_count,"candidate_count":len(rows),"error_count":len(errors),
        "errors":errors[:20],"status":"ok" if len(rows)>=6 else "degraded",
        "llm_enabled":bool(summarizer and summarizer.configured()),
        "quality_version":"v6"
    }
    (data/"health.json").write_text(json.dumps(health_summary,ensure_ascii=False,indent=2),encoding="utf-8")
    update_seen(issue10.get("top3",[])+[i for s in issue10.get("sections",[]) for i in s.get("items",[])])
    if trend_engine:
        try:
            trend_engine.build()
        except Exception as e:
            print("trend engine warning:", e)

def main():
    rows,errors,prefs,quality,source_count,health=collect()
    import exhibitions
    exhibition_rows=exhibitions.refresh(rows)
    import public_classes
    public_classes.refresh(rows)
    (ROOT/"data/raw_candidates.json").write_text(json.dumps({
        "generated_at":NOW.isoformat(timespec="seconds"),"count":len(rows),"items":rows[:180],"errors":errors
    },ensure_ascii=False,indent=2),encoding="utf-8")
    issue5=build_mode(rows,prefs,"5min")
    issue10=build_mode(rows,prefs,"10min")
    if len(rows)>=6 and len(issue10["top3"])>=2:
        write_all(issue5,issue10,rows,errors,source_count,health)
        print(f"updated {TODAY}: {len(rows)} quality candidates")
    else:
        (ROOT/"data/source_health.json").write_text(json.dumps({"generated_at":NOW.isoformat(timespec="seconds"),"sources":health},ensure_ascii=False,indent=2),encoding="utf-8")
        (ROOT/"data/health.json").write_text(json.dumps({
            "updated_at":NOW.isoformat(timespec="seconds"),"source_count":source_count,
            "candidate_count":len(rows),"error_count":len(errors),"errors":errors[:20],
            "status":"degraded","message":"高质量候选不足，保留上一期。","quality_version":"v6"
        },ensure_ascii=False,indent=2),encoding="utf-8")
        print("not enough quality candidates; previous issue kept")

if __name__=="__main__":
    main()
