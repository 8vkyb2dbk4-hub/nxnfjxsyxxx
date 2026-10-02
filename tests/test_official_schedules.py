from pathlib import Path
import sys,datetime
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import exhibitions as e,museum_schedule as m,psa_schedule as p
src={'url':'https://www.neccsh.com/cecsh/exhibitioninfo/exhibitionlist.jspx?v=1&channelIdStr=204','exhibition_collector':'necc','schedule_type':'活动'}
markup='<table><tr><td><div class="exhibit-name">测试活动</div></td><td>2026-10-04 - 2026-10-05</td><td>6.2H</td><td>主办：测试机构 官网：<a href="https://example.com/event">官方网站</a></td></tr></table>'
rows=e.parse_listing(markup,src);assert len(rows)==1;row=rows[0]
assert row['halls']=='6.2H' and row['schedule_type']=='活动' and row['url']=='https://example.com/event'
assert e.item_key({'title':'第九届中国国际进口博览会','event_date':'2026-11-05'})==e.item_key({'title':'中国国际进口博览会','event_date':'2026-11-05'})
payload=dict(code=0,data=[dict(name='测试上博展览',code='E001',exhibitDateRange='2026-09-23 - 2027-01-18',exhibitPlace='东馆二楼',picPath='upload/test.jpg',issueTime='2026-09-02 16:00:00')])
row=m.parse_exhibitions(payload,{'url':'https://example.com'})[0]
assert row['event_end_date']=='2027-01-18' and row['venue']=='东馆二楼' and row['image'].endswith('/mu/upload/test.jpg')
html='<div class="list-item"><a class="item-title" onclick="toLoad(100)">测试工坊</a><span>时间：2026-10-10 Sat 13:30-15:00</span><span>场馆：东馆</span><span>地点：活动中心</span><span>参与年龄段：9-18</span><button>名额已满</button></div>'
row=m.parse_activities(html,{'url':'https://events.shanghaimuseum.net/sheduplatform/activityOut/out/activityPage'})[0]
assert row['registration_status']=='full' and row['event_end_at']=='2026-10-10T15:00:00+08:00' and row['audience']=='9-18'
assert not e.available(row,datetime.date(2026,10,2))
print('official table, source links, alias deduplication, museum API and activity status tests passed')

psa=dict(items=[dict(type='exhibition',title='测试艺术展',slug='sample-art',startDate='2026-09-01T11:00:00.000+0800',endDate='2026-10-07T19:00:00.000+0800',image={}),dict(type='program',title='项目入口',slug='sample-program',startDate='2026-10-02T16:00:00+0800',endDate='2026-10-02T16:00:00+0800')])
row=p.parse(psa,'exhibitions',{'url':'https://www.powerstationofart.com/whats-on'})
assert len(row)==1 and row[0]['museum_key']=='psa' and row[0]['event_end_date']=='2026-10-07'
assert row[0]['url']=='https://www.powerstationofart.com/whats-on/exhibitions/sample-art'
assert not e.available({**row[0],'event_date':'2026-01-01','event_end_date':'2026-01-02','event_end_at':'2026-01-02T19:00:00+08:00'},datetime.date(2026,10,2))
print('PSA exact dates, expired events, detail links and non-event exclusion passed')

