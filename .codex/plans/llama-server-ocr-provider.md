# Add llama-server OCR Provider

## Goal

Make `llama_server` the default local OCR provider while keeping Ollama selectable and preserving OpenAI as the fallback provider.

## Plan

1. Add config/settings fields for `OCR_PROVIDER`, `LLAMA_SERVER_URL`, and `LLAMA_SERVER_MODEL`.
2. Add a llama-server OCR client that calls `/v1/chat/completions` with an OpenAI-compatible multimodal request.
3. Route OCR through the selected local provider by default, and through OpenAI first only when `--prefer-openai` is used.
4. Update the Settings UI, connection testers, Home display, env/compose docs, and repo instructions.
5. Add focused tests for llama-server request shape, fallback behavior, and retained Ollama support.
6. Bump the application version.
