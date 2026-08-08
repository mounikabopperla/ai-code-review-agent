import re

LANGUAGE_MAP = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".js": "javascript",
    ".jsx": "jsx",
    ".json": "json",
    ".sql": "sql",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".sh": "bash",
    ".md": "markdown",
}


def language_from_filename(filename: str) -> str:
    for ext, lang in LANGUAGE_MAP.items():
        if filename.endswith(ext):
            return lang
    return "text"


def wrap_code_if_needed(answer: str, filename: str) -> str:
    """
    Wrap code in markdown fences if Gemini forgot.
    """

    if "```" in answer:
        return answer

    lang = language_from_filename(filename)

    if re.search(r"^\s*(def |class |import |from )", answer, re.MULTILINE):
        return f"```{lang}\n{answer}\n```"

    return answer