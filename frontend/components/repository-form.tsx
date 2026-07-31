"use client";

import { HugeiconsIcon } from "@hugeicons/react";
import { GithubIcon, ArrowUpRight01Icon } from "@hugeicons/core-free-icons";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { IndexRepositoryInput } from "@/lib/api";

type RepositoryFormProps = {
  onSubmit: (input: IndexRepositoryInput) => Promise<void>;
  isIndexing: boolean;
};

export function RepositoryForm({ onSubmit, isIndexing }: RepositoryFormProps) {
  async function submit(formData: FormData) {
    const url = String(formData.get("url") ?? "").trim();
    const branch = String(formData.get("branch") ?? "").trim();
    const accessToken = String(formData.get("access_token") ?? "").trim();
    if (url) await onSubmit({ url, ...(branch && { branch }), ...(accessToken && { access_token: accessToken }) });
  }

  return (
    <form action={submit} className="space-y-4">
      <div className="space-y-2">
        <label className="flex items-center gap-2 text-xs font-semibold tracking-wide" htmlFor="repository-url">
          <HugeiconsIcon icon={GithubIcon} size={16} strokeWidth={1.8} aria-hidden="true" />
          GitHub repository URL
        </label>
        <Input disabled={isIndexing} id="repository-url" name="url" placeholder="https://github.com/owner/repository" required type="url" />
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-2">
          <label className="text-xs font-semibold tracking-wide" htmlFor="branch">Branch <span className="font-normal text-muted-foreground">optional</span></label>
          <Input disabled={isIndexing} id="branch" name="branch" placeholder="main" />
        </div>
        <div className="space-y-2">
          <label className="text-xs font-semibold tracking-wide" htmlFor="access-token">Access token <span className="font-normal text-muted-foreground">optional</span></label>
          <Input autoComplete="off" disabled={isIndexing} id="access-token" name="access_token" placeholder="Private repos" type="password" />
        </div>
      </div>
      <Button className="w-full" disabled={isIndexing} type="submit">
        {isIndexing ? "Queueing source…" : "Index repository"}
        <HugeiconsIcon data-icon="inline-end" icon={ArrowUpRight01Icon} size={16} strokeWidth={1.8} aria-hidden="true" />
      </Button>
      <p className="text-xs leading-5 text-muted-foreground">Indexing runs in the background. Tokens are used only for the clone and are never saved.</p>
    </form>
  );
}
