"use client";

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
    <form action={submit} className="repository-form">
      <label htmlFor="repository-url">Public GitHub repository</label>
      <div className="form-row">
        <input id="repository-url" name="url" type="url" required placeholder="https://github.com/owner/repository" disabled={isIndexing} />
        <button type="submit" disabled={isIndexing}>{isIndexing ? "Indexing…" : "Index repository"}</button>
      </div>
      <p className="hint">Cloning and local vector indexing can take a moment for large repositories.</p>
    </form>
  );
}
