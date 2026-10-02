import pathlib,importlib.util,datetime
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('update',ROOT/'scripts/update.py');u=importlib.util.module_from_spec(spec);spec.loader.exec_module(u)
base={'category':'论坛 / 展会','event_date':u.TODAY.isoformat()}
assert u.event_is_valid(base,{})
assert not u.event_is_valid({**base,'event_date':(u.TODAY-datetime.timedelta(days=1)).isoformat()},{})
assert not u.event_is_valid({**base,'deadline':(datetime.datetime.now(u.TZ)-datetime.timedelta(minutes=1)).isoformat()},{})
assert u.event_is_valid({**base,'deadline':(datetime.datetime.now(u.TZ)+datetime.timedelta(minutes=2)).isoformat()},{})
assert not u.event_is_valid({'category':'论坛 / 展会'},{})
assert u.extract_deadline('报名截止时间：2020年1月1日')[:4]=='2020'
assert u.extract_event_date('活动时间：1月1日')==str(u.TODAY.year)+'-01-01'
print('event availability tests passed')

