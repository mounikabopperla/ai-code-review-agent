export type MessageRole = "user" | "assistant";

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
}

export interface AskResponse {
  question: string;
  answer: string;
}