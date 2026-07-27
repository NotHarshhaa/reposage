import { HugeiconsIcon } from "@hugeicons/react";
import { FileCodeIcon, ViewIcon } from "@hugeicons/core-free-icons";
import type { Source } from "@/lib/api";

type SourceListProps = { sources: Source[] };

export function SourceList({ sources }: SourceListProps) {
  if (!sources.length) return null;

  return (
    <section className="mt-5 border-t border-current/15 pt-4" aria-label="Source references">
      <h3 className="mb-3 text-[0.65rem] font-semibold tracking-[0.17em] text-muted-foreground uppercase">Source references</h3>
      <div className="space-y-2">
        {sources.map((source, index) => (
          <details className="group border border-current/15 bg-background/35" key={`${source.path}:${source.start_line}:${index}`}>
            <summary className="flex cursor-pointer list-none items-center gap-3 p-3 marker:content-none">
              <HugeiconsIcon icon={FileCodeIcon} size={15} strokeWidth={1.8} className="shrink-0" aria-hidden="true" />
              <code className="min-w-0 flex-1 truncate text-xs">{source.path}</code>
              <span className="hidden text-[0.65rem] text-muted-foreground sm:inline">{source.start_line}–{source.end_line} · {Math.round(source.score * 100)}%</span>
              <HugeiconsIcon icon={ViewIcon} size={15} strokeWidth={1.8} className="shrink-0 transition-transform group-open:rotate-180" aria-hidden="true" />
            </summary>
            <pre className="max-h-48 overflow-auto border-t border-current/15 bg-background/55 p-3 font-mono text-[0.7rem] leading-5 whitespace-pre-wrap">{source.excerpt}</pre>
          </details>
        ))}
      </div>
    </section>
  );
}
