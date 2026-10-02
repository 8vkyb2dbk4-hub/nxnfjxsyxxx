from pathlib import Path
import sys,json
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'scripts'))
import update
sources=json.loads((root/'config/sources.json').read_text(encoding='utf-8'))['sources']
video=[s for s in sources if s.get('video_provider')]
assert len(video)==14
assert sum(s['category_priorities']['AI 影视']==5 for s in video)==10
hf=next(s for s in video if s['video_provider']=='Hugging Face')
assert hf['priority']==5 and hf['category_priorities']['AI 影视']==4
prefs=update.jload(root/'config/preferences.json',{})
base=update.score_item('Example','',hf,'AI 影视',prefs,{},'high')
for aliases in prefs['video_keyword_boost']['concepts'].values():
 for alias in aliases:
  assert update.score_item(alias,'',hf,'AI 影视',prefs,{},'high')>=base+8,alias
plain=dict(prefs,video_keyword_boost={})
all_words=' '.join(prefs['video_keyword_boost']['concepts'])
assert update.score_item(all_words,'',hf,'AI 影视',prefs,{},'high')-update.score_item(all_words,'',hf,'AI 影视',plain,{},'high')==40
assert update.score_item(all_words,'',hf,'AI 绘画',prefs,{},'high')==update.score_item(all_words,'',hf,'AI 绘画',plain,{},'high')
print('Video source priorities, bilingual boosts, cap and category isolation passed')
