"""Triggevent JP のソースから読み上げ（TTS）文を抜き出し、callouts_clean.json を作る。

使い方（data/source で実行）:
    python ../../tools/script_builder/extract.py callouts_clean.json <Triggevent-JP のフォルダ>
"""
import collections
import json
import os
import re
import sys

ROOT = sys.argv[2] if len(sys.argv) > 2 else os.path.join('..', '..', '..', 'Triggevent-JP')
CALL = re.compile(r'(new\s+ModifiableCallout\s*(?:<[^>]*>)?|ModifiableCallout\s*\.\s*(?:<[^>]*>\s*)?(\w+))\s*\(')
REPO = re.compile(r'@CalloutRepo\(\s*name\s*=\s*"([^"]*)"(?:\s*,\s*duty\s*=\s*KnownDuty\.(\w+))?')
# 呼び出しのタイミングを決めるだけで、読み上げ文を持たないファクトリー
HELPERS = {'expiresIn', 'durationExpiry', 'durationExpiryPlusDefaultLinger', 'durationExpiryPlusLingerTime', 'getModified'}


def parse_args(src, start):
    """括弧の対応を見ながら引数を分ける。文字列リテラルはそのまま返す。"""
    depth, i, args, cur = 1, start, [], []
    while i < len(src) and depth > 0:
        c = src[i]
        if c == '"':
            j = i + 1
            while src[j] != '"':
                j += 2 if src[j] == '\\' else 1
            cur.append(src[i:j + 1])
            i = j + 1
            continue
        if c in '([{':
            depth += 1
        elif c in ')]}':
            depth -= 1
            if depth == 0:
                break
        if c == ',' and depth == 1:
            args.append(''.join(cur).strip())
            cur = []
        else:
            cur.append(c)
        i += 1
    args.append(''.join(cur).strip())
    return args


def literal(arg):
    """"a" + "b" のような単純な連結までは文字列にする。それ以外は None。"""
    parts = re.findall(r'"((?:[^"\\]|\\.)*)"', arg)
    rest = re.sub(r'"((?:[^"\\]|\\.)*)"', '', arg).replace('+', '').strip()
    if not parts or rest:
        return None
    return ''.join(p.encode().decode('unicode_escape') if '\\' in p else p for p in parts)


rows = []
for dirpath, _, files in os.walk(ROOT):
    if os.sep + 'test' + os.sep in dirpath or os.sep + 'target' + os.sep in dirpath:
        continue
    for name in files:
        if not name.endswith('.java'):
            continue
        path = os.path.join(dirpath, name)
        src = open(path, encoding='utf-8', errors='replace').read()
        repos = REPO.findall(src)
        for m in CALL.finditer(src):
            factory = m.group(2) or 'new'
            if factory in HELPERS:
                continue
            line_start = src.rfind('\n', 0, m.start()) + 1
            if src[line_start:m.start()].lstrip().startswith('//'):
                continue
            lits = [literal(a) for a in parse_args(src, m.end())]
            rel = os.path.relpath(path, ROOT).replace('\\', '/')
            repo = repos[0][0] if repos else None
            duty = repos[0][1] if repos and repos[0][1] else None
            rows.append({
                'module': rel.split('/src/')[0],
                'file': rel,
                'class': name[:-5],
                'line': src.count('\n', 0, m.start()) + 1,
                'factory': factory,
                'description': lits[0] if lits else None,
                'tts': lits[1] if len(lits) > 1 else None,
                'text': lits[2] if len(lits) > 2 and m.group(2) is None else None,
                'disabled': '.disabledByDefault()' in src[m.end():src.find(';', m.end())],
                'repo': repo,
                'duty': duty,
                'content': duty or ('General' if repo else name[:-5]),
            })

json.dump(rows, open(sys.argv[1], 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('callouts', len(rows), '/ without literal tts', sum(1 for r in rows if r['tts'] is None))
print(collections.Counter(r['module'] for r in rows).most_common())
