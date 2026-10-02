from pathlib import Path
import shutil, os, json
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'dist'
OUT.mkdir(exist_ok=True)
for name in ['index.html','app.js','translation.js','styles.css','dashboard.css','sync.js','sync-core.js','sw.js','manifest.webmanifest','assets','config','data','editions']:
    src=ROOT/name; dst=OUT/name
    if src.is_dir(): shutil.copytree(src,dst,dirs_exist_ok=True)
    else: shutil.copy2(src,dst)
(OUT/'.nojekyll').touch()
print('Static site built:',OUT)

url=os.environ.get('SUPABASE_URL','').strip()
key=os.environ.get('SUPABASE_ANON_KEY','').strip()
if url or key:
    if not url.startswith('https://') or not key:
        raise SystemExit('Both HTTPS SUPABASE_URL and public SUPABASE_ANON_KEY required')
    if key.startswith('sb_secret_'):
        raise SystemExit('Private Supabase keys must never enter the frontend')
    cfg=json.loads((OUT/'config/sync.json').read_text(encoding='utf-8'))
    cfg.update(enabled=True,supabaseUrl=url,anonKey=key)
    (OUT/'config/sync.json').write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding='utf-8')
