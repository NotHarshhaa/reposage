"use client";

import { useEffect, useState } from "react";
import { HugeiconsIcon } from "@hugeicons/react";
import { ChartHistogramIcon } from "@hugeicons/core-free-icons";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api, type Repository, type RepositoryInsights } from "@/lib/api";

type InsightsPanelProps = { repository: Repository | null };

function formatCharacters(total: number): string {
  if (total >= 1_000_000) return `${(total / 1_000_000).toFixed(1)}M chars`;
  if (total >= 1_000) return `${Math.round(total / 1_000)}K chars`;
  return `${total} chars`;
}

export function InsightsPanel({ repository }: InsightsPanelProps) {
  const [insights, setInsights] = useState<RepositoryInsights | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setInsights(null);
    setError(null);
    if (!repository || repository.status !== "ready") return;
    let active = true;
    api
      .insights(repository.id)
      .then((value) => { if (active) setInsights(value); })
      .catch((reason: unknown) => { if (active) setError(reason instanceof Error ? reason.message : "Unable to load insights."); });
    return () => { active = false; };
  }, [repository?.id, repository?.status]);

  return (
    <Card>
      <CardHeader className="border-b border-border">
        <div className="flex items-center gap-2 text-muted-foreground">
          <HugeiconsIcon icon={ChartHistogramIcon} size={17} strokeWidth={1.8} aria-hidden="true" />
          <span className="text-[0.65rem] font-semibold tracking-[0.18em] uppercase">Repository insights</span>
        </div>
        <CardTitle className="mt-2">{insights ? `${insights.owner}/${insights.name}` : "Composition and hotspots"}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        {error && <p className="border-l-2 border-destructive px-3 text-sm text-destructive">{error}</p>}
        {!insights && !error && <p className="text-sm text-muted-foreground">Insights appear once a repository finishes indexing.</p>}
        {insights && (
          <>
            <dl className="grid gap-px overflow-hidden border border-border bg-border sm:grid-cols-4">
              {[
                { label: "Files", value: String(insights.file_count) },
                { label: "Chunks", value: String(insights.chunk_count) },
                { label: "Indexed size", value: formatCharacters(insights.total_characters) },
                { label: "Avg chunk", value: `${insights.average_chunk_characters} chars` },
              ].map((item) => (
                <div className="bg-card px-4 py-3" key={item.label}>
                  <dt className="text-[0.6rem] font-semibold tracking-[0.16em] text-muted-foreground uppercase">{item.label}</dt>
                  <dd className="mt-2 truncate text-sm font-semibold">{item.value}</dd>
                </div>
              ))}
            </dl>

            <section aria-label="Language breakdown" className="space-y-2">
              <h3 className="text-[0.65rem] font-semibold tracking-[0.17em] text-muted-foreground uppercase">Language mix</h3>
              {insights.languages.slice(0, 8).map((language) => (
                <div className="space-y-1" key={language.language}>
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-semibold">{language.language}</span>
                    <span className="text-muted-foreground">{language.file_count} files · {language.share}%</span>
                  </div>
                  <div className="h-1.5 bg-muted">
                    <div className="h-full bg-foreground" style={{ width: `${Math.max(language.share, 1)}%` }} />
                  </div>
                </div>
              ))}
            </section>

            <section aria-label="Largest indexed files" className="space-y-2">
              <h3 className="text-[0.65rem] font-semibold tracking-[0.17em] text-muted-foreground uppercase">Largest indexed files</h3>
              <ul className="space-y-1">
                {insights.largest_files.slice(0, 6).map((file) => (
                  <li className="flex items-center justify-between gap-3 border border-border px-3 py-2 text-xs" key={file.path}>
                    <code className="min-w-0 flex-1 truncate">{file.path}</code>
                    <span className="shrink-0 text-muted-foreground">{file.chunk_count} chunks · {formatCharacters(file.character_count)}</span>
                  </li>
                ))}
              </ul>
            </section>

            {insights.documentation_files.length > 0 && (
              <section aria-label="Documentation files" className="space-y-2">
                <h3 className="text-[0.65rem] font-semibold tracking-[0.17em] text-muted-foreground uppercase">Documentation</h3>
                <div className="flex flex-wrap gap-2">
                  {insights.documentation_files.slice(0, 10).map((path) => <Badge key={path} variant="secondary">{path}</Badge>)}
                </div>
              </section>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
