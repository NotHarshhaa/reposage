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
import { RepositoryExplorer } from "@/components/repository-explorer";
import { RepositoryForm } from "@/components/repository-form";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import { api, type ChatTurn, type IndexRepositoryInput, type Repository, type Source } from "@/lib/api";

type Message = { role: "user" | "assistant"; content: string; sources?: Source[] };

export default function Home() {
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [activeRepository, setActiveRepository] = useState<Repository | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isIndexing, setIsIndexing] = useState(false);
  const [isAsking, setIsAsking] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  async function refreshRepositories() {
    const items = await api.listRepositories();
    setRepositories(items);
    setActiveRepository((current) => {
      if (current) return items.find((item) => item.id === current.id) ?? null;
      return items.find((item) => item.status === "ready") ?? items[0] ?? null;
    });
  }

  useEffect(() => {
    void refreshRepositories().catch(() => setNotice("Unable to reach the API. Start the FastAPI backend on port 8000."));
  }, []);

  useEffect(() => {
    if (!repositories.some((item) => item.status === "queued" || item.status === "indexing")) return;
    const timer = window.setInterval(() => { void refreshRepositories().catch(() => undefined); }, 1_500);
    return () => window.clearInterval(timer);
  }, [repositories]);

  async function indexRepository(input: IndexRepositoryInput) {
    setIsIndexing(true);
    setNotice(null);
    try {
      const repository = await api.indexRepository(input);
      setRepositories((current) => [repository, ...current.filter((item) => item.id !== repository.id)]);
      setActiveRepository(repository);
      setMessages([]);
      setNotice(`Indexing ${repository.owner}/${repository.name} in the background. You can continue working while it finishes.`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Unable to queue the repository.");
    } finally {
      setIsIndexing(false);
    }
  }

  async function reindexRepository() {
    if (!activeRepository) return;
    setNotice(null);
    try {
      const repository = await api.reindexRepository(activeRepository.id, { branch: activeRepository.branch ?? undefined });
      setRepositories((current) => [repository, ...current.filter((item) => item.id !== repository.id)]);
      setActiveRepository(repository);
      setMessages([]);
      setNotice(`Re-indexing ${repository.owner}/${repository.name} in the background.`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Unable to re-index the repository.");
    }
  }

  async function deleteRepository() {
    if (!activeRepository || !window.confirm(`Delete the local clone and index for ${activeRepository.owner}/${activeRepository.name}?`)) return;
    try {
      const deletedId = activeRepository.id;
      await api.deleteRepository(deletedId);
      setRepositories((current) => current.filter((item) => item.id !== deletedId));
      setActiveRepository(null);
      setMessages([]);
      setNotice("Repository clone and index deleted.");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Unable to delete the repository.");
    }
  }

  async function ask(question: string) {
    if (!activeRepository || activeRepository.status !== "ready") return;
    const history: ChatTurn[] = messages.slice(-10).map(({ role, content }) => ({ role, content })).filter((message) => message.content.trim());
    const responseIndex = messages.length + 1;
    setMessages((current) => [...current, { role: "user", content: question }, { role: "assistant", content: "" }]);
    setIsAsking(true);
    setNotice(null);
    try {
      await api.streamChat(activeRepository.id, question, history, (event) => {
        if (event.event === "delta") {
          setMessages((current) => current.map((message, index) => index === responseIndex ? { ...message, content: message.content + event.text } : message));
        }
        if (event.event === "sources") {
          setMessages((current) => current.map((message, index) => index === responseIndex ? { ...message, sources: event.sources } : message));
        }
      });
    } catch (error) {
      setMessages((current) => current.map((message, index) => index === responseIndex && !message.content ? { ...message, content: "I couldn't complete that response." } : message));
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

  const activeReady = activeRepository?.status === "ready";
  const processing = activeRepository && activeRepository.status !== "ready" && activeRepository.status !== "failed";

  return (
    <main className="min-h-screen bg-background text-foreground">
      <div className="mx-auto max-w-7xl px-5 py-8 sm:px-8 lg:px-12 lg:py-12">
        <header className="mb-10 flex flex-col gap-8 border-b border-border pb-8 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <div className="mb-5 flex items-center gap-3 text-xs font-semibold tracking-[0.2em] text-muted-foreground uppercase">
              <span className="flex size-8 items-center justify-center border border-foreground bg-foreground text-background"><HugeiconsIcon icon={CodeIcon} size={17} strokeWidth={1.8} aria-hidden="true" /></span>
              RepoSage / Repository Intelligence
            </div>
            <h1 className="font-heading text-4xl leading-[0.96] font-semibold tracking-tight text-balance sm:text-6xl lg:text-7xl">Read the codebase<br /><span className="text-muted-foreground">before you touch it.</span></h1>
          </div>
          <p className="max-w-sm text-sm leading-6 text-muted-foreground">Queue a GitHub repository, watch its indexing progress, then search, browse, and chat with source-grounded context.</p>
        </header>

        {notice && <Alert variant={notice.startsWith("Indexing") || notice.startsWith("Re-indexing") || notice.startsWith("Repository clone") ? "default" : "destructive"} className="mb-6"><HugeiconsIcon icon={notice.startsWith("Indexing") || notice.startsWith("Re-indexing") || notice.startsWith("Repository clone") ? CheckmarkCircle02Icon : AlertCircleIcon} aria-hidden="true" /><AlertTitle>RepoSage</AlertTitle><AlertDescription>{notice}</AlertDescription></Alert>}

        <div className="grid gap-6 lg:grid-cols-[minmax(280px,0.72fr)_minmax(0,1.68fr)]">
          <aside className="space-y-6 lg:sticky lg:top-8 lg:self-start">
            <Card><CardHeader className="border-b border-border"><div className="flex items-center gap-2 text-muted-foreground"><HugeiconsIcon icon={FolderGitIcon} size={17} strokeWidth={1.8} aria-hidden="true" /><span className="text-[0.65rem] font-semibold tracking-[0.18em] uppercase">New source</span></div><CardTitle className="mt-2">Index a repository</CardTitle></CardHeader><CardContent><RepositoryForm onSubmit={indexRepository} isIndexing={isIndexing} /></CardContent></Card>

            <Card>
              <CardHeader className="border-b border-border"><div className="flex items-center justify-between gap-4"><CardTitle>Indexed sources</CardTitle><Badge variant="secondary">{repositories.length} total</Badge></div></CardHeader>
              <CardContent className="space-y-2">
                {!repositories.length ? <div className="py-5 text-sm leading-6 text-muted-foreground">Add a GitHub repository to create your first searchable source.</div> : repositories.map((repository) => {
                  const selected = activeRepository?.id === repository.id;
                  const ready = repository.status === "ready";
                  const running = repository.status === "queued" || repository.status === "indexing";
                  return (
                    <button
                      className={cn("group flex w-full items-start gap-3 border border-transparent p-3 text-left transition-colors", selected ? "border-foreground bg-foreground text-background" : "hover:border-border hover:bg-muted/50")}
                      key={repository.id}
                      onClick={() => chooseRepository(repository)}
                      type="button"
                    >
                      <HugeiconsIcon icon={FolderGitIcon} size={18} strokeWidth={1.7} className="mt-0.5 shrink-0" aria-hidden="true" />
                      <span className="min-w-0 flex-1">
                        <strong className="block truncate text-sm font-semibold">{repository.owner}/{repository.name}</strong>
                        <span className={cn("mt-1 block text-xs leading-5", selected ? "text-background/70" : "text-muted-foreground")}>
                          {ready ? `${repository.file_count} files · ${repository.chunk_count} chunks` : running ? `${repository.stage ?? "Indexing"} · ${repository.progress}%` : repository.error ?? "Indexing failed"}
                        </span>
                        {running && (
                          <span aria-label={`${repository.progress}% indexed`} className="mt-2 block h-1 overflow-hidden bg-current/20">
                            <span className="block h-full bg-current transition-all" style={{ width: `${repository.progress}%` }} />
                          </span>
                        )}
                      </span>
                      {selected && <HugeiconsIcon icon={CheckmarkCircle02Icon} size={17} strokeWidth={1.8} aria-hidden="true" />}
                    </button>
                  );
                })}
              </CardContent>
              {activeRepository && <div className="flex gap-2 px-8 pb-5"><Button disabled={Boolean(processing)} onClick={() => void reindexRepository()} size="sm" variant="outline" type="button">Re-index</Button><Button disabled={Boolean(processing)} onClick={() => void deleteRepository()} size="sm" variant="destructive" type="button">Delete</Button></div>}
              <div className="px-8 pb-8"><Separator className="mb-5" /><p className="text-xs leading-5 text-muted-foreground">Clones and vector indexes stay in the backend data directory. Optional tokens are not persisted.</p></div>
            </Card>
          </aside>

          <section className="space-y-6">
            <div className="grid gap-px overflow-hidden border border-border bg-border sm:grid-cols-3"><Stat label="Active source" value={activeRepository ? `${activeRepository.owner}/${activeRepository.name}` : "None selected"} icon={FolderGitIcon} /><Stat label="Index status" value={activeRepository ? activeRepository.status === "ready" ? `${activeRepository.file_count} files` : `${activeRepository.progress}%` : "—"} icon={Database01Icon} /><Stat label="Conversation" value={messages.length ? `${messages.length} messages` : "Ready to begin"} icon={Message01Icon} /></div>
            {processing && <Alert><HugeiconsIcon icon={Database01Icon} aria-hidden="true" /><AlertTitle>{activeRepository?.stage ?? "Indexing"}</AlertTitle><AlertDescription>{activeRepository?.progress}% complete. Search and chat will unlock when the source is ready.</AlertDescription></Alert>}
            <ChatPanel messages={messages} onSend={ask} disabled={!activeReady} isLoading={isAsking} />
            <RepositoryExplorer repository={activeRepository} />
          </section>
        </div>
      </div>
    </main>
  );
}

function Stat({ icon, label, value }: { icon: typeof FolderGitIcon; label: string; value: string }) {
  return <div className="bg-card px-5 py-4"><div className="mb-5 flex items-center gap-2 text-muted-foreground"><HugeiconsIcon icon={icon} size={15} strokeWidth={1.7} aria-hidden="true" /><span className="text-[0.6rem] font-semibold tracking-[0.16em] uppercase">{label}</span></div><p className="truncate text-sm font-semibold tracking-tight">{value}</p></div>;
}
