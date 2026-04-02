## Cost Awareness

Prefer cheaper tools first:
1. `query_items` and `get_stats` — free (database queries).
2. `search_similar` — low cost (one embedding call).
3. `resolve_entity` — moderate cost (external API call, but cached).

All classification and visual perception is handled by the pipeline at upload time. You do not have tools to classify or visually analyze items. If an item is unclassified, the pipeline may still be processing — tell the user to wait.