from pathlib import Path
import sys,datetime
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import category_news as news
today=datetime.date(2026,10,2)
assert news.cutoff(today)==datetime.date(2026,7,2)
assert news.cutoff(datetime.date(2026,5,31))==datetime.date(2026,2,28)
def item(date,url='https://example.org/a',confidence='high'):
 return {'title':'New video generation model','published_at':date,'category':'AI 影视','date_confidence':confidence,'url':url,'score':100}
assert len(news.merge([item('2026-07-02')],[],today))==1
assert not news.merge([item('2026-07-01'),item('2026-10-03'),item('',confidence='unknown')],[],today)
old=item('2026-09-01')
assert news.merge([], [old],today)==[old]
assert len(news.merge([old],[old],today))==1
assert news.merge([item('2026-10-02','https://example.org/new')],[old],today)[0]['published_at']=='2026-10-02'
print('Three calendar months, date boundaries, deduplication and outage retention passed')
