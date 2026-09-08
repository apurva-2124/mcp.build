"""
Run Python agent — Hal9-style stdin/stdout agent.

Reads a natural language prompt via input(), uses Groq tool calling to
install PyPI packages and execute Python, then prints the result.
"""

import json
import os
import re
import subprocess
import sys
import tempfile

from groq import Groq

MODEL = os.environ.get("GROQ_MODEL", "qwen/qwen3.6-27b")
PYTHON_TIMEOUT = int(os.environ.get("PYTHON_TIMEOUT", "60"))
PIP_TIMEOUT = int(os.environ.get("PIP_TIMEOUT", "180"))
MAX_ROUNDS = int(os.environ.get("MAX_ROUNDS", "8"))
MAX_OUTPUT = 50_000
MAX_PACKAGES = 20
MAX_CODE_CHARS = 100_000

PACKAGES_DIR = os.environ.get(
    "PACKAGES_DIR",
    os.path.join(tempfile.gettempdir(), "mcp-build-run-python-packages"),
)

# PyPI name, optional extras, optional version pin. No URLs, paths, or flags.
_PKG_RE = re.compile(
    r"^([A-Za-z0-9]|[A-Za-z0-9][A-Za-z0-9._-]*[A-Za-z0-9])"
    r"(?:\[([A-Za-z0-9]|[A-Za-z0-9][A-Za-z0-9,._-]*[A-Za-z0-9])\])?"
    r"(?:(?:===|==|!=|<=|>=|~=|<|>)[A-Za-z0-9._*+-]+)?$"
)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "install_packages",
            "description": (
                "Install one or more packages from PyPI into the sandbox. "
                "Call this before run_python when the code needs third-party libraries."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "packages": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "PyPI names, optionally with extras or version pins "
                            "(e.g. skyfield, numpy==2.1.0, astropy[all])."
                        ),
                    },
                },
                "required": ["packages"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_python",
            "description": (
                "Execute Python code in a sandbox and return stdout/stderr. "
                "Print the answer — values that are only computed are not visible."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Python source to execute. Use print() for results.",
                    },
                },
                "required": ["code"],
            },
        },
    },
]

SYSTEM_PROMPT = (
    "You are a Python execution assistant. You have two tools: "
    "install_packages (PyPI) and run_python (execute code, return stdout/stderr).\n"
    "For any numeric or scientific question you MUST run code — do not guess from memory.\n"
    "If a library is needed, install it first, then run. You may call both tools in "
    "one turn; put install_packages before run_python.\n"
    "Always print() the final answer with units and dates. Prefer the standard library "
    "when it is enough. For orbital mechanics prefer skyfield, astropy, or poliastro.\n"
    "If a run fails, read the error, install missing packages or fix the code, and retry.\n"
    "When you have a successful result, reply with a short answer (key numbers, units, "
    "dates) and the packages used. Do not dump full source unless asked.\n"
    "Do not read environment variables, files outside the working directory, or the "
    "network unless the user explicitly asks."
)


def _clip(text: str, limit: int = MAX_OUTPUT) -> str:
    text = text or ""
    if len(text) <= limit:
        return text
    omitted = len(text) - limit
    return text[:limit] + f"\n...[truncated {omitted} characters]"


def _base_env() -> dict:
    """Minimal env so executed code cannot see API keys or deploy tokens."""
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", tempfile.gettempdir()),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "LC_ALL": os.environ.get("LC_ALL", "C.UTF-8"),
        "PYTHONUNBUFFERED": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
        "PIP_DISABLE_PIP_VERSION_CHECK": "1",
    }
    for key in (
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
        "REQUESTS_CA_BUNDLE",
        "CURL_CA_BUNDLE",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "NO_PROXY",
        "http_proxy",
        "https_proxy",
        "no_proxy",
    ):
        if key in os.environ:
            env[key] = os.environ[key]
    return env


def _normalize_packages(packages) -> list:
    if packages is None:
        return []
    if isinstance(packages, str):
        return [p.strip() for p in re.split(r"[,\s]+", packages) if p.strip()]
    return [str(p).strip() for p in packages if str(p).strip()]


def _validate_packages(packages: list) -> str:
    if not packages:
        return "Error: no packages given."
    if len(packages) > MAX_PACKAGES:
        return f"Error: at most {MAX_PACKAGES} packages per install."
    bad = [p for p in packages if not _PKG_RE.match(p)]
    if bad:
        return (
            "Error: invalid package spec(s): "
            + ", ".join(bad)
            + ". Use PyPI names with optional extras and version pins, "
            "e.g. skyfield or numpy==2.1.0."
        )
    return ""


def install_packages(packages=None, package=None, **_kwargs) -> str:
    """Install PyPI packages into PACKAGES_DIR and return a status message."""
    pkgs = _normalize_packages(packages if packages is not None else package)
    err = _validate_packages(pkgs)
    if err:
        return err

    os.makedirs(PACKAGES_DIR, exist_ok=True)
    cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--target",
        PACKAGES_DIR,
        "--upgrade",
        "--no-input",
        "--no-warn-script-location",
        *pkgs,
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=PIP_TIMEOUT,
            env=_base_env(),
        )
    except subprocess.TimeoutExpired:
        return f"Error: pip install timed out after {PIP_TIMEOUT}s."
    except Exception as e:
        return f"Error: pip install failed to start: {e}"

    out = _clip(((result.stdout or "") + "\n" + (result.stderr or "")).strip())
    if result.returncode != 0:
        return f"pip install failed (exit {result.returncode}):\n{out}"
    return f"Installed: {', '.join(pkgs)}\n{out}"


def run_python(code: str = "", **_kwargs) -> str:
    """Execute Python in a temp directory with PACKAGES_DIR on PYTHONPATH."""
    if not code or not str(code).strip():
        return "Error: no Python code given."
    code = str(code)
    if len(code) > MAX_CODE_CHARS:
        return f"Error: code exceeds {MAX_CODE_CHARS} characters."

    os.makedirs(PACKAGES_DIR, exist_ok=True)
    env = _base_env()
    env["PYTHONPATH"] = PACKAGES_DIR + os.pathsep + env.get("PYTHONPATH", "")

    try:
        with tempfile.TemporaryDirectory(prefix="mcp-build-run-python-") as tmp:
            script = os.path.join(tmp, "script.py")
            with open(script, "w", encoding="utf-8") as handle:
                handle.write(code)
            env["HOME"] = tmp
            env["TMPDIR"] = tmp
            result = subprocess.run(
                [sys.executable, script],
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=PYTHON_TIMEOUT,
                cwd=tmp,
                env=env,
            )
    except subprocess.TimeoutExpired:
        return f"Error: Python timed out after {PYTHON_TIMEOUT}s."
    except Exception as e:
        return f"Error: failed to run Python: {e}"

    parts = []
    if result.stdout:
        parts.append(result.stdout.rstrip())
    if result.stderr:
        parts.append("stderr:\n" + result.stderr.rstrip())
    if result.returncode != 0:
        parts.append(f"exit code: {result.returncode}")
    if not parts:
        return "(no output)"
    return _clip("\n".join(parts))


def _assistant_message(message) -> dict:
    payload = {"role": "assistant", "content": message.content}
    if message.tool_calls:
        payload["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments or "{}",
                },
            }
            for tc in message.tool_calls
        ]
        if not payload["content"]:
            payload["content"] = None
    return payload


def run(prompt: str) -> str:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return "Error: GROQ_API_KEY environment variable is not set."

    client = Groq(api_key=api_key)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    available = {
        "install_packages": install_packages,
        "run_python": run_python,
    }
    last_outputs = []

    for _ in range(MAX_ROUNDS):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                temperature=0.2,
            )
        except Exception as e:
            return f"Error calling the model: {e}"

        message = response.choices[0].message
        messages.append(_assistant_message(message))

        if not message.tool_calls:
            if message.content:
                return message.content
            if last_outputs:
                return "\n".join(last_outputs)
            return "I could not determine what Python to run. Please try again."

        for tool_call in message.tool_calls:
            name = tool_call.function.name
            raw_args = tool_call.function.arguments or "{}"
            try:
                args = raw_args if isinstance(raw_args, dict) else json.loads(raw_args)
            except json.JSONDecodeError as e:
                result = f"Error: invalid tool arguments: {e}"
            else:
                fn = available.get(name)
                if not fn:
                    result = f"Unknown tool: {name}"
                else:
                    result = fn(**args) if isinstance(args, dict) else fn()
            last_outputs.append(result)
            messages.append(
                {
                    "role": "tool",
                    "name": name,
                    "tool_call_id": tool_call.id,
                    "content": result,
                }
            )

    if last_outputs:
        return (
            "Reached the maximum number of steps. Last output:\n"
            + last_outputs[-1]
        )
    return "Reached the maximum number of steps without a result."


if __name__ == "__main__":
    prompt = input()
    print(run(prompt))
