// quantseq-counts settings page: builds settings.yaml and samples.csv in the browser. Nothing typed here is sent
// anywhere. The writers below produce the same text as `quantseq-counts setup` (src/quantseq_counts/settings.py).

const yamlScalar = (v) => {
  if (v === null || v === undefined || v === '') return 'null';
  if (typeof v === 'boolean') return v ? 'true' : 'false';
  if (typeof v === 'number' && Number.isInteger(v)) return String(v);
  return "'" + String(v).replace(/'/g, "''") + "'";
};

export function withDefaults(answers, schema) {
  const out = {};
  for (const [k, e] of Object.entries(schema.settings)) out[k] = e.default;
  out.package_version = schema.package_version;
  for (const [k, v] of Object.entries(answers)) if (k in schema.settings) out[k] = v;
  return out;
}

export function buildSettings(answers, schema) {
  const full = withDefaults(answers, schema);
  const lines = ['# quantseq-counts settings. Edit a value, keep the key. Every setting is explained above it.', ''];
  let group = null;
  for (const [k, e] of Object.entries(schema.settings)) {
    if (e.group !== group) {
      group = e.group;
      lines.push(`# ---- ${group === 'basic' ? 'basic settings' : 'advanced settings'} ----`, '');
    }
    lines.push(`# ${e.help}`, `${k}: ${yamlScalar(full[k])}`, '');
  }
  return lines.join('\n');
}

export function buildSamples(text) {
  const rows = text.replace(/^﻿/, '').replace(/\r\n?/g, '\n').split('\n')
    .map((l) => l.split(/\t|,/).map((c) => c.trim())).filter((r) => r.some((c) => c));
  if (rows.length && rows[0][0].toLowerCase() === 'sample') rows.shift();
  return ['sample,fastq,group', ...rows.map((r) => `${r[0]},${r[1] || ''},${r[2] || ''}`)].join('\n') + '\n';
}

export function samplesFromNames(text) {
  const suf = ['.fastq.gz', '.fq.gz', '.fastq', '.fq'];
  const rows = text.split(/\s+/).filter(Boolean).map((n) => {
    const s = suf.find((x) => n.endsWith(x));
    return s ? `${n.slice(0, -s.length)}\t${n}` : null;
  }).filter(Boolean);
  return buildSamples(rows.join('\n'));
}

export function warningsFor(answers, schema) {
  const full = withDefaults(answers, schema);
  return Object.entries(schema.settings)
    .filter(([k, e]) => e.warn_if && e.warn_if.includes(full[k])).map(([, e]) => e.warning);
}

// ---------------------------------------------------------------- the page (browser only)

function field(key, e, value) {
  const id = `f_${key}`;
  const wrap = document.createElement('div');
  wrap.className = 'field';
  wrap.dataset.key = key;
  const label = document.createElement('label');
  label.htmlFor = id;
  label.innerHTML = `<code>${key}</code><span>${e.help}</span>`;
  let input;
  if (e.enum) {
    input = document.createElement('select');
    for (const opt of e.enum) {
      const o = document.createElement('option');
      o.value = String(opt); o.textContent = String(opt);
      input.append(o);
    }
    input.value = String(value ?? e.default);
  } else if (e.type === 'boolean') {
    input = document.createElement('input');
    input.type = 'checkbox';
    input.checked = Boolean(value ?? e.default);
  } else {
    input = document.createElement('input');
    input.type = e.type.startsWith('integer') ? 'number' : 'text';
    if (e.type.startsWith('integer')) input.min = e.minimum ?? 0;
    input.value = value ?? (e.default ?? '');
    if (e.type === 'path') input.placeholder = '/path/on/the/server';
  }
  input.id = id;
  input.name = key;
  wrap.append(label, input);
  return wrap;
}

function readValue(e, input) {
  if (e.type === 'boolean') return input.checked;
  const v = input.value.trim();
  if (v === '') return null;
  if (e.type.startsWith('integer')) return Number.parseInt(v, 10);
  if (e.type === 'auto_or_boolean' && v !== 'auto') return v === 'true';
  return v;
}

function download(name, text) {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([text], { type: 'text/plain' }));
  a.download = name;
  a.click();
  URL.revokeObjectURL(a.href);
}

async function start() {
  const schema = await (await fetch('settings.schema.json')).json();
  document.getElementById('version').textContent = schema.package_version;
  const basic = document.getElementById('basic');
  const adv = document.getElementById('advanced');
  for (const [k, e] of Object.entries(schema.settings)) {
    if (k === 'package_version' || k === 'samples') continue;
    (e.group === 'basic' ? basic : adv).append(field(k, e));
  }
  const answers = () => {
    const a = { samples: 'samples.csv' };
    for (const div of document.querySelectorAll('.field[data-key]')) {
      const k = div.dataset.key;
      a[k] = readValue(schema.settings[k], div.querySelector('input, select'));
    }
    return a;
  };
  const showConditional = () => {
    const a = answers();
    const vis = { fasta: a.reference === 'custom', gtf: a.reference === 'custom', slurm_queue: a.executor === 'slurm',
      slurm_account: a.executor === 'slurm', max_cpus: a.executor === 'local', max_memory: a.executor === 'local',
      udocker_dir: a.engine === 'udocker' };
    for (const [k, v] of Object.entries(vis)) document.querySelector(`.field[data-key="${k}"]`).hidden = !v;
    const w = warningsFor(a, schema);
    const box = document.getElementById('warnings');
    box.hidden = w.length === 0;
    box.innerHTML = w.map((x) => `<p>${x}</p>`).join('');
  };
  document.getElementById('form').addEventListener('input', showConditional);
  showConditional();
  const samplesText = () => {
    const pasted = document.getElementById('pasted').value;
    return pasted.trim() ? buildSamples(pasted) : samplesFromNames(document.getElementById('names').value);
  };
  document.getElementById('get-settings').addEventListener('click', () => download('settings.yaml', buildSettings(answers(), schema)));
  document.getElementById('get-samples').addEventListener('click', () => download('samples.csv', samplesText()));
  document.getElementById('preview').addEventListener('click', () => {
    document.getElementById('preview-out').textContent = samplesText();
  });
}

if (typeof document !== 'undefined') start();
