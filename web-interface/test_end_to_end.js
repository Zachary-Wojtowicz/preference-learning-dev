#!/usr/bin/env node
// End-to-end smoke test: simulates a full participant session by mirroring
// what the browser does when loading the page, running 20 trials, providing
// inference feedback, and getting the eval screen.
//
// Usage: node test_end_to_end.js [domain] [pid] [target_dim_name]
const fs   = require('fs');
const path = require('path');

const DOMAIN = process.argv[2] || 'movies_100';
const PID    = process.argv[3] || 'TEST_PID_001';
const TARGET = process.argv[4] || 'Action Intensity';
const N      = 20;

// Pull fitter functions from index.html
const html = fs.readFileSync(path.join(__dirname,'index.html'),'utf8');
const fullScript = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const wantedFns = ['_matVec','_solveLinear','_sigm','fitNewtonStandard','fitNewtonPartial','scoresFromAlpha','scoresFromBeta'];
const code = wantedFns.map(name => fullScript.match(new RegExp(`function ${name}\\s*\\([\\s\\S]*?\\n\\}`,'m'))[0]);
const ctx = { module:{exports:{}} };
new Function('module', code.join('\n') + '\nmodule.exports={fitNewtonStandard,fitNewtonPartial,scoresFromAlpha,scoresFromBeta,_solveLinear};')(ctx.module);
const F = ctx.module.exports;

// Replicate the JS hashStr/seedRandom/shuffle to get the participant's actual trial order
function hashStr(s){let h=0;for(let i=0;i<s.length;i++){h=((h<<5)-h+s.charCodeAt(i))|0;}return Math.abs(h);}
function seedRandom(seed){let s=seed|0;return ()=>{s=(s+0x6D2B79F5)|0;let t=Math.imul(s^(s>>>15),1|s);t=(t+Math.imul(t^(t>>>7),61|t))^t;return((t^(t>>>14))>>>0)/4294967296;};}
function shuffle(arr,rng){const a=arr.slice();for(let i=a.length-1;i>0;i--){const j=Math.floor(rng()*(i+1));const t=a[i];a[i]=a[j];a[j]=t;}return a;}

const trials = JSON.parse(fs.readFileSync(`outputs/${DOMAIN}/trials.json`,'utf8'));
const tp     = JSON.parse(fs.readFileSync(`outputs/${DOMAIN}/trial_projections.json`,'utf8'));
const cfg    = JSON.parse(fs.readFileSync(`outputs/${DOMAIN}/experiment_config.json`,'utf8'));
const dims   = cfg.dimensions;
const G      = cfg.gram_matrix.map(r=>r.slice());
const K      = dims.length;
const cats   = cfg.inference_categories;

// Replicate buildTrainingPlan: skip the first M=5 dims' best pairs
const M = cfg.num_training_trials || 5;
const usedTrainTrials = new Set();
for (let i = 0; i < Math.min(M, dims.length); i++) {
  let bestT = -1, bestSpread = -1;
  for (let t = 0; t < tp.length; t++) {
    if (usedTrainTrials.has(t)) continue;
    const proj = tp[t].raw_projection;
    const sp = Math.abs(proj[i]);
    if (sp > bestSpread) { bestSpread = sp; bestT = t; }
  }
  if (bestT >= 0) usedTrainTrials.add(bestT);
}
const pool = [];
for (let i = 0; i < trials.length; i++) if (!usedTrainTrials.has(i)) pool.push(i);
const rng = seedRandom(hashStr(PID));
const assigned = shuffle(pool, rng).slice(0, N);

// Simulate participant: choose option with higher target-dim projection; mark "love" on target dim
const targetIdx = dims.findIndex(d => (d.name||d.label) === TARGET);
const responses = [];
for (let i = 0; i < N; i++) {
  const ti = assigned[i];
  const proj = tp[ti].raw_projection;
  const chose = proj[targetIdx] > 0 ? 'a' : 'b';
  // Pick top-5 visible dims by |effective projection|
  const trial = trials[ti];
  const sliders = trial.sliders;
  const vk = chose === 'a' ? 'value_if_a' : 'value_if_b';
  const ranked = sliders.map((s,j)=>({j,abs:Math.abs(s[vk])})).sort((a,b)=>b.abs-a.abs).slice(0,5);
  const visible = ranked.map(x=>sliders[x.j].id);
  // Inference values: target dim → "love" (mult 1.5), others → category from sign
  const iv = {};
  visible.forEach(did => {
    const sli = sliders.find(s=>s.id===did);
    const dimIdx = sliders.indexOf(sli);
    if (dimIdx === targetIdx) {
      iv[did] = { category:'love', action:'none', multiplier:1.5 };
    } else {
      const v = sli[vk];
      let cat = 'indifferent', mult = 0.0;
      if (v > 50) { cat = 'love'; mult = 1.5; }
      else if (v > 20) { cat = 'like'; mult = 1.0; }
      else if (v < -50) { cat = 'skip'; mult = -1.5; }
      else if (v < -20) { cat = 'not_into'; mult = -1.0; }
      iv[did] = { category:cat, action:'none', multiplier:mult };
    }
  });
  responses.push({ trial_id: trial.trial_id, chosen: chose, visible_dimensions: visible, inference_values: iv });
}

// Build U, y, D from the participant's actual responses
const U = []; const y = [];
for (let i = 0; i < N; i++) {
  const ti = assigned[i];
  U.push(tp[ti].raw_projection.slice());
  y.push(responses[i].chosen === 'a' ? 1 : 0);
}
const flat = new Float32Array(fs.readFileSync(`outputs/${DOMAIN}/delta_gram.bin`).buffer);
const nPool = Math.round(Math.sqrt(flat.length));
const D = []; for (let i = 0; i < N; i++) { const row = new Array(N); for (let j = 0; j < N; j++) row[j] = flat[assigned[i]*nPool + assigned[j]]; D.push(row); }

// Build beta_0 from inference_values
const dimIds = dims.map(d => d.id || ('dim_'+d.dimension_id));
const sums = new Array(K).fill(0); const counts = new Array(K).fill(0);
responses.forEach(r => {
  if (!r.inference_values) return;
  Object.entries(r.inference_values).forEach(([did,v]) => {
    const idx = dimIds.indexOf(did); if (idx < 0) return;
    sums[idx] += v.multiplier; counts[idx] += 1;
  });
});
const mean = new Array(K).fill(0); for (let k = 0; k < K; k++) mean[k] = counts[k] > 0 ? sums[k]/counts[k] : 0;
const beta0 = F._solveLinear(G, mean) || new Array(K).fill(0);

const lamS = cfg.comparison.lambda_standard, lamP = cfg.comparison.lambda_partial, nShow = cfg.comparison.n_dimensions_shown;
const t0 = Date.now();
const alpha = F.fitNewtonStandard(D, y, lamS, 15);
const scoresStd = F.scoresFromAlpha(alpha, U);
const beta = F.fitNewtonPartial(U, y, G, beta0, lamP, 15);
const scoresPart = F.scoresFromBeta(beta, G);
const fitMs = Date.now() - t0;

// Build inferences with quintile binning
function buildInferences(scores, n) {
  const idxs = scores.map((s,i)=>({i,abs:Math.abs(s),s})).sort((a,b)=>b.abs-a.abs).slice(0,n);
  const ordered = idxs.slice().sort((a,b)=>b.s-a.s);
  const nCats = cats.length, perBin = Math.ceil(ordered.length/nCats);
  return ordered.map((item,rank)=>{
    const binFromTop = Math.floor(rank/perBin);
    const cat = cats[nCats-1-Math.min(binFromTop,nCats-1)];
    return { dim:dims[item.i].name, category:cat.label, phrase:cat.phrase, score:item.s.toFixed(4) };
  });
}

const stdOnLeft = (hashStr(PID) % 2) === 0;
const left  = stdOnLeft ? 'standard' : 'partial';
const right = stdOnLeft ? 'partial'  : 'standard';
const leftInfs  = buildInferences(stdOnLeft ? scoresStd : scoresPart, nShow);
const rightInfs = buildInferences(stdOnLeft ? scoresPart : scoresStd, nShow);

console.log(`PID=${PID} (hash=${hashStr(PID)}, std on ${stdOnLeft?'left':'right'})`);
console.log(`fit: ${fitMs}ms, lam_std=${lamS}, lam_part=${lamP}, n_show=${nShow}`);
console.log(`\nSummary A (${left}):`);
leftInfs.forEach(i => console.log(`  You ${i.phrase.padEnd(20)} ${i.dim.padEnd(30)} (${i.category})`));
console.log(`\nSummary B (${right}):`);
rightInfs.forEach(i => console.log(`  You ${i.phrase.padEnd(20)} ${i.dim.padEnd(30)} (${i.category})`));

// Final payload structure (matches what the browser sends to Qualtrics)
const payload = {
  participant_id: PID,
  condition: 'inference_categories',
  domain: DOMAIN,
  num_trials: N,
  responses,
  evaluation: {
    fit_duration_ms: fitMs,
    lambda_standard: lamS,
    lambda_partial: lamP,
    n_dimensions_shown: nShow,
    has_multipliers: true,
    left_model: left,
    right_model: right,
    left_inferences: leftInfs.map(i => ({ dim_name:i.dim, category_label:i.category, phrase:i.phrase, score:parseFloat(i.score) })),
    right_inferences: rightInfs.map(i => ({ dim_name:i.dim, category_label:i.category, phrase:i.phrase, score:parseFloat(i.score) })),
    rating: 'B_better',
    rating_numeric: 2,
    response_time_ms: 12340,
  },
};
console.log('\nPayload size:', JSON.stringify(payload).length, 'bytes');
console.log('Eval block:\n', JSON.stringify(payload.evaluation, null, 2));
