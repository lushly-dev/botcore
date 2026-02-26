# Changelog

All notable changes to botcore will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **botcore-connectors** -- New plugin package for typed HTTP connectors (`pip install botcore-connectors`)
  - **Connector base layer** (spec 01) -- `ConnectorBase` with inlined retry, rate-limiting, backoff, telemetry (trace ID + timing), and HTTP-to-error-code mapping. `ConnectorContext` Pydantic model for shared config.
  - **Auth & credential resolution** (spec 02) -- `DefaultCredentialResolver` with env var → `gh` CLI fallback chain, token caching with TTL, 401 auto-retry with invalidation, and token redaction from logs/serialization.
  - **Config & plugin wiring** (spec 03) -- `ConnectorsConfig` Pydantic model with per-connector sub-models, `[connectors].enabled` filtering, `ConnectorsPlugin` with two-phase init and `BotCorePlugin` protocol conformance.
  - **Security model** (spec 04) -- Input validation helpers (`check_max_length`, `check_owner_repo`, `check_no_path_traversal`, `validate_inputs`), scope enforcement (`check_scope`), and structured audit logging with `sanitize_args`.
  - **GitHub connector** (spec 05) -- `GitHubConnector` subclass with dual rate-limit tracking (API vs search), `X-RateLimit-Reset` backoff, error remapping (NOT_FOUND → GITHUB_NOT_FOUND, etc.), and 8 commands: `github_issue_create`, `github_issue_list`, `github_issue_comment`, `github_pr_create`, `github_pr_list`, `github_pr_review`, `github_search_code`, `github_search_issues`. 248 tests passing.
- **Lefthook git hooks** -- Pre-commit, pre-push, and on-demand quality gate hooks
  - `check-file-size.mjs` -- Warn >300 lines, error >500, hard cap 1000 with `# botcore-override: max-lines=N` escape hatch
  - `check-portability.mjs` -- Detect machine-specific paths in Python source
  - Pre-commit: ruff check --fix (staged), ruff format (staged), portability, file-size
  - Pre-push: Full ruff lint, format-check, pytest, portability, file-size
  - On-demand `check`: Same as pre-push
- **Comprehensive test coverage** -- 22+ tests covering non-CDP modules (#1)
- **do-documentation-update** -- standalone skill for documentation update passes (CHANGELOG, AGENTS.md, README.md, specs, roadmap, link verification). Includes changelog-versioning reference covering SemVer, git tags, comparison links, and monorepo strategies.
- **do-clean-repo** -- periodic repo cleanup skill for stale branches, orphaned worktrees, dead test files, agent artifacts, build output, orphaned configs, and lockfile hygiene. Scan and full modes with confirmation before destructive actions.
- **retry_async** -- shared async retry utility in `botcore.utils.runner` with configurable attempts, delay, and input validation. CDP retry loops refactored to use it.
- **PluginRegistry.add_middleware()** -- registration stub for plugin middleware callables (foundation for future command pre/post-processing chain)
- **5 active plugin specs** -- LLM Runtime, Agent Orchestration, Connectors, Memory System, and Teams Interface plugin specs with AFD integration sections

### Changed

- **botcore.toml** -- Expanded configuration with language, tooling, threshold, and hygiene settings
- **CONTRIBUTING.md** -- Comprehensive rewrite with lefthook setup, development workflow, and contribution guidelines
- **do-commit** -- Step 3 (Documentation Gate) now delegates to the `do-documentation-update` skill instead of inlining checks. Adds spec completion, roadmap updates, and link verification to the documentation pass.

## [0.2.1] - 2026-02-22

### Changed

- Promoted project status from Alpha to Beta across repository docs and package metadata.

## [0.2.0] - 2026-02-22

### Changed

- Migrated to standalone repository from `libraries/py/packages/botcore`

### Added

- `do-commit`, `do-pr`, `do-release`, `do-review`, `do-hotfix` action skills
- `automate-browsers`, `build-botcore-plugins`, `configure-botcore`, `run-dev-checks` skills
- 52 bundled universal skills total
- Multi-language project support. `LanguageConfig` model with per-language `root`, `linter`, `test_runner`, `formatter`. `language_config` dict on `BotCoreConfig` with `languages` property and `get_tools_for()` method. `resolve_language()` 5-step priority chain (explicit override → root prefix → package override → marker walkup → primary fallback). All dev commands (`lint`, `test`, `build`) accept `--language` and `--path` params. Quality commands (`check-size`, `check-coverage`, `check-deps`) dispatch to npm/cargo ecosystems. Analysis commands (`dead-code`, `circular-imports`, `unused-deps`, `dep-graph`) dispatch to knip, madge, depcheck, cargo-udeps, cargo-modules. `run_external_tool()` helper with skip-with-warning behavior. Multi-language "run all" mode. Config validation warns on primary language not in `language_config` and overlapping root prefixes. `language` field added to `PackageOverrideConfig`. 24 new tests.

## [0.1.0] - 2026-02-19

Initial release (developed in `libraries/py/packages/botcore`).

### Added

- Shared bot infrastructure package (Phases 1a–1c). Config system, plugin contract, and full command extraction from lushbot: dev commands (lint, test, build, quality gates, analysis, portability), docs (lint, changelog, agents), CDP browser automation (28 commands), research (Gemini + Google), spec lifecycle, and undo/history. Language-aware dispatch (Python/TypeScript/Rust). 80 tests.
- Skill registry (Phase 2). 6 new commands: `skill_seed` (copy skills with `source:` ownership), `skill_list` (installed + available), `skill_status` (version drift detection), `skill_lint` (SK001–SK015 quality rules), `skill_adopt` (claim unmanaged skills), `skill_index` (generate `_index.md`). YAML frontmatter engine with `SkillManifest` model. Three-tier skill ownership via `source:` protocol. 21 bundled universal skills. 70 new tests (150 total).
- Unified plugin system (Phase 3). MCP server factory (`create_mcp_server`), dynamic namespace builder (`build_namespace`), and docs aggregator (`build_docs`). Plugin commands and docs automatically wired into MCP and CLI surfaces. `PluginRegistry` gains `add_docs()`/`docs` for topic-based documentation. `CORE_DOCS` dict centralizes botcore command documentation. 22 new tests (172 total).
- Phase 1d: lushbot wired to botcore plugin system. `LushxPlugin` registers agent commands + afd-lint + docs via `botcore.plugins` entry point. Dead extension code removed (~100 lines).
