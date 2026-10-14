"""script.json と template.html から、台本の確認用ページ（1ファイルの HTML）を作る。data/source で実行する。"""
import json
import sys
from pathlib import Path

here = Path(__file__).resolve().parent
data = json.loads(Path('..', 'script.json').read_text(encoding='utf-8'))
for content in data['contents']:
    for line in content['lines']:
        # ページの容量を減らすため、空の項目は送らない
        if not line.get('note'):
            line.pop('note', None)
        if not line.get('off'):
            line.pop('off', None)
data['phrases'] = {k: {'kind': v['kind']} for k, v in data['phrases'].items()}
# 台本の文に「</」があっても <script> が途中で閉じないようにする
payload = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('</', r'<\/')
page = (here / 'template.html').read_text(encoding='utf-8').replace('/*DATA*/', payload)
out = Path(sys.argv[1] if len(sys.argv) > 1 else 'voice-script.html')
out.write_text(page, encoding='utf-8', newline='\n')
print('wrote', out)
