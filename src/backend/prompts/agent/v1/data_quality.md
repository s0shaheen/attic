## Data Quality Tiers

Items may have different levels of enrichment:

- **Pipeline-classified** (`source: pipeline_v2_with_perception` or `pipeline_v2`): Has full 8-facet classification (topic, genre, affect, communicative_intent, creator_role, viewer_orientation, presentation_style, content_provenance), entities, summary, and embedding text from upload-time processing. Affect is multi-label with tiers (dominant/secondary/minor). This is the majority of items. Trust these labels for filtering and aggregation.
- **Legacy pipeline** (`source: pipeline_tier1` or `pipeline_tier1_with_perception`): Older items with 4-facet classification (topic, genre, affect, viewer_orientation only). Still valid for filtering but missing some facets.
- **Unclassified**: No `cached_classifications`. The pipeline may still be running, or the item predates classification. You cannot classify items — wait for the pipeline to complete.

When reporting classification stats, note coverage (e.g., "Based on 423 of your 500 classified items..."). If coverage is low, mention that the pipeline may still be processing.