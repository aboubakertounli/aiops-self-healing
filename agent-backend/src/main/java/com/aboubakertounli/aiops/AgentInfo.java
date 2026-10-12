package com.aboubakertounli.aiops;

import java.util.List;

public record AgentInfo(String model, String baseUrl, List<McpServer> mcp) {
    public record McpServer(String name, String url) {
    }
}
