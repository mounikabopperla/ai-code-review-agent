import time

from google import genai
from google.genai import errors

from backend.config.settings import settings
from backend.llm.formatter import wrap_code_if_needed


client = genai.Client(api_key=settings.google_api_key)


def build_grounded_prompt(
    question: str,
    retrieved_chunks: list[dict],
    explanation_mode: str = "beginner",
) -> str:
    """
    Builds a grounded prompt using the user's question,
    retrieved code chunks, and explanation preference.
    """

    context_parts = []

    for index, chunk in enumerate(retrieved_chunks, start=1):
        context_parts.append(
            f"""
Code Chunk {index}
File: {chunk.get("file_path", "Unknown")}
Name: {chunk.get("name", "Unknown")}
Type: {chunk.get("type", "Unknown")}
Docstring: {chunk.get("docstring", "")}
Start Line: {chunk.get("start_line", "Unknown")}
End Line: {chunk.get("end_line", "Unknown")}

Source Code:
{chunk.get("source_code", "")}
""".strip()
        )

    context = "\n\n---\n\n".join(context_parts)

    if explanation_mode == "expert":
        explanation_instructions = """
Explain at an expert software-engineering level.

Focus on:
- implementation details
- architecture
- internal data flow
- APIs
- classes and functions
- dependencies
- design choices
- relevant trade-offs

Use technical terminology when appropriate.

Assume the user is comfortable reading code and
understanding software architecture.
"""

    elif explanation_mode == "intermediate":
        explanation_instructions = """
Explain at an intermediate level.

Assume the user understands basic programming
but may not know this codebase.

Focus on:
- what the code does
- how the main parts work together
- important functions and classes
- basic architecture
- relevant technical terms

Explain technical terms clearly without going
too deep into implementation details.
"""

    else:
        explanation_instructions = """
Explain in simple, beginner-friendly language.

Assume the user is new to software development.

Focus first on:
- what it does
- why it exists
- how it helps
- how the main pieces work together

Avoid unnecessary technical terminology.

If a technical term is necessary, explain it
immediately in plain English.

Do not overwhelm the user with implementation
details unless the user specifically asks for them.
"""

    return f"""
You are an AI code understanding assistant.

Answer the user's question using only the retrieved code context below.

Your main goal is to help the user UNDERSTAND the codebase.

Explanation Mode:
{explanation_mode}

Explanation Instructions:
{explanation_instructions}

Important Rules:

1. Answer the user's actual question directly.

2. If the user asks a general question such as:
   - What does this project do?
   - What problem does it solve?
   - How does this project help?
   - Explain this project

   give a high-level explanation first.

3. In beginner mode:
   - prefer normal everyday English
   - explain technical terms simply
   - avoid unnecessary implementation details

4. In intermediate mode:
   - explain the important technical pieces
   - mention useful files, functions, and architecture
   - keep the explanation understandable

5. In expert mode:
   - provide deeper implementation details
   - discuss architecture and internal behavior
   - mention relevant design choices and trade-offs

6. Do not dump functions, classes, filenames,
   or architecture unless they help answer the question.

7. If source code is useful, wrap it in fenced
   Markdown code blocks with the correct language.

8. Mention relevant files, functions, classes,
   and line numbers when helpful.

9. Never invent information that is not present
   in the retrieved context.

10. If the retrieved context is insufficient,
    clearly say what cannot be determined.

User Question:
{question}

Retrieved Code Context:
{context}
""".strip()


def ask_gemini(prompt: str) -> str:
    """
    Sends a prompt to Gemini and retries temporary server errors.
    """

    max_attempts = 3

    for attempt in range(1, max_attempts + 1):
        try:
            response = client.models.generate_content(
                model=settings.gemini_model,
                contents=[
                    {
                        "role": "user",
                        "parts": [
                            {
                                "text": (
                                    prompt
                                    + "\n\nIMPORTANT:\n"
                                    + "Every source code example MUST be "
                                    + "enclosed in triple backticks.\n"
                                    + "Example:\n"
                                    + "```python\n"
                                    + "def hello():\n"
                                    + "    print('hello')\n"
                                    + "```\n"
                                )
                            }
                        ],
                    }
                ],
            )

            answer = (
                response.text
                or "Gemini returned an empty response."
            )

            filename = ""

            if "File:" in prompt:
                try:
                    filename = (
                        prompt
                        .split("File:")[1]
                        .split("\n")[0]
                        .strip()
                    )
                except Exception:
                    filename = ""

            return wrap_code_if_needed(
                answer,
                filename,
            )

        except errors.ServerError as error:
            if attempt == max_attempts:
                raise RuntimeError(
                    "Gemini is temporarily unavailable. "
                    "Please try again shortly."
                ) from error

            time.sleep(2 ** attempt)

    raise RuntimeError("Gemini request failed.")