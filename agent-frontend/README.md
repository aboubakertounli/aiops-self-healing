# Signal desk

Angular console for the agent. `npm start` serves it on port 4200 and proxies `/api` to the Spring app on port 8080.

The agent image build (`agent-backend/Dockerfile`) compiles this app and serves it from the same process on port 8080.
