# Diagnostics Commands Reference

## cdp_screenshot()

```python
async def cdp_screenshot(
    path: str | None = None,
    full_page: bool = False,
) -> CommandResult[dict]
```

Captures a screenshot of the current page.

**Parameters:**
| Parameter | Default | Description |
|---|---|---|
| `path` | None | Save path (auto-generated with timestamp if not specified) |
| `full_page` | False | Capture full scrollable page vs visible viewport |

**Default path:** `{workspace}/.botcore/screenshots/{timestamp}.png`

**Return data:** `path` (saved file path), `full_page` (bool)

**Tips:**
- Take screenshots after navigation to verify the page loaded correctly
- Use `full_page=True` for long pages to capture everything
- Screenshots are saved as PNG files

## cdp_console()

```python
async def cdp_console(
    tail: int | None = None,
    level: str | None = None,
    grep: str | None = None,
    clear: bool = False,
) -> CommandResult[dict]
```

Shows captured console log entries with filtering options.

**Parameters:**
| Parameter | Default | Description |
|---|---|---|
| `tail` | None | Show only the last N entries |
| `level` | None | Filter by level (comma-separated: "log,error,warning") |
| `grep` | None | Regex pattern to search in message text |
| `clear` | False | Clear the console log after returning entries |

**Return data:**
- `entries` — List of `ConsoleEntry` objects with: `timestamp`, `level`, `text`, `url`
- `count` — Number of entries returned

**Examples:**
```
cdp_console()                            — all entries
cdp_console(tail=10)                     — last 10 entries
cdp_console(level="error")               — errors only
cdp_console(level="error,warning")       — errors and warnings
cdp_console(grep="TypeError")            — search for TypeErrors
cdp_console(clear=True)                  — return all and clear
```

## cdp_trace_capture()

```python
async def cdp_trace_capture(
    url: str | None = None,
    path: str | None = None,
    name: str | None = None,
    wait_until: str = "load",
    settle_ms: int = 0,
    categories: str | None = None,
    stream_format: str = "json",
    stream_compression: str = "none",
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
) -> CommandResult[dict]
```

Captures a real Chrome DevTools performance trace in a single browser connection. Optionally navigates first, waits for settle time, and then writes a trace artifact that Perfetto can query directly.

**Parameters:**
| Parameter | Default | Description |
|---|---|---|
| `url` | None | Optional URL to navigate to before stopping the trace |
| `path` | None | Optional output path |
| `name` | None | Optional trace name used for artifact naming |
| `wait_until` | `"load"` | Navigation wait mode when `url` is provided |
| `settle_ms` | `0` | Extra wait after navigation before stopping the trace |
| `categories` | None | Optional comma-separated trace categories override |
| `stream_format` | `"json"` | Trace stream format passed through to CDP |
| `stream_compression` | `"none"` | Optional trace stream compression |
| `timeout_ms` | `DEFAULT_TIMEOUT_MS` | Maximum wait for trace completion |

**Return data:** `path`, `kind`, `url`, `waitUntil`, `settleMs`, `categories`, `streamFormat`, `streamCompression`

**Tips:**
- Use this for focused navigation/render investigations that fit in one scenario.
- Traces are especially useful for layout, scripting, paint, and long-task investigation.
- Keep traces scoped to a short scenario so artifacts stay readable.
- Default output path is `{workspace}/.botcore/traces/{name}-{timestamp}.json`.

## cdp_trace_summary()

```python
async def cdp_trace_summary(
    path: str,
    top_slices_limit: int = 10,
    long_task_threshold_ms: float = 50.0,
) -> CommandResult[dict]
```

Summarizes a captured trace with Perfetto-backed queries and returns a stable structure for automation.

**Parameters:**
| Parameter | Default | Description |
|---|---|---|
| `path` | required | Path to a `.json`, `.pftrace`, or other Perfetto-readable trace |
| `top_slices_limit` | `10` | Number of top slices/categories/threads to keep in the summary |
| `long_task_threshold_ms` | `50.0` | Threshold used for long-task reporting |

**Return data includes:**
- `bounds` — trace start/end/duration
- `actors` — top processes, top threads, detected primary thread
- `categories` — dominant slice categories by total time
- `slices.topByDuration` — top slices overall
- `slices.longTasks` — top slices above the long-task threshold
- `slices.mainThreadTopByDuration` — highest-cost work on the detected primary renderer thread
- `slices.primaryThreadLongTasks` — main-thread long tasks, which are the strongest UI jank signal
- `slices.browserPipelineLongTasks` — compositor / frame pipeline pressure that may not be app-code regressions
- `slices.metricSpans` — metric spans such as `PageLoadMetrics.*`, useful context but not blocking work
- `signals` — quick counts/booleans for main-thread jank vs. browser-pipeline pressure

## cdp_trace_query()

```python
async def cdp_trace_query(
    path: str,
    sql: str,
    limit: int = 100,
) -> CommandResult[dict]
```

Runs a PerfettoSQL query against a saved trace and returns a compact `columns + rows` payload.

**Parameters:**
| Parameter | Default | Description |
|---|---|---|
| `path` | required | Path to a trace file |
| `sql` | required | PerfettoSQL query |
| `limit` | `100` | Maximum rows returned to keep the payload manageable |

**Tips:**
- Prefer `cdp_trace_summary()` for stable automation and dashboards.
- Use `cdp_trace_query()` when you need to drill into a specific thread, slice family, or custom app marker.
- Perfetto timestamps and durations are nanoseconds; divide by `1_000_000` for milliseconds.

## cdp_get_console_message()

```python
async def cdp_get_console_message(index: int) -> CommandResult[dict]
```

Gets a specific console message by index.

**Return data:** `index`, `timestamp`, `level`, `text`, `url`

## cdp_eval()

```python
async def cdp_eval(expression: str) -> CommandResult[dict]
```

Evaluates a JavaScript expression in the current page context.

**Return data:** `expression`, `result` (the JavaScript return value)

**Examples:**
```
cdp_eval("document.title")                        — get page title
cdp_eval("window.location.href")                  — get current URL
cdp_eval("document.querySelectorAll('a').length")  — count links
cdp_eval("localStorage.getItem('token')")          — read storage
cdp_eval("JSON.stringify(performance.timing)")      — performance data
```

**Tips:**
- Return values are serialized to JSON-compatible types
- For complex queries, return a JSON-serializable object
- Use for browser APIs not covered by dedicated CDP commands

## cdp_emulate()

```python
async def cdp_emulate(
    color_scheme: str | None = None,
    viewport: str | None = None,
    user_agent: str | None = None,
    offline: bool = False,
    cpu_throttle: float | None = None,
) -> CommandResult[dict]
```

Emulates device and browser features.

**Parameters:**
| Parameter | Default | Description |
|---|---|---|
| `color_scheme` | None | "light", "dark", or "no-preference" |
| `viewport` | None | "WIDTHxHEIGHT" (e.g., "1920x1080") |
| `user_agent` | None | Custom user agent string |
| `offline` | False | Simulate offline mode |
| `cpu_throttle` | None | CPU throttle factor (e.g., 4.0 = 4x slower) |

**Return data:** `emulated` (list of changes), `count`

**Common viewport presets:**
| Device | Viewport |
|---|---|
| iPhone 14 | "390x844" |
| iPad | "820x1180" |
| Desktop HD | "1920x1080" |
| Desktop 4K | "3840x2160" |

## cdp_list_network() / cdp_get_network()

These are placeholder commands that suggest using `cdp_eval()` with the Performance API:

```
cdp_eval("JSON.stringify(performance.getEntriesByType('resource'))")
```

## Diagnostic Workflow

### Debugging a Page Issue

```
1. cdp_screenshot()                     — visual state
2. cdp_console(level="error")           — JS errors
3. cdp_eval("document.readyState")      — page load state
4. cdp_snapshot()                       — accessibility tree
5. cdp_eval("window.location.href")     — verify URL
```

### Performance Investigation

```
1. cdp_emulate(cpu_throttle=4.0)        — simulate slow CPU
2. cdp_trace_capture(
     url="https://example.test",
     name="slow-path",
     settle_ms=250
   )                                    — capture a real Chrome trace
3. cdp_trace_summary("/path/to/trace.json")
4. cdp_trace_query("/path/to/trace.json", "select name, dur from slice order by dur desc limit 10")
5. cdp_screenshot()                     — visual verification
```
