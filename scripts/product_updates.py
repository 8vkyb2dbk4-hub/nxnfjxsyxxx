"""Read individual dated release notes, never use a listing's overall date."""
import datetime,re,hashlib
MONTHS={name:i for i,name in enumerate(['January','February','March','April','May','June','July','August','September','October','November','December'],1)}
def parse_date(text,year=None):
    m=re.search(r'(20\d{2})[-./](\d{1,2})[-./](\d{1,2})',text)
    if m:
        try:return datetime.date(*map(int,m.groups())).isoformat()
        except ValueError:return None
    m=re.search(r'([A-Za-z]+)\s+(\d{1,2})(?:,?\s+(20\d{2}))?',text)
    if m:
        month=next((i for name,i in MONTHS.items() if name.lower().startswith(m[1].lower())),None)
        if month and (m[3] or year):
            try:return datetime.date(int(m[3] or year),month,int(m[2])).isoformat()
            except ValueError:pass
    return None

def parse_changelog(soup,src):
    main=soup.find('main') or soup;rows=[];year=None
    for heading in main.find_all(['h2','h3']):
        title=heading.get_text(' ',strip=True)
        ym=re.search(r'\b(20\d{2})\b',title)
        if ym and any(name.lower() in title.lower() for name in MONTHS):year=int(ym[1]);continue
        date=parse_date(title,year)
        node=heading;body='';anchor=heading.get('id')
        if date:
            chunks=[]
            for sib in heading.next_siblings:
                if getattr(sib,'name',None) in ['h2','h3']:break
                if hasattr(sib,'get_text'):chunks.append(sib.get_text(' ',strip=True))
            body=' '.join(chunks);title=src['name']+' · '+date+' 更新'
        else:
            for _ in range(3):
                node=node.parent
                if node is None:break
                if len(node.find_all(['h2','h3']))>1:break
                text=node.get_text(' ',strip=True)
                date=parse_date(text)
                if date:
                    body=text;anchor=anchor or node.get('id');break
        if not date or not body:continue
        fragment=anchor or 'update-'+hashlib.sha1((date+title).encode()).hexdigest()[:10]
        rows.append({'title':title,'published_at':date,'summary':body[:1400],'url':src['url'].split('#')[0]+'#'+fragment})
    return rows[:40]

