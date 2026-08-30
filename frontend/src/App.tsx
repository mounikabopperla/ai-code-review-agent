import { useState } from "react";

import ChatBox from "./components/ChatBox";
import InputBox from "./components/InputBox";

import {
  askQuestion,
  getProjectAnalysisStatus,
  getProjectOverview,
  startProjectAnalysis,
} from "./services/api";

import type { ChatMessage } from "./types";


function App() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);

  const [repoPath, setRepoPath] = useState("");

  const [analyzing, setAnalyzing] = useState(false);
  const [analysisProgress, setAnalysisProgress] = useState(0);
  const [analysisMessage, setAnalysisMessage] = useState("");
  const [analysisError, setAnalysisError] = useState("");

  const [projectReady, setProjectReady] = useState(false);

  const [overviewLoading, setOverviewLoading] =
    useState(false);

  const [explanationMode, setExplanationMode] =
    useState("beginner");


  function wait(milliseconds: number) {
    return new Promise((resolve) => {
      setTimeout(resolve, milliseconds);
    });
  }


  async function pollAnalysisStatus(
    jobId: string,
  ) {
    while (true) {
      const status =
        await getProjectAnalysisStatus(jobId);

      setAnalysisProgress(status.progress);
      setAnalysisMessage(status.message);

      if (status.status === "completed") {
        setProjectReady(true);
        setAnalyzing(false);
        setAnalysisProgress(100);

        setAnalysisMessage(
          status.cached
            ? "Project ready — loaded from cache."
            : "Project ready — analysis complete.",
        );

        return;
      }

      if (status.status === "failed") {
        throw new Error(
          status.error ||
            "We couldn't analyze this project.",
        );
      }

      await wait(3000);
    }
  }


  async function handleAnalyzeProject() {
    const trimmedPath = repoPath.trim();

    if (!trimmedPath) {
      setAnalysisError(
        "Please enter a GitHub repository URL or project path.",
      );
      return;
    }

    setAnalyzing(true);
    setProjectReady(false);
    setOverviewLoading(false);
    setAnalysisError("");
    setAnalysisProgress(0);

    setAnalysisMessage(
      "Starting project analysis...",
    );

    setMessages([]);

    try {
      const response =
        await startProjectAnalysis(
          trimmedPath,
        );

      await pollAnalysisStatus(
        response.job_id,
      );
    } catch (error) {
      setAnalyzing(false);
      setProjectReady(false);

      setAnalysisError(
        error instanceof Error
          ? error.message
          : "We couldn't analyze this project.",
      );
    }
  }


  async function handleGenerateOverview() {
    if (
      !projectReady ||
      overviewLoading
    ) {
      return;
    }

    const trimmedPath =
      repoPath.trim();

    if (!trimmedPath) {
      return;
    }

    setOverviewLoading(true);

    const loadingMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: "assistant",
      content:
        "Generating a project overview. This may take a little longer on the free AI tier...",
    };

    setMessages((currentMessages) => [
      ...currentMessages,
      loadingMessage,
    ]);

    try {
      const response =
        await getProjectOverview(
          explanationMode,
          trimmedPath,
        );

      const overviewMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: response.overview,
      };

      setMessages((currentMessages) => [
        ...currentMessages.filter(
          (message) =>
            message.id !== loadingMessage.id,
        ),
        overviewMessage,
      ]);
    } catch (error) {
      const errorMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content:
          error instanceof Error
            ? `Could not generate the project overview: ${error.message}`
            : "Could not generate the project overview.",
      };

      setMessages((currentMessages) => [
        ...currentMessages.filter(
          (message) =>
            message.id !== loadingMessage.id,
        ),
        errorMessage,
      ]);
    } finally {
      setOverviewLoading(false);
    }
  }


  async function handleSend(
    question: string,
  ) {
    if (!projectReady) {
      return;
    }

    const trimmedPath =
      repoPath.trim();

    if (!trimmedPath) {
      return;
    }

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
      const response =
        await askQuestion(
          question,
          explanationMode,
          trimmedPath,
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
            Understand unfamiliar software projects
            with AI.
          </p>
        </div>

        <div className="status-badge">
          <span className="status-dot" />
          AI system online
        </div>

      </header>


      <section className="repository-panel">

        <div className="repository-panel-header">

          <div>
            <h2>Project</h2>

            <p>
              Paste a GitHub repository URL or enter
              a local project path.
            </p>
          </div>

        </div>


        <div className="repository-controls">

          <input
            className="repository-input"
            type="text"
            value={repoPath}
            onChange={(event) => {
              setRepoPath(
                event.target.value,
              );

              if (analysisError) {
                setAnalysisError("");
              }
            }}
            placeholder="https://github.com/username/project"
            disabled={analyzing}
          />

          <button
            className="index-button"
            type="button"
            onClick={
              handleAnalyzeProject
            }
            disabled={
              analyzing ||
              !repoPath.trim()
            }
          >
            {analyzing
              ? "Analyzing..."
              : "Analyze Project"}
          </button>

        </div>


        {analyzing && (
          <>
            <div className="indexing-note">
              {analysisMessage}
            </div>

            <div
              style={{
                marginTop: "12px",
              }}
            >

              <div
                style={{
                  width: "100%",
                  height: "8px",
                  borderRadius: "999px",
                  background:
                    "rgba(255,255,255,0.08)",
                  overflow: "hidden",
                }}
              >

                <div
                  style={{
                    width: `${analysisProgress}%`,
                    height: "100%",
                    background:
                      "linear-gradient(90deg, #3568ff, #7c3aed)",
                    transition:
                      "width 0.4s ease",
                  }}
                />

              </div>

              <div
                style={{
                  marginTop: "8px",
                  fontSize: "0.9rem",
                  opacity: 0.75,
                }}
              >
                {analysisProgress}%
              </div>

            </div>
          </>
        )}


        {projectReady && (
          <>
            <div className="index-status index-success">
              <span>✓</span>
              {analysisMessage}
            </div>

            <div
              style={{
                marginTop: "14px",
              }}
            >

              <button
                className="index-button"
                type="button"
                onClick={
                  handleGenerateOverview
                }
                disabled={
                  overviewLoading ||
                  loading
                }
              >
                {overviewLoading
                  ? "Generating Overview..."
                  : "Generate Project Overview"}
              </button>

            </div>
          </>
        )}


        {analysisError && (
          <div className="index-status index-error">
            <span>!</span>
            {analysisError}
          </div>
        )}

      </section>


      <section className="explanation-panel">

        <div>
          <h2>Explanation Level</h2>

          <p>
            Choose how deeply you want the project
            explained.
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
            onClick={() =>
              setExplanationMode(
                "beginner",
              )
            }
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
            onClick={() =>
              setExplanationMode(
                "intermediate",
              )
            }
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
            onClick={() =>
              setExplanationMode(
                "expert",
              )
            }
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
          loading={
            loading ||
            overviewLoading ||
            !projectReady
          }
        />

      </section>

    </main>
  );
}


export default App;