import { consumeAnswerStream } from "./stream";
import type { AskResponse } from "../types";

const BASE_URL = (
  import.meta.env.VITE_API_URL?.trim() ||
  (import.meta.env.DEV ? "http://127.0.0.1:8000" : "https://ai-code-review-agent-i5jf.onrender.com")
).replace(/\/+$/, "");

async function apiFetch(url: string, options: RequestInit = {}): Promise<Response> {
  let response: Response;
  try {
    response = await fetch(url, {
      ...options,
      signal: AbortSignal.timeout(120_000),
    });
  } catch {
    throw new Error(`Cannot reach the backend at ${BASE_URL}. It may be starting or unavailable. Please retry shortly. If this continues, contact the site owner with this backend address.`);
  }
  if (!response.ok) {
    const body = await response.text();
    let detail = body;
    try { detail = JSON.parse(body).detail || body; } catch { /* Plain-text server error. */ }
    throw new Error(`Request failed (${response.status}): ${detail}`);
  }
  return response;
}

export async function checkBackendHealth(): Promise<void> {
  const response = await apiFetch(`${BASE_URL}/health`);
  const body = await response.json();
  if (body.status !== "ok") throw new Error("Backend is not ready");
}


export async function askQuestion(
  question: string,
  explanationMode: string,
  repoPath: string,
): Promise<AskResponse> {
  const response = await apiFetch(
    `${BASE_URL}/ask`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        question,
        explanation_mode: explanationMode,
        repo_path: repoPath,
      }),
    },
  );

  return response.json();
}


export type ProjectOverviewResponse = {
  explanation_mode: string;
  overview: string;
};


export async function getProjectOverview(
  explanationMode: string,
  repoPath: string,
): Promise<ProjectOverviewResponse> {
  const response = await apiFetch(
    `${BASE_URL}/project/overview`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        explanation_mode: explanationMode,
        repo_path: repoPath,
      }),
    },
  );

  return response.json();
}


export type AnalysisStartResponse = {
  job_id: string;
  status: string;
  message: string;
};


export type AnalysisStatusResponse = {
  job_id: string;
  status:
    | "queued"
    | "running"
    | "completed"
    | "failed";
  progress: number;
  message: string;
  repository_name?: string;
  repository_input?: string;
  chunks_found?: number;
  chunks_indexed?: number;
  source_type?: string;
  cached?: boolean;
  error?: string;
};


export async function startProjectAnalysis(
  repoPath: string,
): Promise<AnalysisStartResponse> {
  const response = await apiFetch(
    `${BASE_URL}/index`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        repo_path: repoPath,
      }),
    },
  );

  return response.json();
}


export async function getProjectAnalysisStatus(
  jobId: string,
): Promise<AnalysisStatusResponse> {
  const response = await apiFetch(
    `${BASE_URL}/index/status/${jobId}`,
  );

  return response.json();
}

async function readAnswerStream(
  path: string, body: object, onText: (text: string) => void,
): Promise<string> {
  const response = await apiFetch(`${BASE_URL}${path}`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return consumeAnswerStream(response, onText);
}


export function streamQuestion(question: string, explanationMode: string, repoPath: string, onText: (text: string) => void) {
  return readAnswerStream("/ask/stream", { question, explanation_mode: explanationMode, repo_path: repoPath }, onText);
}

export function streamOverview(explanationMode: string, repoPath: string, onText: (text: string) => void) {
  return readAnswerStream("/project/overview/stream", { explanation_mode: explanationMode, repo_path: repoPath }, onText);
}
