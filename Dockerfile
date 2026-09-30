FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /build

# Build context is the repo root (docker-compose.yml: build.context: ..), because
# pyproject.toml resolves meadows-protocol and meadows-client through
# [tool.uv.sources] as ../meadows-protocol and ../meadows-client. Those siblings
# must exist at exactly those relative paths next to meadows-tui/, so they are
# copied in first and installed on their own for layer caching.
COPY meadows-protocol/ meadows-protocol/
COPY meadows-client/pyproject.toml meadows-client/README.md meadows-client/
COPY meadows-client/src/ meadows-client/src/
COPY meadows-tui/pyproject.toml meadows-tui/README.md meadows-tui/
COPY meadows-tui/src/ meadows-tui/src/

RUN cd /build/meadows-protocol && uv pip install --system --no-cache . && \
    cd /build/meadows-client && uv pip install --system --no-cache . && \
    cd /build/meadows-tui && uv pip install --system --no-cache .

# The TUI is a terminal app: run with `docker run -it remcoboerma/meadows-tui`.
# Configuration comes from flags or MEADOWS_* env vars (see meadows/tui/cli.py),
# e.g. --server/--token/--theme, or MEADOWS_SERVER_URL + MEADOWS_JWT.
ENTRYPOINT ["meadows-tui"]
