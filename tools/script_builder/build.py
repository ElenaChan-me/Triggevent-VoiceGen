"""翻訳済みの読み上げ文から、収録台本のデータ（../script.json）を作る。data/source で実行する。"""
import collections, glob, hashlib, json, os, re

rows = json.load(open('callouts_clean.json', encoding='utf-8'))
names = json.load(open('game_names.json', encoding='utf-8'))
trans = {}
notes = {}
for path in sorted(glob.glob('translated*.json')):
    for t in json.load(open(path, encoding='utf-8')):
        trans[t['en']] = t['ja']
        if t.get('note'):
            notes[t['en']] = t['note']

CONTENTS = [
    # (key, 日本語名, 拡張, 種類)
    ('DMU', 'DMU（絶）', '黄金のレガシー', '絶'),
    ('FRU', '絶もうひとつの未来', '黄金のレガシー', '絶'),
    ('M9S', '至天の座アルカディア零式 ヘビー級1（M9S）', '黄金のレガシー', '零式'),
    ('M10S', '至天の座アルカディア零式 ヘビー級2（M10S）', '黄金のレガシー', '零式'),
    ('M11S', '至天の座アルカディア零式 ヘビー級3（M11S）', '黄金のレガシー', '零式'),
    ('M12S', '至天の座アルカディア零式 ヘビー級4（M12S）', '黄金のレガシー', '零式'),
    ('M5S', '至天の座アルカディア零式 クルーザー級1（M5S）', '黄金のレガシー', '零式'),
    ('M6S', '至天の座アルカディア零式 クルーザー級2（M6S）', '黄金のレガシー', '零式'),
    ('M7S', '至天の座アルカディア零式 クルーザー級3（M7S）', '黄金のレガシー', '零式'),
    ('M8S', '至天の座アルカディア零式 クルーザー級4（M8S）', '黄金のレガシー', '零式'),
    ('M1S', '至天の座アルカディア零式 ライトヘビー級1（M1S）', '黄金のレガシー', '零式'),
    ('M2S', '至天の座アルカディア零式 ライトヘビー級2（M2S）', '黄金のレガシー', '零式'),
    ('M3S', '至天の座アルカディア零式 ライトヘビー級3（M3S）', '黄金のレガシー', '零式'),
    ('M4S', '至天の座アルカディア零式 ライトヘビー級4（M4S）', '黄金のレガシー', '零式'),
    ('M1N', '至天の座アルカディア ライトヘビー級1（M1N）', '黄金のレガシー', 'ノーマル'),
    ('M3N', '至天の座アルカディア ライトヘビー級3（M3N）', '黄金のレガシー', 'ノーマル'),
    ('M4N', '至天の座アルカディア ライトヘビー級4（M4N）', '黄金のレガシー', 'ノーマル'),
    ('DtEx1', '極ヴァリガルマンダ討滅戦（EX1）', '黄金のレガシー', '極'),
    ('DtEx2', '極ゾラージャ討滅戦（EX2）', '黄金のレガシー', '極'),
    ('DtEx3', '極永遠の女王討滅戦（EX3）', '黄金のレガシー', '極'),
    ('DtEx4', '極ゼレニア討滅戦（EX4）', '黄金のレガシー', '極'),
    ('DtEx5', '極ネクロン討滅戦（EX5）', '黄金のレガシー', '極'),
    ('DtEx6', '極ドゥームトレイン討滅戦（EX6）', '黄金のレガシー', '極'),
    ('DtEx7', '極エヌオー討滅戦（EX7）', '黄金のレガシー', '極'),
    ('ByakkoUn', '幻白虎征魂戦', '黄金のレガシー', '幻'),
    ('SuzakuUn', '幻朱雀征魂戦', '黄金のレガシー', '幻'),
    ('SeiryuUn', '幻青龍征魂戦', '黄金のレガシー', '幻'),
    ('TsukuyomiUn', '幻ツクヨミ討滅戦', '黄金のレガシー', '幻'),
    ('ShinryuUn', '幻神龍討滅戦', '黄金のレガシー', '幻'),
    ('WorqorLarDor', 'ヴァリガルマンダ討滅戦', '黄金のレガシー', '討滅戦'),
    ('Everkeep', 'ゾラージャ討滅戦', '黄金のレガシー', '討滅戦'),
    ('Interphos', '永遠の女王討滅戦', '黄金のレガシー', '討滅戦'),
    ('HellOnRails', 'ドゥームトレイン討滅戦', '黄金のレガシー', '討滅戦'),
    ('TheUnmaking', 'エヌオー討滅戦', '黄金のレガシー', '討滅戦'),
    ('Ihuykatumu', 'イフイカ・トゥム', '黄金のレガシー', 'ダンジョン'),
    ('WorqorZormor', 'ウォーコー・ゾーモー', '黄金のレガシー', 'ダンジョン'),
    ('SkydeepCenote', '天深きセノーテ', '黄金のレガシー', 'ダンジョン'),
    ('Vanguard', 'ヴァンガード', '黄金のレガシー', 'ダンジョン'),
    ('Origenics', 'オリジェニクス', '黄金のレガシー', 'ダンジョン'),
    ('Alexandria', 'アレクサンドリア', '黄金のレガシー', 'ダンジョン'),
    ('StrayboroughDeadwalk', 'ストレイバロー・デッドウォーク', '黄金のレガシー', 'ダンジョン'),
    ('Yuweyawata', 'ユウェヤーワータ・フィールドステーション', '黄金のレガシー', 'ダンジョン'),
    ('Underkeep', 'アンダーキープ', '黄金のレガシー', 'ダンジョン'),
    ('MesoTerminal', 'メソ・ターミナル', '黄金のレガシー', 'ダンジョン'),
    ('Mistwake', 'ミストウェイク', '黄金のレガシー', 'ダンジョン'),
    ('CodCar', '暗闇の雲（CoD・アライアンス零式）', '黄金のレガシー', 'アライアンス'),
    ('OmegaProtocol', '絶オメガ検証戦（TOP）', '暁月のフィナーレ', '絶'),
    ('Dragonsong', '絶竜詩戦争（DSR）', '暁月のフィナーレ', '絶'),
    ('P9S', 'パンデモニウム零式：天獄編1（P9S）', '暁月のフィナーレ', '零式'),
    ('P10S', 'パンデモニウム零式：天獄編2（P10S）', '暁月のフィナーレ', '零式'),
    ('P11S', 'パンデモニウム零式：天獄編3（P11S）', '暁月のフィナーレ', '零式'),
    ('P12S', 'パンデモニウム零式：天獄編4（P12S）', '暁月のフィナーレ', '零式'),
    ('P5S', 'パンデモニウム零式：煉獄編1（P5S）', '暁月のフィナーレ', '零式'),
    ('P6S', 'パンデモニウム零式：煉獄編2（P6S）', '暁月のフィナーレ', '零式'),
    ('P7S', 'パンデモニウム零式：煉獄編3（P7S）', '暁月のフィナーレ', '零式'),
    ('P8S', 'パンデモニウム零式：煉獄編4（P8S）', '暁月のフィナーレ', '零式'),
    ('P1S', 'パンデモニウム零式：辺獄編1（P1S）', '暁月のフィナーレ', '零式'),
    ('P2S', 'パンデモニウム零式：辺獄編2（P2S）', '暁月のフィナーレ', '零式'),
    ('P3S', 'パンデモニウム零式：辺獄編3（P3S）', '暁月のフィナーレ', '零式'),
    ('P4S', 'パンデモニウム零式：辺獄編4（P4S）', '暁月のフィナーレ', '零式'),
    ('P9N', 'パンデモニウム：天獄編1（P9N）', '暁月のフィナーレ', 'ノーマル'),
    ('P10N', 'パンデモニウム：天獄編2（P10N）', '暁月のフィナーレ', 'ノーマル'),
    ('P5N', 'パンデモニウム：煉獄編1（P5N）', '暁月のフィナーレ', 'ノーマル'),
    ('P6N', 'パンデモニウム：煉獄編2（P6N）', '暁月のフィナーレ', 'ノーマル'),
    ('P7N', 'パンデモニウム：煉獄編3（P7N）', '暁月のフィナーレ', 'ノーマル'),
    ('P8N', 'パンデモニウム：煉獄編4（P8N）', '暁月のフィナーレ', 'ノーマル'),
    ('ZeromusEx', '極ゼロムス討滅戦（EX7）', '暁月のフィナーレ', '極'),
    ('GolbezEx', '極ゴルベーザ討滅戦（EX6）', '暁月のフィナーレ', '極'),
    ('RubicanteEx', '極ルビカンテ討滅戦（EX5）', '暁月のフィナーレ', '極'),
    ('BarbarEx', '極バルバリシア討滅戦（EX4）', '暁月のフィナーレ', '極'),
    ('EndsingerEx', '極終焉を謳うもの討滅戦（EX3）', '暁月のフィナーレ', '極'),
    ('ASS_Criterion', '異聞シラディハ水道（ヴァリアント・零式）', '暁月のフィナーレ', 'その他'),
    ('UCoB', '絶バハムート討滅戦（UCoB）', '紅蓮のリベレーター', '絶'),
    ('UWU', '絶アルテマウェポン破壊作戦（UWU）', '紅蓮のリベレーター', '絶'),
    ('Odin', 'オーディン討滅戦', '新生エオルゼア', 'その他'),
]
CONTENT_INDEX = {c[0]: i for i, c in enumerate(CONTENTS)}

PH = re.compile(r'\{((?:[^{}]|\{[^{}]*\})*)\}')
QUOTED = re.compile(r"'([^']*)'|\"([^\"]*)\"")

DIRECTION = re.compile(r'safe|where|side|start|corner|card|sector|^dir|from|unsafe|quadrant|location|spot|platform|facing|At$|pos$|Pos$|^kb|tidal|gaze|relNorth|bird|opposite|positive|negative|thordan|monitor|orb|row$|Row$|^in$|^end$|clone|Dir$|^bad$|lightningBait|twoTower', re.I)
PLAYER = re.compile(r'target|buddy|partner|player|stackOn|^stacks?$|swap|nothings|snipers|^fires?|flareTank|confetti|naPlayers|longSpreadOn|otherTarget|defaTarget|stackTarget|targets|^stack$|^buddies$|Tethers$', re.I)
NUMBER = re.compile(r'number|^num|count|order|group|jailnum|towers|dynamisStacks|longshort|color', re.I)


def classify(expr):
    e = expr.strip()
    if QUOTED.search(e):
        return 'choice'
    if NUMBER.search(e):
        return 'number'
    if PLAYER.search(e):
        return 'player'
    if DIRECTION.search(e):
        return 'direction'
    return 'other'


def pid(prefix, text):
    return prefix + '_' + hashlib.sha1(text.encode('utf-8')).hexdigest()[:8]


phrases = {}


def add_phrase(kind, text, content):
    text = text.strip()
    if not text:
        return None
    key = pid({'line': 'L', 'segment': 'S', 'choice': 'C'}[kind], text)
    p = phrases.setdefault(key, {'id': key, 'kind': kind, 'ja': text, 'contents': [], 'uses': 0})
    p['uses'] += 1
    if content not in p['contents']:
        p['contents'].append(content)
    return key


def split_template(ja, content):
    """可変部分を境に分け、固定の部分と選択肢の語を収録フレーズにする。"""
    parts = []
    pos = 0
    for m in PH.finditer(ja):
        lit = ja[pos:m.start()].strip(' 、,')
        if lit:
            parts.append({'type': 'segment', 'id': add_phrase('segment', lit, content), 'ja': lit})
        expr = m.group(1)
        kind = classify(expr)
        slot = {'type': 'slot', 'kind': kind, 'expr': expr.strip()}
        if kind == 'choice':
            slot['choices'] = []
            for q in QUOTED.finditer(expr):
                word = (q.group(1) if q.group(1) is not None else q.group(2)).strip()
                if word:
                    slot['choices'].append({'id': add_phrase('choice', word, content), 'ja': word})
        parts.append(slot)
        pos = m.end()
    lit = ja[pos:].strip(' 、,')
    if lit:
        parts.append({'type': 'segment', 'id': add_phrase('segment', lit, content), 'ja': lit})
    return parts


contents = []
missing = []
by_content = collections.defaultdict(list)
for r in rows:
    by_content[r['content']].append(r)
for key, name, expac, kind in CONTENTS:
    lines = []
    seen = set()
    for r in by_content.get(key, []):
        en = r['tts']
        if not en or not en.strip() or en in seen:
            continue
        seen.add(en)
        ja = trans.get(en)
        if ja is None:
            missing.append(en)
            continue
        line = {'desc': r['description'], 'en': en, 'ja': ja, 'note': notes.get(en, ''), 'off': r['disabled']}
        if PH.search(ja):
            line['parts'] = split_template(ja, key)
        else:
            line['id'] = add_phrase('line', ja, key)
        lines.append(line)
    if lines:
        contents.append({'key': key, 'name': name, 'expac': expac, 'kind': kind, 'lines': lines})

# 部品（方角・数字・自分）
PARTS = {
    'direction': [('part_dir_n', '北'), ('part_dir_ne', '北東'), ('part_dir_e', '東'), ('part_dir_se', '南東'),
                  ('part_dir_s', '南'), ('part_dir_sw', '南西'), ('part_dir_w', '西'), ('part_dir_nw', '北西'),
                  ('part_dir_c', '中央')],
    'number': [(f'part_num_{i}', str(i)) for i in range(1, 9)],
    'player': [('part_you', '自分')],
}

# DoT とリキャスト。ゲームの日本語名をそのまま読み上げるので、名前ごとに1ファイル。
# 使うジョブはゲームデータから決める（jobs.py が作る job_map.json）
job_map = json.load(open('job_map.json', encoding='utf-8'))
dots = []
for d in names['dots']:
    for sid, ja in zip(d['ids'], d['ja']):
        if ja:
            dots.append({'id': f'dot_{sid}', 'ja': ja, 'jobs': job_map['dots'].get(str(sid), [])})
dots.append({'id': 'dot_brd', 'ja': 'DoT', 'jobs': ['BRD'], 'note': '吟遊詩人の DoT はまとめてこの読み上げになる'})
cds = []
seen_cd = set()
for c in names['cooldowns']:
    for aid, ja in zip(c['ids'], c['ja']):
        if ja and aid not in seen_cd:
            seen_cd.add(aid)
            info = job_map['cooldowns'].get(str(aid), {'jobs': [], 'role': False})
            cds.append({'id': f'cd_{aid}', 'ja': ja, 'jobs': info['jobs'], 'role': info['role']})

system = [
    {'id': 'sys_test', 'ja': 'テスト', 'note': '「TTS をテスト」ボタン（原文 Test）'},
]

script = {'contents': contents, 'phrases': phrases, 'parts': PARTS, 'dots': dots, 'cooldowns': cds, 'system': system, 'jobs': job_map['jobs']}
json.dump(script, open(os.path.join('..', 'script.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

kinds = collections.Counter(p['kind'] for p in phrases.values())
slots = collections.Counter(s['kind'] for c in contents for l in c['lines'] for s in l.get('parts', []) if s['type'] == 'slot')
print('contents', len(contents), 'lines', sum(len(c['lines']) for c in contents))
print('phrases', len(phrases), dict(kinds))
print('slots', dict(slots))
print('dots', len(dots), 'cds', len(cds))
print('missing translations', len(missing))
other = collections.Counter(s['expr'] for c in contents for l in c['lines'] for s in l.get('parts', []) if s['type'] == 'slot' and s['kind'] == 'other')
print('other slots', other.most_common(40))
