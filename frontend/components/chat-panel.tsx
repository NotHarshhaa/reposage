"use client";

import { FormEvent, useState } from "react";
import { HugeiconsIcon } from "@hugeicons/react";
import {
  AiSearchIcon,
  CheckmarkCircle02Icon,
  MessageQuestionIcon,
  SentIcon,
} from "@hugeicons/core-free-icons";
import { SourceList } from "@/components/source-list";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
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
    <Card className="min-h-[620px]">
      <CardHeader className="border-b border-border sm:flex sm:items-end sm:justify-between">
        <div>
          <div className="mb-3 flex items-center gap-2 text-muted-foreground">
            <HugeiconsIcon icon={MessageQuestionIcon} size={17} strokeWidth={1.8} aria-hidden="true" />
            <span className="text-[0.65rem] font-semibold tracking-[0.18em] uppercase">Retrieval-grounded chat</span>
          </div>
          <CardTitle>Ask the codebase</CardTitle>
        </div>
        <Badge variant={disabled ? "secondary" : "default"} className="mt-4 sm:mt-0">
          <HugeiconsIcon icon={disabled ? MessageQuestionIcon : CheckmarkCircle02Icon} size={13} strokeWidth={1.8} aria-hidden="true" />
          {disabled ? "Choose a source" : "Ready"}
        </Badge>
      </CardHeader>

      <CardContent className="flex min-h-[430px] flex-1 flex-col py-0">
        <div className="flex flex-1 flex-col gap-5 py-8" aria-live="polite">
          {!messages.length && (
            <div className="m-auto max-w-md border-l-2 border-foreground py-1 pl-5">
              <p className="mb-4 text-sm leading-6 text-muted-foreground">
                {disabled
                  ? "Select an indexed repository to start a source-grounded conversation."
                  : "Start with a question that helps you navigate the architecture, behavior, or setup."}
              </p>
              <ul className="space-y-2 text-sm leading-6">
                <li className="flex gap-3"><span className="text-muted-foreground">01</span> How do I run this project?</li>
                <li className="flex gap-3"><span className="text-muted-foreground">02</span> Where is authentication implemented?</li>
                <li className="flex gap-3"><span className="text-muted-foreground">03</span> What environment variables are required?</li>
              </ul>
            </div>
          )}

          {messages.map((message, index) => (
            <article
              className={cn(
                "max-w-[92%] border p-5 sm:max-w-[86%]",
                message.role === "user" ? "ml-auto border-foreground bg-foreground text-background" : "border-border bg-muted/45"
              )}
              key={index}
            >
              <div className={cn("mb-3 flex items-center gap-2 text-[0.65rem] font-semibold tracking-[0.17em] uppercase", message.role === "user" ? "text-background/65" : "text-muted-foreground")}>
                <HugeiconsIcon icon={message.role === "user" ? SentIcon : AiSearchIcon} size={14} strokeWidth={1.8} aria-hidden="true" />
                {message.role === "user" ? "You" : "RepoSage"}
              </div>
              <div className="text-sm leading-6 whitespace-pre-wrap">{message.content}</div>
              {message.sources && <SourceList sources={message.sources} />}
            </article>
          ))}

          {isLoading && (
            <article className="flex max-w-[86%] items-center gap-3 border border-border bg-muted/45 p-5 text-sm text-muted-foreground">
              <HugeiconsIcon icon={AiSearchIcon} size={17} strokeWidth={1.8} className="animate-pulse" aria-hidden="true" />
              Searching indexed repository…
            </article>
          )}
        </div>
      </CardContent>

      <form className="border-t border-border px-8 py-6" onSubmit={submit}>
        <label className="mb-3 block text-[0.65rem] font-semibold tracking-[0.18em] text-muted-foreground uppercase" htmlFor="question">
          Your question
        </label>
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end">
          <Textarea
            disabled={disabled || isLoading}
            id="question"
            onChange={(event) => setQuestion(event.target.value)}
            placeholder={disabled ? "Index or select a repository first" : "Ask a question about this repository…"}
            rows={2}
            value={question}
          />
          <Button className="shrink-0" disabled={disabled || isLoading || !question.trim()} type="submit">
            Send
            <HugeiconsIcon data-icon="inline-end" icon={SentIcon} size={16} strokeWidth={1.8} aria-hidden="true" />
          </Button>
        </div>
      </form>
    </Card>
  );
}
