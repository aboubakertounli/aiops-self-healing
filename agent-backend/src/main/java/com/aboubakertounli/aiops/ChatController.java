package com.aboubakertounli.aiops;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

@RestController
public class ChatController {
    private final AgentService agentService;
    private final ClusterWatch clusterWatch;
    private final String baseUrl;
    private final String metricsUrl;
    private final String infraUrl;

    public ChatController(AgentService agentService,
                          ClusterWatch clusterWatch,
                          @Value("${spring.ai.openai.base-url:https://api.openai.com}") String baseUrl,
                          @Value("${spring.ai.mcp.client.sse.connections.metrics.url}") String metricsUrl,
                          @Value("${spring.ai.mcp.client.sse.connections.infra.url}") String infraUrl) {
        this.agentService = agentService;
        this.clusterWatch = clusterWatch;
        this.baseUrl = baseUrl;
        this.metricsUrl = metricsUrl;
        this.infraUrl = infraUrl;
    }

    @GetMapping("/api/health")
    public Map<String, String> health() {
        return Map.of("status", "up");
    }

    @GetMapping("/api/info")
    public AgentInfo info() {
        return new AgentInfo(
                agentService.model(),
                baseUrl,
                List.of(new AgentInfo.McpServer("metrics", metricsUrl), new AgentInfo.McpServer("infra", infraUrl))
        );
    }

    @GetMapping("/api/watch")
    public WatchReport watch() {
        return clusterWatch.status();
    }

    @PostMapping("/api/chat")
    public ChatResponse chat(@RequestBody ChatRequest request) {
        return agentService.chat(request);
    }

    @DeleteMapping("/api/conversations/{conversationId}")
    public void clear(@PathVariable String conversationId) {
        agentService.clear(conversationId);
    }
}
