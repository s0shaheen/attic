## Recall Check

After any text-based search that looks for entities (books, places, movies, songs, products), review your results for items with short or empty captions. These items may contain the entity visually — a book cover, restaurant sign, or movie poster — but without text mentioning it. Use `analyze_visual` with the matching focus mode (books, scenes, places, text, products) on the top 3-5 such items to catch what text search missed.

Only skip the recall check if:
- The user explicitly asked for text-only results.
- All returned items have substantial caption text (3+ sentences).