// レスリング人生ゲームのバランス確認(自動プレイ)
// 使い方: node game/sim.js [回数]
// index.html の「==LOGIC START==」〜「==LOGIC END==」の部分だけを読み込んで、何千回も自動で遊ぶ。
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const html = fs.readFileSync(path.join(__dirname, 'index.html'), 'utf8');
const m = html.match(/\/\/ ==LOGIC START==([\s\S]*?)\/\/ ==LOGIC END==/);
if (!m) throw new Error('index.html にロジック部分が見つかりません');
const sandbox = { module: { exports: {} } };
vm.runInNewContext(m[1], sandbox);
const WL = sandbox.module.exports;

// 例: node game/sim.js 3000 gainScale=0.8 oppScale=1.05 で、つまみを試せる
for (const arg of process.argv.slice(3)) {
  const [k, v] = arg.split('=');
  if (k in WL.BAL) WL.BAL[k] = Number(v);
}

// 再現できる乱数
function mulberry32(a) {
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const STAT_MENU = { str: 'muscle', sta: 'run', tec: 'tech', spd: 'dash', men: 'mind' };
const WEIGHT = { str: 1, sta: 0.8, tec: 1.3, spd: 1, men: 0.9 };

const STRATEGIES = {
  // 標準: 疲労管理しながら、いちばん低い能力を伸ばす。大会前は休む。
  standard(g, rnd) {
    const t = WL.tournamentFor(g.age);
    if (g.season === 2 && t && g.fatigue > 30) return 'rest';
    if (g.fatigue > 55) return 'rest';
    if (rnd() < 0.15) return 'spar';
    const low = WL.STATS.slice().sort((a, b) => g.stats[a] - g.stats[b])[0];
    return STAT_MENU[low];
  },
  // 何も考えずにランダム
  random(g, rnd) {
    return WL.MENUS[Math.floor(rnd() * WL.MENUS.length)].id;
  },
  // 休まず練習しつづける(疲れたときだけ休む)
  noRest(g, rnd) {
    if (g.fatigue > 85) return 'rest';
    const low = WL.STATS.slice().sort((a, b) => g.stats[a] - g.stats[b])[0];
    return STAT_MENU[low];
  },
  // 偏り型: 戦闘力への効き目×伸びしろが一番大きい能力ばかり伸ばす
  focus(g, rnd) {
    const t = WL.tournamentFor(g.age);
    if (g.season === 2 && t && g.fatigue > 25) return 'rest';
    if (g.fatigue > 50) return 'rest';
    let best = null, bestV = -1;
    for (const s of WL.STATS) {
      const v = WEIGHT[s] * g.talent[s] * (1 - g.stats[s] / 150);
      if (v > bestV) { bestV = v; best = s; }
    }
    return STAT_MENU[best];
  }
};

function play(strategy, seed, keepGoing) {
  const rnd = mulberry32(seed);
  WL.setRandom(mulberry32(seed * 7919 + 1));
  const g = WL.newGame('テスト');
  WL.startInfancy(g);
  WL.chooseInfancy(g, WL.INFANCY[Math.floor(rnd() * 3)].id);
  const powerAt = {};
  let injuries = 0;
  let guard = 0;
  while (guard++ < 10000) {
    if (g.phase === 'ending') {
      // 金メダルのあとも続けるか(keepGoing のときだけ続ける)
      if (keepGoing && g.ending.type === 'gold' && !g.ending.done && g.age < 36) { WL.continueAfterGold(g); continue; }
      break;
    }
    if (g.phase === 'event') {
      const e = g.event;
      WL.resolveEvent(g, e.options ? e.options[Math.floor(rnd() * e.options.length)].id : '');
    } else if (g.phase === 'train') {
      const r = WL.train(g, strategy(g, rnd));
      if (r && r.injured) injuries++;
    } else if (g.phase === 'tournament') {
      WL.finishTournament(g);
    } else if (g.phase === 'yearEnd') {
      powerAt[g.age] = WL.power(g);
      WL.nextYear(g);
    } else throw new Error('unknown phase ' + g.phase);
  }
  return { g, powerAt, injuries };
}

function report(name, n) {
  const strategy = STRATEGIES[name];
  let gold = 0, anyMedal = 0, injuries = 0, trialsWins = 0;
  const goldAge = {};
  const pw = { 12: [], 15: [], 18: [], 21: [], 24: [], 28: [], 32: [], 36: [] };
  let rivalW = 0, rivalL = 0;
  for (let i = 1; i <= n; i++) {
    const { g, powerAt, injuries: inj } = play(strategy, i);
    injuries += inj;
    for (const a in pw) if (powerAt[a] !== undefined) pw[a].push(powerAt[a]);
    if (g.ending.type === 'gold') { gold++; goldAge[g.ending.age] = (goldAge[g.ending.age] || 0) + 1; }
    if (g.medals.length) anyMedal++;
    trialsWins += g.log.filter(l => l.name === 'オリンピック').length;
    if (g.rival) { rivalW += g.rival.w; rivalL += g.rival.l; }
  }
  const pct = v => (v / n * 100).toFixed(1) + '%';
  console.log(`\n■ ${name}(${n}回)`);
  console.log(`  金メダル率: ${pct(gold)}  何かしらのメダル: ${pct(anyMedal)}  五輪出場回数/人: ${(trialsWins / n).toFixed(2)}`);
  console.log('  金メダルを取った年齢: ' + WL.OLYMPIC_AGES.map(a => `${a}歳 ${pct(goldAge[a] || 0)}`).join(' / '));
  const avg = a => a.length ? (a.reduce((x, y) => x + y, 0) / a.length).toFixed(1) : '-';
  console.log('  平均戦闘力(その年の終わり・まだ現役の人): ' + Object.keys(pw).map(a => `${a}歳 ${avg(pw[a])}`).join(' / '));
  console.log(`  ケガ回数/人: ${(injuries / n).toFixed(2)}  ライバル通算: ${rivalW}勝${rivalL}敗`);
}

const N = Number(process.argv[2]) || 5000;
console.log('つまみ:', JSON.stringify(WL.BAL));
for (const name of Object.keys(STRATEGIES)) report(name, N);

// 金メダルを取っても36歳まで続けた場合、金メダルを何個取れるか
{
  const dist = {};
  for (let i = 1; i <= N; i++) {
    const n = play(STRATEGIES.standard, i, true).g.medals.filter(m => m.medal === '金').length;
    dist[n] = (dist[n] || 0) + 1;
  }
  console.log(`\n■ standard で金メダル後も36歳まで続けた場合の金メダルの数(${N}回)`);
  console.log('  ' + Object.keys(dist).sort().map(k => `${k}個 ${(dist[k] / N * 100).toFixed(1)}%`).join(' / '));
}
