import pathlib,sys,os
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from x_updates import parse_posts,fetch
base=dict(id='1234567890',author_id='42',text='Introducing a new model with improved video generation',created_at='2026-10-01T18:00:00Z')
rows=parse_posts({'data':[base]},'OpenAI','42')
assert len(rows)==1 and rows[0]['published_at']=='2026-10-02'
assert rows[0]['url']=='https://x.com/OpenAI/status/1234567890'
for extra in [dict(author_id='99'),dict(created_at=''),dict(referenced_tweets=[dict(type='retweeted')]),dict(text='Happy Friday everyone!')]:
 assert not parse_posts({'data':[{**base,**extra}]},'OpenAI','42')
os.environ.pop('AI_BRIEF_X_BEARER_TOKEN',None)
try:fetch(dict(x_handle='OpenAI'));raise AssertionError('Missing token must be explicit')
except RuntimeError as e:assert '官网' in str(e)
print('X author, update filter, publication date and missing authorization tests passed')

share={**base,'text':'My thoughts on neural networks and AI safety'}
assert parse_posts({'data':[share]},'geoffreyhinton','42',True)
assert not parse_posts({'data':[{**share,'text':'Lovely sunset today'}]},'geoffreyhinton','42',True)
