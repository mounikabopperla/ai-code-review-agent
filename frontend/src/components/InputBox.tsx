import { useState } from "react";

interface InputBoxProps {
  onSend: (question: string) => void;
  loading: boolean;
}

function InputBox({ onSend, loading }: InputBoxProps) {
  const [question, setQuestion] = useState("");

  function sendQuestion() {
    const trimmedQuestion = question.trim();

    if (!trimmedQuestion || loading) {
      return;
    }

    onSend(trimmedQuestion);
    setQuestion("");
  }

  function handleKeyDown(
    event: React.KeyboardEvent<HTMLTextAreaElement>,
  ) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendQuestion();
    }
  }

  return (
    <section className="input-section">
      <div className="input-container">
        <textarea
          className="question-input"
          value={question}
          rows={1}
          placeholder="Ask anything about the indexed codebase..."
          disabled={loading}
          onChange={(event) => setQuestion(event.target.value)}
          onKeyDown={handleKeyDown}
        />

        <button
          className="send-button"
          type="button"
          disabled={loading || !question.trim()}
          onClick={sendQuestion}
          aria-label="Send question"
        >
          {loading ? "..." : "↑"}
        </button>
      </div>

      <p className="input-hint">
        Press Enter to send · Shift + Enter for a new line
      </p>
    </section>
  );
}

export default InputBox;