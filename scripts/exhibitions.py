"""Independent dated exhibition feed, kept through news freshness and fetch failures."""
import json,re,datetime,hashlib
from pathlib import Path
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[1]
TZ=datetime.timezone(datetime.timedelta(hours=8))
RANGE=re.compile(r"(20\d{2})[./年-](\d{1,2})[./月-](\d{1,2})日?\s*[~～—–－至-]\s*(20\d{2})[./年-](\d{1,2})[./月-](\d{1,2})日?")
def date_range(text):
    match=RANGE.search(text)
    if not match:return None
    try:
        start=datetime.date(*map(int,match.groups()[:3]));end=datetime.date(*map(int,match.groups()[3:]))
        if end<start:return None
        return start.isoformat(),end.isoformat()
    except ValueError:return None

def available(item,today=None):
    today=today or datetime.datetime.now(TZ).date()
    if item.get('registration_status') in ['closed','full','cancelled']:return False
    if item.get('deadline'):
        try:
            if datetime.datetime.fromisoformat(item['deadline'])<=datetime.datetime.now(TZ):return False
        except (ValueError,TypeError):return False
    try:
        start=datetime.date.fromisoformat(item['event_date']);end=datetime.date.fromisoformat(item.get('event_end_date') or item['event_date'])
        return end>=start and end>=today and (start<=today or (start-today).days<=180)
    except (ValueError,KeyError,TypeError):return False

def parse_listing(markup,src):
    soup=BeautifulSoup(markup,'html.parser');items=[]
    if src.get('exhibition_collector')=='powerlong':
        for anchor in soup.find_all('a',href=True):
            text=anchor.get_text(' ',strip=True);dates=date_range(text)
            if not dates or '/exhibition_detail/' not in anchor['href']:continue
            title=RANGE.sub('',text).strip();items.append({'title':title,'url':urljoin(src['url'],anchor['href']),'event_date':dates[0],'event_end_date':dates[1],'venue':'上海宝龙美术馆','event_kind':'美术馆展览'})
    elif src.get('exhibition_collector')=='necc':
        for heading in soup.find_all(['h4','h3']):
            title=heading.get_text(' ',strip=True)
            if len(title)<4 or title=='展会排期':continue
            node=heading
            for _ in range(3):
                node=node.parent
                if node is None:break
                text=node.get_text(' ',strip=True)
                if len(text)>1800:break
                dates=date_range(text)
                if dates:
                    items.append({'title':title,'url':src['url'],'event_date':dates[0],'event_end_date':dates[1],'venue':'国家会展中心（上海）','event_kind':'国家会展中心'});break
    return items

def item_key(item):
    return (re.sub(r"[^\w]", "", item["title"]).casefold(), item["event_date"])

def refresh(rows=()):
    now=datetime.datetime.now(TZ);today=now.date();path=ROOT/'data/exhibitions.json'
    try:prior=json.loads(path.read_text(encoding='utf-8')).get('items',[])
    except (OSError,ValueError):prior=[]
    seeds=json.loads((ROOT/'config/exhibitions.json').read_text(encoding='utf-8')).get('items',[])
    sources=json.loads((ROOT/'config/sources.json').read_text(encoding='utf-8')).get('sources',[])
    merged={}
    for item in prior+seeds+[x for x in rows if x.get('category')=='论坛 / 展会']:
        if available(item,today):merged[item_key(item)]=dict(item)
    errors=[]
    for source in sources:
        if not source.get('exhibition_collector'):continue
        try:
            response=requests.get(source['url'],headers={'User-Agent':'Mozilla/5.0'},timeout=15);response.raise_for_status();response.encoding='utf-8'
            for item in parse_listing(response.text,source):
                if not available(item,today):continue
                item.update(location='上海',source=source['name'],verified_at=today.isoformat(),summary=f"官方展期：{item['event_date']} 至 {item['event_end_date']}。场馆：{item['venue']}。",why='关注展览内容、展期与入场条件；开放日及票务以主办方通知为准。')
                merged[item_key(item)]=item
        except (requests.RequestException,ValueError) as error:errors.append({'source':source['name'],'error':type(error).__name__})
    items=[]
    for item in merged.values():
        item.setdefault('id',hashlib.sha256((item['title']+item['event_date']+item.get('venue','')).encode()).hexdigest()[:14]);item.update(category='论坛 / 展会');item.setdefault('location','上海');item.setdefault('score',95);item.setdefault('tier','建议看');item.setdefault('action','查看展览与预约');item.setdefault('published_at','');item.setdefault('date_confidence','unknown');item.setdefault('date_label','官方展期')
        items.append(item)
    path.write_text(json.dumps({'updated_at':now.isoformat(),'items':sorted(items,key=lambda x:x['event_date']),'source_errors':errors},ensure_ascii=False,indent=2),encoding='utf-8')
    return items
if __name__=='__main__':print('Exhibition feed:',len(refresh()))

