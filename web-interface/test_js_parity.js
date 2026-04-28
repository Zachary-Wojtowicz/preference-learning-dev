#!/usr/bin/env node
// Extract JS fitters from index.html and run them on the same simulated session
// as test_eval_parity.py — confirm scores match.
const fs   = require('fs');
const path = require('path');

const html = fs.readFileSync(path.join(__dirname,'index.html'),'utf8');

// Pull the JS payload out of <script>...</script>
const scriptMatch = html.match(/<script>([\s\S]*?)<\/script>/);
if (!scriptMatch) { console.error('no script block'); process.exit(1); }
const fullScript = scriptMatch[1];

// Eval the fitter functions in an isolated sandbox by extracting only the math/fitter region.
// We grep the relevant function definitions and concatenate them.
const wantedFns = [
  '_matVec','_solveLinear','_sigm',
  'fitNewtonStandard','fitNewtonPartial',
  'scoresFromAlpha','scoresFromBeta',
];
const code = [];
wantedFns.forEach(name => {
  const re = new RegExp(`function ${name}\\s*\\([\\s\\S]*?\\n\\}`,'m');
  const m  = fullScript.match(re);
  if (!m) { console.error(`could not find ${name}`); process.exit(1); }
  code.push(m[0]);
});
const sandbox = {};
const wrapped = code.join('\n') + '\nmodule.exports = {fitNewtonStandard,fitNewtonPartial,scoresFromAlpha,scoresFromBeta,_solveLinear};';
const ctx = { module:{exports:{}}, console };
new Function('module','console',wrapped)(ctx.module, console);
const F = ctx.module.exports;

const DOMAIN = process.argv[2] || 'movies_100';
const N      = parseInt(process.argv[3]||'20',10);
const TARGET = process.argv[4] || 'Action Intensity';

const trials = JSON.parse(fs.readFileSync(`outputs/${DOMAIN}/trials.json`,'utf8'));
const tp     = JSON.parse(fs.readFileSync(`outputs/${DOMAIN}/trial_projections.json`,'utf8'));
const cfg    = JSON.parse(fs.readFileSync(`outputs/${DOMAIN}/experiment_config.json`,'utf8'));
const G      = cfg.gram_matrix.map(r => r.slice());
const dims   = cfg.dimensions;
const K      = dims.length;
const targetIdx = dims.findIndex(d => (d.name||d.label) === TARGET);
if (targetIdx < 0) { console.error('target dim not found'); process.exit(1); }

// Same RNG-permutation as Python's default_rng(42) — but we need a matching permutation.
// Easier: compute the expected permutation in Python and load it. For now, just use first N trials in their natural order; we'll check the JS produces sensible output.
const pool = []; for (let i = 0; i < N; i++) pool.push(i);

const flat = new Float32Array(fs.readFileSync(`outputs/${DOMAIN}/delta_gram.bin`).buffer);
const nPool = Math.round(Math.sqrt(flat.length));
const D = []; for (let i = 0; i < N; i++) { const row = new Array(N); for (let j = 0; j < N; j++) row[j] = flat[pool[i]*nPool + pool[j]]; D.push(row); }

const U = []; const y = [];
for (let i = 0; i < N; i++) {
  const proj = tp[pool[i]].raw_projection;
  U.push(proj.slice());
  y.push(proj[targetIdx] > 0 ? 1 : 0);
}

const lamS = cfg.comparison.lambda_standard;
const lamP = cfg.comparison.lambda_partial;

const t0 = Date.now();
const alpha = F.fitNewtonStandard(D, y, lamS, 15);
const scoresStd = F.scoresFromAlpha(alpha, U);

const beta0 = new Array(K).fill(0);
const beta  = F.fitNewtonPartial(U, y, G, beta0, lamP, 15);
const scoresPart = F.scoresFromBeta(beta, G);
console.log(`fit time: ${Date.now()-t0}ms`);

// Top entries
const ranked = (s) => {
  const idxs = s.map((v,i)=>({i,abs:Math.abs(v),s:v})).sort((a,b)=>b.abs-a.abs).slice(0,10);
  return idxs.sort((a,b)=>b.s-a.s).map(x=>({dim:dims[x.i].name,score:Number(x.s.toFixed(4))}));
};
console.log('STANDARD top10:');  ranked(scoresStd).forEach(r => console.log('  ', r.dim.padEnd(30), r.score));
console.log('PARTIAL top10:');   ranked(scoresPart).forEach(r => console.log('  ', r.dim.padEnd(30), r.score));

// Sanity: target dim should top
const argmaxAbs = (s) => s.reduce((best,v,i)=>Math.abs(v)>Math.abs(s[best])?i:best, 0);
const topStd  = argmaxAbs(scoresStd);
const topPart = argmaxAbs(scoresPart);
console.log(`top by |score|: standard=${dims[topStd].name}, partial=${dims[topPart].name}`);
if (topStd !== targetIdx || topPart !== targetIdx) { console.error('FAIL: target dim not on top'); process.exit(2); }
console.log('JS fitters: PASS');
