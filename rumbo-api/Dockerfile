FROM python:3.13-slim
WORKDIR /workspace/rumbo-api
COPY pyproject.toml ./
COPY app ./app
COPY assets ./assets
COPY alembic.ini ./
COPY migrations ./migrations
RUN pip install --no-cache-dir -e .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
