import pathlib,sys,types,datetime
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'));import update as u
page='<a href="/2026/10/paper">An experimental handmade paper construction</a><a href="/2026/10/paper">Read the full article</a><a href="/login">Sign into your account</a>'
source={'url':'https://example.com','force_category':'艺术','article_url_pattern':r'/20\d{2}/\d{2}/'}
with patch.object(u,'get',return_value=types.SimpleNamespace(text=page)):
 links=u.list_links(source);assert len(links)==1;assert 'paper construction' in links[0]['title']
row={'id':'art','category':'艺术','score':120,'tier':'必看'}
issue=u.build_mode([row],{},'10min');assert any(s['name']=='艺术' for s in issue['sections'])
base={'category':'论坛 / 展会','event_date':(u.TODAY-datetime.timedelta(days=1)).isoformat(),'event_end_date':u.TODAY.isoformat()}
assert u.event_is_valid(base,{})
assert not u.event_is_valid({**base,'event_end_date':(u.TODAY-datetime.timedelta(days=1)).isoformat()},{})
page='<div><h4><a href="/event1">Art and Craft Fair</a></h4><p>2026/10/03 - 2026/10/04</p></div>'
with patch.object(u,'get',return_value=types.SimpleNamespace(text=page)):
 event=u.list_links({'url':'https://sniec.net','collector':'sniec'})[0];assert event['location']=='上海';assert event['event_end_date']=='2026-10-04'
print('Art section, article URL deduplication and Shanghai multi-day events passed')

