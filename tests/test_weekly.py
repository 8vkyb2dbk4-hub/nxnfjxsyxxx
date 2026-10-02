import importlib.util,pathlib,tempfile,json
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('upd',ROOT/'scripts/update.py')
u=importlib.util.module_from_spec(spec);spec.loader.exec_module(u)
with tempfile.TemporaryDirectory() as tmp:
    u.ROOT=pathlib.Path(tmp)
    (u.ROOT/'data/archive').mkdir(parents=True)
    (u.ROOT/'data/archive/index.json').write_text('[{"date":"2026-10-02"}]')
    (u.ROOT/'data/archive/2026-10-02.json').write_text(json.dumps({'top3':[{'id':'a','title':'AI model','url':'https://example.com','score':100}]}))
    u.build_weekly()
    assert json.loads((u.ROOT/'data/weekly.json').read_text(encoding='utf-8'))['items'][0]['id']=='a'
print('weekly archive regression passed')

