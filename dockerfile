FROM python:3.13-slim

WORKDIR /app

# Install dependencies from the locked project manifest for reproducible builds
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv \
    && uv sync --frozen --no-dev --no-install-project

ENV PATH="/app/.venv/bin:${PATH}"

COPY main.py .

CMD ["python", "-u", "main.py"]
