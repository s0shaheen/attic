/**
 * Shared TypeScript types for Attic frontend.
 */

/**
 * Media type classification for content processing.
 * Matches backend MediaType enum.
 */
export enum MediaType {
  VIDEO = "video",
  IMAGE = "image",
  SLIDESHOW = "slideshow",
}

/**
 * Pipeline run progress tracking.
 * Uses media-agnostic naming to support videos, images, and slideshows.
 */
export interface PipelineProgress {
  id: string;
  upload_id: string;
  user_id: string;
  status: "pending" | "processing" | "complete" | "failed";
  started_at: string | null;
  finished_at: string | null;

  // Progress tracking (media-agnostic)
  total_items: number | null;
  items_enriched: number;
  items_media_downloaded: number;
  items_transcribed: number;
  items_vision_done: number;
  items_embedded: number;
  items_complete: number;
  items_failed: number;

  total_cost_usd: string;
  estimated_completion_at: string | null;
  error_summary: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

/**
 * Media event representing a TikTok interaction.
 * Core entity with enriched metadata and AI analysis.
 */
export interface MediaEvent {
  id: string;
  user_id: string;
  upload_id: string;
  platform: string;
  platform_id: string;
  canonical_url: string | null;
  interaction_type: string | null;
  interaction_at: string | null;
  processing_state: string;
  processing_substate: string | null;

  // Media type classification
  media_type: MediaType;
  image_count: number | null;
  image_urls: string[] | null;
  is_slideshow: boolean | null;

  // Apify enrichment
  caption_text: string | null;
  hashtags: string[] | null;
  mentions: string[] | null;
  creator_username: string | null;
  creator_name: string | null;
  video_duration_seconds: number | null;
  video_created_at: string | null;
  thumbnail_url: string | null;

  // Transcription
  subtitle_text: string | null;
  subtitle_source: string | null;

  // Vision analysis
  visual_tags: string[] | null;
  ocr_text: string | null;

  // Classifications
  mood_primary: string | null;
  content_category_primary: string | null;

  // Timestamps
  created_at: string;
  updated_at: string;
}

/**
 * Helper to check if media has audio content.
 */
export function hasAudioContent(mediaType: MediaType): boolean {
  return mediaType === MediaType.VIDEO;
}

/**
 * Helper to get display label for media type.
 */
export function getMediaTypeLabel(mediaType: MediaType): string {
  switch (mediaType) {
    case MediaType.VIDEO:
      return "Video";
    case MediaType.IMAGE:
      return "Image";
    case MediaType.SLIDESHOW:
      return "Slideshow";
    default:
      return "Media";
  }
}
