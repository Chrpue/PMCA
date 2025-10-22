FROM node:20-alpine AS build

# 拉取 Xczer 的 todo MCP 服务器源码（若需指定 tag/commit 自行替换）
ARG REPO_URL=https://github.com/Xczer/todo-mcp-server.git
ARG REPO_REF=main
RUN apk add --no-cache git python3 py3-pip
WORKDIR /src
RUN git clone --depth 1 --branch ${REPO_REF} ${REPO_URL} app
WORKDIR /src/app
RUN npm ci && npm run build

# ---- runtime ----
FROM node:20-alpine
# 安装 mcp-proxy（Python 发行版），用于把 stdio 暴露为 SSE/HTTP
RUN apk add --no-cache python3 py3-pip && pip install --no-cache-dir mcp-proxy
# 非 root 账号
RUN addgroup -S mcp && adduser -S mcp -G mcp
USER mcp
WORKDIR /app
COPY --from=build /src/app/dist /app/dist

# 数据目录（SQLite）
ENV TODO_DB_PATH=/app/data/todos.db
ENV PORT=11009
# 选择暴露协议：sse 或 streamablehttp（二选一，见下 compose）
ENV TRANSPORT=sse

# 入口：mcp-proxy 监听 11009，并以子进程方式拉起 stdio 服务器（node dist/index.js）
# --port 会在 /sse（SSE）或 /mcp（Streamable HTTP）上提供 MCP 端点
ENTRYPOINT ["mcp-proxy"]
