import type { Source } from "@/lib/api";

type SourceListProps = { sources: Source[] };

export function SourceList({ sources }: SourceListProps) {
  if (!sources.length) return null;
  return (
    <section className="sources" aria-label="Source references">
      <h3>Sources</h3>
      <div className="source-grid">
        {sources.map((source, index) => (
          <details className="source-card" key={`${source.path}:${source.start_line}:${index}`}>
            <summary><code>{source.path}</code><span>lines {source.start_line}–{source.end_line} · {Math.round(source.score * 100)}%</span></summary>
            <pre>{source.excerpt}</pre>
          </details>
        ))}
      </div>
    </section>
  );
}
