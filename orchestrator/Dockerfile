# Optional container build for the orchestrator (used by infrastructure/docker-compose.yml). Untested on the
# reference machine, which runs everything natively.
FROM python:3.12-slim
RUN useradd -m app
WORKDIR /app
COPY pyproject.toml ./
RUN pip install --no-cache-dir "fastmcp==4.1.3" "httpx>=0.27" "pyyaml>=6.0"
COPY orchestrator ./orchestrator
COPY agents ./agents
COPY memory ./memory
USER app
ENV ORCHESTRATOR_HOST=0.0.0.0 ORCHESTRATOR_PORT=8765 AGENT_STACK_REPO=/app
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8765/healthz', timeout=3).status==200 else 1)"
CMD ["python", "-m", "orchestrator.server"]
