"""Google スプレッドシート(scores シート)を CSV で保存したものを、D1 に入れる SQL にする。
使い方: python cloudflare/csv_to_sql.py scores.csv > import.sql
(列: updated, stage, name, score, level, id。1人・1ステージで、いちばん高いスコアだけを残す)"""
import csv, sys
sys.stdout.reconfigure(encoding="utf-8", newline=chr(10))
best = {}
for r in csv.DictReader(open(sys.argv[1], encoding='utf-8-sig')):
    try:
        k = (r['stage'], r['id']); s = int(float(r['score'])); lv = int(float(r['level']))
    except Exception:
        continue
    if k not in best or s >= best[k][0]:
        best[k] = (s, lv, r['name'], r.get('updated', ''))
q = lambda t: "'" + str(t).replace("'", "''") + "'"
for (stage, id_), (s, lv, name, upd) in best.items():
    print(f"INSERT INTO scores (stage,id,name,score,level,updated) VALUES ({q(stage)},{q(id_)},{q(name)},{s},{lv},{q(upd)}) "
          f"ON CONFLICT(stage,id) DO UPDATE SET name=excluded.name,score=excluded.score,level=excluded.level WHERE excluded.score>=scores.score;")
