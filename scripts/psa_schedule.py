"""PSA's public feed used by the museum's What's On page."""
import datetime,requests
from urllib.parse import quote
TZ=datetime.timezone(datetime.timedelta(hours=8));BASE='https://www.powerstationofart.com'
def parse(payload,kind,src):
 if not isinstance(payload.get('items'),list):raise ValueError('invalid PSA public feed')
 result=[]
 for row in payload['items']:
  if row.get('type') not in ['activity','exhibition'] or not row.get('slug') or not row.get('title'):continue
  try:
   start=datetime.datetime.fromisoformat(row['startDate'].replace('Z','+00:00')).astimezone(TZ);end=datetime.datetime.fromisoformat(row['endDate'].replace('Z','+00:00')).astimezone(TZ)
   if end<start:continue
  except (KeyError,TypeError,ValueError):continue
  images=(row.get('image') or {}).get('srcs',[]);image=next((x.get('url') for x in images if x.get('width')==800),(row.get('image') or {}).get('placeholder',''))
  state='closed' if row.get('cancelled') or row.get('soldOut') else 'check'
  url=BASE+'/whats-on/'+kind+'/'+quote(row['slug'],safe='-')
  result.append(dict(id='psa-'+row['type']+'-'+row['slug'],title=row['title'],event_date=start.date().isoformat(),event_end_date=end.date().isoformat(),event_start_at=start.isoformat(),event_end_at=end.isoformat(),venue='上海当代艺术博物馆（具体展厅以官方详情为准）',location='上海',event_kind='PSA展览与活动',museum_key='psa',schedule_type='展览' if row['type']=='exhibition' else '活动',url=url,schedule_url=src['url'],image=image,image_source=url,registration_status=state,registration='预约、购票与参与资格请查看官方详情'))
 return result

def fetch(src):
 items=[];errors=[]
 for kind in ['exhibitions','activities']:
  response=requests.get(BASE+'/campus/api/feed/public/psa/whats-on/'+kind,params={'offset':0,'limit':1000},headers={'X-Language':'zh-Hans','User-Agent':'Mozilla/5.0'},timeout=20);response.raise_for_status();payload=response.json();items+=parse(payload,kind,src)
  if payload.get('info',{}).get('count',0)>1000:errors.append('history_limit_1000')
 return items,errors,2

