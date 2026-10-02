import pathlib,importlib.util,datetime
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('classes',ROOT/'scripts/public_classes.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
now=datetime.datetime(2026,10,2,16,tzinfo=m.TZ);base=dict(event_date='2026-10-03',location='杭州',registration_status='open')
assert m.available(base,now)
for status in ['closed','full','cancelled']:assert not m.available({**base,'registration_status':status},now)
assert not m.available({**base,'event_date':'2026-10-01'},now)
assert not m.available({**base,'event_date':'2026-10-02','event_end_at':'2026-10-02T15:30:00+08:00'},now)
assert not m.available({**base,'deadline':'2026-10-02T14:00:00+08:00'},now)
assert not m.available({**base,'location':'北京'},now)
html='<h1>2026年10月活动一览</h1><table><tr><td>AI课堂</td><td>10月3日14:00-15:30</td><td>杭图</td><td>无需报名</td></tr><tr><td>AI课堂</td><td>10月</td><td>杭图</td><td>无需报名</td></tr></table>'
rows=m.parse_table(html,'https://example.com');assert len(rows)==1 and rows[0]['event_end_at']=='2026-10-03T15:30:00+08:00'
print('public class expiry, deadline, cancellation, city and table tests passed')

