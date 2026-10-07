#!/usr/bin/env node
/**
 * check-anonymized.mjs — the privacy gate.
 *
 * Fails (exit 1) if anything that looks like personal or private data is
 * present in the sources or in the built output. Two kinds of check:
 *
 *   1. shape checks  — data that is never allowed: addresses, personal paths,
 *                      credentials, long numbers that look like phone numbers;
 *   2. term checks   — the actual names and identifiers that must not be
 *                      published, read from `.private-terms` (git-ignored, so
 *                      the repository holds the mechanism and the machine
 *                      holds the list).
 *
 * It always reports what it scanned. "0 findings" from a walker that read
 * nothing is not a pass, and the difference must be visible in the output.
 *
 *   node scripts/check-anonymized.mjs [--terms .private-terms] [--quiet]
 */

import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs';
import { join, relative, extname, sep } from 'node:path';

const args = process.argv.slice(2);
const flag = (name, fallback) => {
  const i = args.indexOf(name);
  return i === -1 ? fallback : args[i + 1];
};
const TERMS_FILE = flag('--terms', '.private-terms');
const QUIET = args.includes('--quiet');

/** Directories walked, in order. `dist` is optional (needs a build first). */
const ROOTS = ['src', 'scripts', 'public', 'README.md', 'ANONYMIZATION.md', 'package.json', 'astro.config.mjs', 'dist'];
const SKIP_DIRS = new Set(['node_modules', '.git', '.astro', '.verify', '.research', 'dist/assets']);

/** Only these are scanned inside dist/: the published documents, not the JS. */
const DIST_TEXT = new Set(['.html', '.xml', '.txt', '.css', '.json']);

/** Emails that are placeholders by construction. */
const EMAIL_ALLOW = [/@example\.(com|org|net)$/i, /@localhost$/i];

/** Addresses that carry no information. */
const IP_ALLOW = [
  /^127\.0\.0\.1$/,
  /^0\.0\.0\.0$/,
  /^255\.255\.255\.0$/,
  /^10\./,
  /^192\.0\.2\./,
  /^198\.51\.100\./,
  /^203\.0\.113\./,
];

/** Placeholder usernames in documented paths: <user>, %USERNAME%, "me". */
const PATH_ALLOW = /^(user|username|USER|USERNAME|me|name|your|you|someone|somebody|example|test|demo|fake|sample|<|\{|\$|%)/;

/** A path segment only looks like a person's if it starts with an ASCII
 *  word character; "…", "<user>" and "%USERNAME%" are placeholders. */
const isPlaceholderUser = (segment) =>
  !/^[A-Za-z0-9_]/.test(segment) || PATH_ALLOW.test(segment);

const SHAPES = [
  {
    id: 'email address',
    re: /[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+/g,
    allow: (m) => EMAIL_ALLOW.some((r) => r.test(m)),
  },
  {
    id: 'IPv4 address',
    re: /\b(?:\d{1,3}\.){3}\d{1,3}\b/g,
    allow: (m) => IP_ALLOW.some((r) => r.test(m)),
  },
  {
    id: 'personal path',
    // the first capture group is the user segment
    re: /(?<![A-Za-z0-9])(?:[A-Za-z]:[\\/]Users[\\/]|\/home\/|\/Users\/)([A-Za-z0-9._-]*)/g,
    allow: (m, captures) => isPlaceholderUser(captures[0] ?? ''),
  },
  {
    id: 'credential',
    re: /\b(?:sk-[A-Za-z0-9_-]{16,}|ghp_[A-Za-z0-9]{20,}|gho_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{12,}|xox[baprs]-[A-Za-z0-9-]{10,})\b/g,
  },
  {
    id: 'private key',
    re: /-----BEGIN [A-Z ]*PRIVATE KEY-----/g,
  },
  {
    id: 'bearer token',
    re: /\bBearer\s+[A-Za-z0-9._~+/=-]{24,}/g,
  },
  {
    id: 'password assignment',
    re: /\b(?:password|passwd|pwd|secret|api[_-]?key|token)\s*[:=]\s*["'][^"'\s]{8,}["']/gi,
  },
  {
    id: 'phone number',
    re: /\+\d[\d\s().-]{8,}\d/g,
    allow: (m) => /U\+\d/.test(m),
  },
];

function walk(root, out = []) {
  if (!existsSync(root)) return out;
  const st = statSync(root);
  if (st.isFile()) {
    out.push(root);
    return out;
  }
  for (const entry of readdirSync(root)) {
    const full = join(root, entry);
    if (SKIP_DIRS.has(full.split(sep).join('/').replace(/^\.\//, ''))) continue;
    if (SKIP_DIRS.has(entry)) continue;
    const s = statSync(full);
    if (s.isDirectory()) walk(full, out);
    else out.push(full);
  }
  return out;
}

function isScannable(file) {
  const ext = extname(file);
  const normalised = file.split(sep).join('/');
  if (normalised.startsWith('dist/')) return DIST_TEXT.has(ext);
  return true;
}

// --- load the private term list -------------------------------------------

let terms = [];
let termsSource = 'none';
if (existsSync(TERMS_FILE)) {
  termsSource = TERMS_FILE;
  terms = readFileSync(TERMS_FILE, 'utf8')
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter((l) => l && !l.startsWith('#'));
}

// --- scan ------------------------------------------------------------------

const files = [];
for (const root of ROOTS) walk(root, files);
const scannable = files.filter(isScannable);

const findings = [];
let bytes = 0;
let read = 0;

for (const file of scannable) {
  let text;
  try {
    text = readFileSync(file, 'utf8');
  } catch {
    continue; // binary
  }
  if (text.includes('\u0000')) continue; // binary
  read += 1;
  bytes += Buffer.byteLength(text);

  const lines = text.split(/\r?\n/);
  const flat = text.replace(/\s+/g, ' ');

  for (const shape of SHAPES) {
    // scan the flattened text so a term split across a line break is still seen,
    // but report the line it came from
    for (const match of flat.matchAll(shape.re)) {
      const captures = match.slice(1); // captures[0] is the first group
      if (shape.allow?.(match[0], captures)) continue;
      findings.push({ file, id: shape.id, sample: match[0].slice(0, 60) });
    }
  }

  for (const term of terms) {
    const re = new RegExp(term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi');
    for (const match of flat.matchAll(re)) {
      const line = lines.findIndex((l) => l.toLowerCase().includes(term.toLowerCase()));
      findings.push({
        file,
        id: `private term "${term}"`,
        sample: `…${flat.slice(Math.max(0, match.index - 30), match.index + 40)}…`,
        line: line === -1 ? undefined : line + 1,
      });
    }
  }
}

// --- report ----------------------------------------------------------------

const rel = (f) => relative(process.cwd(), f).split(sep).join('/');

if (!QUIET) {
  console.log(`scanned ${read} files (${(bytes / 1024).toFixed(1)} KB) across: ${ROOTS.join(', ')}`);
  console.log(`term list: ${terms.length} term${terms.length === 1 ? '' : 's'} from ${termsSource}`);
  if (terms.length === 0) {
    console.log('  note: no terms loaded — private names in the text would NOT be caught by the term checks');
  }
}

if (findings.length === 0) {
  console.log(`\nOK — ${read} files, 0 findings`);
  process.exit(0);
}

console.log(`\n${findings.length} finding${findings.length === 1 ? '' : 's'}:`);
for (const f of findings) {
  console.log(`  ${rel(f.file)}${f.line ? `:${f.line}` : ''}  [${f.id}]  ${f.sample}`);
}
console.log('\nFix or generalise the text above, then run this again.');
process.exit(1);
