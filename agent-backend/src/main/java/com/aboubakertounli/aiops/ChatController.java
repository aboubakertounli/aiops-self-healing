package com.aboubakertounli.aiops;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
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
    private final AlertInbox alertInbox;
    private final String baseUrl;
    private final String metricsUrl;
    private final String infraUrl;

    public ChatController(AgentService agentService,
                          AlertInbox alertInbox,
                          @Value("${spring.ai.openai.base-url:https://api.openai.com}") String baseUrl,
                          @Value("${spring.ai.mcp.client.streamable-http.connections.k8s-container-metrics.url}") String metricsUrl,
                          @Value("${spring.ai.mcp.client.streamable-http.connections.k8s-cluster-openstack.url}") String infraUrl) {
        this.agentService = agentService;
        this.alertInbox = alertInbox;
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
                List.of(
                        new AgentInfo.McpServer("k8s-container-metrics", metricsUrl),
                        new AgentInfo.McpServer("k8s-cluster-openstack", infraUrl))
        );
    }

    @GetMapping("/api/alerts")
    public AlertReport lastAlert() {
        return alertInbox.last();
    }

    @PostMapping("/api/alerts")
    public ChatResponse alerts(@RequestBody AlertmanagerWebhook webhook) {
        if (webhook == null || webhook.firing().isEmpty()) {
            return new ChatResponse("No firing alerts.", agentService.model(), List.of());
        }
        ChatResponse response = agentService.chat(new ChatRequest("alerts", webhook.toPrompt()));
        alertInbox.remember(response);
        return response;
    }

    @PostMapping("/api/chat")
    public ChatResponse chat(@RequestBody ChatRequest request) {
        return agentService.chat(request);
    }

    @DeleteMapping("/api/conversations/{conversationId}")
    public ResponseEntity<Void> clear(@PathVariable String conversationId) {
        agentService.clear(conversationId);
        return ResponseEntity.noContent().build();
    }
}
