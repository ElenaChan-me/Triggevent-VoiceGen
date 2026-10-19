"""Triggevent Plus の設定画面に出るコンテンツ名とコールアウトの説明を日本語にする辞書（ja-callouts.tsv）を作る。

使い方（data/source で実行）:
    python ../../tools/script_builder/ui_dictionary.py <出力ファイル> [Triggevent Plus のフォルダ]

コンテンツ名は duty_names.json（ゲームデータの日本語名）から、説明はゲームデータの技名・ステータス名から引く。
訳せないものは辞書に入れず、画面では英語のまま表示される。
"""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

OUT = sys.argv[1]
ROOT = sys.argv[2] if len(sys.argv) > 2 else next(
    (os.path.join('..', '..', '..', n) for n in ('Triggevent-Plus', 'Triggevent-JP') if os.path.isdir(os.path.join('..', '..', '..', n))),
    os.path.join('..', '..', '..', 'Triggevent-Plus'))
CACHE = os.path.join('..', '..', 'work', 'xivapi_names.json')
UA = {'User-Agent': 'Triggevent-Plus UI dictionary builder'}
# 辞書は画面全体に効くので、ボタンなどの一般的な語と同じ技名は訳さない
STOP = {'Test', 'Reset', 'Enable', 'Disable', 'Clear', 'Reload', 'Save', 'Load', 'Close', 'Open', 'Start', 'Stop', 'Delete', 'Edit',
        'Import', 'Export', 'Apply', 'Cancel', 'Add', 'Remove', 'Help', 'Settings', 'Debug', 'Refresh', 'Pull', 'Wipe', 'Enrage'}


def fetch_names():
    if os.path.exists(CACHE):
        with open(CACHE, encoding='utf-8') as f:
            return json.load(f)
    names = {}
    for sheet in ('Action', 'Status'):
        after = None
        while True:
            q = {'fields': 'Name,Name@lang(ja)', 'language': 'en', 'limit': '500'}
            if after is not None:
                q['after'] = str(after)
            url = f'https://v2.xivapi.com/api/sheet/{sheet}?' + urllib.parse.urlencode(q)
            rows = json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60)).get('rows', [])
            if not rows:
                break
            for r in rows:
                en, ja = r['fields'].get('Name'), r['fields'].get('Name@lang(ja)')
                if en and ja and en != ja:
                    names.setdefault(en, ja)
            after = rows[-1]['row_id']
            time.sleep(0.2)
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    with open(CACHE, 'w', encoding='utf-8') as f:
        json.dump(names, f, ensure_ascii=False)
    return names


def known_duty_names():
    path = os.path.join(ROOT, 'xivdata', 'src', 'main', 'java', 'gg', 'xp', 'xivdata', 'data', 'duties', 'KnownDuty.java')
    with open(path, encoding='utf-8') as f:
        src = f.read()
    return {m.group(1): m.group(2) for m in re.finditer(r'^\s*(\w+)\("([^"]*)",', src, re.M)}


# 補足（括弧やコロンの後ろ）によく出る語。全部の語がここにあるときだけ補足も訳す
QUALIFIERS = {
    'on you': '自分', 'not on you': '自分以外', 'you': '自分', 'other': 'ほか', 'others': 'ほか', 'tank': 'タンク', 'tanks': 'タンク',
    'healer': 'ヒーラー', 'healers': 'ヒーラー', 'dps': 'DPS', 'support': 'タンクヒーラー', 'supports': 'タンクヒーラー',
    'left': '左', 'right': '右', 'front': '前', 'back': '後ろ', 'behind': '背後', 'in': '中', 'out': '外', 'side': '横', 'sides': '横',
    'north': '北', 'south': '南', 'east': '東', 'west': '西', 'middle': '中央', 'center': '中央',
    'delayed': '遅延', 'initial': '最初', 'first': '1回目', 'second': '2回目', 'third': '3回目', 'fourth': '4回目', 'final': '最後',
    'followup': '続き', 'follow-up': '続き', 'unknown': '不明', 'soon': 'まもなく', 'stack': '頭割り', 'spread': '散開',
    'clones': '分身', 'clone': '分身', 'blue': '青', 'red': '赤', 'green': '緑', 'yellow': '黄', 'purple': '紫',
    'fire': '炎', 'ice': '氷', 'lightning': '雷', 'water': '水', 'wind': '風', 'earth': '土', 'light': '光', 'dark': '闇',
    'short': '短', 'long': '長', 'near': '近', 'far': '遠', 'cw': '時計回り', 'ccw': '反時計回り', 'cast': '詠唱', 'hit': '命中',
}


def qualifier(text):
    parts = [p.strip() for p in text.split(',')]
    out = []
    for p in parts:
        ja = QUALIFIERS.get(p.lower())
        if ja is None:
            return text
        out.append(ja)
    return '、'.join(out)


def describe(desc, names):
    """説明（多くは技名）を日本語にする。「技名: 補足」「技名 (補足)」は技名を訳し、補足は分かる語だけなら訳す。"""
    if desc in STOP or len(desc) < 3:
        return None
    if desc in names:
        return names[desc]
    m = re.match(r'^([^():]+?): ([^()]+)$', desc)
    if m and m.group(1) in names and m.group(1) not in STOP:
        return names[m.group(1)] + '：' + qualifier(m.group(2))
    m = re.match(r'^([^():]+?) \(([^()]+)\)$', desc)
    if m and m.group(1) in names and m.group(1) not in STOP:
        return names[m.group(1)] + '（' + qualifier(m.group(2)) + '）'
    return None


def main():
    names = fetch_names()
    with open('callouts_clean.json', encoding='utf-8') as f:
        rows = json.load(f)
    with open('duty_names.json', encoding='utf-8') as f:
        duty_ja = {d['key']: d['name'] for d in json.load(f)}
    duty_en = known_duty_names()
    entries = {}
    # コンテンツ一覧に出る KnownDuty の名前
    for key, en in duty_en.items():
        if key in duty_ja and en != duty_ja[key]:
            entries[en] = duty_ja[key]
    # コールアウトの設定のまとまり（@CalloutRepo の name）。略称はそのまま後ろに残す
    for r in rows:
        repo, duty = r.get('repo'), r.get('duty')
        if repo and duty in duty_ja and repo not in entries:
            entries[repo] = duty_ja[duty] if ' ' in repo else f'{duty_ja[duty]}（{repo}）'
    described = 0
    for r in rows:
        desc = (r.get('description') or '').strip()
        if not desc or desc in entries:
            continue
        ja = describe(desc, names)
        if ja:
            entries[desc] = ja
            described += 1
    with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        f.write('# 自動生成（tools/script_builder/ui_dictionary.py）。手で直す場合は ja.tsv に書く\n')
        for en in sorted(entries):
            if '\t' in en or '\n' in en:
                continue
            f.write(f'{en}\t{entries[en]}\n')
    print(f'{OUT}: {len(entries)} 件（うち説明 {described} 件）')


if __name__ == '__main__':
    main()
