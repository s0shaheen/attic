You are analyzing a saved social media item's visual content. Your observations will be used by a separate classification system. DESCRIBE what you see — do not classify or judge.

{media_instruction}

METADATA (for context only — focus on what the VISUAL content shows):
{context}

Return JSON:
{
  "visual_description": "3-5 sentences describing what's visible. Be specific about people, settings, objects, actions.",
  "text_on_screen": "Transcribe ALL visible text: overlays, captions, watermarks, signs, labels, titles. Exact wording. null if none.",
  "entities_detected": [
    {
      "name": "specific name (e.g., 'Nike Air Force 1', 'Trader Joe's', 'Taylor Swift')",
      "type": "person|place|product|brand|food|animal|restaurant|book|song|movie_or_show|app|other",
      "how_identified": "visual|text_overlay|logo|context",
      "confidence": "high|medium|low"
    }
  ],
  "people": [
    {
      "description": "appearance, clothing, actions",
      "identified_as": "name if recognizable, null otherwise",
      "is_speaking": false
    }
  ],
  "scene_type": "indoor|outdoor|kitchen|gym|restaurant|store|office|bedroom|street|nature|screen_recording|text_graphic|product_shot|food_close_up|selfie|group_shot|landscape|abstract|other",
  "visual_mood": "one word: cozy, energetic, minimal, chaotic, polished, raw, luxurious, clinical, moody, bright, dark, playful, serious",
  "colors_dominant": ["2-3 dominant colors"],
  "presentation_format": "photo|screenshot|graphic_design|meme|text_post|product_photo|food_photo|selfie|group_photo|landscape|before_after|tutorial_steps|infographic|other"
}

CRITICAL INSTRUCTIONS:
- Be SPECIFIC. Name every identifiable person, place, product, song, brand.
- Transcribe ALL on-screen text — this is often the most valuable signal for classification.
- If you recognize a celebrity, character, TV show, restaurant, or brand — NAME IT.
- Distinguish what you SEE from what you INFER.
- "Starbucks cup with 'Sarah' written on it" not "a coffee cup".
- "Nike Pegasus 39 in coral colorway" not "running shoes".
- For carousels: describe each image, noting what changes between slides.