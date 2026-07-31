"use client";

import { HugeiconsIcon } from "@hugeicons/react";
import { BookmarkAdd01Icon, Delete02Icon, Download01Icon } from "@hugeicons/core-free-icons";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ConversationSummary } from "@/lib/api";

type SavedConversationsProps = {
  conversations: ConversationSummary[];
  canSave: boolean;
  onSave: () => Promise<void>;
  onLoad: (conversationId: string) => Promise<void>;
  onExport: (conversationId: string) => Promise<void>;
  onDelete: (conversationId: string) => Promise<void>;
};

export function SavedConversations({ conversations, canSave, onSave, onLoad, onExport, onDelete }: SavedConversationsProps) {
  return (
    <Card>
      <CardHeader className="border-b border-border">
        <div className="flex items-center gap-2 text-muted-foreground">
          <HugeiconsIcon icon={BookmarkAdd01Icon} size={17} strokeWidth={1.8} aria-hidden="true" />
          <span className="text-[0.65rem] font-semibold tracking-[0.18em] uppercase">Saved chats</span>
        </div>
        <CardTitle className="mt-2">Conversation history</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <Button className="w-full" disabled={!canSave} onClick={() => void onSave()} size="sm" type="button" variant="outline">
          Save current conversation
        </Button>
        {!conversations.length ? (
          <p className="text-xs leading-5 text-muted-foreground">Saved conversations persist on the backend and can be exported as Markdown.</p>
        ) : (
          <ul className="space-y-2">
            {conversations.map((conversation) => (
              <li className="border border-border p-3" key={conversation.id}>
                <button className="block w-full text-left" onClick={() => void onLoad(conversation.id)} type="button">
                  <strong className="block truncate text-xs font-semibold">{conversation.title}</strong>
                  <span className="mt-1 block text-[0.7rem] text-muted-foreground">
                    {conversation.message_count} messages · {new Date(conversation.updated_at).toLocaleDateString()}
                  </span>
                </button>
                <div className="mt-2 flex gap-2">
                  <Button onClick={() => void onExport(conversation.id)} size="xs" type="button" variant="ghost">
                    <HugeiconsIcon icon={Download01Icon} size={13} strokeWidth={1.8} aria-hidden="true" />
                    Export
                  </Button>
                  <Button onClick={() => void onDelete(conversation.id)} size="xs" type="button" variant="ghost">
                    <HugeiconsIcon icon={Delete02Icon} size={13} strokeWidth={1.8} aria-hidden="true" />
                    Delete
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
