import { useState } from "react";

import ChatBox from "./components/ChatBox";
import InputBox from "./components/InputBox";
import {
  askQuestion,
  indexRepository,
} from "./services/api";
import type { ChatMessage } from "./types";

function App() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);

  const [repoPath, setRepoPath] = useState("");
  const [indexing, setIndexing] = useState(false);
  const [indexMessage, setIndexMessage] = useState("");
  const [indexError, setIndexError] = useState("");

  const [explanationMode, setExplanationMode] = useState("beginner");

  async function handleIndexRepository() {
    const trimmedPath = repoPath.trim();

    if (!trimmedPath) {
      setIndexError("Please enter a repository path.");
      setIndexMessage("");
      return;
    }

    setIndexing(true);
    setIndexError("");
    setIndexMessage("");

    try {
      const response = await indexRepository(trimmedPath);

      setIndexMessage(
        `Indexed successfully: ${response.chunks_indexed} chunks from ${response.repository}`,
      );
    } catch (error) {
      setIndexError(
        error instanceof Error
          ? error.message
          : "Repository indexing failed.",
      );
    } finally {
      setIndexing(false);
    }
  }

  async function handleSend(question: string) {
    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: question,
    };

    setMessages((currentMessages) => [
      ...currentMessages,
      userMessage,
    ]);

    setLoading(true);

    try {
      const response = await askQuestion(
        question,
        explanationMode,
      );

      const assistantMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: response.answer,
      };

      setMessages((currentMessages) => [
        ...currentMessages,
        assistantMessage,
      ]);
    } catch (error) {
      const errorMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content:
          error instanceof Error
            ? error.message
            : "An unexpected error occurred.",
      };

      setMessages((currentMessages) => [
        ...currentMessages,
        errorMessage,
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="app-shell">
      <header className="app-header">
        <div className="brand-section">
          <h1>AI Code Review Agent</h1>
          <p>
            Index a repository, then search and understand its code.
          </p>
        </div>

        <div className="status-badge">
          <span className="status-dot" />
          RAG system online
        </div>
      </header>

      <section className="repository-panel">
        <div className="repository-panel-header">
          <div>
            <h2>Repository</h2>
            <p>
              Enter the full local path of the project you want to
              analyze.
            </p>
          </div>
        </div>

        <div className="repository-controls">
          <input
            className="repository-input"
            type="text"
            value={repoPath}
            onChange={(event) => {
              setRepoPath(event.target.value);

              if (indexError) {
                setIndexError("");
              }
            }}
            placeholder="/Users/mounika/Documents/my-project"
            disabled={indexing}
          />

          <button
            className="index-button"
            type="button"
            onClick={handleIndexRepository}
            disabled={indexing || !repoPath.trim()}
          >
            {indexing ? "Indexing..." : "Index Repository"}
          </button>
        </div>

        {indexMessage && (
          <div className="index-status index-success">
            <span>✓</span>
            {indexMessage}
          </div>
        )}

        {indexError && (
          <div className="index-status index-error">
            <span>!</span>
            {indexError}
          </div>
        )}

        {indexing && (
          <div className="indexing-note">
            Generating code chunks and embeddings. Large repositories
            can take a few minutes.
          </div>
        )}
      </section>

      <section className="explanation-panel">
        <div>
          <h2>Explanation Level</h2>
          <p>
            Choose how deeply you want the code explained.
          </p>
        </div>

        <div className="explanation-options">
          <button
            type="button"
            className={
              explanationMode === "beginner"
                ? "explanation-button active"
                : "explanation-button"
            }
            onClick={() => setExplanationMode("beginner")}
          >
            Beginner
          </button>

          <button
            type="button"
            className={
              explanationMode === "intermediate"
                ? "explanation-button active"
                : "explanation-button"
            }
            onClick={() => setExplanationMode("intermediate")}
          >
            Intermediate
          </button>

          <button
            type="button"
            className={
              explanationMode === "expert"
                ? "explanation-button active"
                : "explanation-button"
            }
            onClick={() => setExplanationMode("expert")}
          >
            Expert
          </button>
        </div>
      </section>

      <section className="chat-layout">
        <ChatBox
          messages={messages}
          loading={loading}
        />

        <InputBox
          onSend={handleSend}
          loading={loading}
        />
      </section>
    </main>
  );
}

export default App;