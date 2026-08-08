import type { ChatMessage } from "../types";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface MessageProps {
  message: ChatMessage;
}

function Message({ message }: MessageProps) {
  const isUser = message.role === "user";

  return (
    <div className={`message-row ${isUser ? "user-row" : "assistant-row"}`}>
      <div className={`avatar ${isUser ? "user-avatar" : "assistant-avatar"}`}>
        {isUser ? "U" : "AI"}
      </div>

      <div className={`message-bubble ${isUser ? "user-message" : "assistant-message"}`}>
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {message.content}
        </ReactMarkdown>
      </div>
    </div>
  );
}

export default Message;