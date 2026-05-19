## ADDED Requirements

### Requirement: OpenAI-compatible LLM call layer
The system SHALL expose a single `llm.py` module that makes chat-format LLM calls via the `openai` Python SDK. All LLM calls in the codebase MUST go through this module. No other provider SDK SHALL be imported in any other module.

#### Scenario: LLM call succeeds
- **WHEN** any feature code calls `llm.chat(messages=[...])` with a system and user message
- **THEN** `llm.py` constructs the request using the configured base URL, API key, and model, and returns the response content as a string

#### Scenario: Provider-specific SDK imported outside llm.py
- **WHEN** a code review finds `import anthropic` or `import openai` outside of `llm.py`
- **THEN** this MUST be treated as a bug and refactored to route through `llm.py`

### Requirement: Environment variable configuration
The system SHALL read LLM provider settings exclusively from environment variables: `LLM_API_KEY` (required), `LLM_BASE_URL` (required), `LLM_MODEL` (required). The system SHALL load a `.env` file via `python-dotenv` if present.

#### Scenario: Environment variables set
- **WHEN** `.env` contains `LLM_API_KEY=sk-...`, `LLM_BASE_URL=https://api.anthropic.com/v1`, `LLM_MODEL=claude-sonnet-4-6`
- **THEN** all LLM calls use those values without any code changes

#### Scenario: Missing required env var
- **WHEN** `LLM_API_KEY` is not set and no `.env` file is present
- **THEN** `llm.py` raises a clear `EnvironmentError` naming the missing variable before making any API call

### Requirement: Plain chat-format prompts only
All prompts constructed by feature code (tagger.py, skills) SHALL use only system + user message pairs. No provider-specific parameters (tool use schemas, vision payloads, extended thinking flags) SHALL be included unless the calling code provides an explicit fallback path for providers that do not support them.

#### Scenario: Prompt uses only standard chat format
- **WHEN** tagger.py constructs a tagging prompt
- **THEN** it passes only `[{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]` to `llm.chat()`, with no extra parameters

### Requirement: LLM error handling
The system SHALL catch API errors (rate limit, auth failure, timeout) in `llm.py` and raise a typed `LLMError` with the original message, so callers can handle or surface it without coupling to the provider SDK's exception types.

#### Scenario: API rate limit hit
- **WHEN** the LLM API returns a 429 rate limit response
- **THEN** `llm.py` raises `LLMError("Rate limit exceeded: ...")` which the caller can catch and display to the user
