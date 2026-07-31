"use client";

import { FormEvent, useEffect, useState } from "react";
import { HugeiconsIcon } from "@hugeicons/react";
import { AiSearchIcon, FileCodeIcon } from "@hugeicons/core-free-icons";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { api, type Repository, type RepositoryFile, type Source } from "@/lib/api";

type RepositoryExplorerProps = { repository: Repository | null };

export function RepositoryExplorer({ repository }: RepositoryExplorerProps) {
  const [query, setQuery] = useState("");
  const [language, setLanguage] = useState("");
  const [pathPrefix, setPathPrefix] = useState("");
  const [files, setFiles] = useState<RepositoryFile[]>([]);
  const [results, setResults] = useState<Source[]>([]);
  const [selected, setSelected] = useState<RepositoryFile | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const ready = repository?.status === "ready";
  const languages = Array.from(new Set(files.map((file) => file.language))).sort();

  useEffect(() => {
    setFiles([]);
    setResults([]);
    setSelected(null);
    setError(null);
    if (!repository || repository.status !== "ready") return;
    let active = true;
    api.listFiles(repository.id).then((items) => { if (active) setFiles(items); }).catch((reason: unknown) => {
      if (active) setError(reason instanceof Error ? reason.message : "Unable to load repository files.");
    });
    return () => { active = false; };
  }, [repository?.id, repository?.status]);

  async function openFile(path: string) {
    if (!repository) return;
    setIsLoading(true);
    setError(null);
    try {
      setSelected(await api.getFile(repository.id, path));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load the file.");
    } finally {
      setIsLoading(false);
    }
  }

  async function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!repository || !query.trim()) return;
    setIsLoading(true);
    setError(null);
    try {
      const response = await api.search(repository.id, {
        query: query.trim(), languages: language ? [language] : [], path_prefix: pathPrefix.trim() || undefined,
      });
      setResults(response.sources);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to search this repository.");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <Card>
      <CardHeader className="border-b border-border">
        <div className="flex items-center gap-2 text-muted-foreground">
          <HugeiconsIcon icon={FileCodeIcon} size={17} strokeWidth={1.8} aria-hidden="true" />
          <span className="text-[0.65rem] font-semibold tracking-[0.18em] uppercase">Source explorer</span>
        </div>
        <CardTitle className="mt-2">Search and inspect files</CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        <form className="grid gap-3 md:grid-cols-[1fr_150px_180px_auto]" onSubmit={search}>
          <Input disabled={!ready || isLoading} onChange={(event) => setQuery(event.target.value)} placeholder={ready ? "Search code, docs, or symbols…" : "Choose a ready repository"} value={query} />
          <select aria-label="Language filter" className="h-10 border border-input bg-background px-3 text-sm" disabled={!ready || isLoading} onChange={(event) => setLanguage(event.target.value)} value={language}>
            <option value="">All languages</option>
            {languages.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
          <Input disabled={!ready || isLoading} onChange={(event) => setPathPrefix(event.target.value)} placeholder="Path prefix (src/)" value={pathPrefix} />
          <Button disabled={!ready || isLoading || !query.trim()} type="submit">Search <HugeiconsIcon data-icon="inline-end" icon={AiSearchIcon} size={15} strokeWidth={1.8} aria-hidden="true" /></Button>
        </form>
        {error && <p className="border-l-2 border-destructive px-3 text-sm text-destructive">{error}</p>}
        <div className="grid gap-5 lg:grid-cols-[minmax(180px,.55fr)_minmax(220px,.8fr)_minmax(0,1.65fr)]">
          <section className="max-h-72 overflow-auto border border-border" aria-label="Repository files">
            <p className="border-b border-border px-3 py-2 text-[0.65rem] font-semibold tracking-[0.15em] text-muted-foreground uppercase">Files ({files.length})</p>
            {files.map((file) => <button className={cn("block w-full border-b border-border px-3 py-2 text-left text-xs hover:bg-muted", selected?.path === file.path && "bg-muted font-semibold")} key={file.path} onClick={() => void openFile(file.path)} type="button"><code className="block truncate">{file.path}</code><span className="text-muted-foreground">{file.language}</span></button>)}
            {!files.length && <p className="p-3 text-xs text-muted-foreground">{ready ? "Loading files…" : "Files appear after indexing."}</p>}
          </section>
          <section className="max-h-72 overflow-auto border border-border" aria-label="Search results">
            <p className="border-b border-border px-3 py-2 text-[0.65rem] font-semibold tracking-[0.15em] text-muted-foreground uppercase">Results</p>
            {results.map((source) => <button className="block w-full border-b border-border px-3 py-2 text-left hover:bg-muted" key={`${source.path}:${source.start_line}`} onClick={() => void openFile(source.path)} type="button"><code className="block truncate text-xs">{source.path}:{source.start_line}</code><span className="block truncate text-xs text-muted-foreground">{source.excerpt}</span></button>)}
            {!results.length && <p className="p-3 text-xs text-muted-foreground">Run a filtered search to see ranked sources.</p>}
          </section>
          <section className="min-h-72 overflow-hidden border border-border" aria-label="Selected file">
            <p className="border-b border-border px-3 py-2 text-[0.65rem] font-semibold tracking-[0.15em] text-muted-foreground uppercase">{selected?.path ?? "File preview"}</p>
            {selected?.content ? <pre className="max-h-72 overflow-auto bg-muted/30 p-4 font-mono text-xs leading-5 whitespace-pre">{selected.content}</pre> : <p className="p-4 text-sm text-muted-foreground">Select a file or search result to view its indexed source.</p>}
          </section>
        </div>
      </CardContent>
    </Card>
  );
}
