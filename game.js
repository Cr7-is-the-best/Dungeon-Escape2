// DUNGEON ESCAPE 2 — Tower Defense
const canvas = document.getElementById("gameCanvas");
const ctx = canvas.getContext("2d");
const CW = 800, CH = 500;

// Grid config
const CELL = 40, COLS = 16, ROWS = 11;
const GX = 0, GY = 50;    // grid origin (below top HUD)
const PX = 640, PW = 160;  // right panel

// Path waypoints (pixel centers of the road corridor)
const WP = [
  [-20,  150],   // entry off-screen left (row 2 center)
  [180,  150],   // col 4, row 2
  [180,  390],   // col 4, row 8
  [460,  390],   // col 11, row 8
  [460,  190],   // col 11, row 3
  [820,  190],   // exit off-screen right
];

// Precompute path segments
const SEGS = [];
let TOTAL_LEN = 0;
for (let i = 1; i < WP.length; i++) {
  const [ax,ay] = WP[i-1], [bx,by] = WP[i];
  const len = Math.hypot(bx-ax, by-ay);
  SEGS.push({ ax, ay, bx, by, len, start: TOTAL_LEN });
  TOTAL_LEN += len;
}

function posAtDist(d) {
  for (const s of SEGS) {
    if (d <= s.start + s.len) {
      const t = Math.max(0, (d - s.start) / s.len);
      return [s.ax + (s.bx-s.ax)*t, s.ay + (s.by-s.ay)*t];
    }
  }
  return [...WP[WP.length-1]];
}

// Mark which grid cells are on the path (cannot place towers here)
const PATH_SET = new Set();
// Row 2: cols 0-4
for (let c=0;c<=4;c++) PATH_SET.add(`${c},2`);
// Col 4: rows 2-8
for (let r=2;r<=8;r++) PATH_SET.add(`4,${r}`);
// Row 8: cols 4-11
for (let c=4;c<=11;c++) PATH_SET.add(`${c},8`);
// Col 11: rows 3-8
for (let r=3;r<=8;r++) PATH_SET.add(`11,${r}`);
// Row 3: cols 11-15
for (let c=11;c<=15;c++) PATH_SET.add(`${c},3`);

// Upgrade multipliers per level (index = level-1)
const UPGRADE_MULTS = [
  { dmg:1.0, range:1.0, rate:1.0  },  // level 1 (base)
  { dmg:1.5, range:1.2, rate:0.80 },  // level 2
  { dmg:2.2, range:1.4, rate:0.62 },  // level 3
];
function upgradeCost(t) {
  const def = TDEFS[t.type];
  if (t.level === 1) return Math.floor(def.cost * 0.75);
  if (t.level === 2) return Math.floor(def.cost * 1.5);
  return Infinity; // max level
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
  rifle:   { name:"Rifle",   cost:20,  req:0,  dmg:40,  range:120, rate:500,  col:"cyan",    aoe:0,  n:1, sprd:0,    pspd:240, desc:"Fast, single shot" },
  shotgun: { name:"Shotgun", cost:40,  req:10, dmg:25,  range:90,  rate:1200, col:"#ff8800", aoe:0,  n:5, sprd:0.35, pspd:200, desc:"Short range spread" },
  sniper:  { name:"Sniper",  cost:60,  req:15, dmg:130, range:230, rate:1800, col:"#88ff00", aoe:0,  n:1, sprd:0,    pspd:420, desc:"Long range, high dmg" },
  minigun: { name:"Minigun", cost:100, req:25, dmg:15,  range:130, rate:100,  col:"#ffff00", aoe:0,  n:1, sprd:0.10, pspd:280, desc:"Rapid fire stream" },
  rpg:     { name:"RPG",     cost:150, req:40, dmg:80,  range:160, rate:2500, col:"#ff4444", aoe:80, n:1, sprd:0,    pspd:160, desc:"Explosive AoE blast" },
};

// Enemy types
const ETYPES = [
  { type:"normal", color:"#cc2200", mhp:80,  spd:55,  gold:5,  sc:1, lives:1, sz:11 },
  { type:"fast",   color:"#ff7700", mhp:50,  spd:100, gold:8,  sc:2, lives:1, sz:8  },
  { type:"tank",   color:"#8800cc", mhp:240, spd:32,  gold:20, sc:5, lives:3, sz:14 },
];

// ---- GAME STATE ----
let state = "title";
let lives, score, gold, wave;
let towers, enemies, projs, explosions;
let selected;
let waveQueue, waveIdx, waveTimer, waveDelay;
let betweenTimer;  // countdown before next wave starts
let hoverC = -1, hoverR = -1;
let sellFlashes = [];

function initGame() {
  lives = 10;
  score = 0; gold = 120; wave = 0;
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
}

function buildWave(w) {
  const n = 8 + w * 3;
  const list = [];
  for (let i = 0; i < n; i++) {
    const r = Math.random();
    let et = ETYPES[0];
    if (w >= 4 && r < 0.20) et = ETYPES[2];       // tank
    else if (w >= 2 && r < 0.45) et = ETYPES[1];   // fast
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
  if (state === "title" || state === "gameover") { initGame(); return; }
  if (state !== "playing") return;
  // Quit button hit-test (top-right of HUD)
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

window.addEventListener("keydown", e => {
  if ((e.key === "Enter" || e.key === " ") && (state === "title" || state === "gameover")) {
    e.preventDefault(); initGame();
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
    // Upgrade existing tower
    const cost = upgradeCost(existing);
    if (existing.level >= 3 || gold < cost) return;
    gold -= cost;
    existing.totalInvested += cost;
    existing.level++;
    applyLevel(existing);
    sellFlashes.push({ x: existing.cx, y: existing.cy, text: `⬆ LV${existing.level}!`, life: 1400, col: "#88ccff" });
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
  // Spawn enemies for current wave
  if (waveIdx < waveQueue.length) {
    waveTimer -= dt;
    if (waveTimer <= 0) {
      spawnEnemy(waveQueue[waveIdx++]);
      waveTimer = waveDelay;
    }
  }

  // Check wave complete (all spawned + all dead/escaped)
  const waveDone = waveIdx >= waveQueue.length && enemies.length === 0 && projs.length === 0;
  if (waveDone && betweenTimer === 0) {
    gold += 15 + wave * 5;  // end-of-wave bonus
    betweenTimer = 4000;    // 4 second break
  }
  if (betweenTimer > 0) {
    betweenTimer = Math.max(0, betweenTimer - dt);
    if (betweenTimer === 0) startWave();
  }

  // Move enemies
  for (const en of enemies) {
    en.dist += en.spd * (dt / 1000);
    const [nx, ny] = posAtDist(en.dist);
    if (nx !== en.x || ny !== en.y) en.angle = Math.atan2(ny-en.y, nx-en.x);
    en.x = nx; en.y = ny;
    if (en.flash > 0) en.flash -= dt;
    if (en.dist >= TOTAL_LEN) {
      en.escaped = true;
      lives -= en.lives;
    }
  }
  enemies = enemies.filter(en => !en.escaped);

  // Tower fire
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

  // Move projectiles
  const liveProjs = [];
  for (const p of projs) {
    const dx = p.tx - p.x, dy = p.ty - p.y;
    const dist = Math.hypot(dx, dy);
    const step = p.pspd * dt / 1000;
    if (dist <= step + 2) {
      // Arrived at target point
      if (p.aoe > 0) {
        explosions.push({ x:p.tx, y:p.ty, r:0, maxR:p.aoe, life:500, mLife:500, isAoe:true });
        for (const en of enemies) {
          const ed = Math.hypot(en.x-p.tx, en.y-p.ty);
          if (ed < p.aoe) {
            const falloff = 1 - ed/p.aoe * 0.5;
            en.hp -= p.dmg * falloff;
            en.flash = 120;
          }
        }
      } else if (p.target && !p.target.escaped) {
        p.target.hp -= p.dmg;
        p.target.flash = 120;
      }
    } else {
      p.x += dx/dist * step;
      p.y += dy/dist * step;
      liveProjs.push(p);
    }
  }
  projs = liveProjs;

  // Kill enemies with 0 HP
  enemies = enemies.filter(en => {
    if (en.hp <= 0) {
      score += en.sc; gold += en.gold;
      explosions.push({ x:en.x, y:en.y, r:0, maxR:en.sz+8, life:250, mLife:250, isAoe:false });
      return false;
    }
    return true;
  });

  // Update explosions
  for (const ex of explosions) { ex.r += ex.maxR/(ex.mLife/16); ex.life -= dt; }
  explosions = explosions.filter(ex => ex.life > 0);

  if (lives <= 0) { lives = 0; state = "gameover"; }

  // Tick sell flashes
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
  if (state === "title")    { drawTitle(ts); return; }
  if (state === "gameover") { drawGameOver(); return; }
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
        // Range preview
        if (ok) {
          ctx.strokeStyle = "rgba(255,255,255,0.06)";
          ctx.lineWidth = 1;
          ctx.beginPath(); ctx.arc(x+CELL/2, y+CELL/2, def.range, 0, Math.PI*2); ctx.stroke();
        }
      }
    }
  }
}

function drawPath() {
  // Road fill
  ctx.save();
  ctx.strokeStyle = "#2a1e08";
  ctx.lineWidth = CELL;
  ctx.lineCap = "butt";
  ctx.lineJoin = "miter";
  ctx.beginPath();
  ctx.moveTo(WP[0][0], WP[0][1]);
  for (let i=1;i<WP.length;i++) ctx.lineTo(WP[i][0], WP[i][1]);
  ctx.stroke();

  // Road border highlights
  ctx.strokeStyle = "#3d2c10";
  ctx.lineWidth = CELL; ctx.setLineDash([0]);
  ctx.globalAlpha = 0.25;
  ctx.beginPath();
  ctx.moveTo(WP[0][0], WP[0][1]);
  for (let i=1;i<WP.length;i++) ctx.lineTo(WP[i][0], WP[i][1]);
  ctx.stroke();
  ctx.globalAlpha = 1;

  // Center dashes
  ctx.strokeStyle = "#4a3a14";
  ctx.lineWidth = 2; ctx.setLineDash([10,14]);
  ctx.beginPath();
  ctx.moveTo(WP[0][0], WP[0][1]);
  for (let i=1;i<WP.length;i++) ctx.lineTo(WP[i][0], WP[i][1]);
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.restore();

  // START / END markers
  ctx.font = "bold 10px Arial"; ctx.textAlign = "center";
  ctx.fillStyle = "#00dd55";
  ctx.fillRect(0, 135, 22, 30);
  ctx.fillStyle = "#000"; ctx.fillText("IN", 11, 155);
  ctx.fillStyle = "#cc2200";
  ctx.fillRect(PX-22, 175, 22, 30);
  ctx.fillStyle = "#fff"; ctx.fillText("OUT", PX-11, 195);
  ctx.textAlign = "left";
}

function drawTowers() {
  for (const t of towers) {
    const def = TDEFS[t.type];
    // Base plate
    ctx.fillStyle = "#1a1a30"; ctx.fillRect(t.cx-14, t.cy-14, 28, 28);
    ctx.strokeStyle = def.col; ctx.lineWidth = 1.5; ctx.strokeRect(t.cx-14, t.cy-14, 28, 28);
    // Body
    ctx.fillStyle = def.col;
    ctx.beginPath(); ctx.arc(t.cx, t.cy, 7, 0, Math.PI*2); ctx.fill();
    // Barrel
    ctx.strokeStyle = def.col; ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(t.cx, t.cy);
    ctx.lineTo(t.cx + Math.cos(t.angle)*15, t.cy + Math.sin(t.angle)*15);
    ctx.stroke();
    // Level stars beneath tower
    ctx.textAlign = "center"; ctx.font = "9px Arial";
    const stars = t.level === 3 ? "★★★" : t.level === 2 ? "★★" : "★";
    ctx.fillStyle = t.level === 3 ? "#FFD700" : t.level === 2 ? "#aaa" : "#555";
    ctx.fillText(stars, t.cx, t.cy + 22);
    ctx.textAlign = "left";

    // Hover: show upgrade or sell tooltip
    if (t.col===hoverC && t.row===hoverR) {
      const isMax = t.level >= 3;
      const upCost = upgradeCost(t);
      const canUp = !isMax && gold >= upCost;

      ctx.fillStyle = canUp ? "rgba(0,180,255,0.14)" : "rgba(255,60,0,0.14)";
      ctx.fillRect(t.cx-14, t.cy-14, 28, 28);
      ctx.strokeStyle = canUp ? "#44aaff" : "#ff4400"; ctx.lineWidth = 2;
      ctx.strokeRect(t.cx-14, t.cy-14, 28, 28);

      // Range ring using effective range
      ctx.strokeStyle = "rgba(200,200,255,0.18)"; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.arc(t.cx, t.cy, t.eff_range, 0, Math.PI*2); ctx.stroke();

      // Tooltip lines above tower
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
    ctx.save();
    ctx.translate(en.x, en.y);
    ctx.fillStyle = en.flash > 0 ? "#ffffff" : en.color;
    ctx.fillRect(-en.sz, -en.sz, en.sz*2, en.sz*2);
    ctx.restore();
    // HP bar
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
  ctx.globalAlpha = 1;
  ctx.textAlign = "left";
}

function drawExplosions() {
  for (const ex of explosions) {
    const a = ex.life / ex.mLife;
    if (ex.isAoe) {
      ctx.strokeStyle = `rgba(255,120,0,${a})`;
      ctx.lineWidth = 3;
      ctx.beginPath(); ctx.arc(ex.x, ex.y, Math.max(1,ex.r), 0, Math.PI*2); ctx.stroke();
      ctx.fillStyle = `rgba(255,160,0,${a*0.18})`;
      ctx.fill();
    } else {
      ctx.fillStyle = `rgba(180,0,0,${a*0.7})`;
      ctx.beginPath(); ctx.arc(ex.x, ex.y, Math.max(1,ex.r), 0, Math.PI*2); ctx.fill();
    }
  }
}

function drawHUD(ts) {
  // Top bar bg
  ctx.fillStyle = "#0a0a1a"; ctx.fillRect(0, 0, CW, GY);
  ctx.strokeStyle = "#1a1a30"; ctx.lineWidth = 1; ctx.strokeRect(0, 0, CW, GY);

  // Lives (shown as red squares)
  ctx.font = "bold 12px Arial"; ctx.fillStyle = "#aaa"; ctx.fillText("LIVES:", 8, 32);
  for (let i = 0; i < 10; i++) {
    ctx.fillStyle = i < lives ? "#cc2200" : "#2a0000";
    ctx.fillRect(62 + i*16, 20, 12, 12);
    ctx.strokeStyle = "#550000"; ctx.lineWidth = 1;
    ctx.strokeRect(62 + i*16, 20, 12, 12);
  }

  ctx.textAlign = "center";
  ctx.fillStyle = "white"; ctx.font = "bold 15px Arial";
  ctx.fillText(`Wave ${wave}`, 350, 22);
  ctx.fillStyle = "#FFD700"; ctx.font = "bold 14px Arial";
  ctx.fillText(`⬡ ${gold}g`, 350, 40);
  ctx.fillStyle = "#aaa"; ctx.font = "13px Arial";
  ctx.fillText(`Score: ${score}`, 480, 30);
  ctx.textAlign = "left";

  // Between-wave countdown
  if (betweenTimer > 0) {
    const secs = Math.ceil(betweenTimer/1000);
    ctx.fillStyle = "#00cc44"; ctx.font = "bold 13px Arial"; ctx.textAlign = "center";
    ctx.fillText(`Wave ${wave+1} starts in ${secs}s…  +${15+wave*5}g bonus!`, 350, 48);
    ctx.textAlign = "left";
  }

  // Quit button (top-right of HUD bar)
  const qx = CW - 68, qy = 10, qw = 58, qh = 30;
  const hoveringQuit = hoverC === -1 && hoverR === -1 &&
    typeof lastMX !== "undefined" &&
    lastMX >= qx && lastMX <= qx+qw &&
    lastMY >= 0 && lastMY <= GY;
  ctx.fillStyle = hoveringQuit ? "#882200" : "#551100";
  ctx.fillRect(qx, qy, qw, qh);
  ctx.strokeStyle = "#cc3300"; ctx.lineWidth = 1.5;
  ctx.strokeRect(qx, qy, qw, qh);
  ctx.fillStyle = "#ff6644"; ctx.font = "bold 13px Arial"; ctx.textAlign = "center";
  ctx.fillText("QUIT", qx + qw/2, qy + 20);
  ctx.textAlign = "left";
}

function drawPanel() {
  ctx.fillStyle = "#09091a"; ctx.fillRect(PX, 0, PW, CH);
  ctx.strokeStyle = "#1a1a30"; ctx.lineWidth = 1; ctx.strokeRect(PX, 0, PW, CH);
  ctx.fillStyle = "#666"; ctx.font = "bold 11px Arial"; ctx.textAlign = "center";
  ctx.fillText("TOWERS [1-5]", PX+PW/2, GY+18);
  ctx.textAlign = "left";

  for (const item of panelItems()) {
    const def = TDEFS[item.id];
    const unlocked = score >= def.req;
    const isSel = selected === item.id;
    const canBuy = unlocked && gold >= def.cost;

    ctx.fillStyle = isSel ? "#162040" : unlocked ? "#0d0d1e" : "#080808";
    ctx.fillRect(item.x, item.y, item.w, item.h);
    ctx.strokeStyle = isSel ? "#88ccff" : unlocked ? "#334" : "#1a1a1a";
    ctx.lineWidth = isSel ? 2 : 1;
    ctx.strokeRect(item.x, item.y, item.w, item.h);

    const cx = item.x + item.w/2;
    ctx.fillStyle = def.col; ctx.font = `bold 12px Arial`; ctx.textAlign = "center";
    ctx.fillText(def.name, cx, item.y + 16);
    ctx.fillStyle = "#555"; ctx.font = "10px Arial";
    ctx.fillText(def.desc, cx, item.y + 28);
    ctx.fillStyle = canBuy ? "#FFD700" : unlocked ? "#664" : "#442";
    ctx.fillText(`${def.cost}g`, cx, item.y + 42);
    if (!unlocked) { ctx.fillStyle="#664400"; ctx.fillText(`Score ${def.req}+`,cx,item.y+54); }
    ctx.textAlign = "left";
  }

  // Selected tower info
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

function drawTitle(ts) {
  // Grid bg
  ctx.strokeStyle = "#12122a"; ctx.lineWidth = 1;
  for (let x=0;x<CW;x+=40){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,CH);ctx.stroke();}
  for (let y=0;y<CH;y+=40){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(CW,y);ctx.stroke();}
  // Draw the road on title screen
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

  ctx.fillStyle = "#aaa"; ctx.font = "14px Arial";
  ctx.fillText("Place towers on the grid alongside the road", CW/2, CH/2+20);
  ctx.fillText("Enemies follow the path — stop them before they escape!", CW/2, CH/2+44);
  ctx.fillText("Kill enemies to earn gold • Buy better towers in the panel", CW/2, CH/2+68);

  const blink = Math.floor(ts/600)%2===0;
  ctx.fillStyle = blink ? "#88ccff" : "#5588aa"; ctx.font = "bold 20px Arial";
  ctx.fillText("▶  Click or Enter to Start  ◀", CW/2, CH/2+110);
  ctx.textAlign = "left";
}

function drawGameOver() {
  ctx.textAlign = "center";
  ctx.shadowColor = "#cc0000"; ctx.shadowBlur = 25;
  ctx.fillStyle = "#cc2200"; ctx.font = "bold 52px Arial";
  ctx.fillText("GAME OVER", CW/2, CH/2 - 50);
  ctx.shadowBlur = 0;
  ctx.fillStyle = "white"; ctx.font = "22px Arial";
  ctx.fillText(`Score: ${score}  •  Wave: ${wave}  •  Gold: ${gold}g`, CW/2, CH/2 + 8);
  ctx.fillStyle = "#88ccff"; ctx.font = "18px Arial";
  ctx.fillText("Click or Enter to play again", CW/2, CH/2 + 55);
  ctx.textAlign = "left";
}

requestAnimationFrame(gameLoop);
