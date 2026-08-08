import type { AskResponse } from "../types";

const BASE_URL =
  import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

export async function askQuestion(
  question: string,
  explanationMode: string,
): Promise<AskResponse> {
  const response = await fetch(`${BASE_URL}/ask`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      question,
      explanation_mode: explanationMode,
    }),
  });

  if (!response.ok) {
    throw new Error(await response.text());
  }

  return response.json();
}

export async function indexRepository(
  repoPath: string,
): Promise<{
  status: string;
  source_type?: string;
  repository_name?: string;
  repository: string;
  chunks_indexed: number;
}> {
  const response = await fetch(`${BASE_URL}/index`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      repo_path: repoPath,
    }),
  });

  if (!response.ok) {
    throw new Error(await response.text());
  }

  return response.json();
}