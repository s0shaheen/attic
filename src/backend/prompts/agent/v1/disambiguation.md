## Disambiguation

- If the user's query could match multiple intent types, default to the most specific one. "Show me books" → Entity Retrieval, not Simple Filter.
- If a text search returns zero results, try `search_similar` before telling the user nothing was found.
- When `query_items` returns results with cached classifications, use that data to enrich your response — don't re-classify items that already have labels.
- If an entity type is ambiguous (e.g., "that song" could be music_name or a video about songs), try the entity-specific path first.