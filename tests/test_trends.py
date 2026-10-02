import importlib.util, pathlib, datetime

ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("trends", ROOT/"scripts/trends.py")
tr=importlib.util.module_from_spec(spec)
spec.loader.exec_module(tr)

def test_insufficient_history():
    cfg={"minimum_unique_days_for_trend":3,"minimum_mentions_for_trend":3,"topic_aliases":{"Agent":["agent"]}}
    rows=[
      {"_issue_date":"2026-10-01","title":"Agent update","summary":"","why":"","category":"","source":"A","score":100}
    ]
    out=tr.build_signals(rows,cfg)
    assert out["enough_history"] is False
    assert out["topics"]==[]

def test_rising_trend():
    cfg={
      "minimum_unique_days_for_trend":3,
      "minimum_mentions_for_trend":3,
      "rising_window_days":3,
      "baseline_window_days":7,
      "rising_ratio_threshold":1.4,
      "hot_topics_limit":10,
      "source_velocity_limit":10,
      "urgent_deadline_hours":36,
      "topic_aliases":{"Agent":["agent"]}
    }
    rows=[]
    for d in ["2026-09-28","2026-09-30","2026-10-01","2026-10-02"]:
      rows.append({"_issue_date":d,"title":"Agent capability update","summary":"","why":"","category":"","source":"A","score":100})
    out=tr.build_signals(rows,cfg)
    assert out["enough_history"] is True
    assert len(out["topics"])==1
    assert out["topics"][0]["topic"]=="Agent"

def test_urgent_deadline():
    now=datetime.datetime.now().astimezone()
    dl=now+datetime.timedelta(hours=5)
    cfg={"minimum_unique_days_for_trend":3,"minimum_mentions_for_trend":3,"urgent_deadline_hours":36,"topic_aliases":{}}
    rows=[{"_issue_date":now.date().isoformat(),"title":"论坛报名","summary":"","why":"","category":"论坛 / 展会","source":"X","score":90,"deadline":dl.isoformat(),"url":"https://x","id":"1"}]
    out=tr.build_signals(rows,cfg)
    assert len(out["urgent"])==1

if __name__=="__main__":
    test_insufficient_history()
    test_rising_trend()
    test_urgent_deadline()
    print("trend tests passed")
