"use client";

import { parseSSEChunk } from "@/lib/sse";
import { createClient } from "@/lib/supabase/client";
import { useEffect, useRef, useState } from "react";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function getAccessToken(): Promise<string | null> {
    const supabase = createClient();
    const { data } = await supabase.auth.getSession();
    return data.session?.access_token ?? null;
  }

  async function sendChat(token: string, message: string): Promise<Response> {
    const response = await fetch(`${API_URL}/api/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        message,
        conversation_id: conversationId,
      }),
    });

    // On 401, refresh session and retry once
    if (response.status === 401) {
      const supabase = createClient();
      const { data } = await supabase.auth.getUser();
      if (!data.user) throw new Error("Session expired. Please log in again.");
      const { data: sessionData } = await supabase.auth.getSession();
      const newToken = sessionData.session?.access_token;
      if (!newToken) throw new Error("Session expired. Please log in again.");

      return fetch(`${API_URL}/api/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${newToken}`,
        },
        body: JSON.stringify({
          message,
          conversation_id: conversationId,
        }),
      });
    }

    return response;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || isStreaming) return;

    const token = await getAccessToken();
    if (!token) {
      setError("Not authenticated. Please log in.");
      return;
    }

    // Add user message
    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: trimmed,
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setError(null);
    setIsStreaming(true);

    // Add placeholder for assistant response
    const assistantId = crypto.randomUUID();
    setMessages((prev) => [
      ...prev,
      { id: assistantId, role: "assistant", content: "" },
    ]);

    try {
      const response = await sendChat(token, trimmed);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error("No response body");

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const { events, remaining } = parseSSEChunk(chunk, buffer);
        buffer = remaining;

        for (const event of events) {
          handleSSEEvent(event.type, event.data, assistantId);
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
      // Remove empty assistant message on error
      setMessages((prev) =>
        prev.filter((m) => m.id !== assistantId || m.content !== "")
      );
    } finally {
      setIsStreaming(false);
      inputRef.current?.focus();
    }
  }

  function handleSSEEvent(
    eventType: string,
    data: Record<string, unknown>,
    assistantId: string
  ) {
    switch (eventType) {
      case "meta":
        if (data.conversation_id) {
          setConversationId(data.conversation_id as string);
        }
        break;
      case "token":
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? { ...m, content: m.content + (data.text as string) }
              : m
          )
        );
        break;
      case "error":
        setError(data.error as string);
        break;
      case "done":
        break;
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  }

  return (
    <div className="flex h-screen flex-col bg-neutral-950">
      {/* Header */}
      <header className="flex items-center justify-between border-b border-neutral-800 px-4 py-3">
        <h1 className="text-lg font-semibold text-white">Attic</h1>
        <button
          onClick={() => {
            setMessages([]);
            setConversationId(null);
            setError(null);
          }}
          className="rounded-md px-3 py-1.5 text-sm text-neutral-400 transition-colors hover:bg-neutral-800 hover:text-white"
        >
          New Chat
        </button>
      </header>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        <div className="mx-auto max-w-2xl space-y-6">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center pt-20 text-center">
              <h2 className="text-xl font-medium text-white">
                What would you like to know?
              </h2>
              <p className="mt-2 text-sm text-neutral-400">
                Ask about your TikTok history — search videos, discover
                patterns, explore your data.
              </p>
            </div>
          )}

          {messages.map((message) => (
            <div
              key={message.id}
              className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                  message.role === "user"
                    ? "bg-blue-600 text-white"
                    : "bg-neutral-800 text-neutral-100"
                }`}
              >
                {message.content || (
                  <span className="inline-block h-4 w-4 animate-pulse rounded-full bg-neutral-600" />
                )}
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="border-t border-red-900/50 bg-red-950/30 px-4 py-2">
          <p className="mx-auto max-w-2xl text-sm text-red-400">
            {error}
            {error.toLowerCase().includes("authenticated") && (
              <a
                href="/login"
                className="ml-2 underline hover:text-red-300"
              >
                Go to login
              </a>
            )}
          </p>
        </div>
      )}

      {/* Input */}
      <div className="border-t border-neutral-800 px-4 py-4">
        <form
          onSubmit={handleSubmit}
          className="mx-auto flex max-w-2xl items-end gap-2"
        >
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about your TikTok data..."
            rows={1}
            disabled={isStreaming}
            className="flex-1 resize-none rounded-xl border border-neutral-700 bg-neutral-900 px-4 py-3 text-sm text-white placeholder-neutral-500 focus:border-blue-500 focus:outline-none disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={isStreaming || !input.trim()}
            className="rounded-xl bg-blue-600 px-4 py-3 text-sm font-medium text-white transition-colors hover:bg-blue-500 disabled:opacity-50"
          >
            {isStreaming ? "..." : "Send"}
          </button>
        </form>
      </div>
    </div>
  );
}
