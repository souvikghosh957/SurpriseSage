"""SurpriseSage — Multi-provider LLM abstraction.

Supports: Ollama (local), Grok, Claude, ChatGPT, Gemini, and any
OpenAI-compatible endpoint. Provider is configured via the "llm"
section in user_profile.json. API keys can live in the profile,
in environment variables, or in a .env file.

Quick-start examples for user_profile.json:

  Local (default — no API key needed):
    "llm": {"provider": "ollama", "model": "surprisesage:latest"}

  Grok:
    "llm": {"provider": "grok", "model": "grok-3-mini"}

  Claude:
    "llm": {"provider": "claude", "model": "claude-sonnet-4-6"}

  ChatGPT:
    "llm": {"provider": "chatgpt", "model": "gpt-4o"}

  Gemini:
    "llm": {"provider": "gemini", "model": "gemini-2.5-flash"}

  Any OpenAI-compatible endpoint:
    "llm": {"provider": "openai_compatible", "model": "my-model",
            "base_url": "http://localhost:8080/v1"}
"""

import logging
import os
import time

logger = logging.getLogger("surprisesage.llm")

_CLOUD_MAX_RETRIES = 2
_CLOUD_BASE_DELAY = 1.0  # seconds

# ── Provider → litellm model prefix mapping ─────────────────────────────
_PROVIDER_PREFIX = {
    "grok": "xai/",
    "claude": "anthropic/",
    "chatgpt": "openai/",
    "openai": "openai/",
    "gemini": "gemini/",
}

# ── Provider → environment variable for the API key ─────────────────────
_PROVIDER_ENV_KEY = {
    "grok": "XAI_API_KEY",
    "claude": "ANTHROPIC_API_KEY",
    "chatgpt": "OPENAI_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "openai_compatible": "OPENAI_API_KEY",
}

# ── Default models per provider ─────────────────────────────────────────
_DEFAULT_MODELS = {
    "ollama": "surprisesage:latest",
    "grok": "grok-3-mini",
    "claude": "claude-sonnet-4-6",
    "chatgpt": "gpt-4o",
    "openai": "gpt-4o",
    "gemini": "gemini-2.5-flash",
}

# ── Defaults ────────────────────────────────────────────────────────────
DEFAULT_LLM_CONFIG = {
    "provider": "ollama",
    "model": "surprisesage:latest",
    "temperature": 0.82,
    "max_tokens": 300,
}


def get_llm_config(profile: dict) -> dict:
    """Extract LLM config from profile, merging with defaults."""
    user_llm = profile.get("llm", {})
    merged = {**DEFAULT_LLM_CONFIG, **user_llm}

    # If user set a provider but no model, use that provider's default
    if "provider" in user_llm and "model" not in user_llm:
        merged["model"] = _DEFAULT_MODELS.get(merged["provider"], merged["model"])

    return merged


def _resolve_api_key(llm_config: dict) -> str | None:
    """Resolve API key: profile value → env var → None."""
    key = llm_config.get("api_key")
    if key:
        return key

    provider = llm_config.get("provider", "ollama")
    env_var = _PROVIDER_ENV_KEY.get(provider)
    if env_var:
        return os.environ.get(env_var)

    return None


def generate(system_prompt: str, user_prompt: str, profile: dict) -> str:
    """Generate text from the configured LLM provider.

    Raises on failure — callers should handle exceptions.
    """
    llm = get_llm_config(profile)
    provider = llm["provider"]

    logger.info("LLM provider=%s model=%s", provider, llm["model"])

    if provider == "ollama":
        return _generate_ollama(system_prompt, user_prompt, llm)
    else:
        return _generate_litellm(system_prompt, user_prompt, llm)


def _generate_ollama(system_prompt: str, user_prompt: str, llm: dict) -> str:
    """Generate via local Ollama."""
    import ollama

    base_url = llm.get("base_url")
    client = ollama.Client(host=base_url) if base_url else ollama

    response = client.chat(
        model=llm["model"],
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        options={
            "num_predict": llm.get("max_tokens", 300),
            "temperature": llm.get("temperature", 0.82),
        },
        think=False,
    )
    return response.message.content.strip()


def _generate_litellm(system_prompt: str, user_prompt: str, llm: dict) -> str:
    """Generate via litellm (supports all cloud providers)."""
    import litellm

    litellm.suppress_debug_info = True

    provider = llm["provider"]
    model = llm["model"]
    api_key = _resolve_api_key(llm)

    if not api_key:
        env_var = _PROVIDER_ENV_KEY.get(provider, "???")
        raise ValueError(
            f"No API key for provider '{provider}'. "
            f"Set it in user_profile.json under llm.api_key, "
            f"or export {env_var} in your environment / .env file."
        )

    # Build the litellm model string: "prefix/model"
    prefix = _PROVIDER_PREFIX.get(provider, "")
    if prefix and not model.startswith(prefix):
        model_str = f"{prefix}{model}"
    else:
        model_str = model

    kwargs: dict = {
        "model": model_str,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": llm.get("temperature", 0.82),
        "max_tokens": llm.get("max_tokens", 300),
        "api_key": api_key,
    }

    # Custom base URL (for openai_compatible or self-hosted)
    base_url = llm.get("base_url")
    if base_url:
        kwargs["api_base"] = base_url

    # Retry with exponential backoff for transient cloud errors
    last_err = None
    for attempt in range(_CLOUD_MAX_RETRIES + 1):
        try:
            response = litellm.completion(**kwargs)
            return response.choices[0].message.content.strip()
        except Exception as e:
            last_err = e
            if attempt < _CLOUD_MAX_RETRIES:
                delay = _CLOUD_BASE_DELAY * (2 ** attempt)
                logger.warning("Cloud LLM attempt %d failed (%s), retrying in %.1fs",
                               attempt + 1, e, delay)
                time.sleep(delay)
    raise last_err


def check_provider_health(profile: dict) -> bool:
    """Quick health check for the configured provider."""
    llm = get_llm_config(profile)
    provider = llm["provider"]

    if provider == "ollama":
        try:
            import ollama
            ollama.list()
            return True
        except Exception:
            return False
    else:
        # For cloud providers, just check that an API key is available
        return _resolve_api_key(llm) is not None
