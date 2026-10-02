from __future__ import annotations
from pathlib import Path
from collections import defaultdict, Counter
import json, re, datetime, math

ROOT = Path(__file__).resolve().parents[1]

def jload(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default

def norm(s):
    return re.sub(r"\s+"," ",str(s or "")).strip()

def date_of_issue(issue):
    try:
        return datetime.date.fromisoformat(issue.get("date",""))
    except Exception:
        return None

def flatten_issue(issue):
    rows=[]
    for x in issue.get("top3",[]):
        rows.append(dict(x))
    for sec in issue.get("sections",[]):
        for x in sec.get("items",[]):
            y=dict(x)
            y.setdefault("category",sec.get("name",""))
            rows.append(y)
    return rows

def topic_hits(text, aliases):
    t=text.lower()
    hits=[]
    for topic,kws in aliases.items():
        if any(k.lower() in t for k in kws):
            hits.append(topic)
    return hits

def load_history(lookback_days):
    archive_dir=ROOT/"data/archive"
    rows=[]
    cutoff=datetime.date.today()-datetime.timedelta(days=lookback_days-1)
    for p in sorted(archive_dir.glob("*.json")):
        issue=jload(p,{})
        d=date_of_issue(issue)
        if not d or d<cutoff:
            continue
        for item in flatten_issue(issue):
            item["_issue_date"]=d.isoformat()
            rows.append(item)
    return rows

def build_signals(rows, cfg):
    aliases=cfg.get("topic_aliases",{})
    topic_days=defaultdict(set)
    topic_mentions=Counter()
    topic_scores=defaultdict(list)
    topic_sources=defaultdict(set)
    recent_counts=Counter()
    baseline_counts=Counter()
    source_days=defaultdict(set)
    source_mentions=Counter()

    today=max([datetime.date.fromisoformat(x["_issue_date"]) for x in rows], default=datetime.date.today())
    rising_days=int(cfg.get("rising_window_days",3))
    baseline_days=int(cfg.get("baseline_window_days",7))
    recent_cut=today-datetime.timedelta(days=rising_days-1)
    baseline_cut=today-datetime.timedelta(days=baseline_days-1)

    urgent=[]
    for x in rows:
        d=datetime.date.fromisoformat(x["_issue_date"])
        text=" ".join([x.get("title",""),x.get("summary",""),x.get("why",""),x.get("category","")])
        topics=topic_hits(text,aliases)
        for topic in topics:
            topic_days[topic].add(d.isoformat())
            topic_mentions[topic]+=1
            topic_scores[topic].append(float(x.get("score") or 0))
            topic_sources[topic].add(x.get("source",""))
            if d>=recent_cut:
                recent_counts[topic]+=1
            if d>=baseline_cut:
                baseline_counts[topic]+=1

        src=x.get("source","")
        if src:
            source_days[src].add(d.isoformat())
            source_mentions[src]+=1

        dl=x.get("deadline")
        if dl:
            try:
                raw=str(dl).replace("T24:00:00","T23:59:59")
                deadline=datetime.datetime.fromisoformat(raw)
                now=datetime.datetime.now(deadline.tzinfo) if deadline.tzinfo else datetime.datetime.now()
                hours=(deadline-now).total_seconds()/3600
                if 0 < hours <= float(cfg.get("urgent_deadline_hours",36)):
                    urgent.append({
                        "id":x.get("id"),
                        "title":x.get("title"),
                        "source":x.get("source"),
                        "url":x.get("url"),
                        "deadline":dl,
                        "hours_left":round(hours,1),
                        "category":x.get("category","论坛 / 展会")
                    })
            except Exception:
                pass

    min_days=int(cfg.get("minimum_unique_days_for_trend",3))
    min_mentions=int(cfg.get("minimum_mentions_for_trend",3))
    ratio_threshold=float(cfg.get("rising_ratio_threshold",1.8))

    topics=[]
    for topic,count in topic_mentions.items():
        days=len(topic_days[topic])
        if days<min_days or count<min_mentions:
            continue

        recent=recent_counts[topic]
        baseline=baseline_counts[topic]
        prior=max(0,baseline-recent)
        recent_rate=recent/max(1,rising_days)
        prior_window=max(1,baseline_days-rising_days)
        prior_rate=prior/prior_window
        ratio=(recent_rate+0.15)/(prior_rate+0.15)

        if ratio>=ratio_threshold and recent>=2:
            direction="升温"
        elif ratio<=0.65 and prior>=2:
            direction="降温"
        else:
            direction="持续"

        strength = min(100, round(
            count*7 + days*6 + len(topic_sources[topic])*4 + min(25,max(0,(ratio-1)*15))
        ))
        topics.append({
            "topic":topic,
            "mentions":count,
            "unique_days":days,
            "sources":len(topic_sources[topic]),
            "recent_mentions":recent,
            "baseline_mentions":baseline,
            "velocity_ratio":round(ratio,2),
            "direction":direction,
            "strength":strength,
            "avg_score":round(sum(topic_scores[topic])/max(1,len(topic_scores[topic])),1)
        })

    topics.sort(key=lambda x:(x["direction"]=="升温",x["strength"],x["mentions"]), reverse=True)
    topics=topics[:int(cfg.get("hot_topics_limit",12))]

    sources=[]
    for src,count in source_mentions.items():
        days=len(source_days[src])
        if count<2:
            continue
        sources.append({"source":src,"mentions":count,"unique_days":days})
    sources.sort(key=lambda x:(x["mentions"],x["unique_days"]), reverse=True)
    sources=sources[:int(cfg.get("source_velocity_limit",10))]

    unique_days=len(set(x["_issue_date"] for x in rows))
    enough_history=unique_days>=min_days

    return {
        "generated_at":datetime.datetime.now().isoformat(timespec="seconds"),
        "history_days":unique_days,
        "enough_history":enough_history,
        "minimum_days_needed":min_days,
        "topics":topics if enough_history else [],
        "source_velocity":sources if enough_history else [],
        "urgent":sorted(urgent,key=lambda x:x["hours_left"]),
        "message":(
            "趋势判断基于多日重复信号，不把单日热词当趋势。"
            if enough_history else
            f"正在积累趋势样本：目前 {unique_days} 天，至少需要 {min_days} 天后才开始判断升温/降温。"
        )
    }

def build():
    cfg=jload(ROOT/"config/trends.json",{})
    rows=load_history(int(cfg.get("lookback_days",14)))
    out=build_signals(rows,cfg)
    (ROOT/"data/signals.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
    return out

if __name__=="__main__":
    out=build()
    print(json.dumps({"history_days":out["history_days"],"topics":len(out["topics"]),"urgent":len(out["urgent"])},ensure_ascii=False))
