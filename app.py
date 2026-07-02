#pip install flask

from flask import Flask, jsonify, request
import json, os

app = Flask(__name__)
SCORES_FILE = "scores.json"

def load_scores():
    if os.path.exists(SCORES_FILE):
        try:
            with open(SCORES_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return []

def save_score(name, score, wave, map_name):
    scores = load_scores()
    scores.append({"name": str(name)[:16], "score": int(score), "wave": int(wave), "map": str(map_name)})
    scores.sort(key=lambda x: x["score"], reverse=True)
    with open(SCORES_FILE, "w") as f:
        json.dump(scores[:10], f)

PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Dungeon Escape 2</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    background: #05050d;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    font-family: Arial, sans-serif;
    color: white;
  }
  canvas {
    border: 2px solid #222;
    display: block;
    cursor: crosshair;
    box-shadow: 0 0 30px rgba(255, 200, 0, 0.08);
  }
  #hint {
    margin-top: 8px;
    font-size: 0.75em;
    color: #333;
    text-align: center;
  }
  #scoreForm {
    display: none;
    position: absolute;
    top: 50%; left: 50%;
    transform: translate(-50%, -50%);
    background: #0d0d20;
    border: 2px solid #445;
    padding: 20px 28px;
    text-align: center;
    z-index: 10;
  }
  #scoreForm p { color:#aaa; font-size:13px; margin-bottom:10px; }
  #scoreForm input {
    background:#07070f; border:1px solid #445; color:#fff;
    padding:6px 10px; font-size:14px; width:160px; text-align:center;
    outline:none; letter-spacing:1px;
  }
  #scoreForm button {
    display:block; margin:10px auto 0; background:#224488;
    border:1px solid #88ccff; color:#88ccff;
    padding:7px 24px; font-size:13px; cursor:pointer;
  }
  #scoreForm button:hover { background:#2a5aaa; }
</style>
</head>
<body>
<div style="position:relative;display:inline-block;">
<canvas id="gameCanvas" width="1200" height="730"></canvas>
<div id="scoreForm">
  <p id="scoreMsg">Game Over! Enter your name:</p>
  <input id="scoreName" maxlength="16" placeholder="Your name" />
  <button id="scoreSubmit">Submit Score</button>
</div>
</div>
<div id="hint">Dungeon Escape 2 — Kill enemies to earn gold &bull; Keys 1-5 select towers</div>
<script>
// DUNGEON ESCAPE 2 — Tower Defense
const canvas = document.getElementById("gameCanvas");
const ctx = canvas.getContext("2d");
const CW = 1200, CH = 730;

// Grid config
const CELL = 60, COLS = 16, ROWS = 11;
const GX = 0, GY = 70;    // grid origin (below top HUD)
const PX = 960, PW = 240;  // right panel

// ---- MAP DEFINITIONS ----
const MAPS = [
  {
    name: "The Bend",
    desc: "A classic winding road",
    diff: "Easy",
    diffCol: "#44cc44",
    wp: [[-30,220],[270,220],[270,580],[690,580],[690,280],[990,280]],
    buildPath() {
      const s = new Set();
      for (let c=0;c<=4;c++) s.add(`${c},2`);
      for (let r=2;r<=8;r++) s.add(`4,${r}`);
      for (let c=4;c<=11;c++) s.add(`${c},8`);
      for (let r=3;r<=8;r++) s.add(`11,${r}`);
      for (let c=11;c<=15;c++) s.add(`${c},3`);
      return s;
    }
  },
  {
    name: "S-Curve",
    desc: "A serpentine switchback",
    diff: "Medium",
    diffCol: "#ffaa00",
    wp: [[-30,160],[450,160],[450,460],[150,460],[150,640],[990,640]],
    buildPath() {
      const s = new Set();
      for (let c=0;c<=7;c++) s.add(`${c},1`);
      for (let r=1;r<=7;r++) s.add(`7,${r}`);
      for (let c=2;c<=7;c++) s.add(`${c},7`);
      for (let r=7;r<=9;r++) s.add(`2,${r}`);
      for (let c=2;c<=15;c++) s.add(`${c},9`);
      return s;
    }
  },
  {
    name: "The Maze",
    desc: "Long route across the grid",
    diff: "Hard",
    diffCol: "#ff3333",
    wp: [[-30,100],[870,100],[870,340],[210,340],[210,580],[750,580],[750,220],[990,220]],
    buildPath() {
      const s = new Set();
      for (let c=0;c<=14;c++) s.add(`${c},0`);
      for (let r=0;r<=4;r++) s.add(`14,${r}`);
      for (let c=3;c<=14;c++) s.add(`${c},4`);
      for (let r=4;r<=8;r++) s.add(`3,${r}`);
      for (let c=3;c<=12;c++) s.add(`${c},8`);
      for (let r=2;r<=8;r++) s.add(`12,${r}`);
      for (let c=12;c<=15;c++) s.add(`${c},2`);
      return s;
    }
  },
];

let selectedMap = 0;
let WP = [], PATH_SET = new Set(), SEGS = [], TOTAL_LEN = 0;

function applyMap(idx) {
  selectedMap = idx;
  WP = MAPS[idx].wp;
  PATH_SET = MAPS[idx].buildPath();
  SEGS = []; TOTAL_LEN = 0;
  for (let i = 1; i < WP.length; i++) {
    const [ax,ay] = WP[i-1], [bx,by] = WP[i];
    const len = Math.hypot(bx-ax, by-ay);
    SEGS.push({ ax, ay, bx, by, len, start: TOTAL_LEN });
    TOTAL_LEN += len;
  }
}
applyMap(0);

function posAtDist(d) {
  for (const s of SEGS) {
    if (d <= s.start + s.len) {
      const t = Math.max(0, (d - s.start) / s.len);
      return [s.ax + (s.bx-s.ax)*t, s.ay + (s.by-s.ay)*t];
    }
  }
  return [...WP[WP.length-1]];
}

// Upgrade multipliers per level (index = level-1)
const UPGRADE_MULTS = [
  { dmg:1.0, range:1.0, rate:1.0  },
  { dmg:1.5, range:1.2, rate:0.80 },
  { dmg:2.2, range:1.4, rate:0.62 },
];
function upgradeCost(t) {
  const def = TDEFS[t.type];
  if (t.level === 1) return Math.floor(def.cost * 3.5);
  if (t.level === 2) return Math.floor(def.cost * 7);
  return Infinity;
}
function applyLevel(t) {
  const def = TDEFS[t.type];
  const m = UPGRADE_MULTS[t.level - 1];
  t.eff_dmg   = Math.round(def.dmg   * m.dmg);
  t.eff_range = Math.round(def.range * m.range);
  t.eff_rate  = Math.round(def.rate  * m.rate);
}

// Tower definitions
const TOWER_ORDER = ["rifle","shotgun","sniper","minigun","rpg"];
const TDEFS = {
  rifle:   { name:"Rifle",   cost:50,  req:0,  dmg:40,  range:120, rate:500,  col:"cyan",    aoe:0,  n:1, sprd:0,    pspd:240, desc:"Fast, single shot" },
  shotgun: { name:"Shotgun", cost:150, req:10, dmg:25,  range:90,  rate:1200, col:"#ff8800", aoe:0,  n:5, sprd:0.35, pspd:200, desc:"Short range spread" },
  sniper:  { name:"Sniper",  cost:300, req:15, dmg:130, range:230, rate:1800, col:"#88ff00", aoe:0,  n:1, sprd:0,    pspd:420, desc:"Long range, high dmg" },
  minigun: { name:"Minigun", cost:450, req:25, dmg:25,  range:130, rate:100,  col:"#ffff00", aoe:0,  n:1, sprd:0.10, pspd:280, desc:"Rapid fire stream" },
  rpg:     { name:"RPG",     cost:600, req:40, dmg:80,  range:160, rate:2500, col:"#ff4444", aoe:80, n:1, sprd:0,    pspd:160, desc:"Explosive AoE blast" },
};

// Enemy types
const ETYPES = [
  { type:"normal", color:"#cc2200", mhp:350,  spd:100,  gold:30,  sc:1, lives:10, sz:11 },
  { type:"fast",   color:"#ff7700", mhp:550, spd:150, gold:50,  sc:2, lives:5,  sz:8  },
  { type:"tank",   color:"#8800cc", mhp:450, spd:125,  gold:75, sc:5, lives:20, sz:14 },
];

// ---- LEADERBOARD ----
let lbData = [];
let lbLoaded = false;

function fetchLeaderboard(cb) {
  fetch("/scores").then(r => r.json()).then(data => {
    lbData = data; lbLoaded = true;
    if (cb) cb();
  }).catch(() => { lbLoaded = true; });
}

function submitScore(name) {
  fetch("/scores", {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({ name, score, wave, map: MAPS[selectedMap].name })
  }).then(() => fetchLeaderboard());
}

const scoreForm = document.getElementById("scoreForm");
const scoreName = document.getElementById("scoreName");
document.getElementById("scoreSubmit").addEventListener("click", () => {
  const name = scoreName.value.trim() || "Anonymous";
  scoreForm.style.display = "none";
  submitScore(name);
  state = "leaderboard";
  fetchLeaderboard();
});
scoreName.addEventListener("keydown", e => {
  if (e.key === "Enter") document.getElementById("scoreSubmit").click();
});

// ---- GAME STATE ----
let state = "title";
let lives, score, gold, wave;
let towers, enemies, projs, explosions;
let selected;
let waveQueue, waveIdx, waveTimer, waveDelay;
let betweenTimer;
let hoverC = -1, hoverR = -1;
let sellFlashes = [];

function initGame() {
  applyMap(selectedMap);
  lives = 100;
  score = 0; gold = 120; wave = ;
  towers = []; enemies = []; projs = []; explosions = []; sellFlashes = [];
  selected = "rifle";
  waveQueue = []; waveIdx = 0; waveTimer = 0; waveDelay = 0;
  betweenTimer = 0;
  state = "playing";
  startWave();
}

function startWave() {
  wave++;
  waveQueue = buildWave(wave);
  waveIdx = 0;
  waveTimer = 1500;
  waveDelay = Math.max(350, 1200 - wave * 55);
  betweenTimer = 0;
  gameOverFormShown = false;
}

function buildWave(w) {
  const n = 8 + w * 3;
  const list = [];
  for (let i = 0; i < n; i++) {
    const r = Math.random();
    let et = ETYPES[0];
    if (w >= 4 && r < 0.20) et = ETYPES[2];
    else if (w >= 2 && r < 0.45) et = ETYPES[1];
    list.push({ ...et, hp: et.mhp });
  }
  return list;
}

// ---- INPUT ----
let lastMX = -1, lastMY = -1;
canvas.addEventListener("mousemove", e => {
  const r = canvas.getBoundingClientRect();
  lastMX = e.clientX - r.left;
  lastMY = e.clientY - r.top;
  if (lastMX >= 0 && lastMX < PX && lastMY >= GY && lastMY < GY + ROWS*CELL) {
    hoverC = Math.floor(lastMX / CELL);
    hoverR = Math.floor((lastMY - GY) / CELL);
  } else { hoverC = -1; hoverR = -1; }
});

canvas.addEventListener("click", e => {
  const r = canvas.getBoundingClientRect();
  const cx = e.clientX - r.left, cy = e.clientY - r.top;
  if (state === "title") {
    const lbBtnY = CH/2 + 90;
    if (cx >= CW/2-70 && cx <= CW/2+70 && cy >= lbBtnY-16 && cy <= lbBtnY+14) {
      fetchLeaderboard(); state = "leaderboard";
    } else {
      state = "mapselect";
    }
    return;
  }
  if (state === "gameover") { return; }
  if (state === "mapselect") { mapSelectClick(cx, cy); return; }
  if (state === "leaderboard") { state = "title"; return; }
  if (state !== "playing") return;
  if (cx >= CW-68 && cx <= CW-10 && cy >= 10 && cy <= 40) { state = "title"; return; }
  if (cx >= PX) { panelClick(cx, cy); return; }
  if (cy >= GY) gridClick(Math.floor(cx/CELL), Math.floor((cy-GY)/CELL));
});

canvas.addEventListener("contextmenu", e => {
  e.preventDefault();
  const r = canvas.getBoundingClientRect();
  const cx = e.clientX - r.left, cy = e.clientY - r.top;
  if (state !== "playing" || cx >= PX || cy < GY) return;
  const col = Math.floor(cx/CELL), row = Math.floor((cy-GY)/CELL);
  const idx = towers.findIndex(t => t.col===col && t.row===row);
  if (idx === -1) return;
  const refund = Math.floor(towers[idx].totalInvested * 0.5);
  gold += refund;
  sellFlashes.push({ x: GX+col*CELL+CELL/2, y: GY+row*CELL+CELL/2, text: `+${refund}g sold`, life: 1200, col: "#FFD700" });
  towers.splice(idx, 1);
});

function mapSelectClick(cx, cy) {
  const cardW = 170, cardH = 260, gap = 20;
  const totalW = MAPS.length * cardW + (MAPS.length - 1) * gap;
  const startX = (CW - totalW) / 2;
  const cardY = 160;
  for (let i = 0; i < MAPS.length; i++) {
    const x = startX + i * (cardW + gap);
    if (cx >= x && cx <= x + cardW && cy >= cardY && cy <= cardY + cardH) {
      selectedMap = i;
      initGame();
      return;
    }
  }
  // Back button
  if (cx >= CW/2 - 60 && cx <= CW/2 + 60 && cy >= cardY + cardH + 20 && cy <= cardY + cardH + 50) {
    state = "title";
  }
}

window.addEventListener("keydown", e => {
  if ((e.key === "Enter" || e.key === " ") && state === "title") {
    e.preventDefault(); state = "mapselect";
  }
  if (state === "gameover" && e.key === "Escape") {
    e.preventDefault(); scoreForm.style.display = "none"; state = "mapselect";
  }
  if (state === "leaderboard" && (e.key === "Escape" || e.key === "Enter")) {
    e.preventDefault(); state = "title";
  }
  if (state === "mapselect") {
    if (e.key === "1") { selectedMap = 0; initGame(); }
    if (e.key === "2") { selectedMap = 1; initGame(); }
    if (e.key === "3") { selectedMap = 2; initGame(); }
    if (e.key === "Escape") state = "title";
  }
  if (state === "playing") {
    if (e.key === "1") selected = "rifle";
    if (e.key === "2" && score >= TDEFS.shotgun.req) selected = "shotgun";
    if (e.key === "3" && score >= TDEFS.sniper.req) selected = "sniper";
    if (e.key === "4" && score >= TDEFS.minigun.req) selected = "minigun";
    if (e.key === "5" && score >= TDEFS.rpg.req) selected = "rpg";
  }
});

function panelClick(cx, cy) {
  for (const item of panelItems()) {
    if (cx>=item.x&&cx<=item.x+item.w&&cy>=item.y&&cy<=item.y+item.h) {
      if (score >= TDEFS[item.id].req) selected = item.id;
    }
  }
}

function gridClick(col, row) {
  if (col < 0 || col >= COLS || row < 0 || row >= ROWS) return;
  if (PATH_SET.has(`${col},${row}`)) return;
  const existing = towers.find(t => t.col===col && t.row===row);
  if (existing) {
    const cost = upgradeCost(existing);
    if (existing.level >= 3 || gold < cost) return;
    gold -= cost;
    existing.totalInvested += cost;
    existing.level++;
    applyLevel(existing);
    sellFlashes.push({ x: existing.cx, y: existing.cy, text: `\u2b06 LV${existing.level}!`, life: 1400, col: "#88ccff" });
    return;
  }
  const def = TDEFS[selected];
  if (score < def.req || gold < def.cost) return;
  gold -= def.cost;
  const tx = GX + col*CELL + CELL/2;
  const ty = GY + row*CELL + CELL/2;
  const t = { col, row, cx: tx, cy: ty, type: selected, angle: -Math.PI/2, lastFire: 0, level: 1, totalInvested: def.cost };
  applyLevel(t);
  towers.push(t);
}

function panelItems() {
  const items = [], iw = PW-14, ih = 58, gap = 5;
  let y = GY + 32;
  for (const id of TOWER_ORDER) {
    items.push({ id, x: PX+7, y, w: iw, h: ih });
    y += ih + gap;
  }
  return items;
}

// ---- GAME LOOP ----
let lastTs = 0;
function gameLoop(ts) {
  const dt = Math.min(ts - lastTs, 100);
  lastTs = ts;
  if (state === "playing") update(dt, ts);
  draw(ts);
  requestAnimationFrame(gameLoop);
}

function update(dt, ts) {
  if (waveIdx < waveQueue.length) {
    waveTimer -= dt;
    if (waveTimer <= 0) {
      spawnEnemy(waveQueue[waveIdx++]);
      waveTimer = waveDelay;
    }
  }

  const waveDone = waveIdx >= waveQueue.length && enemies.length === 0 && projs.length === 0;
  if (waveDone && betweenTimer === 0) {
    gold += 15 + wave * 5;
    betweenTimer = 4000;
  }
  if (betweenTimer > 0) {
    betweenTimer = Math.max(0, betweenTimer - dt);
    if (betweenTimer === 0) startWave();
  }

  for (const en of enemies) {
    en.dist += en.spd * (dt / 1000);
    const [nx, ny] = posAtDist(en.dist);
    if (nx !== en.x || ny !== en.y) en.angle = Math.atan2(ny-en.y, nx-en.x);
    en.x = nx; en.y = ny;
    if (en.flash > 0) en.flash -= dt;
    if (en.dist >= TOTAL_LEN) { en.escaped = true; lives -= en.lives; }
  }
  enemies = enemies.filter(en => !en.escaped);

  for (const t of towers) {
    if (ts - t.lastFire < t.eff_rate) continue;
    let target = null, best = -1;
    for (const en of enemies) {
      const d = Math.hypot(en.x - t.cx, en.y - t.cy);
      if (d <= t.eff_range && en.dist > best) { best = en.dist; target = en; }
    }
    if (!target) continue;
    t.lastFire = ts;
    t.angle = Math.atan2(target.y - t.cy, target.x - t.cx);
    fireTower(t, target);
  }

  const liveProjs = [];
  for (const p of projs) {
    const dx = p.tx - p.x, dy = p.ty - p.y;
    const dist = Math.hypot(dx, dy);
    const step = p.pspd * dt / 1000;
    if (dist <= step + 2) {
      if (p.aoe > 0) {
        explosions.push({ x:p.tx, y:p.ty, r:0, maxR:p.aoe, life:500, mLife:500, isAoe:true });
        for (const en of enemies) {
          const ed = Math.hypot(en.x-p.tx, en.y-p.ty);
          if (ed < p.aoe) { const falloff = 1 - ed/p.aoe * 0.5; en.hp -= p.dmg * falloff; en.flash = 120; }
        }
      } else if (p.target && !p.target.escaped) {
        p.target.hp -= p.dmg; p.target.flash = 120;
      }
    } else {
      p.x += dx/dist * step; p.y += dy/dist * step; liveProjs.push(p);
    }
  }
  projs = liveProjs;

  enemies = enemies.filter(en => {
    if (en.hp <= 0) {
      score += en.sc; gold += en.gold;
      explosions.push({ x:en.x, y:en.y, r:0, maxR:en.sz+8, life:250, mLife:250, isAoe:false });
      return false;
    }
    return true;
  });

  for (const ex of explosions) { ex.r += ex.maxR/(ex.mLife/16); ex.life -= dt; }
  explosions = explosions.filter(ex => ex.life > 0);

  if (lives <= 0) { lives = 0; state = "gameover"; }

  for (const f of sellFlashes) f.life -= dt;
  sellFlashes = sellFlashes.filter(f => f.life > 0);
}

function spawnEnemy(tmpl) {
  enemies.push({ ...tmpl, x: WP[0][0], y: WP[0][1], dist: 0, angle: 0, flash: 0, escaped: false });
}

function fireTower(t, target) {
  const def = TDEFS[t.type];
  const base = t.angle;
  const targetDist = Math.hypot(target.x - t.cx, target.y - t.cy);
  for (let i = 0; i < def.n; i++) {
    let ang = base;
    if (def.n > 1) ang = base + (i - (def.n-1)/2) * (def.sprd * 2 / Math.max(1, def.n-1));
    ang += (Math.random() - 0.5) * def.sprd * 0.2;
    projs.push({
      x: t.cx, y: t.cy,
      tx: t.cx + Math.cos(ang) * targetDist,
      ty: t.cy + Math.sin(ang) * targetDist,
      pspd: def.pspd, dmg: t.eff_dmg, col: def.col,
      aoe: def.aoe, target: i === 0 ? target : null,
    });
  }
}

// ---- DRAW ----
function draw(ts) {
  ctx.fillStyle = "#07070f"; ctx.fillRect(0,0,CW,CH);
  if (state === "title")     { drawTitle(ts); return; }
  if (state === "mapselect") { drawMapSelect(ts); return; }
  if (state === "gameover")  { drawGameOver(); return; }
  if (state === "leaderboard") { drawLeaderboard(); return; }
  drawGrid();
  drawPath();
  drawExplosions();
  drawEnemies();
  drawProjectiles();
  drawTowers();
  drawSellFlashes();
  drawHUD(ts);
  drawPanel();
}

function drawGrid() {
  for (let c=0;c<COLS;c++) {
    for (let r=0;r<ROWS;r++) {
      const x = GX+c*CELL, y = GY+r*CELL;
      const onPath = PATH_SET.has(`${c},${r}`);
      const hasTower = !!towers.find(t=>t.col===c&&t.row===r);
      ctx.fillStyle = onPath ? "#1a1208" : "#0c0c18";
      ctx.fillRect(x, y, CELL, CELL);
      ctx.strokeStyle = onPath ? "#261a08" : "#111128";
      ctx.lineWidth = 1; ctx.strokeRect(x, y, CELL, CELL);
      if (c===hoverC && r===hoverR && !onPath && !hasTower && state==="playing") {
        const def = TDEFS[selected];
        const ok = score>=def.req && gold>=def.cost;
        ctx.fillStyle = ok ? "rgba(0,255,120,0.13)" : "rgba(255,60,0,0.13)";
        ctx.fillRect(x, y, CELL, CELL);
        if (ok) {
          ctx.strokeStyle = "rgba(255,255,255,0.06)"; ctx.lineWidth = 1;
          ctx.beginPath(); ctx.arc(x+CELL/2, y+CELL/2, def.range, 0, Math.PI*2); ctx.stroke();
        }
      }
    }
  }
}

function drawPath() {
  ctx.save();
  ctx.strokeStyle = "#2a1e08"; ctx.lineWidth = CELL; ctx.lineCap = "butt"; ctx.lineJoin = "miter";
  ctx.beginPath(); ctx.moveTo(WP[0][0], WP[0][1]);
  for (let i=1;i<WP.length;i++) ctx.lineTo(WP[i][0], WP[i][1]);
  ctx.stroke();
  ctx.strokeStyle = "#3d2c10"; ctx.lineWidth = CELL; ctx.globalAlpha = 0.25;
  ctx.beginPath(); ctx.moveTo(WP[0][0], WP[0][1]);
  for (let i=1;i<WP.length;i++) ctx.lineTo(WP[i][0], WP[i][1]);
  ctx.stroke(); ctx.globalAlpha = 1;
  ctx.strokeStyle = "#4a3a14"; ctx.lineWidth = 2; ctx.setLineDash([10,14]);
  ctx.beginPath(); ctx.moveTo(WP[0][0], WP[0][1]);
  for (let i=1;i<WP.length;i++) ctx.lineTo(WP[i][0], WP[i][1]);
  ctx.stroke(); ctx.setLineDash([]); ctx.restore();
  ctx.font = "bold 10px Arial"; ctx.textAlign = "center";
  ctx.fillStyle = "#00dd55"; ctx.fillRect(0, 135, 22, 30);
  ctx.fillStyle = "#000"; ctx.fillText("IN", 11, 155);
  ctx.fillStyle = "#cc2200"; ctx.fillRect(PX-22, 175, 22, 30);
  ctx.fillStyle = "#fff"; ctx.fillText("OUT", PX-11, 195);
  ctx.textAlign = "left";
}

function drawTowers() {
  for (const t of towers) {
    const def = TDEFS[t.type];
    ctx.fillStyle = "#1a1a30"; ctx.fillRect(t.cx-14, t.cy-14, 28, 28);
    ctx.strokeStyle = def.col; ctx.lineWidth = 1.5; ctx.strokeRect(t.cx-14, t.cy-14, 28, 28);
    ctx.fillStyle = def.col;
    ctx.beginPath(); ctx.arc(t.cx, t.cy, 7, 0, Math.PI*2); ctx.fill();
    ctx.strokeStyle = def.col; ctx.lineWidth = 3;
    ctx.beginPath(); ctx.moveTo(t.cx, t.cy);
    ctx.lineTo(t.cx + Math.cos(t.angle)*15, t.cy + Math.sin(t.angle)*15); ctx.stroke();
    ctx.textAlign = "center"; ctx.font = "9px Arial";
    const stars = t.level === 3 ? "\u2605\u2605\u2605" : t.level === 2 ? "\u2605\u2605" : "\u2605";
    ctx.fillStyle = t.level === 3 ? "#FFD700" : t.level === 2 ? "#aaa" : "#555";
    ctx.fillText(stars, t.cx, t.cy + 22); ctx.textAlign = "left";

    if (t.col===hoverC && t.row===hoverR) {
      const isMax = t.level >= 3;
      const upCost = upgradeCost(t);
      const canUp = !isMax && gold >= upCost;
      ctx.fillStyle = canUp ? "rgba(0,180,255,0.14)" : "rgba(255,60,0,0.14)";
      ctx.fillRect(t.cx-14, t.cy-14, 28, 28);
      ctx.strokeStyle = canUp ? "#44aaff" : "#ff4400"; ctx.lineWidth = 2;
      ctx.strokeRect(t.cx-14, t.cy-14, 28, 28);
      ctx.strokeStyle = "rgba(200,200,255,0.18)"; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.arc(t.cx, t.cy, t.eff_range, 0, Math.PI*2); ctx.stroke();
      ctx.textAlign = "center"; ctx.font = "bold 10px Arial";
      const refund = Math.floor(t.totalInvested * 0.5);
      if (!isMax) {
        ctx.fillStyle = canUp ? "#88ccff" : "#886644";
        ctx.fillText(`Click: upgrade LV${t.level+1} (${upCost}g)`, t.cx, t.cy-22);
      } else {
        ctx.fillStyle = "#FFD700"; ctx.fillText("MAX LEVEL", t.cx, t.cy-22);
      }
      ctx.fillStyle = "#FFD700";
      ctx.fillText(`RClick: sell (${refund}g)`, t.cx, t.cy-10);
      ctx.textAlign = "left";
    }
  }
}

function drawEnemies() {
  for (const en of enemies) {
    ctx.save(); ctx.translate(en.x, en.y);
    ctx.fillStyle = en.flash > 0 ? "#ffffff" : en.color;
    ctx.fillRect(-en.sz, -en.sz, en.sz*2, en.sz*2); ctx.restore();
    const bw = en.sz*2+4;
    ctx.fillStyle = "#330000"; ctx.fillRect(en.x-bw/2, en.y-en.sz-8, bw, 4);
    ctx.fillStyle = "#00dd44"; ctx.fillRect(en.x-bw/2, en.y-en.sz-8, bw*(en.hp/en.mhp), 4);
  }
}

function drawProjectiles() {
  for (const p of projs) {
    ctx.fillStyle = p.col;
    if (p.aoe > 0) {
      ctx.beginPath(); ctx.arc(p.x, p.y, 6, 0, Math.PI*2); ctx.fill();
      ctx.strokeStyle = "rgba(255,80,0,0.5)"; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.arc(p.x, p.y, 8, 0, Math.PI*2); ctx.stroke();
    } else {
      const ang = Math.atan2(p.ty-p.y, p.tx-p.x);
      ctx.save(); ctx.translate(p.x, p.y); ctx.rotate(ang);
      ctx.fillRect(-5, -2, 10, 4); ctx.restore();
    }
  }
}

function drawSellFlashes() {
  ctx.font = "bold 13px Arial"; ctx.textAlign = "center";
  for (const f of sellFlashes) {
    const maxLife = f.life > 1200 ? 1400 : 1200;
    const a = Math.min(1, f.life / maxLife);
    const rise = (1 - a) * 36;
    ctx.globalAlpha = a;
    ctx.fillStyle = f.col || "#FFD700";
    ctx.fillText(f.text, f.x, f.y - rise);
  }
  ctx.globalAlpha = 1; ctx.textAlign = "left";
}

function drawExplosions() {
  for (const ex of explosions) {
    const a = ex.life / ex.mLife;
    if (ex.isAoe) {
      ctx.strokeStyle = `rgba(255,120,0,${a})`; ctx.lineWidth = 3;
      ctx.beginPath(); ctx.arc(ex.x, ex.y, Math.max(1,ex.r), 0, Math.PI*2); ctx.stroke();
      ctx.fillStyle = `rgba(255,160,0,${a*0.18})`; ctx.fill();
    } else {
      ctx.fillStyle = `rgba(180,0,0,${a*0.7})`;
      ctx.beginPath(); ctx.arc(ex.x, ex.y, Math.max(1,ex.r), 0, Math.PI*2); ctx.fill();
    }
  }
}

function drawHUD(ts) {
  ctx.fillStyle = "#0a0a1a"; ctx.fillRect(0, 0, CW, GY);
  ctx.strokeStyle = "#1a1a30"; ctx.lineWidth = 1; ctx.strokeRect(0, 0, CW, GY);
  ctx.font = "bold 12px Arial"; ctx.fillStyle = "#aaa"; ctx.fillText("LIVES:", 8, 32);
  ctx.fillStyle = lives > 50 ? "#cc2200" : lives > 20 ? "#ff6600" : "#ff0000";
  ctx.font = "bold 14px Arial"; ctx.fillText(lives, 62, 32);
  const barW = 180, barH = 10;
  ctx.fillStyle = "#2a0000"; ctx.fillRect(62, 37, barW, barH);
  ctx.fillStyle = lives > 50 ? "#cc2200" : lives > 20 ? "#ff6600" : "#ff2200";
  ctx.fillRect(62, 37, Math.max(0, barW * (lives / 100)), barH);
  ctx.strokeStyle = "#550000"; ctx.lineWidth = 1; ctx.strokeRect(62, 37, barW, barH);
  ctx.textAlign = "center";
  ctx.fillStyle = "white"; ctx.font = "bold 15px Arial"; ctx.fillText(`Wave ${wave}`, 350, 22);
  ctx.fillStyle = "#FFD700"; ctx.font = "bold 14px Arial"; ctx.fillText(`\u2b21 ${gold}g`, 350, 40);
  ctx.fillStyle = "#aaa"; ctx.font = "13px Arial"; ctx.fillText(`Score: ${score}`, 480, 30);
  ctx.textAlign = "left";
  if (betweenTimer > 0) {
    const secs = Math.ceil(betweenTimer/1000);
    ctx.fillStyle = "#00cc44"; ctx.font = "bold 13px Arial"; ctx.textAlign = "center";
    ctx.fillText(`Wave ${wave+1} starts in ${secs}s\u2026  +${15+wave*5}g bonus!`, 350, 48);
    ctx.textAlign = "left";
  }
  const qx = CW - 68, qy = 10, qw = 58, qh = 30;
  const hoveringQuit = lastMX >= qx && lastMX <= qx+qw && lastMY >= 0 && lastMY <= GY;
  ctx.fillStyle = hoveringQuit ? "#882200" : "#551100";
  ctx.fillRect(qx, qy, qw, qh);
  ctx.strokeStyle = "#cc3300"; ctx.lineWidth = 1.5; ctx.strokeRect(qx, qy, qw, qh);
  ctx.fillStyle = "#ff6644"; ctx.font = "bold 13px Arial"; ctx.textAlign = "center";
  ctx.fillText("QUIT", qx + qw/2, qy + 20); ctx.textAlign = "left";
}

function drawPanel() {
  ctx.fillStyle = "#09091a"; ctx.fillRect(PX, 0, PW, CH);
  ctx.strokeStyle = "#1a1a30"; ctx.lineWidth = 1; ctx.strokeRect(PX, 0, PW, CH);
  ctx.fillStyle = "#666"; ctx.font = "bold 11px Arial"; ctx.textAlign = "center";
  ctx.fillText("TOWERS [1-5]", PX+PW/2, GY+18); ctx.textAlign = "left";
  for (const item of panelItems()) {
    const def = TDEFS[item.id];
    const unlocked = score >= def.req;
    const isSel = selected === item.id;
    const canBuy = unlocked && gold >= def.cost;
    ctx.fillStyle = isSel ? "#162040" : unlocked ? "#0d0d1e" : "#080808";
    ctx.fillRect(item.x, item.y, item.w, item.h);
    ctx.strokeStyle = isSel ? "#88ccff" : unlocked ? "#334" : "#1a1a1a";
    ctx.lineWidth = isSel ? 2 : 1; ctx.strokeRect(item.x, item.y, item.w, item.h);
    const cx = item.x + item.w/2;
    ctx.fillStyle = def.col; ctx.font = "bold 12px Arial"; ctx.textAlign = "center";
    ctx.fillText(def.name, cx, item.y + 16);
    ctx.fillStyle = "#555"; ctx.font = "10px Arial"; ctx.fillText(def.desc, cx, item.y + 28);
    ctx.fillStyle = canBuy ? "#FFD700" : unlocked ? "#664" : "#442";
    ctx.fillText(`${def.cost}g`, cx, item.y + 42);
    if (!unlocked) { ctx.fillStyle="#664400"; ctx.fillText(`Score ${def.req}+`,cx,item.y+54); }
    ctx.textAlign = "left";
  }
  const sel = TDEFS[selected];
  ctx.fillStyle = "#33334a"; ctx.fillRect(PX+5, CH-75, PW-10, 70);
  ctx.strokeStyle = "#445"; ctx.lineWidth = 1; ctx.strokeRect(PX+5, CH-75, PW-10, 70);
  ctx.fillStyle = sel.col; ctx.font = "bold 12px Arial"; ctx.textAlign = "center";
  ctx.fillText(sel.name, PX+PW/2, CH-59);
  ctx.fillStyle = "#888"; ctx.font = "11px Arial";
  ctx.fillText(`Range: ${sel.range}`, PX+PW/2, CH-44);
  ctx.fillText(`Dmg: ${sel.dmg}  Rate: ${(1000/sel.rate).toFixed(1)}/s`, PX+PW/2, CH-30);
  ctx.fillText(`Cost: ${sel.cost}g`, PX+PW/2, CH-16);
  ctx.textAlign = "left";
}

function drawMapSelect(ts) {
  // Background grid
  ctx.strokeStyle = "#12122a"; ctx.lineWidth = 1;
  for (let x=0;x<CW;x+=40){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,CH);ctx.stroke();}
  for (let y=0;y<CH;y+=40){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(CW,y);ctx.stroke();}

  ctx.textAlign = "center";
  ctx.fillStyle = "#FFD700"; ctx.font = "bold 28px Arial";
  ctx.fillText("SELECT A MAP", CW/2, 60);
  ctx.fillStyle = "#555"; ctx.font = "13px Arial";
  ctx.fillText("Press 1, 2 or 3 — or click a card", CW/2, 85);

  const cardW = 170, cardH = 260, gap = 20;
  const totalW = MAPS.length * cardW + (MAPS.length - 1) * gap;
  const startX = (CW - totalW) / 2;
  const cardY = 110;

  MAPS.forEach((map, i) => {
    const x = startX + i * (cardW + gap);
    const hov = lastMX >= x && lastMX <= x+cardW && lastMY >= cardY && lastMY <= cardY+cardH;
    const sel = selectedMap === i;

    // Card background
    ctx.fillStyle = sel ? "#1a2a4a" : hov ? "#141428" : "#0d0d20";
    ctx.fillRect(x, cardY, cardW, cardH);
    ctx.strokeStyle = sel ? "#88ccff" : hov ? "#4466aa" : "#2a2a55";
    ctx.lineWidth = sel ? 2.5 : 1.5;
    ctx.strokeRect(x, cardY, cardW, cardH);

    // Number badge
    ctx.fillStyle = "#222244";
    ctx.fillRect(x+6, cardY+6, 24, 24);
    ctx.fillStyle = "#aaa"; ctx.font = "bold 14px Arial"; ctx.textAlign = "center";
    ctx.fillText(i+1, x+18, cardY+23);

    // Map name
    ctx.fillStyle = "#ffffff"; ctx.font = "bold 15px Arial";
    ctx.fillText(map.name, x + cardW/2, cardY + 44);

    // Difficulty badge
    ctx.fillStyle = map.diffCol; ctx.font = "bold 11px Arial";
    ctx.fillText(map.diff, x + cardW/2, cardY + 62);

    // Mini path preview
    const pw = cardW - 20, ph = 120, px2 = x + 10, py2 = cardY + 76;
    ctx.fillStyle = "#080818"; ctx.fillRect(px2, py2, pw, ph);
    ctx.strokeStyle = "#1a1a35"; ctx.lineWidth = 1; ctx.strokeRect(px2, py2, pw, ph);

    // Scale waypoints to preview box (game area is 960×660, offset GY=70)
    const scaleX = pw / 960, scaleH = ph / 660;
    ctx.save();
    ctx.beginPath(); ctx.rect(px2, py2, pw, ph); ctx.clip();
    ctx.strokeStyle = "#3a2a08"; ctx.lineWidth = 10; ctx.lineCap = "butt";
    ctx.beginPath();
    map.wp.forEach(([wx,wy], j) => {
      const mx2 = px2 + wx * scaleX;
      const my2 = py2 + (wy - GY) * scaleH;
      j === 0 ? ctx.moveTo(mx2, my2) : ctx.lineTo(mx2, my2);
    });
    ctx.stroke();
    ctx.strokeStyle = "#554422"; ctx.lineWidth = 1.5; ctx.setLineDash([4,6]);
    ctx.beginPath();
    map.wp.forEach(([wx,wy], j) => {
      const mx2 = px2 + wx * scaleX;
      const my2 = py2 + (wy - GY) * scaleH;
      j === 0 ? ctx.moveTo(mx2, my2) : ctx.lineTo(mx2, my2);
    });
    ctx.stroke(); ctx.setLineDash([]);
    ctx.restore();

    // Description
    ctx.fillStyle = "#888"; ctx.font = "11px Arial";
    ctx.fillText(map.desc, x + cardW/2, cardY + cardH - 30);

    // Play button
    const btnY = cardY + cardH - 20;
    ctx.fillStyle = sel ? "#224488" : hov ? "#1a3366" : "#111133";
    ctx.fillRect(x+20, btnY - 14, cardW-40, 26);
    ctx.strokeStyle = sel ? "#88ccff" : "#445";
    ctx.lineWidth = 1; ctx.strokeRect(x+20, btnY - 14, cardW-40, 26);
    ctx.fillStyle = sel ? "#88ccff" : "#aaa"; ctx.font = "bold 12px Arial";
    ctx.fillText(sel ? "SELECTED" : "PLAY", x + cardW/2, btnY + 4);
  });

  // Back button
  const bkY = cardY + cardH + 30;
  const hb = lastMX >= CW/2-60 && lastMX <= CW/2+60 && lastMY >= bkY-14 && lastMY <= bkY+12;
  ctx.fillStyle = hb ? "#330000" : "#1a0000";
  ctx.fillRect(CW/2-60, bkY-14, 120, 26);
  ctx.strokeStyle = "#553333"; ctx.lineWidth = 1; ctx.strokeRect(CW/2-60, bkY-14, 120, 26);
  ctx.fillStyle = "#cc6644"; ctx.font = "bold 12px Arial";
  ctx.fillText("\u2190 BACK", CW/2, bkY + 4);
  ctx.textAlign = "left";
}

function drawTitle(ts) {
  ctx.strokeStyle = "#12122a"; ctx.lineWidth = 1;
  for (let x=0;x<CW;x+=40){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,CH);ctx.stroke();}
  for (let y=0;y<CH;y+=40){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(CW,y);ctx.stroke();}
  ctx.save();
  ctx.strokeStyle = "#2a1e08"; ctx.lineWidth = 40; ctx.lineCap="butt";
  ctx.beginPath(); ctx.moveTo(WP[0][0],WP[0][1]);
  for (let i=1;i<WP.length;i++) ctx.lineTo(WP[i][0],WP[i][1]);
  ctx.stroke();
  ctx.strokeStyle="#554422"; ctx.lineWidth=2; ctx.setLineDash([10,14]);
  ctx.beginPath(); ctx.moveTo(WP[0][0],WP[0][1]);
  for (let i=1;i<WP.length;i++) ctx.lineTo(WP[i][0],WP[i][1]);
  ctx.stroke(); ctx.setLineDash([]); ctx.restore();
  ctx.textAlign = "center";
  ctx.shadowColor = "#FFD700"; ctx.shadowBlur = 25;
  ctx.fillStyle = "#FFD700"; ctx.font = "bold 52px Arial";
  ctx.fillText("DUNGEON ESCAPE 2", CW/2, 100);
  ctx.shadowBlur = 0;
  ctx.fillStyle = "#888"; ctx.font = "16px Arial";
  ctx.fillText("TOWER DEFENSE", CW/2, 130);

  const blink = Math.floor(ts/600)%2===0;
  ctx.fillStyle = blink ? "#88ccff" : "#5588aa"; ctx.font = "bold 20px Arial"; ctx.textAlign = "center";
  ctx.fillText("\u25b6  Click or Enter to Start  \u25c4", CW/2, CH/2 + 40);

  // Leaderboard button
  const lbBtnY = CH/2 + 90;
  const lbHov = typeof lastMX !== "undefined" && lastMX >= CW/2-70 && lastMX <= CW/2+70 && lastMY >= lbBtnY-16 && lastMY <= lbBtnY+12;
  ctx.fillStyle = lbHov ? "#1a2a44" : "#0d1a2e";
  ctx.fillRect(CW/2-70, lbBtnY-16, 140, 30);
  ctx.strokeStyle = lbHov ? "#88ccff" : "#335577"; ctx.lineWidth = 1;
  ctx.strokeRect(CW/2-70, lbBtnY-16, 140, 30);
  ctx.fillStyle = lbHov ? "#88ccff" : "#6699bb"; ctx.font = "bold 14px Arial";
  ctx.fillText("\u2605 LEADERBOARD", CW/2, lbBtnY + 4);
  ctx.textAlign = "left";
}

let gameOverFormShown = false;
function drawGameOver() {
  if (!gameOverFormShown) {
    gameOverFormShown = true;
    document.getElementById("scoreMsg").textContent =
      `Score: ${score} | Wave: ${wave} | ${MAPS[selectedMap].name} — Enter your name:`;
    scoreName.value = "";
    scoreForm.style.display = "block";
    setTimeout(() => scoreName.focus(), 50);
  }
  ctx.textAlign = "center";
  ctx.shadowColor = "#cc0000"; ctx.shadowBlur = 25;
  ctx.fillStyle = "#cc2200"; ctx.font = "bold 52px Arial";
  ctx.fillText("GAME OVER", CW/2, CH/2 - 80);
  ctx.shadowBlur = 0;
  ctx.fillStyle = "white"; ctx.font = "22px Arial";
  ctx.fillText(`Score: ${score}  \u2022  Wave: ${wave}  \u2022  Map: ${MAPS[selectedMap].name}`, CW/2, CH/2 - 30);
  ctx.fillStyle = "#556"; ctx.font = "14px Arial";
  ctx.fillText("Press Escape to skip leaderboard", CW/2, CH/2 + 10);
  ctx.textAlign = "left";
}

function drawLeaderboard() {
  ctx.textAlign = "center";
  ctx.shadowColor = "#FFD700"; ctx.shadowBlur = 18;
  ctx.fillStyle = "#FFD700"; ctx.font = "bold 34px Arial";
  ctx.fillText("\u2605 LEADERBOARD \u2605", CW/2, 60);
  ctx.shadowBlur = 0;

  if (!lbLoaded) {
    ctx.fillStyle = "#888"; ctx.font = "16px Arial";
    ctx.fillText("Loading...", CW/2, CH/2);
    ctx.textAlign = "left"; return;
  }
  if (lbData.length === 0) {
    ctx.fillStyle = "#666"; ctx.font = "16px Arial";
    ctx.fillText("No scores yet — be the first!", CW/2, CH/2);
    ctx.textAlign = "left"; return;
  }

  const rowH = 36, startY = 100, colX = [80, 260, 400, 500, 630];
  ctx.fillStyle = "#445"; ctx.font = "bold 12px Arial";
  ["#", "NAME", "SCORE", "WAVE", "MAP"].forEach((h, i) => ctx.fillText(h, colX[i], startY));
  ctx.strokeStyle = "#334"; ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(60, startY + 8); ctx.lineTo(740, startY + 8); ctx.stroke();

  lbData.forEach((entry, i) => {
    const y = startY + rowH * (i + 1);
    const hl = i === 0;
    ctx.fillStyle = hl ? "rgba(255,215,0,0.06)" : (i%2===0 ? "rgba(255,255,255,0.02)" : "transparent");
    ctx.fillRect(62, y - rowH + 10, 676, rowH);
    ctx.fillStyle = hl ? "#FFD700" : (i < 3 ? "#aad4ff" : "#888");
    ctx.font = hl ? "bold 14px Arial" : "13px Arial";
    const rank = i === 0 ? "\uD83E\uDD47" : i === 1 ? "\uD83E\uDD48" : i === 2 ? "\uD83E\uDD49" : `${i+1}.`;
    ctx.fillText(rank, colX[0], y);
    ctx.fillText(entry.name, colX[1], y);
    ctx.fillStyle = "#88ff88"; ctx.font = "bold 13px Arial";
    ctx.fillText(entry.score.toLocaleString(), colX[2], y);
    ctx.fillStyle = hl ? "#FFD700" : "#888"; ctx.font = "13px Arial";
    ctx.fillText(entry.wave, colX[3], y);
    ctx.fillText(entry.map || "?", colX[4], y);
  });

  ctx.fillStyle = "#445"; ctx.font = "13px Arial";
  ctx.fillText("Click or press Enter / Escape to return", CW/2, CH - 30);
  ctx.textAlign = "left";
}

requestAnimationFrame(gameLoop);
</script>
</body>
</html>"""

@app.route("/")
def index():
    return PAGE

@app.route("/scores", methods=["GET"])
def get_scores():
    return jsonify(load_scores())

@app.route("/scores", methods=["POST"])
def post_score():
    data = request.get_json(silent=True) or {}
    save_score(data.get("name","???"), data.get("score",0), data.get("wave",0), data.get("map","?"))
    return jsonify({"ok": True})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
