from __future__ import annotations
import os, json, requests

SYSTEM = """你是一名面向忙碌创作者的AI资讯编辑。
只做信息压缩，不夸张，不制造结论。
输出JSON，字段固定为 summary、why、action。
summary：1-2句说明发生了什么。
why：根据原文列出具体关注重点和已明确的新增、改进或变化；不要写“看它能否”等假设建议。原文未说明更新时明确标注，不得编造。
action：只能从“今天看”“建议收藏”“有空试一下”“扫一眼即可”“今天决定是否报名”中选择。
"""

def configured():
    return bool(os.getenv("AI_BRIEF_LLM_ENDPOINT") and os.getenv("AI_BRIEF_LLM_API_KEY"))

def rewrite(item: dict) -> dict:
    """兼容常见 Chat Completions 风格接口。失败时原样返回。"""
    if not configured():
        return item
    endpoint = os.getenv("AI_BRIEF_LLM_ENDPOINT","").rstrip("/")
    key = os.getenv("AI_BRIEF_LLM_API_KEY","")
    model = os.getenv("AI_BRIEF_LLM_MODEL","")
    payload = {
        "model": model,
        "messages": [
            {"role":"system","content":SYSTEM},
            {"role":"user","content":json.dumps({
                "title":item.get("title"),
                "source":item.get("source"),
                "category":item.get("category"),
                "raw_summary":item.get("summary"),
                "deadline":item.get("deadline"),
                "score":item.get("score")
            }, ensure_ascii=False)}
        ],
        "temperature": 0.2,
        "response_format": {"type":"json_object"}
    }
    try:
        r = requests.post(
            endpoint,
            headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"},
            json=payload,
            timeout=35
        )
        r.raise_for_status()
        data = r.json()
        content = data["choices"][0]["message"]["content"]
        out = json.loads(content)
        for k in ("summary","why","action"):
            if out.get(k):
                item[k] = str(out[k]).strip()
        return item
    except Exception:
        return item

