---
type: added
---

**research** -- `research_stream` streams a research answer as afd stream chunks (progress, text data chunks, then a complete or error chunk); `research_query` collects it into the same result as before and no longer blocks the event loop. The MCP `{name}-research` tool forwards the stream as MCP progress notifications and now returns the result's JSON fields instead of its string form
