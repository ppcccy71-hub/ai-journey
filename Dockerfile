# ---------- 前端构建 ----------
FROM node:20-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---------- 后端 ----------
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY build/requirements.txt /app/build/requirements.txt
RUN pip install --no-cache-dir -r /app/build/requirements.txt

COPY build/ /app/build/
COPY --from=web /web/dist /app/frontend/dist

WORKDIR /app/build
ENV PORT=8000
EXPOSE 8000

# 用 shell 形式，让云平台的 PORT 环境变量生效
CMD ["sh", "-c", "python -m uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"]
