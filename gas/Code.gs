/**
 * Yokohama ハイスコア共有 (Google スプレッドシート + Apps Script)
 *
 * 使い方は gas/README.md を見てください。
 *  - doPost: ゲームから「名前・スコア・レベル」を受け取って、シート "scores" に保存する
 *  - doGet : ステージごとの上位10件を JSON で返す   例) .../exec?stage=yokohama
 *
 * 1人(id = ブラウザごとのID)につき、ステージごとに1行。より高いスコアのときだけ更新する。
 */
const SHEET_NAME = 'scores';
const STAGES = ['yokohama', 'minato', 'chinatown'];   // ゲーム側のステージIDと同じ
const TOP_N = 10;
const MAX_SCORE = 1e11;        // これを超えるスコアは受け付けない(明らかな不正)
const MAX_LEVEL = 30;
const NAME_MAX = 8;
const CACHE_SEC = 30;          // 一覧のキャッシュ(秒)。アクセスが多くても軽くする

function sheet_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sh = ss.getSheetByName(SHEET_NAME);
  if (!sh) {
    sh = ss.insertSheet(SHEET_NAME);
    sh.appendRow(['updated', 'stage', 'name', 'score', 'level', 'id']);
    sh.setFrozenRows(1);
  }
  return sh;
}

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

function cleanName_(s) {
  return String(s == null ? '' : s).replace(/[<>&"'`\u0000-\u001f]/g, '').trim().slice(0, NAME_MAX);
}

// ---- 受け取り ----
function doPost(e) {
  const lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    const d = JSON.parse(e.postData.contents);
    const stage = String(d.stage || '');
    const name = cleanName_(d.name);
    const score = Math.floor(Number(d.score));
    const level = Math.floor(Number(d.level));
    const id = String(d.id || '').slice(0, 40);
    if (STAGES.indexOf(stage) < 0 || !name || !id) return json_({ ok: false, error: 'bad request' });
    if (!(score >= 0 && score <= MAX_SCORE) || !(level >= 1 && level <= MAX_LEVEL)) return json_({ ok: false, error: 'bad value' });

    const sh = sheet_();
    const last = sh.getLastRow();
    if (last >= 2) {
      const ids = sh.getRange(2, 6, last - 1, 1).getValues();      // id 列
      const stages = sh.getRange(2, 2, last - 1, 1).getValues();   // stage 列
      for (let i = 0; i < ids.length; i++) {
        if (String(ids[i][0]) === id && String(stages[i][0]) === stage) {   // 同じゲームの再送: 高いスコアなら更新
          const row = i + 2, old = Number(sh.getRange(row, 4).getValue());
          if (score >= old) sh.getRange(row, 1, 1, 6).setValues([[new Date(), stage, name, score, level, id]]);
          CacheService.getScriptCache().remove('top_' + stage);
          return json_({ ok: true, updated: true });
        }
      }
    }
    sh.appendRow([new Date(), stage, name, score, level, id]);
    CacheService.getScriptCache().remove('top_' + stage);
    return json_({ ok: true });
  } catch (err) {
    return json_({ ok: false, error: String(err) });
  } finally {
    lock.releaseLock();
  }
}

// ---- 上位10件を返す ----
function doGet(e) {
  const stage = String((e && e.parameter && e.parameter.stage) || '');
  if (STAGES.indexOf(stage) < 0) return json_([]);
  const cache = CacheService.getScriptCache();
  const hit = cache.get('top_' + stage);
  if (hit) return ContentService.createTextOutput(hit).setMimeType(ContentService.MimeType.JSON);

  const sh = sheet_();
  const last = sh.getLastRow();
  let rows = [];
  if (last >= 2) {
    const vals = sh.getRange(2, 1, last - 1, 6).getValues();
    rows = vals
      .filter(function (r) { return String(r[1]) === stage; })
      .map(function (r) { return { name: String(r[2]), score: Number(r[3]), level: Number(r[4]) }; })
      .sort(function (a, b) { return b.score - a.score || b.level - a.level; })
      .slice(0, TOP_N);
  }
  const out = JSON.stringify(rows);
  cache.put('top_' + stage, out, CACHE_SEC);
  return ContentService.createTextOutput(out).setMimeType(ContentService.MimeType.JSON);
}
