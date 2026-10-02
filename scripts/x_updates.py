"""Read official account timelines only when an authorized X API token is configured."""
import os,re,datetime,requests

def parse_posts(payload,handle,author_id,expert=False):
 rows=[]
 for post in payload.get('data',[]):
  if str(post.get('author_id'))!=str(author_id):continue
  if any(x.get('type') in ['retweeted','replied_to'] for x in post.get('referenced_tweets',[])):continue
  text=post.get('text','').strip();stamp=post.get('created_at','')
  if not re.fullmatch(r'\d+',str(post.get('id',''))):continue
  try:date=datetime.datetime.fromisoformat(stamp.replace('Z','+00:00')).astimezone(datetime.timezone(datetime.timedelta(hours=8))).date().isoformat()
  except (TypeError,ValueError):continue
  pattern=r'\bAI\b|AGI|LLM|neural|learning|intelligence|robot|research|paper|reasoning|agent|model|人工智能|模型|研究|课程|神经|访谈' if expert else r'launch|release|introduc|announc|update|model|available|new|发布|更新|上线|模型|升级'
  if not re.search(pattern,text,re.I):continue
  rows.append(dict(title=text[:160],summary=text,url=f'https://x.com/{handle}/status/{post["id"]}',published_at=date))
 return rows

def fetch(src):
 token=os.environ.get('AI_BRIEF_X_BEARER_TOKEN','').strip()
 if not token:raise RuntimeError('未配置 X API 授权；使用该机构官网备用来源')
 handle=src['x_handle']
 if not re.fullmatch(r'[A-Za-z0-9_]{1,15}',handle):raise ValueError('Invalid account handle')
 headers={'Authorization':'Bearer '+token}
 def read(url,params=None):
  r=requests.get(url,params=params,headers=headers,timeout=15)
  if r.status_code!=200:raise RuntimeError(f'X API HTTP {r.status_code}；使用官网备用来源')
  return r.json()
 user=read('https://api.x.com/2/users/by/username/'+handle)['data']
 if user.get('username','').lower()!=handle.lower():raise ValueError('Unexpected X author')
 posts=read(f'https://api.x.com/2/users/{user["id"]}/tweets',{'max_results':20,'exclude':'retweets,replies','tweet.fields':'created_at,author_id,referenced_tweets'})
 return parse_posts(posts,handle,user['id'],src.get('expert_source',False))
