"use client";

import { FormEvent, useState } from "react";
import { SourceList } from "@/components/source-list";
import type { Source } from "@/lib/api";

type Message = { role: "user" | "assistant"; content: string; sources?: Source[] };
type ChatPanelProps = {
  messages: Message[];
  onSend: (question: string) => Promise<void>;
  disabled: boolean;
  isLoading: boolean;
};

export function ChatPanel({ messages, onSend, disabled, isLoading }: ChatPanelProps) {
  const [question, setQuestion] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = question.trim();
    if (!text || disabled || isLoading) return;
    setQuestion("");
    await onSend(text);
  }

  return (
    <section className="chat-panel">
      <div className="chat-header"><div><p className="eyebrow">Retrieval-grounded chat</p><h2>Ask about the codebase</h2></div><span className="status-dot">{disabled ? "Choose a repository" : "Ready"}</span></div>
      <div className="conversation" aria-live="polite">
        {!messages.length && <div className="empty-state"><p>Start with questions like:</p><ul><li>How do I run this project?</li><li>Where is authentication implemented?</li><li>What environment variables are required?</li></ul></div>}
        {messages.map((message, index) => <article className={`message ${message.role}`} key={index}><p className="message-role">{message.role === "user" ? "You" : "RepoSage"}</p><div className="message-content">{message.content}</div>{message.sources && <SourceList sources={message.sources} />}</article>)}
        {isLoading && <article className="message assistant"><p className="message-role">RepoSage</p><div className="message-content loading">Searching indexed repository…</div></article>}
      </div>
      <form className="chat-form" onSubmit={submit}><textarea value={question} onChange={(event) => setQuestion(event.target.value)} placeholder={disabled ? "Index or select a repository first" : "Ask a question about this repository…"} disabled={disabled || isLoading} rows={3} /><button type="submit" disabled={disabled || isLoading || !question.trim()}>Send</button></form>
    </section>
  );
}
