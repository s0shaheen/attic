/**
 * SSE (Server-Sent Events) parsing utilities.
 *
 * Extracts structured events from raw SSE text streams.
 */

export interface SSEEvent {
  type: string;
  data: Record<string, unknown>;
}

/**
 * Parse a chunk of SSE text into structured events.
 *
 * SSE format:
 *   event: <type>\n
 *   data: <json>\n\n
 *
 * @param text - Raw SSE text (may contain multiple events)
 * @param buffer - Leftover text from a previous chunk
 * @returns Parsed events and any remaining buffer text
 */
export function parseSSEChunk(
  text: string,
  buffer: string = ""
): { events: SSEEvent[]; remaining: string } {
  const combined = buffer + text;
  const parts = combined.split("\n\n");
  const remaining = parts.pop() ?? "";

  const events: SSEEvent[] = [];
  for (const part of parts) {
    if (!part.trim()) continue;

    let eventType = "";
    let eventData = "";
    for (const line of part.split("\n")) {
      if (line.startsWith("event: ")) eventType = line.slice(7).trim();
      else if (line.startsWith("data: ")) eventData = line.slice(6);
    }

    if (eventType && eventData) {
      try {
        events.push({ type: eventType, data: JSON.parse(eventData) });
      } catch {
        // Skip malformed JSON
      }
    }
  }

  return { events, remaining };
}
