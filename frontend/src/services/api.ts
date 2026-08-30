import type { AskResponse } from "../types";

const BASE_URL =
  import.meta.env.VITE_API_URL ||
  "http://127.0.0.1:8000";


export async function askQuestion(
  question: string,
  explanationMode: string,
  repoPath: string,
): Promise<AskResponse> {
  const response = await fetch(
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

  if (!response.ok) {
    throw new Error(
      await response.text(),
    );
  }

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
  const response = await fetch(
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

  if (!response.ok) {
    throw new Error(
      await response.text(),
    );
  }

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
  const response = await fetch(
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

  if (!response.ok) {
    throw new Error(
      await response.text(),
    );
  }

  return response.json();
}


export async function getProjectAnalysisStatus(
  jobId: string,
): Promise<AnalysisStatusResponse> {
  const response = await fetch(
    `${BASE_URL}/index/status/${jobId}`,
  );

  if (!response.ok) {
    throw new Error(
      await response.text(),
    );
  }

  return response.json();
}