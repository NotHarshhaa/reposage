"use client";

import { useEffect, useState } from "react";
import { HugeiconsIcon } from "@hugeicons/react";
import {
  AlertCircleIcon,
  CheckmarkCircle02Icon,
  CodeIcon,
  Database01Icon,
  FolderGitIcon,
  Message01Icon,
} from "@hugeicons/core-free-icons";
import { ChatPanel } from "@/components/chat-panel";
import { RepositoryForm } from "@/components/repository-form";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import { api, type Repository, type Source } from "@/lib/api";

type Message = { role: "user" | "assistant"; content: string; sources?: Source[] };

export default function Home() {
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [activeRepository, setActiveRepository] = useState<Repository | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isIndexing, setIsIndexing] = useState(false);
  const [isAsking, setIsAsking] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    api
      .listRepositories()
      .then((items) => {
        setRepositories(items);
        const ready = items.find((item) => item.status === "ready");
        if (ready) setActiveRepository(ready);
      })
      .catch(() => setNotice("Unable to reach the API. Start the FastAPI backend on port 8000."));
  }, []);

  async function indexRepository(url: string) {
    setIsIndexing(true);
    setNotice(null);
    try {
      const repository = await api.indexRepository(url);
      setRepositories((current) => [repository, ...current.filter((item) => item.id !== repository.id)]);
      if (repository.status === "ready") {
        setActiveRepository(repository);
        setMessages([]);
        setNotice(`Indexed ${repository.file_count} files into ${repository.chunk_count} searchable chunks.`);
      } else {
        setNotice(`Indexing failed: ${repository.error ?? "Unknown error"}`);
      }
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Unable to index the repository.");
    } finally {
      setIsIndexing(false);
    }
  }

  async function ask(question: string) {
    if (!activeRepository) return;
    setMessages((current) => [...current, { role: "user", content: question }]);
    setIsAsking(true);
    setNotice(null);
    try {
      const response = await api.chat(activeRepository.id, question);
      setMessages((current) => [
        ...current,
        { role: "assistant", content: response.answer, sources: response.sources },
      ]);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Unable to answer the question.");
    } finally {
      setIsAsking(false);
    }
  }

  function chooseRepository(repository: Repository) {
    setActiveRepository(repository);
    setMessages([]);
    setNotice(null);
  }

  return (
    <main className="min-h-screen bg-background text-foreground">
      <div className="mx-auto max-w-7xl px-5 py-8 sm:px-8 lg:px-12 lg:py-12">
        <header className="mb-10 flex flex-col gap-8 border-b border-border pb-8 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <div className="mb-5 flex items-center gap-3 text-xs font-semibold tracking-[0.2em] text-muted-foreground uppercase">
              <span className="flex size-8 items-center justify-center border border-foreground bg-foreground text-background">
                <HugeiconsIcon icon={CodeIcon} size={17} strokeWidth={1.8} aria-hidden="true" />
              </span>
              RepoSage / Repository Intelligence
            </div>
            <h1 className="font-heading text-4xl leading-[0.96] font-semibold tracking-tight text-balance sm:text-6xl lg:text-7xl">
              Read the codebase<br />
              <span className="text-muted-foreground">before you touch it.</span>
            </h1>
          </div>
          <p className="max-w-sm text-sm leading-6 text-muted-foreground">
            Index a public GitHub repository, then ask focused questions grounded in its source code and documentation.
          </p>
        </header>

        {notice && (
          <Alert variant={notice.startsWith("Indexed") ? "default" : "destructive"} className="mb-6">
            <HugeiconsIcon icon={notice.startsWith("Indexed") ? CheckmarkCircle02Icon : AlertCircleIcon} aria-hidden="true" />
            <AlertTitle>{notice.startsWith("Indexed") ? "Repository ready" : "Connection notice"}</AlertTitle>
            <AlertDescription>{notice}</AlertDescription>
          </Alert>
        )}

        <div className="grid gap-6 lg:grid-cols-[minmax(280px,0.72fr)_minmax(0,1.68fr)]">
          <aside className="space-y-6 lg:sticky lg:top-8 lg:self-start">
            <Card>
              <CardHeader className="border-b border-border">
                <div className="flex items-center gap-2 text-muted-foreground">
                  <HugeiconsIcon icon={FolderGitIcon} size={17} strokeWidth={1.8} aria-hidden="true" />
                  <span className="text-[0.65rem] font-semibold tracking-[0.18em] uppercase">New source</span>
                </div>
                <CardTitle className="mt-2">Index a repository</CardTitle>
              </CardHeader>
              <CardContent>
                <RepositoryForm onSubmit={indexRepository} isIndexing={isIndexing} />
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="border-b border-border">
                <div className="flex items-center justify-between gap-4">
                  <CardTitle>Indexed sources</CardTitle>
                  <Badge variant="secondary">{repositories.length} total</Badge>
                </div>
              </CardHeader>
              <CardContent className="space-y-2">
                {!repositories.length ? (
                  <div className="py-5 text-sm leading-6 text-muted-foreground">
                    Add a public repository to create your first searchable source.
                  </div>
                ) : (
                  repositories.map((repository) => {
                    const selected = activeRepository?.id === repository.id;
                    const ready = repository.status === "ready";
                    return (
                      <button
                        className={cn(
                          "group flex w-full items-start gap-3 border border-transparent p-3 text-left transition-colors",
                          selected ? "border-foreground bg-foreground text-background" : "hover:border-border hover:bg-muted/50",
                          !ready && "cursor-not-allowed opacity-55"
                        )}
                        disabled={!ready}
                        key={repository.id}
                        onClick={() => chooseRepository(repository)}
                        type="button"
                      >
                        <HugeiconsIcon icon={FolderGitIcon} size={18} strokeWidth={1.7} className="mt-0.5 shrink-0" aria-hidden="true" />
                        <span className="min-w-0 flex-1">
                          <strong className="block truncate text-sm font-semibold">{repository.owner}/{repository.name}</strong>
                          <span className={cn("mt-1 block text-xs leading-5", selected ? "text-background/70" : "text-muted-foreground")}>
                            {ready ? `${repository.file_count} files · ${repository.chunk_count} chunks` : repository.error ?? "Indexing failed"}
                          </span>
                        </span>
                        {selected && <HugeiconsIcon icon={CheckmarkCircle02Icon} size={17} strokeWidth={1.8} aria-hidden="true" />}
                      </button>
                    );
                  })
                )}
              </CardContent>
              <div className="px-8 pb-8">
                <Separator className="mb-5" />
                <p className="text-xs leading-5 text-muted-foreground">
                  Cloned source and vector indexes stay in the backend data directory. No remote LLM is required.
                </p>
              </div>
            </Card>
          </aside>

          <section className="space-y-6">
            <div className="grid gap-px overflow-hidden border border-border bg-border sm:grid-cols-3">
              <Stat label="Active source" value={activeRepository ? `${activeRepository.owner}/${activeRepository.name}` : "None selected"} icon={FolderGitIcon} />
              <Stat label="Indexed files" value={activeRepository ? String(activeRepository.file_count) : "—"} icon={Database01Icon} />
              <Stat label="Conversation" value={messages.length ? `${messages.length} messages` : "Ready to begin"} icon={Message01Icon} />
            </div>
            <ChatPanel messages={messages} onSend={ask} disabled={!activeRepository} isLoading={isAsking} />
          </section>
        </div>
      </div>
    </main>
  );
}

function Stat({ icon, label, value }: { icon: typeof FolderGitIcon; label: string; value: string }) {
  return (
    <div className="bg-card px-5 py-4">
      <div className="mb-5 flex items-center gap-2 text-muted-foreground">
        <HugeiconsIcon icon={icon} size={15} strokeWidth={1.7} aria-hidden="true" />
        <span className="text-[0.6rem] font-semibold tracking-[0.16em] uppercase">{label}</span>
      </div>
      <p className="truncate text-sm font-semibold tracking-tight">{value}</p>
    </div>
  );
}
