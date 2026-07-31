"use client";

import { FormEvent, useEffect, useState } from "react";
import { HugeiconsIcon } from "@hugeicons/react";
import { AiSearchIcon, CodeCircleIcon, FileCodeIcon } from "@hugeicons/core-free-icons";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { api, type FileOutline, type Repository, type RepositoryFile, type RepositoryMatches, type Source } from "@/lib/api";

type RepositoryExplorerProps = { repository: Repository | null };

export function RepositoryExplorer({ repository }: RepositoryExplorerProps) {
  const [query, setQuery] = useState("");
  const [language, setLanguage] = useState("");
  const [pathPrefix, setPathPrefix] = useState("");
  const [allRepositories, setAllRepositories] = useState(false);
  const [files, setFiles] = useState<RepositoryFile[]>([]);
  const [results, setResults] = useState<Source[]>([]);
  const [groups, setGroups] = useState<RepositoryMatches[]>([]);
  const [selected, setSelected] = useState<RepositoryFile | null>(null);
  const [outline, setOutline] = useState<FileOutline | null>(null);
  const [highlightLine, setHighlightLine] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const ready = repository?.status === "ready";
  const languages = Array.from(new Set(files.map((file) => file.language))).sort();
  const previewLines = selected?.content ? selected.content.split("\n") : [];

  useEffect(() => {
    setFiles([]);
    setResults([]);
    setGroups([]);
    setSelected(null);
    setOutline(null);
    setHighlightLine(null);
    setError(null);
    if (!repository || repository.status !== "ready") return;
    let active = true;
    api.listFiles(repository.id).then((items) => { if (active) setFiles(items); }).catch((reason: unknown) => {
      if (active) setError(reason instanceof Error ? reason.message : "Unable to load repository files.");
    });
    return () => { active = false; };
  }, [repository?.id, repository?.status]);

  async function openFile(path: string, line?: number) {
    if (!repository) return;
    setIsLoading(true);
    setError(null);
    setHighlightLine(line ?? null);
    try {
      const [file, fileOutline] = await Promise.all([
        api.getFile(repository.id, path),
        api.outline(repository.id, path).catch(() => null),
      ]);
      setSelected(file);
      setOutline(fileOutline);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load the file.");
    } finally {
      setIsLoading(false);
    }
  }

  async function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!query.trim() || (!allRepositories && !repository)) return;
    setIsLoading(true);
    setError(null);
    try {
      if (allRepositories) {
        const response = await api.searchAll({
          query: query.trim(), languages: language ? [language] : [], limit_per_repository: 3,
        });
        setGroups(response.repositories);
        setResults([]);
      } else if (repository) {
        const response = await api.search(repository.id, {
          query: query.trim(), languages: language ? [language] : [], path_prefix: pathPrefix.trim() || undefined,
        });
        setResults(response.sources);
        setGroups([]);
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to run that search.");
    } finally {
      setIsLoading(false);
    }
  }

  async function findSimilar() {
    if (!repository || !selected) return;
    setIsLoading(true);
    setError(null);
    try {
      const response = await api.similar(repository.id, selected.path, highlightLine ?? 1);
      setResults(response.sources);
      setGroups([]);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to find similar code.");
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
        <CardTitle className="mt-2">Search, outline, and inspect files</CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        <form className="space-y-3" onSubmit={search}>
          <div className="grid gap-3 md:grid-cols-[1fr_150px_180px_auto]">
            <Input disabled={isLoading} onChange={(event) => setQuery(event.target.value)} placeholder={allRepositories ? "Search every ready repository…" : ready ? "Search code, docs, or symbols…" : "Choose a ready repository"} value={query} />
            <select aria-label="Language filter" className="h-10 border border-input bg-background px-3 text-sm" disabled={isLoading} onChange={(event) => setLanguage(event.target.value)} value={language}>
              <option value="">All languages</option>
              {languages.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
            <Input disabled={isLoading || allRepositories} onChange={(event) => setPathPrefix(event.target.value)} placeholder="Path prefix (src/)" value={pathPrefix} />
            <Button disabled={isLoading || !query.trim() || (!allRepositories && !ready)} type="submit">
              Search
              <HugeiconsIcon data-icon="inline-end" icon={AiSearchIcon} size={15} strokeWidth={1.8} aria-hidden="true" />
            </Button>
          </div>
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            <input checked={allRepositories} className="size-3.5 accent-current" onChange={(event) => setAllRepositories(event.target.checked)} type="checkbox" />
            Search across all indexed repositories
          </label>
        </form>

        {error && <p className="border-l-2 border-destructive px-3 text-sm text-destructive">{error}</p>}

        {groups.length > 0 && (
          <section aria-label="Cross-repository results" className="space-y-2">
            <h3 className="text-[0.65rem] font-semibold tracking-[0.17em] text-muted-foreground uppercase">Matches across repositories</h3>
            {groups.map((group) => (
              <article className="border border-border" key={group.repository_id}>
                <p className="border-b border-border px-3 py-2 text-xs font-semibold">{group.owner}/{group.name}</p>
                {group.sources.map((source) => (
                  <div className="border-b border-border px-3 py-2 last:border-b-0" key={`${group.repository_id}:${source.path}:${source.start_line}`}>
                    <code className="block truncate text-xs">{source.path}:{source.start_line}</code>
                    <span className="block truncate text-xs text-muted-foreground">{source.excerpt}</span>
                  </div>
                ))}
              </article>
            ))}
          </section>
        )}

        <div className="grid gap-5 lg:grid-cols-[minmax(170px,.5fr)_minmax(190px,.6fr)_minmax(0,1.7fr)]">
          <section className="max-h-72 overflow-auto border border-border" aria-label="Repository files">
            <p className="border-b border-border px-3 py-2 text-[0.65rem] font-semibold tracking-[0.15em] text-muted-foreground uppercase">Files ({files.length})</p>
            {files.map((file) => (
              <button className={cn("block w-full border-b border-border px-3 py-2 text-left text-xs hover:bg-muted", selected?.path === file.path && "bg-muted font-semibold")} key={file.path} onClick={() => void openFile(file.path)} type="button">
                <code className="block truncate">{file.path}</code>
                <span className="text-muted-foreground">{file.language}</span>
              </button>
            ))}
            {!files.length && <p className="p-3 text-xs text-muted-foreground">{ready ? "Loading files…" : "Files appear after indexing."}</p>}
          </section>

          <section className="max-h-72 overflow-auto border border-border" aria-label="Outline and results">
            <p className="border-b border-border px-3 py-2 text-[0.65rem] font-semibold tracking-[0.15em] text-muted-foreground uppercase">
              {outline?.symbols.length ? `Outline (${outline.symbols.length})` : "Results"}
            </p>
            {outline?.symbols.length
              ? outline.symbols.map((symbol) => (
                  <button className="block w-full border-b border-border px-3 py-2 text-left hover:bg-muted" key={`${symbol.kind}:${symbol.name}:${symbol.line}`} onClick={() => setHighlightLine(symbol.line)} type="button">
                    <code className="block truncate text-xs">{symbol.name}</code>
                    <span className="text-[0.7rem] text-muted-foreground">{symbol.kind} · line {symbol.line}</span>
                  </button>
                ))
              : results.map((source) => (
                  <button className="block w-full border-b border-border px-3 py-2 text-left hover:bg-muted" key={`${source.path}:${source.start_line}`} onClick={() => void openFile(source.path, source.start_line)} type="button">
                    <code className="block truncate text-xs">{source.path}:{source.start_line}</code>
                    <span className="block truncate text-xs text-muted-foreground">{source.excerpt}</span>
                  </button>
                ))}
            {!outline?.symbols.length && !results.length && <p className="p-3 text-xs text-muted-foreground">Search or open a file to see ranked sources and its symbol outline.</p>}
          </section>

          <section className="min-h-72 overflow-hidden border border-border" aria-label="Selected file">
            <div className="flex items-center justify-between gap-3 border-b border-border px-3 py-2">
              <p className="min-w-0 truncate text-[0.65rem] font-semibold tracking-[0.15em] text-muted-foreground uppercase">{selected?.path ?? "File preview"}</p>
              {selected && (
                <Button disabled={isLoading} onClick={() => void findSimilar()} size="xs" type="button" variant="ghost">
                  <HugeiconsIcon icon={CodeCircleIcon} size={13} strokeWidth={1.8} aria-hidden="true" />
                  Similar code
                </Button>
              )}
            </div>
            {previewLines.length ? (
              <div className="max-h-72 overflow-auto bg-muted/30 font-mono text-xs leading-5">
                {previewLines.map((line, index) => (
                  <div className={cn("flex gap-3 px-3", highlightLine === index + 1 && "bg-foreground/10")} key={index}>
                    <span className="w-10 shrink-0 select-none text-right text-muted-foreground">{index + 1}</span>
                    <span className="whitespace-pre">{line || " "}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="p-4 text-sm text-muted-foreground">Select a file or search result to view its indexed source with line numbers.</p>
            )}
          </section>
        </div>
      </CardContent>
    </Card>
  );
}
