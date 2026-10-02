"""Rolling, publication-dated drawing/video news, independent of daily quotas."""
import calendar,datetime,json,re
from pathlib import Path
CATEGORIES={'AI 绘画','AI 影视'}
def relevant(x):
    title=x.get('title','')
    if re.fullmatch(r'Text to Speech|Speech to Text|Changelog|Documentation|Research|Community Articles|Comfy MCP|Overview|Get Started|Introduction|Models|Pricing|Community|Blog|News',title,re.I):return False
    text=title+' '+x.get('summary','')
    pattern=(r'\b(video|film|audio|voice|speech|music|dubbing|seedance|kling|pika|heygen|hailuo|sora|veo)\b|视频|影视|配音|音效|镜头|嘴型' if x.get('category')=='AI 影视' else r'\b(image|images|diffusion|flux|illustration|midjourney|seedream|firefly|inpaint|outpaint)\b|绘画|图像|生图|参考图|图片生成|图生')
    return bool(re.search(pattern,text,re.I))
def cutoff(today):
    month=today.month-3
    year=today.year
    if month<=0:year-=1;month+=12
    return today.replace(year=year,month=month,day=min(today.day,calendar.monthrange(year,month)[1]))
def merge(rows,previous,today):
    start=cutoff(today).isoformat();end=today.isoformat();out={}
    for x in previous+rows:
        date=str(x.get('published_at',''))
        if x.get('category') not in CATEGORIES or x.get('date_confidence') not in ('high','medium'):continue
        try:datetime.date.fromisoformat(date)
        except ValueError:continue
        if not start<=date<=end:continue
        if not x.get('url') or len(x.get('title',''))<8:continue
        if not relevant(x):continue
        out[(x['category'],x['url'])]=x
    return sorted(out.values(),key=lambda x:(x['published_at'],x.get('score',0)),reverse=True)
def refresh(root,rows,today,errors):
    p=Path(root)/'data/category_news.json'
    old=json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
    # Preserve dated items when any external source is temporarily unavailable.
    items=merge(rows,old.get('items',[]),today)
    payload={'date':today.isoformat(),'start_date':cutoff(today).isoformat(),'items':items,'errors':errors}
    p.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return payload
