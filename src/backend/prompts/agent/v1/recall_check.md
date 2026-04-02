## Recall Check

After any text-based search that looks for entities (books, places, movies, songs, products), review your results:

1. Check `cached_classifications.perception` on low-text items — the pipeline's visual perception step already extracted entities, text on screen, and scene descriptions from every item (including full video analysis). Use this data to find entities that caption search missed.
2. Check `cached_classifications.entities` — the classification step extracted searchable entities with types and relevance.
3. If both are empty and the item has short/no caption, try `search_similar` with a more specific query.

The pipeline handles all visual analysis at upload time. You do not need to call any vision tool — the data is already in the item's `cached_classifications`.