"""Translate public focus text during generation; retain a disk cache and Chinese fallback."""
import hashlib,json,re,requests,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def chunks(value):
    result=[];part=""
    for c in value:
        if len((part+c).encode('utf-8'))>480:result.append(part);part=""
        part+=c
    if part:result.append(part)
    return result

def prepare(items):
    path=ROOT/'data/translation_cache.json'
    try:cache=json.loads(path.read_text(encoding='utf-8'))
    except (OSError,ValueError):cache={}
    budget=4000;unavailable=False
    for item in items:
        focus=item.get('why','')
        if len(re.findall(r'[a-zA-Z]',focus))<=2*len(re.findall(r'[\u4e00-\u9fff]',focus)):continue
        item['why_original']=focus
        raw=re.sub(r'^(更新重点|关注内容|关注主题)：','',focus).split('（原文未明确')[0]
        key=hashlib.sha256(raw.encode()).hexdigest()
        translated=cache.get(key)
        if not translated and not unavailable and len(raw)<=budget:
            try:
                parts=[]
                for segment in chunks(raw):
                    response=requests.get('https://api.mymemory.translated.net/get',params={'q':segment,'langpair':'en|zh-CN'},timeout=10)
                    response.raise_for_status();out=response.json()
                    value=out.get('responseData',{}).get('translatedText','')
                    if int(out.get('responseStatus',0))!=200 or out.get('quotaFinished') or not re.search(r'[\u4e00-\u9fff]',value):raise ValueError('translation unavailable')
                    parts.append(value)
                translated=''.join(parts);cache[key]=translated;budget-=len(raw)
            except (requests.RequestException,ValueError,TypeError):unavailable=True
        if translated:
            item['why']=('更新重点：' if focus.startswith('更新重点') else '关注内容：')+translated
            if '未明确' in focus:item['why']+='（原文未明确列出版本变化。）'
        else:item['why']='中文关注重点暂未生成；该内容的具体能力和更新需查看原文。'
    path.write_text(json.dumps(cache,ensure_ascii=False,indent=2),encoding='utf-8')

