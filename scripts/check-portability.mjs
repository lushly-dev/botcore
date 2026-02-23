#!/usr/bin/env node
/**
 * Portability Check — Pre-commit
 *
 * Detects machine-specific paths and localhost URLs that reduce repo portability.
 *
 * Errors:
 * - Windows drive-letter absolute paths (D:\..., C:\...)
 * - User-home absolute paths (C:\Users\name, /home/name, /Users/name)
 *
 * Warnings:
 * - Hardcoded localhost URLs
 *
 * Escape hatch:
 * - Python files: `# portability-ok: reason` on the same or previous line
 * - .mjs files: `// portability-ok: reason` on the same or previous line
 *
 * Allowlist:
 * - Markdown files (*.md) — documentation may reference paths
 */

import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { extname, join, normalize, resolve } from 'node:path';

const CHECK_EXTENSIONS = new Set([
	'.py',
	'.md',
	'.yml',
	'.yaml',
	'.toml',
	'.json',
	'.mjs',
]);
const SKIP_DIRS = new Set([
	'node_modules',
	'.venv',
	'__pycache__',
	'dist',
	'.git',
	'chrome-profile',
	'coverage',
]);
const ESCAPE_HATCH = /portability-ok\s*:/i;
const PATTERNS = [
	{
		id: 'windows-drive-path',
		severity: 'error',
		regex: /(?:^|[\s"'`(=])([A-Za-z]:\\[^'"`\s)]+)/g,
		message: 'Windows absolute path detected',
		suggestion: 'Use repo-relative paths or aliases instead of machine-specific drive paths.',
	},
	{
		id: 'windows-user-home',
		severity: 'error',
		regex: /C:\\Users\\[^\\'"`\s)]+/g,
		message: 'Windows user-home absolute path detected',
		suggestion: 'Use environment variables or relative paths instead of user profile paths.',
	},
	{
		id: 'unix-user-home',
		severity: 'error',
		regex: /(?:^|[\s"'`(=])(\/home\/[A-Za-z0-9._-]+(?:\/|\b))/g,
		message: 'Unix home-directory absolute path detected',
		suggestion: 'Use relative paths or environment variables instead of home-directory paths.',
	},
	{
		id: 'mac-user-home',
		severity: 'error',
		regex: /(?:^|[\s"'`(=])(\/Users\/[A-Za-z0-9._-]+(?:\/|\b))/g,
		message: 'macOS user-directory absolute path detected',
		suggestion: 'Use relative paths or environment variables instead of user-directory paths.',
	},
	{
		id: 'localhost-url',
		severity: 'warn',
		regex: /http:\/\/localhost:\d{4,5}/g,
		message: 'Hardcoded localhost URL detected',
		suggestion:
			'Prefer configurable base URLs or documented setup defaults to avoid environment coupling.',
	},
];

let errors = 0;
let warnings = 0;
let checkedFiles = 0;

function collectFiles(dir, out = []) {
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
			collectFiles(fullPath, out);
			continue;
		}
		if (!entry.isFile()) continue;
		if (!CHECK_EXTENSIONS.has(extname(entry.name))) continue;
		out.push(fullPath);
	}
	return out;
}

function getInputFiles() {
	const args = process.argv.slice(2);
	if (args.length > 0) {
		return args.filter((file) => existsSync(file));
	}

	const files = [];
	const roots = ['src', 'tests', 'scripts', 'docs', '.github'];
	for (const root of roots) {
		collectFiles(resolve(root), files);
	}
	for (const file of ['AGENTS.md', 'README.md', 'SETUP.md', 'CHANGELOG.md']) {
		const fullPath = resolve(file);
		if (existsSync(fullPath)) files.push(fullPath);
	}
	return files;
}

function isAllowed(filePath, _line, _patternId) {
	const normalized = normalize(filePath).replace(/\\/g, '/');
	// Markdown files are allowed — documentation may reference paths
	if (normalized.endsWith('.md')) return true;
	return false;
}

function report(filePath, lineNum, severity, message, excerpt, suggestion) {
	const cwd = process.cwd().replace(/\\/g, '/');
	const name = normalize(filePath).replace(/\\/g, '/').replace(cwd, '.');
	const label = severity === 'error' ? '✘' : '⚠';
	if (severity === 'error') {
		errors++;
		console.error(`  ${label} ${name}:${lineNum}  ${message}`);
		console.error(`    ${excerpt}`);
		console.error(`    💡 ${suggestion}\n`);
		return;
	}
	warnings++;
	console.warn(`  ${label} ${name}:${lineNum}  ${message}`);
	console.warn(`    ${excerpt}`);
	console.warn(`    💡 ${suggestion}\n`);
}

function scanFile(filePath) {
	const normalizedPath = normalize(filePath).replace(/\\/g, '/');
	// Skip self
	if (normalizedPath.endsWith('/scripts/check-portability.mjs')) return;

	let content = '';
	try {
		content = readFileSync(filePath, 'utf-8');
	} catch {
		return;
	}

	const lines = content.split('\n');
	checkedFiles++;

	for (let i = 0; i < lines.length; i++) {
		const line = lines[i];
		const prev = i > 0 ? lines[i - 1] : '';
		// Skip comment-only lines (Python # and JS //)
		if (/^\s*(#|\/\/|\/\*|\*|\*\/)/.test(line)) continue;
		if (ESCAPE_HATCH.test(line) || ESCAPE_HATCH.test(prev)) continue;

		for (const pattern of PATTERNS) {
			pattern.regex.lastIndex = 0;
			const matches = [...line.matchAll(pattern.regex)];
			if (matches.length === 0) continue;
			if (isAllowed(filePath, line, pattern.id)) continue;
			report(
				filePath,
				i + 1,
				pattern.severity,
				pattern.message,
				line.trim().slice(0, 140),
				pattern.suggestion,
			);
		}
	}
}

const files = getInputFiles();
for (const filePath of files) {
	scanFile(filePath);
}

if (warnings > 0) {
	console.warn(`\n⚠  ${warnings} portability warning(s)`);
}
if (errors > 0) {
	console.error(`❌ ${errors} portability error(s) across ${checkedFiles} file(s) checked`);
	process.exit(1);
}
process.exit(0);
