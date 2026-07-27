"use client";

import { HugeiconsIcon } from "@hugeicons/react";
import { GithubIcon, ArrowUpRight01Icon } from "@hugeicons/core-free-icons";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type RepositoryFormProps = {
  onSubmit: (url: string) => Promise<void>;
  isIndexing: boolean;
};

export function RepositoryForm({ onSubmit, isIndexing }: RepositoryFormProps) {
  async function submit(formData: FormData) {
    const url = String(formData.get("url") ?? "").trim();
    if (url) await onSubmit(url);
  }

  return (
    <form action={submit} className="space-y-5">
      <div className="space-y-2">
        <label className="flex items-center gap-2 text-xs font-semibold tracking-wide" htmlFor="repository-url">
          <HugeiconsIcon icon={GithubIcon} size={16} strokeWidth={1.8} aria-hidden="true" />
          Public GitHub URL
        </label>
        <Input
          disabled={isIndexing}
          id="repository-url"
          name="url"
          placeholder="https://github.com/owner/repository"
          required
          type="url"
        />
      </div>
      <Button className="w-full" disabled={isIndexing} type="submit">
        {isIndexing ? "Indexing source…" : "Index repository"}
        <HugeiconsIcon data-icon="inline-end" icon={ArrowUpRight01Icon} size={16} strokeWidth={1.8} aria-hidden="true" />
      </Button>
      <p className="text-xs leading-5 text-muted-foreground">
        Cloning and local vector indexing can take a moment for large repositories.
      </p>
    </form>
  );
}
