"""Provider-agnostic LLM layer. Swapping providers touches only this file."""

from dataclasses import dataclass, field

import json

import anthropic
import openai
from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_random_exponential

from app.config import settings

ANTHROPIC_MODEL = "claude-haiku-4-5"
GEMINI_MODEL = "gemini-2.5-flash"
GITHUB_MODEL = "openai/gpt-4.1"
GITHUB_MODELS_BASE_URL = "https://models.github.ai/inference"
TOGETHER_MODEL = "meta-llama/Llama-3.3-70B-Instruct-Turbo"
TOGETHER_BASE_URL = "https://api.together.ai/v1"
OPENROUTER_MODEL = "anthropic/claude-haiku-4.5"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


@dataclass
class LLMResponse:
    content: str | None
    tool_calls: list[dict] = field(default_factory=list)


def _to_anthropic_messages(messages: list[dict]) -> tuple[str, list[dict]]:
    """Convert our provider-agnostic message list into an Anthropic
    (system, messages) pair. `system` messages are pulled out of the list;
    `tool` results become `tool_result` blocks on a synthetic user turn."""
    system = ""
    anthropic_messages: list[dict] = []

    for message in messages:
        role = message["role"]
        if role == "system":
            system = message["content"]
        elif role == "user":
            anthropic_messages.append({"role": "user", "content": message["content"]})
        elif role == "assistant":
            content = []
            if message.get("content"):
                content.append({"type": "text", "text": message["content"]})
            for call in message.get("tool_calls", []):
                content.append(
                    {"type": "tool_use", "id": call["id"], "name": call["name"], "input": call["arguments"]}
                )
            anthropic_messages.append({"role": "assistant", "content": content})
        elif role == "tool":
            anthropic_messages.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": message["tool_call_id"],
                            "content": message["content"],
                        }
                    ],
                }
            )
        else:
            raise ValueError(f"unknown message role: {role}")

    return system, anthropic_messages


def _to_gemini_contents(messages: list[dict]) -> tuple[str, list[dict]]:
    """Convert our provider-agnostic message list into Gemini's
    (system_instruction, contents) shape. Gemini's function_response part needs the
    called function's *name*, which our `tool` messages don't carry (only
    `tool_call_id`) — recovered here from the preceding assistant tool_call."""
    system = ""
    contents: list[dict] = []
    call_id_to_name: dict[str, str] = {}

    for message in messages:
        role = message["role"]
        if role == "system":
            system = message["content"]
        elif role == "user":
            contents.append({"role": "user", "parts": [{"text": message["content"]}]})
        elif role == "assistant":
            parts = []
            if message.get("content"):
                parts.append({"text": message["content"]})
            for call in message.get("tool_calls", []):
                call_id_to_name[call["id"]] = call["name"]
                parts.append(
                    {"function_call": {"id": call["id"], "name": call["name"], "args": call["arguments"]}}
                )
            contents.append({"role": "model", "parts": parts})
        elif role == "tool":
            call_id = message["tool_call_id"]
            contents.append(
                {
                    "role": "user",
                    "parts": [
                        {
                            "function_response": {
                                "id": call_id,
                                "name": call_id_to_name.get(call_id, call_id),
                                "response": {"content": message["content"]},
                            }
                        }
                    ],
                }
            )
        else:
            raise ValueError(f"unknown message role: {role}")

    return system, contents


def _gemini_tool_declarations(tools: list[dict]) -> list[genai_types.Tool]:
    return [
        genai_types.Tool(
            function_declarations=[
                genai_types.FunctionDeclaration(
                    name=tool["name"],
                    description=tool["description"],
                    parameters=tool["input_schema"],
                )
                for tool in tools
            ]
        )
    ]


def _is_rate_limited(exc: BaseException) -> bool:
    return isinstance(exc, genai_errors.APIError) and exc.code == 429


@retry(
    retry=retry_if_exception(_is_rate_limited),
    wait=wait_random_exponential(multiplier=1, max=20),
    stop=stop_after_attempt(3),
    reraise=True,
)
def _generate_gemini_content(client: genai.Client, **kwargs):
    return client.models.generate_content(**kwargs)


def _complete_anthropic(messages: list[dict], tools: list[dict] | None) -> LLMResponse:
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    system, anthropic_messages = _to_anthropic_messages(messages)

    response = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=1024,
        system=system,
        messages=anthropic_messages,
        tools=tools or [],
    )

    text = None
    tool_calls = []
    for block in response.content:
        if block.type == "text":
            text = (text or "") + block.text
        elif block.type == "tool_use":
            tool_calls.append({"id": block.id, "name": block.name, "arguments": block.input})

    return LLMResponse(content=text, tool_calls=tool_calls)


def _complete_gemini(messages: list[dict], tools: list[dict] | None) -> LLMResponse:
    client = genai.Client(api_key=settings.gemini_api_key)
    system, contents = _to_gemini_contents(messages)

    config = genai_types.GenerateContentConfig(
        system_instruction=system or None,
        tools=_gemini_tool_declarations(tools) if tools else None,
    )

    response = _generate_gemini_content(client, model=GEMINI_MODEL, contents=contents, config=config)

    text = None
    tool_calls = []
    for part in response.candidates[0].content.parts:
        if getattr(part, "text", None):
            text = (text or "") + part.text
        elif getattr(part, "function_call", None):
            call = part.function_call
            call_id = call.id or call.name
            tool_calls.append({"id": call_id, "name": call.name, "arguments": dict(call.args or {})})

    return LLMResponse(content=text, tool_calls=tool_calls)


def _to_openai_messages(messages: list[dict]) -> list[dict]:
    """Convert our provider-agnostic message list into OpenAI's chat.completions
    message shape (used for Cerebras, which is OpenAI-compatible)."""
    openai_messages: list[dict] = []

    for message in messages:
        role = message["role"]
        if role == "system":
            openai_messages.append({"role": "system", "content": message["content"]})
        elif role == "user":
            openai_messages.append({"role": "user", "content": message["content"]})
        elif role == "assistant":
            entry: dict = {"role": "assistant", "content": message.get("content")}
            if message.get("tool_calls"):
                entry["tool_calls"] = [
                    {
                        "id": call["id"],
                        "type": "function",
                        "function": {"name": call["name"], "arguments": json.dumps(call["arguments"])},
                    }
                    for call in message["tool_calls"]
                ]
            openai_messages.append(entry)
        elif role == "tool":
            openai_messages.append(
                {"role": "tool", "tool_call_id": message["tool_call_id"], "content": message["content"]}
            )
        else:
            raise ValueError(f"unknown message role: {role}")

    return openai_messages


def _openai_tool_declarations(tools: list[dict]) -> list[dict]:
    """OpenAI-compatible tool declarations with `strict: true` so enum constraints
    (e.g. escalate_to_human's reason codes) are structurally enforced via constrained
    decoding rather than merely requested in the description."""
    declarations = []
    for tool in tools:
        parameters = {**tool["input_schema"], "additionalProperties": False}
        declarations.append(
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": parameters,
                    "strict": True,
                },
            }
        )
    return declarations


def _is_openai_rate_limited(exc: BaseException) -> bool:
    return isinstance(exc, openai.RateLimitError)


@retry(
    retry=retry_if_exception(_is_openai_rate_limited),
    wait=wait_random_exponential(multiplier=1, max=20),
    stop=stop_after_attempt(3),
    reraise=True,
)
def _create_github_models_completion(client: openai.OpenAI, **kwargs):
    return client.chat.completions.create(**kwargs)


def _complete_github(messages: list[dict], tools: list[dict] | None) -> LLMResponse:
    client = openai.OpenAI(api_key=settings.github_models_token, base_url=GITHUB_MODELS_BASE_URL)
    openai_messages = _to_openai_messages(messages)

    response = _create_github_models_completion(
        client,
        model=GITHUB_MODEL,
        messages=openai_messages,
        tools=_openai_tool_declarations(tools) if tools else None,
    )

    choice = response.choices[0].message
    text = choice.content or None
    tool_calls = [
        {"id": call.id, "name": call.function.name, "arguments": json.loads(call.function.arguments)}
        for call in (choice.tool_calls or [])
    ]

    return LLMResponse(content=text, tool_calls=tool_calls)


def _plain_openai_tool_declarations(tools: list[dict]) -> list[dict]:
    """Together and OpenRouter's OpenAI-compatible endpoints don't document support
    for OpenAI's `strict` constrained-decoding mode, so tool schemas are passed
    through as-is rather than reusing `_openai_tool_declarations`."""
    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["input_schema"],
            },
        }
        for tool in tools
    ]


@retry(
    retry=retry_if_exception(_is_openai_rate_limited),
    wait=wait_random_exponential(multiplier=1, max=20),
    stop=stop_after_attempt(3),
    reraise=True,
)
def _create_together_completion(client: openai.OpenAI, **kwargs):
    return client.chat.completions.create(**kwargs)


def _complete_together(messages: list[dict], tools: list[dict] | None) -> LLMResponse:
    client = openai.OpenAI(api_key=settings.together_api_key, base_url=TOGETHER_BASE_URL)
    openai_messages = _to_openai_messages(messages)

    response = _create_together_completion(
        client,
        model=TOGETHER_MODEL,
        messages=openai_messages,
        tools=_plain_openai_tool_declarations(tools) if tools else None,
    )

    choice = response.choices[0].message
    text = choice.content or None
    tool_calls = [
        {"id": call.id, "name": call.function.name, "arguments": json.loads(call.function.arguments)}
        for call in (choice.tool_calls or [])
    ]

    return LLMResponse(content=text, tool_calls=tool_calls)


@retry(
    retry=retry_if_exception(_is_openai_rate_limited),
    wait=wait_random_exponential(multiplier=1, max=20),
    stop=stop_after_attempt(3),
    reraise=True,
)
def _create_openrouter_completion(client: openai.OpenAI, **kwargs):
    return client.chat.completions.create(**kwargs)


def _complete_openrouter(messages: list[dict], tools: list[dict] | None) -> LLMResponse:
    client = openai.OpenAI(api_key=settings.openrouter_api_key, base_url=OPENROUTER_BASE_URL)
    openai_messages = _to_openai_messages(messages)

    response = _create_openrouter_completion(
        client,
        model=OPENROUTER_MODEL,
        messages=openai_messages,
        tools=_plain_openai_tool_declarations(tools) if tools else None,
    )

    choice = response.choices[0].message
    text = choice.content or None
    tool_calls = [
        {"id": call.id, "name": call.function.name, "arguments": json.loads(call.function.arguments)}
        for call in (choice.tool_calls or [])
    ]

    return LLMResponse(content=text, tool_calls=tool_calls)


def complete(messages: list[dict], tools: list[dict] | None = None) -> LLMResponse:
    if settings.llm_provider == "anthropic":
        return _complete_anthropic(messages, tools)
    if settings.llm_provider == "gemini":
        return _complete_gemini(messages, tools)
    if settings.llm_provider == "github":
        return _complete_github(messages, tools)
    if settings.llm_provider == "together":
        return _complete_together(messages, tools)
    if settings.llm_provider == "openrouter":
        return _complete_openrouter(messages, tools)
    raise ValueError(f"unknown llm_provider: {settings.llm_provider}")
