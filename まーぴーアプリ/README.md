# まーぴーアプリ（事前作成のベース）

音声で話せるカスタマーサポートbot「まーぴー」（青い小鳥）。
JMC役員ハンズオン「生成AI」パートの**ベースアプリ**です。参加者はこの動くまーぴーを、
Claude Code に話し言葉で頼んで**自分流にアレンジ**します（方言・多言語・動き＝バイブコーディング）。

## 構成

| ファイル | 役割 |
|---|---|
| `main.py` | アプリ本体（Streamlit ＋ Realtime API ＋ WebRTC） |
| `img_bird.png` | まーぴー（青い小鳥）の立ち絵 |
| `requirements.txt` | 依存（streamlit / requests / python-dotenv） |
| `.env.example` | APIキーのサンプル（`.env` にコピーして使う） |

> 実装仕様の詳細は `../../RealTimeAPI/仕様設計書.md`（ベース実装の正）を参照。

## 起動（最短手順）

> Python は **3.11**。Community Cloud にデプロイする場合も Advanced settings で 3.11 を選択。

```bash
pip install -r requirements.txt
cp .env.example .env          # .env に OpenAI APIキーを記入
streamlit run main.py
```

1. ブラウザが開く
2. サイドバーで声を選び「セッション開始 / 再発行」を押す（短命トークン発行）
3. 「🎤 まーぴーと話す」→ マイクを許可
4. 話しかける → まーぴーが音声で応答し、声に合わせて動く

> マイクは HTTPS または `localhost` が必要（ブラウザ制約）。Community Cloud は HTTPS で可。

## アレンジ（バイブコーディング・3Step）

Claude Code に話し言葉で頼むだけ。例：

- 方言：「まーぴーの口調を関西弁にして」
- 多言語：「英語でも話せるようにして」
- 動き：「話すときにもっと大きく跳ねるようにして」
- 連結（ベター）：「数値AIが出力した予測Ad数のCSVを読んで、聞かれたら答えて」

> 口調は `main.py` の `SYSTEM_PROMPT` 1か所が中心。見た目は `img_bird.png` を差し替え（※まーぴーがダメなら別キャラ＝ライオンちゃん等に差し替え可）。

## セキュリティ

- APIキーは `.env`（サーバ側のみ）。`.gitignore` で除外。ブラウザには**短命トークンのみ**。
- 会話は保存しない（揮発）。機微情報は口頭で求めない設定。
