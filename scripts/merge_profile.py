"""
把浏览器导出的“AI前沿日报_我的偏好.json”合并成服务器端偏好建议。
不会直接覆盖 config/preferences.json，而是生成 config/preferences_suggested.json 供你确认。
"""
from pathlib import Path
import json, sys

ROOT=Path(__file__).resolve().parents[1]
if len(sys.argv)<2:
    print("用法：python scripts/merge_profile.py AI前沿日报_我的偏好.json")
    raise SystemExit(1)

profile_path=Path(sys.argv[1])
if not profile_path.is_absolute():
    profile_path=Path.cwd()/profile_path

profile=json.loads(profile_path.read_text(encoding="utf-8"))
prefs=json.loads((ROOT/"config/preferences.json").read_text(encoding="utf-8"))
cats=profile.get("categories",{})

for cat,delta in cats.items():
    if cat in prefs.get("category_weights",{}):
        base=prefs["category_weights"][cat]
        prefs["category_weights"][cat]=max(1,min(10,round(base + delta/8)))

prefs["_learning_summary"]={
    "source_preferences":dict(sorted(profile.get("sources",{}).items(),key=lambda x:x[1],reverse=True)[:20]),
    "keyword_preferences":dict(sorted(profile.get("keywords",{}).items(),key=lambda x:x[1],reverse=True)[:30]),
    "interactions":profile.get("interactions",0)
}

out=ROOT/"config/preferences_suggested.json"
out.write_text(json.dumps(prefs,ensure_ascii=False,indent=2),encoding="utf-8")
print("已生成：",out)
