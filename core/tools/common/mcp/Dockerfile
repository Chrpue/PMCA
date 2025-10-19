FROM python:3.11-slim

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 更换为国内 Debian (清华大学) 源并安装基础依赖
RUN echo "\
Types: deb\n\
URIs: https://mirrors.tuna.tsinghua.edu.cn/debian/\n\
Suites: bookworm bookworm-updates\n\
Components: main contrib non-free non-free-firmware\n\
Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg\n\
\n\
Types: deb\n\
URIs: https://mirrors.tuna.tsinghua.edu.cn/debian-security/\n\
Suites: bookworm-security\n\
Components: main contrib non-free non-free-firmware\n\
Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg\n\
" > /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt /app/requirements.txt

# 使用国内 PyPI (清华大学) 源安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用程序代码
COPY server/ /app/server/

# 暴露端口
EXPOSE 8000

# 使用 Uvicorn 启动 ASGI 应用 (这是您指定的正确命令)
CMD ["uvicorn", "server.assistant_emitter:app", "--host", "0.0.0.0", "--port", "8000"]
