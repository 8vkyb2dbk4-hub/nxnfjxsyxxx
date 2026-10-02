import importlib.util, pathlib, datetime, json

ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("upd", ROOT/"scripts/update.py")
upd=importlib.util.module_from_spec(spec)
spec.loader.exec_module(upd)

def test_canonical_url():
    a=upd.canonical_url("https://example.com/a/?utm_source=x&foo=1")
    assert a=="https://example.com/a?foo=1"

def test_similarity():
    a="OpenAI 发布全新 Agent 工作流"
    b="OpenAI：发布全新的 Agent 工作流程"
    assert upd.title_similarity(a,b) > 0.75

def test_date_parser():
    assert upd.parse_isoish("2026-10-02T09:00:00Z")=="2026-10-02"
    assert upd.parse_isoish("2026年10月2日")=="2026-10-02"

def test_cluster_prefers_reliable():
    rows=[
        {"title":"某模型正式发布","url":"https://a.com/1","source":"转载站","source_reliability":5,"date_confidence":"high","score":120},
        {"title":"某模型正式发布！","url":"https://official.com/1","source":"官方","source_reliability":10,"date_confidence":"high","score":110},
    ]
    out=upd.cluster_duplicates(rows,0.80)
    assert len(out)==1
    assert out[0]["source"]=="官方"
    assert out[0]["alternatives"][0]["source"]=="转载站"

if __name__=="__main__":
    test_canonical_url()
    test_similarity()
    test_date_parser()
    test_cluster_prefers_reliable()
    print("all tests passed")
