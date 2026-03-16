import { describe, expect, it } from "vitest";
import { parseSSEChunk } from "@/lib/sse";

describe("parseSSEChunk", () => {
  it("parses a single complete event", () => {
    const text = 'event: token\ndata: {"text":"hello"}\n\n';
    const { events, remaining } = parseSSEChunk(text);
    expect(events).toHaveLength(1);
    expect(events[0].type).toBe("token");
    expect(events[0].data).toEqual({ text: "hello" });
    expect(remaining).toBe("");
  });

  it("parses multiple events in one chunk", () => {
    const text =
      'event: meta\ndata: {"conversation_id":"abc"}\n\n' +
      'event: token\ndata: {"text":"hi"}\n\n' +
      'event: done\ndata: {"total_tokens":100}\n\n';
    const { events } = parseSSEChunk(text);
    expect(events).toHaveLength(3);
    expect(events[0].type).toBe("meta");
    expect(events[1].type).toBe("token");
    expect(events[2].type).toBe("done");
  });

  it("returns remaining buffer for incomplete events", () => {
    const text = 'event: token\ndata: {"text":"hel';
    const { events, remaining } = parseSSEChunk(text);
    expect(events).toHaveLength(0);
    expect(remaining).toBe(text);
  });

  it("continues parsing from buffer", () => {
    const buffer = 'event: token\ndata: {"text":"hel';
    const newText = 'lo"}\n\n';
    const { events, remaining } = parseSSEChunk(newText, buffer);
    expect(events).toHaveLength(1);
    expect(events[0].data).toEqual({ text: "hello" });
    expect(remaining).toBe("");
  });

  it("skips malformed JSON data", () => {
    const text = "event: token\ndata: {invalid json}\n\n";
    const { events } = parseSSEChunk(text);
    expect(events).toHaveLength(0);
  });

  it("skips events without type or data", () => {
    const text = "data: {}\n\n";
    const { events } = parseSSEChunk(text);
    expect(events).toHaveLength(0);
  });

  it("handles empty input", () => {
    const { events, remaining } = parseSSEChunk("");
    expect(events).toHaveLength(0);
    expect(remaining).toBe("");
  });

  it("handles error events", () => {
    const text = 'event: error\ndata: {"error":"rate limited"}\n\n';
    const { events } = parseSSEChunk(text);
    expect(events).toHaveLength(1);
    expect(events[0].type).toBe("error");
    expect(events[0].data.error).toBe("rate limited");
  });
});
