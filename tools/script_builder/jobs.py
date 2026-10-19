"""DoT・リキャストの読み上げを、使うジョブ・クラスごとに分ける。ゲームデータ（XIVAPI）の ClassJob / ClassJobCategory を使う。"""
import json, urllib.request

UA = {'User-Agent': 'Triggevent-Plus voice script builder'}


def get(url):
    return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA)))


def rows(sheet, ids, fields):
    out = {}
    ids = sorted(set(ids))
    for i in range(0, len(ids), 100):
        chunk = ids[i:i + 100]
        data = get(f"https://v2.xivapi.com/api/sheet/{sheet}?rows={','.join(map(str, chunk))}&fields={fields}&language=ja")
        for r in data['rows']:
            out[r['row_id']] = r['fields']
    return out


# 戦闘職（クラス・ジョブ）。ClassJob 1〜42 から、ギャザラー・クラフター（ClassJobCategory 33/32）を除く
cj = rows('ClassJob', range(1, 43), 'Name,Abbreviation,ClassJobParent.Abbreviation,Role,ClassJobCategory,JobIndex')
combat = {}
for rid, f in cj.items():
    cat = f['ClassJobCategory']['value']
    if cat not in (30, 31):  # 30=戦闘職クラス、31=戦闘職ジョブ
        continue
    abbr = f['Abbreviation']
    parent = f['ClassJobParent']['fields']['Abbreviation'] if f['ClassJobParent'].get('fields') else abbr
    combat[abbr] = {'abbr': abbr, 'name': f['Name'], 'parent': parent, 'role': f['Role'], 'isJob': f['JobIndex'] > 0, 'id': rid}

# ジョブと、その元になったクラスの組を作る（例: PLD ← GLA）。クラスの無いジョブは単独
jobs = [j for j in combat.values() if j['isJob']]
for j in jobs:
    base = combat.get(j['parent'])
    j['className'] = base['name'] if base and base['abbr'] != j['abbr'] else None
name_to_abbr = {v['name']: k for k, v in combat.items()}


def jobs_in_category(text):
    """「剣術士 斧術士 ナイト …」をジョブ略称の集合にする。クラスは、そのクラスから転職するジョブに広げる。"""
    result = set()
    for word in text.split():
        abbr = name_to_abbr.get(word)
        if not abbr:
            continue
        if combat[abbr]['isJob']:
            result.add(abbr)
        else:
            result.update(j['abbr'] for j in jobs if j['parent'] == abbr)
    return result


names = json.load(open('game_names.json', encoding='utf-8'))
action_ids = [i for c in names['cooldowns'] for i in c['ids']]
acts = rows('Action', action_ids, 'Name,ClassJob.Abbreviation,ClassJobCategory.Name,IsRoleAction')
cd_jobs = {}
for aid, f in acts.items():
    cat = f['ClassJobCategory'].get('fields', {}).get('Name', '')
    js = jobs_in_category(cat)
    own = f['ClassJob'].get('fields', {}).get('Abbreviation')
    if not js and own in combat:
        js = {own} if combat[own]['isJob'] else {j['abbr'] for j in jobs if j['parent'] == own}
    cd_jobs[aid] = {'jobs': sorted(js), 'role': bool(f['IsRoleAction'])}

dot_jobs = {}
for d in names['dots']:
    js = {d['job']} if d['job'] in combat else set()
    for sid in d['ids']:
        dot_jobs[sid] = sorted(js)

ROLE = {1: 'タンク', 2: '近接DPS', 3: '遠隔DPS', 4: 'ヒーラー'}
job_list = sorted(jobs, key=lambda j: (j['role'], j['id']))
out = {
    'jobs': [{'abbr': j['abbr'], 'name': j['name'], 'className': j['className'], 'role': ROLE.get(j['role'], 'その他')} for j in job_list],
    'cooldowns': cd_jobs,
    'dots': dot_jobs,
}
json.dump(out, open('job_map.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(len(job_list), 'jobs')
print(sum(1 for v in cd_jobs.values() if not v['jobs']), 'cooldown actions without job')
print([j['abbr'] for j in job_list])
