import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';

export interface ToolTrace {
  name: string;
  arguments: string;
  result: string;
}

export interface ChatResponse {
  reply: string;
  model: string;
  tools: ToolTrace[] | null;
}

export interface McpServer {
  name: string;
  url: string;
}

export interface AgentInfo {
  model: string;
  baseUrl: string;
  mcp: McpServer[];
}

export interface AlertReport {
  received: boolean;
  at: string | null;
  reply: string | null;
  tools: ToolTrace[] | null;
}

@Injectable({ providedIn: 'root' })
export class DeskApi {
  private readonly http = inject(HttpClient);

  health() {
    return this.http.get<{ status: string }>('/api/health');
  }

  info() {
    return this.http.get<AgentInfo>('/api/info');
  }

  alerts() {
    return this.http.get<AlertReport>('/api/alerts');
  }

  chat(conversationId: string, message: string) {
    return this.http.post<ChatResponse>('/api/chat', { conversationId, message });
  }

  clear(conversationId: string) {
    return this.http.delete(`/api/conversations/${encodeURIComponent(conversationId)}`, {
      responseType: 'text',
    });
  }
}
