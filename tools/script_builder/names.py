import re, json, urllib.request
root=r'C:\Users\patop\Desktop\Workspace\Triggevent-JP\xivdata\src\main\java\gg\xp\xivdata\data'
NUM=r'(?:0x[0-9a-fA-F]+|\d+)L?'
def entries(src):
    body=src[src.index('{')+1:]
    i=0; out=[]
    for m in re.finditer(r'^\s+([A-Z][A-Za-z_0-9]+)\(', body, re.M):
        start=m.end(); depth=1; j=start
        while depth:
            if body[j]=='(': depth+=1
            elif body[j]==')': depth-=1
            j+=1
        out.append((m.group(1), body[start:j-1]))
    return out
cd=open(root+r'\Cooldown.java',encoding='utf-8').read()
cds=[]
for name,args in entries(cd):
    m=re.search(r'CooldownType\.(\w+)\s*,\s*(?:(?:true|false)\s*,\s*)?((?:'+NUM+r'\s*,?\s*)+)', args)
    if not m: continue
    ids=[int(x.rstrip('L'),0) for x in re.findall(NUM, m.group(2))]
    cds.append({'key':name,'type':m.group(1),'ids':ids})
dot=open(root+r'\DotBuff.java',encoding='utf-8').read()
dots=[]
for name,args in entries(dot):
    m=re.match(r'\s*(\w+),\s*"([^"]+)",\s*(.*)', args, re.S)
    if not m: continue
    dots.append({'key':name,'job':m.group(1),'label':m.group(2),'ids':[int(x.rstrip('L'),0) for x in re.findall(NUM, m.group(3))]})
print(len(cds),'cds',len(dots),'dots')
def fetch(sheet, ids):
    out={}
    for i in range(0,len(ids),100):
        chunk=ids[i:i+100]
        url=f"https://v2.xivapi.com/api/sheet/{sheet}?rows={','.join(map(str,chunk))}&fields=Name&language=ja"
        req=urllib.request.Request(url, headers={'User-Agent':'Triggevent-JP voice script builder'})
        data=json.load(urllib.request.urlopen(req))
        for r in data['rows']: out[r['row_id']]=r['fields']['Name']
    return out
an=fetch('Action', sorted({i for c in cds for i in c['ids']}))
sn=fetch('Status', sorted({i for d in dots for i in d['ids']}))
for c in cds: c['ja']=[an.get(i) for i in c['ids']]
for d in dots: d['ja']=[sn.get(i) for i in d['ids']]
json.dump({'cooldowns':cds,'dots':dots},open('game_names.json','w',encoding='utf-8'),ensure_ascii=False,indent=1)
for d in dots: print(d['key'], d['ja'])
print([(c['key'],c['ja']) for c in cds[:15]])
print('missing', [c['key'] for c in cds if not any(c['ja'])])
