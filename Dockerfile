FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY src ./src

RUN pip install --no-cache-dir . \
    && git config --system --add safe.directory /traefik

ENV MCP_TRANSPORT=streamable-http
ENV MCP_HTTP_HOST=0.0.0.0
ENV MCP_HTTP_PORT=8765

EXPOSE 8765

CMD ["python", "-m", "traefik_mcp.server"]
