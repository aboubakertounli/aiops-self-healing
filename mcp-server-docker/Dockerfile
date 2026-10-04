FROM python:3.12-slim

WORKDIR /app
COPY shared /app/shared
COPY mcp-server-docker/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY mcp-server-docker/server.py /app/server.py

ENV PYTHONPATH=/app
ENV PORT=8001
EXPOSE 8001
CMD ["python", "server.py"]
