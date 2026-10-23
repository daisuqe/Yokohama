# ランキングを Cloudflare に移す手順

Google(Apps Script)のランキングを、Cloudflare Workers + D1 に移します。2日間は両方に送り、両方の結果をまとめて表示します。

## 1. Worker を作る(最初の1回)
```bash
cd cloudflare
npx wrangler login                          # ブラウザでCloudflareにログイン
npx wrangler d1 create yokohama-ranking     # 出てきた database_id を wrangler.toml に貼る
npx wrangler d1 execute yokohama-ranking --remote --file=schema.sql
npx wrangler deploy                         # 出てきた https://yokohama-ranking.<あなたの名前>.workers.dev がURL
```

## 2. 今までの記録を移す
1. スプレッドシートの `scores` シートを CSV でダウンロードする(ファイル → ダウンロード → CSV)。
2. SQL にして、D1 に入れる。
```bash
python csv_to_sql.py scores.csv > import.sql
npx wrangler d1 execute yokohama-ranking --remote --file=import.sql
```

## 3. ゲームを2か所対応にする
`index.html` の `const LB2_URL = ... : '';` の `''` に、Worker のURLを入れて、公開する。
以後、スコアは Google と Cloudflare の両方に送られ、ランキングは両方をまとめて表示します(同じ記録は1件にまとめ、片方が止まっていても、もう片方で表示します)。

## 4. 2日後に Google をやめる
`index.html` の `LB_URL` を `''` にして公開する(`LB2_URL` だけが残る)。
