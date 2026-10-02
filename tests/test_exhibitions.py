import pathlib,importlib.util,datetime
ROOT=pathlib.Path(__file__).resolve().parents[1]
def load(name):
 spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/f'{name}.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
m=load('exhibitions');u=load('update');today=datetime.date(2026,10,2)
assert m.date_range('2026.10.01~2027.04.05')==('2026-10-01','2027-04-05')
assert m.date_range('2026年10月1日至2026年10月5日')==('2026-10-01','2026-10-05')
assert m.date_range('2026.10.05~2026.10.01') is None
assert m.available({'event_date':'2025-04-29','event_end_date':'2026-10-18'},today)
assert not m.available({'event_date':'2026-10-17','event_end_date':'2026-10-18','registration_status':'full'},today)
assert not m.available({'event_date':'2026-09-01','event_end_date':'2026-09-20'},today)
assert m.available({'event_date':'2026-11-05','event_end_date':'2026-11-10'},today)
assert m.item_key({'title':'风禾有叙：中国女性艺术家的百年对话','event_date':'2026-09-18'})==m.item_key({'title':'风禾有叙: 中国女性艺术家的百年对话','event_date':'2026-09-18'})
assert m.item_key({'title':'展览A','event_date':'2026-10-31'})!=m.item_key({'title':'展览B','event_date':'2026-10-31'})
html='<a href="/exhibition_detail/1.html">测试展 2026.09.01~2026.10.18</a>'
assert m.parse_listing(html,{'url':'https://art.powerlongmuseum.com/search.html','exhibition_collector':'powerlong'})[0]['event_end_date']=='2026-10-18'
item={'category':'论坛 / 展会','event_date':(u.TODAY-datetime.timedelta(days=300)).isoformat(),'event_end_date':(u.TODAY+datetime.timedelta(days=200)).isoformat(),'published_at':'2025-01-01'}
assert u.event_is_valid(item,{})
assert u.within_freshness(item,{})
print('exhibition range, ongoing, expiry, preview, duplicate and freshness tests passed')

