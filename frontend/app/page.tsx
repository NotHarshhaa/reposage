"use client";

import { useEffect, useState } from "react";
import { ChatPanel } from "@/components/chat-panel";
import { RepositoryForm } from "@/components/repository-form";
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
    api.listRepositories().then((items) => {
      setRepositories(items);
      const ready = items.find((item) => item.status === "ready");
      if (ready) setActiveRepository(ready);
    }).catch(() => setNotice("Unable to reach the API. Start the FastAPI backend on port 8000."));
  }, []);

  async function indexRepository(url: string) {
    setIsIndexing(true); setNotice(null);
    try {
      const repository = await api.indexRepository(url);
      setRepositories((current) => [repository, ...current.filter((item) => item.id !== repository.id)]);
      if (repository.status === "ready") {
        setActiveRepository(repository); setMessages([]);
        setNotice(`Indexed ${repository.file_count} files into ${repository.chunk_count} searchable chunks.`);
      } else setNotice(`Indexing failed: ${repository.error ?? "Unknown error"}`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Unable to index the repository.");
    } finally { setIsIndexing(false); }
  }

  async function ask(question: string) {
    if (!activeRepository) return;
    setMessages((current) => [...current, { role: "user", content: question }]);
    setIsAsking(true); setNotice(null);
    try {
      const response = await api.chat(activeRepository.id, question);
      setMessages((current) => [...current, { role: "assistant", content: response.answer, sources: response.sources }]);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Unable to answer the question.");
    } finally { setIsAsking(false); }
  }

  function chooseRepository(repository: Repository) {
    setActiveRepository(repository); setMessages([]); setNotice(null);
  }

  return <main>
    <header className="hero"><div className="brand">✦ RepoSage</div><p className="eyebrow">Repository intelligence</p><h1>Understand any public<br /><em>GitHub repository.</em></h1><p className="hero-copy">Clone, index, search, and chat with codebases using retrieval-grounded answers and transparent file references.</p></header>
    <div className="workspace">
      <aside className="sidebar"><RepositoryForm onSubmit={indexRepository} isIndexing={isIndexing} />
        {notice && <p className="notice" role="status">{notice}</p>}
        <section className="repository-list"><div className="section-title"><h2>Indexed repositories</h2><span>{repositories.length}</span></div>
          {!repositories.length ? <p className="hint">No repository has been indexed yet.</p> : repositories.map((repository) => <button className={`repository-item ${activeRepository?.id === repository.id ? "selected" : ""}`} onClick={() => chooseRepository(repository)} key={repository.id} disabled={repository.status !== "ready"}><strong>{repository.owner}/{repository.name}</strong><small>{repository.status === "ready" ? `${repository.file_count} files · ${repository.chunk_count} chunks` : repository.error ?? "Indexing failed"}</small></button>)}
        </section>
        <p className="privacy-note">Local mode keeps cloned source and vector indexes in the backend data directory. A remote LLM is not required.</p>
      </aside>
      <ChatPanel messages={messages} onSend={ask} disabled={!activeRepository} isLoading={isAsking} />
    </div>
  </main>;
}
