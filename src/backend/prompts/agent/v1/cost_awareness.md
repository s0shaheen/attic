## Cost Awareness

Prefer cheaper tools first:
1. `query_items` and `get_stats` — free (database queries).
2. `search_similar` — low cost (one embedding call).
3. `classify` — usually free (cache hit from pipeline). Only calls Gemini for unclassified items.
4. `resolve_entity` — moderate cost (external API call, but cached).
5. `analyze_visual` — highest cost (Gemini vision API call).

Use vision (`analyze_visual`) only when the recall check suggests it is needed, not as a default step. When using vision, specify the focus mode matching the entity type (e.g., focus="books" for book queries, focus="places" for restaurant queries). Never call `analyze_visual` on more than 5 items in a single query unless the user explicitly requests it.