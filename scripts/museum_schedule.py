"""Read Shanghai Museum's public exhibition API and activity listing."""
import re,datetime
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor
import requests
from bs4 import BeautifulSoup
from exhibitions import date_range
BASE='https://www.shanghaimuseum.cn/mu/'
def parse_exhibitions(payload,src):
 if payload.get('code')!=0 or not isinstance(payload.get('data'),list):raise ValueError('museum exhibition response')
 items=[]
 for row in payload['data']:
  dates=date_range(row.get('exhibitDateRange') or row.get('exhibitDateRangeFormatted') or '')
  if not dates or not row.get('name') or not row.get('code'):continue
  title=BeautifulSoup(row['name']+(row.get('subtitle') or ''),'html.parser').get_text(' ',strip=True)
  items.append(dict(id='shm-'+row['code'],title=title,event_date=dates[0],event_end_date=dates[1],venue=row.get('exhibitPlace') or '上海博物馆',location='上海',event_kind='博物馆展览',schedule_type='展览',url=urljoin(BASE,'frontend/pg/article/id/'+row['code']),schedule_url=src['url'],image=urljoin(BASE,row.get('picPath') or '') if row.get('picPath') else '',image_source=src['url'],published_at=(row.get('issueTime') or '')[:10],date_confidence='high' if row.get('issueTime') else 'unknown'))
 return items

def parse_activities(markup,src):
 soup=BeautifulSoup(markup,'html.parser');items=[]
 for node in soup.select('.list-item'):
  heading=node.select_one('.item-title')
  if not heading:continue
  text=node.get_text(' ',strip=True);m=re.search(r'时间[：:]\s*(20\d{2}-\d{2}-\d{2})\s*\w*\s*(\d{2}:\d{2})-(\d{2}:\d{2})',text)
  if not m:continue
  def field(label):
   span=next((x for x in node.select('span') if x.get_text(strip=True).startswith(label+'：')),None)
   return span.get_text(strip=True).split('：',1)[1] if span else ''
  state='closed' if any(k in text for k in ['活动已结束','报名已结束','预约已结束','已取消']) else ('full' if any(k in text for k in ['名额已满','报名已满','预约已满','已报满']) else ('announced' if any(k in text for k in ['报名未开始','预约未开始','即将开始']) else 'check'))
  code=re.search(r'toLoad\((\d+)\)',heading.get('onclick',''))
  item=dict(id='shm-activity-'+code[1] if code else '',title=heading.get_text(' ',strip=True),event_date=m[1],event_end_date=m[1],event_start_at=m[1]+'T'+m[2]+':00+08:00',event_end_at=m[1]+'T'+m[3]+':00+08:00',venue='上海博物馆'+field('场馆')+' · '+field('地点'),location='上海',event_kind='上海博物馆活动',participation_mode='线下',schedule_type='活动',audience=field('参与年龄段'),speaker=field('主讲人'),registration_status=state,registration='上海博物馆官方活动预约平台；资格和余票以官方实时状态为准',url=src['url'],schedule_url=src['url'])
  img=node.select_one('img')
  if img and img.get('src'):item.update(image=urljoin(src['url'],img['src']),image_source=src['url'])
  items.append(item)
 return items

def fetch(src):
 if src['exhibition_collector']=='shmuseum_exhibitions':
  response=requests.post(urljoin(BASE,'frontend/pg/display/search-exhibit'),json=dict(params=dict(exhibitTypeCode='OFFLINE_EXHIBITION',langCode='CHINESE',offlineExhibitionType='PRESENT'),page=1,limit=65536),timeout=15);response.raise_for_status();return parse_exhibitions(response.json(),src),[],1
 response=requests.get(src['url'],timeout=15);response.raise_for_status();response.encoding='utf-8';first=response.text;items=parse_activities(first,src)
 m=re.search(r'共\d+条\s*(\d+)页',BeautifulSoup(first,'html.parser').get_text(' ',strip=True));pages=min(int(m[1]) if m else 1,60);errors=[]
 def read(page):
  try:
   r=requests.post(src['url'],data={'pageNo':page},timeout=15);r.raise_for_status();r.encoding='utf-8';return parse_activities(r.text,src),None
  except requests.RequestException as error:return [],type(error).__name__
 with ThreadPoolExecutor(max_workers=4) as pool:
  for rows,error in pool.map(read,range(2,pages+1)):
   items+=rows
   if error:errors.append(error)
 return list({x['id']:x for x in items}.values()),errors,pages

