FROM python:3.12-slim

WORKDIR /app
COPY shared /app/shared
COPY mcp-server-metrics/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY mcp-server-metrics/server.py /app/server.py

ENV PYTHONPATH=/app
ENV PORT=8002
EXPOSE 8002
CMD ["python", "server.py"]
