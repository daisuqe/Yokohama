/**
 * Yokohama ハイスコア共有 (Cloudflare Workers + D1)
 *  - POST /        : ゲームから {stage, name, score, level, id} を受け取って保存 (1人・1ステージにつき1件、高いスコアのときだけ更新)
 *  - GET  /?stage= : そのステージの上位100件を [{name, score, level}] で返す (Apps Script版と同じ形)
 * 使い方は cloudflare/README.md を見てください。
 */
const STAGES = ['yokohama', 'minato', 'chinatown'];   // ゲーム側のステージIDと同じ
const TOP_N = 100, MAX_SCORE = 1e11, MAX_LEVEL = 30, NAME_MAX = 8;

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
};
const json = (obj, status = 200, extra = {}) =>
  new Response(JSON.stringify(obj), { status, headers: { 'Content-Type': 'application/json; charset=utf-8', ...CORS, ...extra } });
const cleanName = s => String(s == null ? '' : s).replace(/[<>&"'`\u0000-\u001f]/g, '').trim().slice(0, NAME_MAX);

export default {
  async fetch(req, env) {
    if (req.method === 'OPTIONS') return new Response(null, { headers: CORS });
    const url = new URL(req.url);

    if (req.method === 'GET') {
      const stage = url.searchParams.get('stage') || '';
      if (!STAGES.includes(stage)) return json([]);
      const { results } = await env.DB
        .prepare('SELECT name, score, level FROM scores WHERE stage = ?1 ORDER BY score DESC, level DESC LIMIT ?2')
        .bind(stage, TOP_N).all();
      return json(results, 200, { 'Cache-Control': 'public, max-age=20' });
    }

    if (req.method === 'POST') {
      let d;
      try { d = JSON.parse(await req.text()); } catch (_) { return json({ ok: false, error: 'bad json' }, 400); }
      const stage = String(d.stage || ''), name = cleanName(d.name), id = String(d.id || '').slice(0, 40);
      const score = Math.floor(Number(d.score)), level = Math.floor(Number(d.level));
      if (!STAGES.includes(stage) || !name || !id) return json({ ok: false, error: 'bad request' }, 400);
      if (!(score >= 0 && score <= MAX_SCORE) || !(level >= 1 && level <= MAX_LEVEL)) return json({ ok: false, error: 'bad value' }, 400);
      // 同じ人・同じステージは1件だけ。今より高いスコアのときだけ更新する(名前は、最新のものにそろえる)
      await env.DB.prepare(
        `INSERT INTO scores (stage, id, name, score, level, updated) VALUES (?1, ?2, ?3, ?4, ?5, datetime('now'))
         ON CONFLICT(stage, id) DO UPDATE SET name = excluded.name, score = excluded.score, level = excluded.level, updated = excluded.updated
         WHERE excluded.score >= scores.score`
      ).bind(stage, id, name, score, level).run();
      return json({ ok: true });
    }
    return json({ ok: false }, 405);
  },
};
