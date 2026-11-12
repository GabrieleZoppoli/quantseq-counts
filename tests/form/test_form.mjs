// The form page's file writers: same settings.yaml as `quantseq-counts setup` for the same answers.
// Usage: node tests/form/test_form.mjs   (from the repository root; Node 18+, no packages)
import { readFileSync } from 'node:fs';
import { buildSettings, buildSamples, warningsFor } from '../../docs/form.js';

const schema = JSON.parse(readFileSync('docs/settings.schema.json', 'utf8'));
let fails = 0;
const ok = (cond, what) => { console.log(`${cond ? 'ok' : 'FAIL'} - ${what}`); if (!cond) fails++; };

const answers = JSON.parse(readFileSync('tests/python/fixtures/form_answers.json', 'utf8'));
answers.samples = 'samples.csv';
const expected = readFileSync('tests/python/fixtures/form_settings.yaml', 'utf8');
ok(buildSettings(answers, schema) === expected, 'settings.yaml equal to the one setup writes');

const pasted = 'sample\tfastq\tgroup\r\nA1\ta1.fastq.gz\tcase\r\nB2 \t b2.fastq.gz\t\r\n\r\n';
ok(buildSamples(pasted) === 'sample,fastq,group\nA1,a1.fastq.gz,case\nB2,b2.fastq.gz,\n', 'pasted spreadsheet block to samples.csv');
ok(buildSamples('A1\ta1.fastq.gz\n') === 'sample,fastq,group\nA1,a1.fastq.gz,\n', 'a block without header');

const w = warningsFor({ ...answers, strand: 'reverse' }, schema);
ok(w.length === 1 && w[0] === schema.settings.strand.warning, 'reverse strand gives its warning');
ok(warningsFor(answers, schema).length === 0, 'standard settings give no warning');

const quoted = buildSettings({ ...answers, slurm_account: "it's" }, schema);
ok(quoted.includes("slurm_account: 'it''s'"), 'quotes doubled as in YAML');
console.log(fails === 0 ? 'RESULT: PASS' : 'RESULT: FAIL'); process.exit(fails ? 1 : 0);
