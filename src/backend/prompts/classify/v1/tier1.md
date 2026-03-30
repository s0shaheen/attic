You are processing a saved social media item for a personal media library. Your output powers search, browse filters, and aggregate stats. Users will search for specific items ("that grilled cheese recipe"), browse by category ("show me fitness videos"), and ask questions about their collection ("what topics do I save most?").

{image_instruction}

METADATA:
{context}

Return JSON with this exact structure:

{
  "summary": "2-3 sentences: what is this about? Why save it? Be specific — name people, products, places.",
  "entities": [
    {
      "name": "specific name (e.g., 'Adidas Samba')",
      "type": "person|place|product|brand|song|artist|book|movie_or_show|app_or_tool|restaurant|exercise|recipe|ingredient|clothing|technique|trend_or_meme|cultural_reference|event|podcast|game",
      "relevance": "primary|supporting"
    }
  ],
  "topic": {
    "primary": "label",
    "secondary": "label or null"
  },
  "genre": "label",
  "affect": {
    "dominant": "label",
    "secondary": "label or null"
  },
  "viewer_orientation": "active_learning|passive_consumption|inspiration_saving|shopping_research|social_sharing|emotional_regulation",
  "embedding_text": "A 100-150 word paragraph for semantic search. Describe the video as if helping someone find it later. Include: main subject, key entities by name, what happens, content type. Be specific — 'Adidas Samba sneaker recommendation for European travel' over 'shoe video'."
}

TOPIC LABELS (pick one primary, optional secondary):
food, fashion, beauty, fitness, travel, music, dance, comedy, education, technology, gaming, sports, pets, art, books, movies_tv, news, politics, science, nature, diy, finance, relationships, parenting, health, career, real_estate, automotive, other

Key definitions:
- fitness: Exercise must be VISIBLE or explicitly discussed. NOT content that merely has fitness hashtags.
- comedy: Primary purpose is humor. For funny-but-informative content, use the informative topic and let affect capture humor.
- education: Structured teaching. Career advice = career.
- health: Wellbeing/medical. Distinct from fitness (exercise).

GENRE LABELS:
tutorial, review, vlog, skit, storytime, haul, asmr, challenge, reaction, compilation, before_after, day_in_life, get_ready_with_me, unboxing, recipe, workout, news_commentary, interview, timelapse, meme, duet, room_tour, outfit_showcase, ranking, edit, pov, other

AFFECT LABELS:
funny, wholesome, sad, angry, nostalgic, inspiring, informative, cringe, satisfying, scary, relaxing, shocking, neutral

Key definitions:
- inspiring: Genuine emotional uplift — NOT merely useful/informative content.
- informative: Saved to LEARN or REFERENCE. Tutorials, tips, advice, recommendations.
- neutral: Only when no other label applies.

INSTRUCTIONS:
- Extract up to 5 entities. Focus on what someone would search for.
- Use comments to identify entities, cultural references, and context.
- On-screen text in images is high-value — transcribe names, products, places.
- Be specific in entity names: "Nike Pegasus 39" not "running shoes".
- The embedding_text field is critical — it determines whether users can find this item via search. Write it like a rich description, not a label list.