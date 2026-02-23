#!/usr/bin/env node
/**
 * File Size Enforcement — Pre-commit
 *
 * Checks Python source files against line count thresholds.
 * Runs on staged files. Exit code 1 = violations found.
 *
 * Thresholds:
 *   WARN:  300 lines (non-blocking)
 *   ERROR: 500 lines (blocks commit)
 *
 * Escape hatch (lines 1-5 of file):
 *   # botcore-override: max-lines=N
 *   Where N ≤ 1000 (hard cap). File must still be under N lines.
 *
 * Skip patterns: test_*.py, conftest.py, __init__.py, .pyc
 */

import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { basename, extname, join, resolve } from 'node:path';

// ─── Config ──────────────────────────────────────────────────────────────────

const WARN_THRESHOLD = 300;
const ERROR_THRESHOLD = 500;
const OVERRIDE_CAP = 1000;
const OVERRIDE_PATTERN = /#\s*botcore-override:\s*max-lines=(\d+)/;

// Skip patterns
const SKIP_PREFIXES = ['test_'];
const SKIP_NAMES = new Set(['conftest.py', '__init__.py']);
const SKIP_DIRS = new Set([
	'node_modules',
	'.venv',
	'__pycache__',
	'dist',
	'.git',
	'chrome-profile',
]);

// ─── Helpers ─────────────────────────────────────────────────────────────────

const args = process.argv.slice(2);

let violations = 0;
let warnings = 0;
let overrides = 0;
let checkedFiles = 0;

function report(file, lineCount, rule, suggestion) {
	violations++;
	const name = basename(file);
	console.error(`  ✘ ${name}  ${rule}`);
	console.error(`    ${lineCount} lines`);
	console.error(`    💡 ${suggestion}\n`);
}

function warn(file, lineCount, rule, suggestion) {
	warnings++;
	const name = basename(file);
	console.warn(`  ⚠ ${name}  ${rule}`);
	console.warn(`    ${lineCount} lines`);
	console.warn(`    💡 ${suggestion}\n`);
}

function shouldSkip(filePath) {
	const name = basename(filePath);
	const ext = extname(filePath);

	// Only check .py files
	if (ext !== '.py') return true;

	// Skip .pyc files
	if (name.endsWith('.pyc')) return true;

	// Skip test files and known small files
	if (SKIP_NAMES.has(name)) return true;
	for (const prefix of SKIP_PREFIXES) {
		if (name.startsWith(prefix)) return true;
	}

	// Skip files in excluded directories
	for (const dir of SKIP_DIRS) {
		if (filePath.includes(`/${dir}/`) || filePath.includes(`\\${dir}\\`)) return true;
	}

	return false;
}

function parseOverride(lines) {
	// Check first 5 lines for override comment
	const head = lines.slice(0, 5);
	for (const line of head) {
		const match = line.match(OVERRIDE_PATTERN);
		if (match) {
			return parseInt(match[1], 10);
		}
	}
	return null;
}

function collectPyFiles(dir, out = []) {
	if (!existsSync(dir)) return out;
	let entries = [];
	try {
		entries = readdirSync(dir, { withFileTypes: true });
	} catch {
		return out;
	}
	for (const entry of entries) {
		if (entry.name.startsWith('.')) continue;
		if (SKIP_DIRS.has(entry.name)) continue;
		const fullPath = join(dir, entry.name);
		if (entry.isDirectory()) {
			collectPyFiles(fullPath, out);
			continue;
		}
		if (!entry.isFile()) continue;
		if (extname(entry.name) !== '.py') continue;
		out.push(fullPath);
	}
	return out;
}

function getInputFiles() {
	if (args.length > 0) {
		return args.filter((file) => existsSync(file));
	}
	// Full scan mode: check src/ and scripts/
	const files = [];
	for (const root of ['src', 'scripts']) {
		collectPyFiles(resolve(root), files);
	}
	return files;
}

// ─── Main ────────────────────────────────────────────────────────────────────

const files = getInputFiles();

if (files.length === 0) {
	process.exit(0);
}

for (const filePath of files) {
	if (shouldSkip(filePath)) continue;

	let content;
	try {
		content = readFileSync(filePath, 'utf-8');
	} catch {
		continue;
	}

	const lines = content.split('\n');
	const lineCount = lines.length;
	checkedFiles++;

	const override = parseOverride(lines);

	if (override !== null) {
		overrides++;

		// Validate override cap
		if (override > OVERRIDE_CAP) {
			report(
				filePath,
				lineCount,
				`Override max-lines=${override} exceeds hard cap of ${OVERRIDE_CAP}`,
				`Reduce the override to ≤${OVERRIDE_CAP} or refactor the file into smaller modules`,
			);
			continue;
		}

		// Check against override threshold
		if (lineCount > override) {
			report(
				filePath,
				lineCount,
				`File exceeds its own override limit of ${override} lines`,
				`Refactor to stay under ${override} lines, or increase the override (max ${OVERRIDE_CAP})`,
			);
		}
		// Override file within limit — no warning even if above default thresholds
		continue;
	}

	// No override — check against default thresholds
	if (lineCount > ERROR_THRESHOLD) {
		report(
			filePath,
			lineCount,
			`File exceeds ${ERROR_THRESHOLD} lines (no override)`,
			`Split into smaller modules, or add # botcore-override: max-lines=N (≤${OVERRIDE_CAP}) in the first 5 lines with justification`,
		);
	} else if (lineCount > WARN_THRESHOLD) {
		warn(
			filePath,
			lineCount,
			`File approaching size limit (>${WARN_THRESHOLD} lines)`,
			`Consider splitting. Will block at ${ERROR_THRESHOLD} lines.`,
		);
	}
}

// ─── Summary ─────────────────────────────────────────────────────────────────

if (checkedFiles > 0) {
	if (warnings > 0) {
		console.warn(`\n  ⚠ ${warnings} file size warning(s) (non-blocking)`);
	}
	if (overrides > 0) {
		console.log(`  ℹ ${overrides} file(s) with botcore-override`);
	}
}

if (violations > 0) {
	console.error(
		`\n  ✘ ${violations} file size violation(s) across ${checkedFiles} file(s) checked`,
	);
	console.error(
		`    Add # botcore-override: max-lines=N for legitimate exceptions\n`,
	);
	process.exit(1);
}
