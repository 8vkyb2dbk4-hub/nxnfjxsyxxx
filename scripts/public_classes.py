"""Dated public classes, independent of news publication age."""
import json,datetime,re,hashlib
from pathlib import Path
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[1];TZ=datetime.timezone(datetime.timedelta(hours=8))
def available(x,now=None):
 now=now or datetime.datetime.now(TZ)
 try:
  start=datetime.date.fromisoformat(x['event_date']);end=datetime.date.fromisoformat(x.get('event_end_date') or x['event_date'])
  if x.get('location') not in ['上海','杭州'] or end<start or end<now.date() or (start-now.date()).days>180:return False
  if x.get('registration_status') in ['closed','full','cancelled']:return False
  for field in ['deadline','event_end_at']:
   if x.get(field) and datetime.datetime.fromisoformat(x[field])<=now:return False
  return True
 except (KeyError,TypeError,ValueError):return False

def parse_table(markup,url):
 soup=BeautifulSoup(markup,'html.parser');title=soup.get_text(' ',strip=True);ym=re.search(r'(20\d{2})年(\d{1,2})月活动',title)
 if not ym:return []
 year,month=map(int,ym.groups());rows=[]
 for tr in soup.find_all('tr'):
  cells=[c.get_text(' ',strip=True) for c in tr.find_all(['td','th'],recursive=False)]
  if len(cells)<4:continue
  name,when,venue,registration=cells[:4]
  if not any(k in name for k in ['讲座','课堂','讲堂','手作','科普','AI','打印','领导力','工坊','成长','学堂','茶叙','沙龙','读书会','慢读','古琴','鉴赏','阅读']):continue
  m=re.search(r'(\d{1,2})月(\d{1,2})日',when)
  if not m:continue # Monthly, repeated or ambiguous dates require individual verification.
  date=datetime.date(year,int(m[1]),int(m[2])).isoformat();times=re.findall(r'(\d{1,2}):(\d{2})',when)
  row=dict(title=name,event_date=date,event_end_date=date,location='杭州',venue=venue,url=url,source='杭州图书馆 · 官方月度活动',registration=registration[:160],registration_status='no_signup' if '无需报名' in registration else ('onsite' if '现场报名' in registration else 'check'),participation_mode='线上' if any(k in venue for k in ['直播','公众号']) else '线下',audience='参与人群以官方说明为准',event_kind='讲座' if any(k in name for k in ['讲座','讲堂','沙龙','读书会','慢读','茶叙']) else '公开课',summary='官方公开课堂活动。具体参与要求与报名方式请查看活动原文。',why='关注开课主题、时间、地点与适用人群；预约课程先核对名额。')
  if times:
   row['event_start_at']=date+'T'+f'{int(times[0][0]):02d}:{times[0][1]}:00+08:00'
   if len(times)>1:row['event_end_at']=date+'T'+f'{int(times[1][0]):02d}:{times[1][1]}:00+08:00'
  if any(k in registration for k in ['已满','额满','报名结束','报名截止','已取消']):row['registration_status']='closed'
  rows.append(row)
 return rows

def lecture_details(text,city):
 # Require an explicit event-time label and full year. Publication dates are not event dates.
 m=re.search(r'(?<![\u4e00-\u9fff])(?:活动时间|讲座时间|开课时间|举办时间|时间)[：: ]+(20\d{2})[年/-](\d{1,2})[月/-](\d{1,2})日?',text)
 if not m or city not in ['上海','杭州']:return None
 try:date=datetime.date(*map(int,m.groups())).isoformat()
 except ValueError:return None
 state='closed' if any(k in text for k in ['报名已满','名额已满','报名已截止','活动已取消','活动已结束']) else 'check'
 return dict(event_kind='讲座',event_date=date,event_end_date=date,location=city,registration_status=state,registration='请核对官方报名说明与剩余名额',participation_mode='线下',audience='以官方说明为准')

def refresh(rows=()):
 now=datetime.datetime.now(TZ);path=ROOT/'data/public_classes.json'
 try:prior=json.loads(path.read_text(encoding='utf-8')).get('items',[])
 except (OSError,ValueError):prior=[]
 seeds=json.loads((ROOT/'config/public_classes.json').read_text(encoding='utf-8')).get('items',[]);items=prior+seeds+[x for x in rows if x.get('event_kind') in ['公开课','讲座']];errors=[]
 try:
  url='https://www.zjhzlib.cn/hdyg/index.htm';r=requests.get(url,timeout=12);r.raise_for_status();soup=BeautifulSoup(r.content,'html.parser')
  links=[urljoin(url,a['href']) for a in soup.find_all('a',href=True) if '月活动一览' in a.get_text()][:2]
  for link in links:
   r=requests.get(link,timeout=12);r.raise_for_status();items+=parse_table(BeautifulSoup(r.content,'html.parser').decode(),link)
 except (requests.RequestException,ValueError) as e:errors.append(type(e).__name__)
 merged={}
 for item in items:
  key=(re.sub(r'\W','',item['title']),item['event_date'])
  if not available(item,now):
   merged.pop(key,None)
   continue
  item=dict(item);item.setdefault('id',hashlib.sha256(str(key).encode()).hexdigest()[:14]);item.update(category='论坛 / 展会');item.setdefault('tier','建议看');item.setdefault('score',90);item.setdefault('action','查看课程与报名');item.setdefault('date_label','官方活动时间');item.setdefault('verified_at',now.date().isoformat());merged[key]=item
 result=sorted(merged.values(),key=lambda x:x['event_date']);path.write_text(json.dumps(dict(updated_at=now.isoformat(),items=result,libraries=json.loads((ROOT/'config/libraries.json').read_text(encoding='utf-8'))['libraries'],source_errors=errors),ensure_ascii=False,indent=2),encoding='utf-8');return result
if __name__=='__main__':print('Public classes:',len(refresh()))
