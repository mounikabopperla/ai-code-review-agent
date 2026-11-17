export async function consumeAnswerStream(response: Response, onText: (text: string) => void): Promise<string> {
  if (!response.body) throw new Error("Streaming is unavailable. Please retry.");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let answer = "";
  let completed = false;
  const consume = () => {
    let boundary: number;
    while ((boundary = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      for (const line of frame.split("\n")) {
        if (!line.startsWith("data: ")) continue;
        const event = JSON.parse(line.slice(6));
        if (event.type === "error") throw new Error(event.message);
        if (event.type === "done") completed = true;
        if (event.type === "delta") {
          answer += event.text;
          onText(answer);
        }
      }
    }
  };
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      consume();
    }
    buffer += decoder.decode();
    consume();
    if (!completed) throw new Error("The connection ended before the answer finished. Please retry.");
    return answer;
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}
