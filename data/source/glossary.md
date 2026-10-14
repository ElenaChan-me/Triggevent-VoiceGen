# Triggevent 読み上げ文 日本語化の用語集

戦闘中にプレイヤーが一瞬で聞き取れる、短い日本語にする。日本の FF14 プレイヤーが普段使う言い方を優先する。

## 基本方針
- 短く。助詞は意味が通る範囲で省略してよい（例: 「散開してから頭割り」より「散開→頭割り」ではなく「散開、そのあと頭割り」も可。読み上げなので記号「→」は使わない）。
- 文末に「〜してください」は付けない。体言止め・命令形の短い言い方（「外へ」「中へ」「塔を踏む」）。
- 読点「、」で区切ってよい（英語のカンマはそのまま「、」）。
- 固有名詞（ボス名・技名）は、原文が英語の技名でも日本語の正式名が確実に分かる場合だけ日本語にする。分からない場合はカタカナ表記にし、note に「技名要確認」と書く。
- ジョブ略称（PLD, WAR など）とロール略称（MT, ST, H1, H2, D1〜D4）、DPS、TH はそのまま。
- 数字はアラビア数字（1, 2, 3）。順番は「1番」「2番」。
- `{...}` の中はプログラムの式。**式はそのまま残す**。ただし式の中の文字列リテラル（'...' や "..."）だけは日本語に訳す。
  - 例: `{real ? 'Real' : 'Fake'}` → `{real ? '本物' : '偽物'}`
  - 例: `Buster on {event.target}` → `{event.target}にタンク強攻撃`
- `{...}` の位置は日本語の語順に合わせて動かしてよい。消したり増やしたりはしない。
- `{...}` にはプレイヤー名・方角・数字・ジョブ名などが入る。プレイヤーが自分のときは「自分」が入る。

## 用語
| 英語 | 日本語 |
| --- | --- |
| Raidwide | 全体攻撃 |
| Big Raidwide | 強い全体攻撃 |
| Multiple Raidwides | 連続全体攻撃 |
| Raidwide with Bleed | 全体攻撃、継続ダメージあり |
| Tankbuster / Buster | タンク強攻撃 |
| Buster on You | 自分にタンク強攻撃 |
| Shared Buster / Tank Stack | タンク頭割り |
| Tank Swap | タンクスイッチ |
| Spread | 散開 |
| Stack / Stacks | 頭割り |
| Partners / Pairs | ペア |
| Light Parties | 4人頭割り |
| Healer Stacks | ヒーラー頭割り |
| Proteans | 扇誘導 |
| Knockback | ノックバック |
| Enrage | 時間切れ |
| Move | 動く |
| Out | 外 |
| In | 中 |
| Middle / Center / Mid | 中央 |
| Out and Spread | 外で散開 |
| Clockwise / CW | 時計回り |
| Counter-Clockwise / CCW | 反時計回り |
| Left / Right | 左 / 右 |
| Front / Back / Behind | 前 / 後ろ / 背後 |
| Sides | 横 |
| Corners | 角 |
| Cardinals / Intercards | 十字 / 斜め |
| North / South / East / West | 北 / 南 / 東 / 西 |
| Northeast / Southeast / Southwest / Northwest | 北東 / 南東 / 南西 / 北西 |
| X Safe | Xが安置 |
| Safe Spot | 安置 |
| Tower | 塔 |
| Take Tower / Soak Tower / Soak | 塔を踏む |
| Avoid Towers | 塔を避ける |
| Tether | 線 |
| No Tether | 線なし |
| Avoid Tethers | 線を避ける |
| Take Tether / Grab Tether | 線を取る |
| Bait | 誘導 |
| Dodge | 避ける |
| Avoid | 避ける |
| Cleanse | エスナ |
| Look Away | 背を向ける |
| Stop / Stop Moving | 止まる |
| Keep Moving | 動き続ける |
| Wait | 待機 |
| Nothing | 何もなし |
| Error | エラー |
| First / Second / Third / Fourth | 1番目 / 2番目 / 3番目 / 4番目 |
| One / Two / Three / Four | 1 / 2 / 3 / 4 |
| Later | 後で（例: Spread Later → 後で散開） |
| then | 、そのあと（例: Spread then Stack → 散開、そのあと頭割り） |
| Supports | タンクヒーラー |
| DPS | DPS |
| Tanks / Healers | タンク / ヒーラー |
| Melee / Ranged | 近接 / 遠隔 |
| Puddle / Puddles | 床 |
| Bait Puddles | 床誘導 |
| Line / Lines | 直線 |
| Cone / Cleave | 扇範囲 / 範囲攻撃 |
| Donut | ドーナツ |
| Gaze | 視線 |
| Orbs | 玉 |
| Flare | フレア |
| Real / Fake | 本物 / 偽物 |
| Debuff | デバフ |
| Short / Long | 短い / 長い |
| Adds | 雑魚 |
| Kill X | Xを倒す |
| Mitigate | 軽減 |
| Heal / Heal to Full | 回復 / 全回復 |
| Invuln | 無敵 |
| Interrupt | 詠唱中断 |
| Jump | ジャンプ |
| Dive | ダイブ |
| Laser | レーザー |
| Rot | 腐敗 |
| Pass | 渡す |
| Swap | 交代 |
| Same / Opposite | 同じ / 反対 |
