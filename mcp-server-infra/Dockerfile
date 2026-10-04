FROM python:3.12-slim

WORKDIR /app
COPY mcp-server-infra/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY mcp-server-infra/server.py /app/server.py

ENV PORT=8003
EXPOSE 8003
CMD ["python", "server.py"]
