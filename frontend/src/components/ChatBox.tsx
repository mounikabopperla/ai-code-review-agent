import { useEffect, useRef } from "react";

import type { ChatMessage } from "../types";
import Message from "./Message";

interface ChatBoxProps {
  messages: ChatMessage[];
  loading: boolean;
}

function ChatBox({ messages, loading }: ChatBoxProps) {
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({
      behavior: "smooth",
    });
  }, [messages, loading]);

  return (
    <section className="chat-box">
      {messages.length === 0 && !loading ? (
        <div className="empty-state">
          <div className="empty-icon">{"</>"}</div>

          <h2>Ask about your codebase</h2>

          <p>
            Search functions, classes, files, tests, and implementation details
            from the indexed repository.
          </p>

          <div className="example-questions">
            <span>Where is argument parsing implemented?</span>
            <span>Show me the test_split_arg_string function.</span>
            <span>Which file contains OptionParser?</span>
          </div>
        </div>
      ) : (
        <>
          {messages.map((message) => (
            <Message key={message.id} message={message} />
          ))}

          {loading && (
            <div className="message-row assistant-row">
              <div className="avatar assistant-avatar">AI</div>

              <div className="message-bubble assistant-message loading-message">
                <span className="typing-dot" />
                <span className="typing-dot" />
                <span className="typing-dot" />
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </>
      )}
    </section>
  );
}

export default ChatBox;