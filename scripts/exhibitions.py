"""Independent dated exhibition feed, kept through news freshness and fetch failures."""
import json,re,datetime,hashlib
from pathlib import Path
from urllib.parse import urljoin,urlsplit,urlunsplit,parse_qsl,urlencode
from concurrent.futures import ThreadPoolExecutor
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
    if item.get('event_end_at'):
        try:
            if datetime.datetime.fromisoformat(item['event_end_at'])<=datetime.datetime.now(TZ):return False
        except (ValueError,TypeError):return False
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
        for row in soup.select('table tr'):
            cells=row.find_all('td',recursive=False)
            if len(cells)<4:continue
            title=cells[0].get_text(' ',strip=True);dates=date_range(cells[1].get_text(' ',strip=True))
            if not title or not dates:continue
            halls=cells[2].get_text(' ',strip=True);contents=cells[3].get_text(' ',strip=True)
            official=next((urljoin(src['url'],a['href']) for a in cells[3].find_all('a',href=True) if a['href'].strip() and a['href'].startswith(('http://','https://'))),'')
            items.append(dict(title=title,event_date=dates[0],event_end_date=dates[1],venue='国家会展中心（上海）',event_kind='国家会展中心',schedule_type=src.get('schedule_type','展览'),halls=halls,exhibition_content=contents,organizer_url=official,url=official or src['url'],schedule_url=src['url']))
        if items:return items
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
    if str(item.get("id","")).startswith("shm-activity-"):return (item["id"],item["event_date"])
    if "进口博览会" in item["title"]:return ("中国国际进口博览会",item["event_date"])
    return (re.sub(r"[^\w]", "", item["title"]).casefold(), item["event_date"])

def fetch_necc(src):
    def read(url):
        response=requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=15);response.raise_for_status();response.encoding='utf-8';return response.text
    first=read(src['url']);items=parse_listing(first,src)
    match=re.search(r'var\s+totalPage\s*=\s*(\d+)',first)
    pages=min(int(match[1]) if match else 1,40);errors=[]
    base=urlsplit(src['url']);query=dict(parse_qsl(base.query))
    urls=[urlunsplit((base.scheme,base.netloc,base.path,urlencode({**query,'pageNo':page}),'')) for page in range(2,pages+1)]
    def read_page(url):
        try:return parse_listing(read(url),src),None
        except requests.RequestException as error:return [],type(error).__name__
    with ThreadPoolExecutor(max_workers=4) as pool:
        for rows,error in pool.map(read_page,urls):
            items+=rows
            if error:errors.append(error)
    return list({item_key(x):x for x in items}.values()),errors,pages

def refresh(rows=()):
    now=datetime.datetime.now(TZ);today=now.date();path=ROOT/'data/exhibitions.json'
    try:prior=json.loads(path.read_text(encoding='utf-8')).get('items',[])
    except (OSError,ValueError):prior=[]
    seeds=json.loads((ROOT/'config/exhibitions.json').read_text(encoding='utf-8')).get('items',[])
    sources=json.loads((ROOT/'config/sources.json').read_text(encoding='utf-8')).get('sources',[])
    merged={}
    for item in prior+seeds+[x for x in rows if x.get('category')=='论坛 / 展会']:
        if available(item,today):merged[item_key(item)]=dict(item)
    errors=[];source_status=[]
    for source in sources:
        if not source.get('exhibition_collector'):continue
        try:
            if source.get('exhibition_collector')=='psa':
                import psa_schedule
                fetched,page_errors,pages=psa_schedule.fetch(source)
                for error in page_errors:errors.append({'source':source['name'],'error':error})
                source_status.append(dict(source=source['name'],url=source['url'],schedule_type='展览与活动',checked_at=now.isoformat(),total_items=len(fetched),valid_items=sum(available(x,today) for x in fetched),pages=pages,status='partial' if page_errors else 'ok'))
            elif source.get('exhibition_collector','').startswith('shmuseum_'):
                import museum_schedule
                fetched,page_errors,pages=museum_schedule.fetch(source)
                for error in page_errors:errors.append({'source':source['name'],'error':error})
                source_status.append(dict(source=source['name'],url=source['url'],schedule_type=source.get('schedule_type','展览'),checked_at=now.isoformat(),total_items=len(fetched),valid_items=sum(available(x,today) for x in fetched),pages=pages,status='partial' if page_errors else 'ok'))
            elif source.get('exhibition_collector')=='necc':
                fetched,page_errors,pages=fetch_necc(source)
                for error in page_errors:errors.append({'source':source['name'],'error':error})
                source_status.append(dict(source=source['name'],url=source['url'],schedule_type=source.get('schedule_type','展览'),checked_at=now.isoformat(),total_items=len(fetched),valid_items=sum(available(x,today) for x in fetched),pages=pages,status='partial' if page_errors else 'ok'))
            else:
                response=requests.get(source['url'],headers={'User-Agent':'Mozilla/5.0'},timeout=15);response.raise_for_status();response.encoding='utf-8';fetched=parse_listing(response.text,source)
            for item in fetched:
                if not available(item,today):
                    merged.pop(item_key(item),None)
                    continue
                item.update(location='上海',source=source['name'],verified_at=today.isoformat(),summary=f"官方展期：{item['event_date']} 至 {item['event_end_date']}。场馆：{item['venue']}。",why='关注活动主题、日期、地点与入场资格；报名和预约名额以主办方实时通知为准。' if item.get('schedule_type')=='活动' else '关注展览内容、完整展期与入场条件；开放日及票务以主办方通知为准。')
                key=item_key(item);previous=merged.get(key,{})
                if previous.get('id'):item['id']=previous['id']
                if item.get('halls'):item['summary']+=' 展馆：'+item['halls']+'。'
                if item.get('exhibition_content') and item['exhibition_content']!='官网：':item['summary']+=' '+item['exhibition_content']
                merged[key]=item
        except (requests.RequestException,ValueError,TypeError) as error:errors.append({'source':source['name'],'error':type(error).__name__})
    items=[]
    for item in merged.values():
        item.setdefault('id',hashlib.sha256((item['title']+item['event_date']+item.get('venue','')).encode()).hexdigest()[:14]);item.update(category='论坛 / 展会');item.setdefault('location','上海');item.setdefault('score',95);item.setdefault('tier','建议看');item.setdefault('action','查看展览与预约');item.setdefault('published_at','');item.setdefault('date_confidence','unknown');item.setdefault('date_label','官方展期')
        items.append(item)
    path.write_text(json.dumps({'updated_at':now.isoformat(),'items':sorted(items,key=lambda x:x['event_date']),'source_errors':errors,'schedule_sources':source_status},ensure_ascii=False,indent=2),encoding='utf-8')
    return items
if __name__=='__main__':print('Exhibition feed:',len(refresh()))

