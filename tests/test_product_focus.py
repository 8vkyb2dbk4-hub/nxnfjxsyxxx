from pathlib import Path
import sys,json
sys.path.insert(0,str(Path('outputs/ai-frontier-daily/scripts').resolve()))
import update,product_updates
from bs4 import BeautifulSoup
prefs=update.jload(update.ROOT/'config/preferences.json',{})
for text in ['Meshy 7 model update','Hunyuan3D new model','Codex release','Nano Banana update','Unity 6 update','Godot update','World Labs Marble update']:
 assert update.classify(text)=='游戏与 3D',text
for text in ['即梦更新','豆包更新','DeepSeek update','LibTV update','Hailuo model update']:
 assert update.classify(text)=='AI 影视',text
assert not update.product_match('community','unity')
assert update.classify('Codex 公开课论坛报名',['论坛 / 展会'])=='论坛 / 展会'
soup=BeautifulSoup('<main><h2>September 2026</h2><h3>Sep 29</h3><p>Added meshy-7.1</p><h3>Sep 28</h3><p>Fixed export</p></main>','html.parser')
rows=product_updates.parse_changelog(soup,{'name':'Meshy','url':'https://docs.meshy.ai/en/api/changelog'})
assert rows[0]['published_at']=='2026-09-29' and '7.1' in rows[0]['summary']
assert rows[0]['url']!=rows[1]['url']
assert product_updates.parse_changelog(BeautifulSoup('<main><h2>New model</h2><p>Available now</p></main>','html.parser'),{'name':'X','url':'https://example.com'})==[]
print('product focus, word boundaries and dated changelog tests passed')

