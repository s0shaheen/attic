## Data Quality Tiers

Items may have different levels of enrichment:

- **Pipeline-classified** (`source: pipeline_tier1`): Has classification labels, entities, summary, and embedding text from upload-time processing. This is the majority of items. Trust these labels for filtering and aggregation.
- **Agent-classified** (`source: agent_chat`): Classified on-demand during a conversation. Same quality as pipeline-classified.
- **Unclassified**: No `cached_classifications`. The pipeline may still be running, or the item predates classification. Use the `classify` tool to classify these on demand.

When reporting classification stats, note coverage (e.g., "Based on 423 of your 500 classified items..."). If coverage is low, mention that the pipeline may still be processing.