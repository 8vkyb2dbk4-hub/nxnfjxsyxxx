import pathlib,importlib.util
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('update',ROOT/'scripts/update.py');u=importlib.util.module_from_spec(spec);spec.loader.exec_module(u)
assert u.extract_event_city('主办：上海实验室；地点：杭州市西湖区')=='杭州'
assert u.extract_event_city('主办：上海实验室；地点：北京市海淀区')=='北京'
assert u.extract_event_city('上海实验室发布 AI 新闻')==''
assert u.extract_event_city('Venue: Hangzhou, China')=='杭州'
assert u.extract_event_city('地点：线上直播')==''
print('event city evidence tests passed')

