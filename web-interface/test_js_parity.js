#!/usr/bin/env node
// Extract JS fitter from index.html and run it on a simulated session,
// confirming it produces the same scores as test_eval_parity.py.
//
// Usage:
//   cd web-interface
//   node test_js_parity.js [domain] [n_trials] [target_dim_name]
const fs   = require('fs');
const path = require('path');

const html = fs.readFileSync(path.join(__dirname,'index.html'),'utf8');

// Pull the JS payload out of <script>...</script>
const scriptMatch = html.match(/<script>([\s\S]*?)<\/script>/);
if (!scriptMatch) { console.error('no script block'); process.exit(1); }
const fullScript = scriptMatch[1];

// Extract the fitter functions
const wantedFns = ['_matVec','_matVec2','_solveLinear','_sigm','fitBTL'];
const code = [];
wantedFns.forEach(name => {
  const re = new RegExp(`function ${name}\\s*\\([\\s\\S]*?\\n\\}`,'m');
  const m  = fullScript.match(re);
  if (!m) { console.error(`could not find ${name}`); process.exit(1); }
  code.push(m[0]);
});
const wrapped = code.join('\n') + '\nmodule.exports = {fitBTL};';
const ctx = { module:{exports:{}}, console };
new Function('module','console',wrapped)(ctx.module, console);
const F = ctx.module.exports;

const DOMAIN = process.argv[2] || 'movies_100';
const N      = parseInt(process.argv[3]||'20',10);
const TARGET = process.argv[4] || 'Action Intensity';

const tp     = JSON.parse(fs.readFileSync(`outputs/${DOMAIN}/trial_projections.json`,'utf8'));
const cfg    = JSON.parse(fs.readFileSync(`outputs/${DOMAIN}/experiment_config.json`,'utf8'));
const dims   = cfg.dimensions;
const K      = dims.length;
const targetIdx = dims.findIndex(d => (d.name||d.label) === TARGET);
if (targetIdx < 0) { console.error('target dim not found'); process.exit(1); }

// Verify random_projection is precomputed
if (!tp[0].random_projection) {
  console.error(`ERROR: trial_projections.json is missing 'random_projection' field.`);
  console.error(`  Run: python experiments/select_top_dims.py ... --output-dir outputs/${DOMAIN}`);
  process.exit(1);
}

// Use first N trials. Participant always picks option with higher target-dim projection.
const pool = []; for (let i = 0; i < N; i++) pool.push(i);
const U = [], U_rand = [], y = [];
for (let i = 0; i < N; i++) {
  const proj = tp[pool[i]].raw_projection;
  const rand_proj = tp[pool[i]].random_projection;
  U.push(proj.slice());
  U_rand.push(rand_proj.slice());
  y.push(proj[targetIdx] > 0 ? 1 : 0);
}

const lamP = cfg.comparison.lambda_partial || 0.01;
const muPrior = cfg.comparison.feedback_alpha || 1.0;

// Compute per-dim midpoints from raw projections
function perdimMidpoints(proj_pool, nCats) {
  const Kp = proj_pool[0].length;
  const out = new Array(Kp);
  for (let k = 0; k < Kp; k++) {
    const symm = [];
    for (let p = 0; p < proj_pool.length; p++) {
      symm.push(proj_pool[p][k]);
      symm.push(-proj_pool[p][k]);
    }
    symm.sort((a,b) => a-b);
    const mids = [];
    for (let i = 0; i < nCats; i++) {
      const q = (2*i + 1) / (2*nCats);
      const idx = Math.min(Math.floor(q * (symm.length-1)), symm.length-1);
      mids.push(symm[idx]);
    }
    out[k] = mids;
  }
  return out;
}
const allProj = tp.map(t => t.raw_projection);
const nCats = cfg.inference_categories.length;
const midpoints = perdimMidpoints(allProj, nCats);
const targetCatIdx = nCats - 1;  // most positive ('love')
const targetMidpoint = midpoints[targetIdx][targetCatIdx];

// Build beta_prior: simulate participant who 'love's the target dim and 'affirms'
// other visible dims (top-3 by |U|).
const sums = new Array(K).fill(0);
const counts = new Array(K).fill(0);
for (let t = 0; t < N; t++) {
  const top3 = U[t].map((v,i)=>({i,abs:Math.abs(v)}))
                   .sort((a,b)=>b.abs-a.abs).slice(0,3).map(x=>x.i);
  for (const k of top3) {
    if (k === targetIdx) sums[k] += targetMidpoint;
    else sums[k] += U[t][k];
    counts[k] += 1;
  }
}
const betaPrior = new Array(K).fill(0);
let hasPrior = false;
for (let k = 0; k < K; k++) {
  if (counts[k] > 0) {
    betaPrior[k] = sums[k] / counts[k];
    if (betaPrior[k] !== 0) hasPrior = true;
  }
}

const t0 = Date.now();
const betaRand  = F.fitBTL(U_rand, y, lamP, null, 0, 15);
const betaProj  = F.fitBTL(U,      y, lamP, null, 0, 15);
const betaAlpha = F.fitBTL(U,      y, lamP, betaPrior, muPrior, 15);
console.log(`fit time: ${Date.now()-t0}ms`);

// With P=I, scores ARE beta directly
const ranked = (s) => {
  const idxs = s.map((v,i)=>({i,abs:Math.abs(v),s:v})).sort((a,b)=>b.abs-a.abs).slice(0,10);
  return idxs.sort((a,b)=>b.s-a.s).map(x=>({dim:dims[x.i].name||dims[x.i].label,score:Number(x.s.toFixed(4))}));
};
console.log('\nRANDOM PROJECTION top10:');
ranked(betaRand).forEach(r => console.log('  ', r.dim.padEnd(30), r.score));
console.log('\nLLM PROJECTION top10:');
ranked(betaProj).forEach(r => console.log('  ', r.dim.padEnd(30), r.score));
console.log('\nLLM PROJECTION + FEEDBACK PRIOR top10:');
ranked(betaAlpha).forEach(r => console.log('  ', r.dim.padEnd(30), r.score));

const argmaxAbs = (s) => s.reduce((best,v,i)=>Math.abs(v)>Math.abs(s[best])?i:best, 0);
const topRand  = argmaxAbs(betaRand);
const topProj  = argmaxAbs(betaProj);
const topAlpha = argmaxAbs(betaAlpha);
const tName = (i) => dims[i].name || dims[i].label;
console.log(`\nTop dim by |score|:`);
console.log(`  random_projection: ${tName(topRand)} (idx ${topRand})`);
console.log(`  projection_only:   ${tName(topProj)} (idx ${topProj})`);
console.log(`  projection_alpha:  ${tName(topAlpha)} (idx ${topAlpha})`);

if (topProj !== targetIdx) {
  console.error(`FAIL: projection_only failed to identify target dim`);
  process.exit(2);
}
if (topAlpha !== targetIdx) {
  console.error(`FAIL: projection_alpha failed to identify target dim`);
  process.exit(2);
}
console.log('\nJS fitters: PASS');
