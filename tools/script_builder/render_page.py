"""script.json と template.html から、台本の確認用ページ（1ファイルの HTML）を作る。data/source で実行する。"""
import io
import json
import os
import sys

here = os.path.dirname(os.path.abspath(__file__))
data = json.load(open(os.path.join('..', 'script.json'), encoding='utf-8'))
for content in data['contents']:
    for line in content['lines']:
        # ページの容量を減らすため、空の項目は送らない
        if not line.get('note'):
            line.pop('note', None)
        if not line.get('off'):
            line.pop('off', None)
data['phrases'] = {k: {'kind': v['kind']} for k, v in data['phrases'].items()}
payload = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('</', '<\/')
page = io.open(os.path.join(here, 'template.html'), encoding='utf-8').read().replace('/*DATA*/', payload)
out = sys.argv[1] if len(sys.argv) > 1 else 'voice-script.html'
io.open(out, 'w', encoding='utf-8', newline='\n').write(page)
print('wrote', out)
