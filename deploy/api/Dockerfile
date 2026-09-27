# fieldforge-api 镜像（构建上下文 = 仓库根目录）
# docker build -f deploy/api/Dockerfile -t fieldforge-api:latest .
FROM python:3.12-slim

WORKDIR /app
ENV FF_REPO=/app FF_DATA=/data PYTHONUNBUFFERED=1

COPY deploy/api/requirements.txt deploy/api/requirements.txt
RUN pip install --no-cache-dir -r deploy/api/requirements.txt

COPY fieldforge/ fieldforge/
COPY schemas/ schemas/
COPY recipes/ recipes/
COPY sweeps/ sweeps/
COPY scripts/ scripts/
COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir -e . \
    && useradd -m ffuser && mkdir -p /data && chown -R ffuser /data

USER ffuser
EXPOSE 8000
CMD ["uvicorn", "fieldforge.serve.app:app", "--host", "0.0.0.0", "--port", "8000"]
