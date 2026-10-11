package com.aboubakertounli.aiops;

import org.springframework.ai.chat.client.ChatClient;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

@Service
public class AgentService {
    static final String SYSTEM = """
            You are the AIOps agent for a Kubernetes cluster running on OpenStack.
            Use the MCP tools to read Prometheus, Kubernetes, and OpenStack.
            You may delete one application pod when metrics and logs show it is failing or about to hit its memory limit. The Deployment starts a replacement through containerd.
            When the cause is node capacity or the OpenStack compute host, recommend the change and stop.
            Do not claim you edited a manifest, launched a VM, or scaled the cluster.
            Do not delete pods in kube-system.
            """;

    private final ChatClient chatClient;
    private final Map<String, List<String>> memory = new ConcurrentHashMap<>();

    public AgentService(ChatClient.Builder builder) {
        this.chatClient = builder.defaultSystem(SYSTEM).build();
    }

    public ChatResponse chat(ChatRequest request) {
        String conversationId = request.conversationId() == null || request.conversationId().isBlank()
                ? "default"
                : request.conversationId();
        List<String> turns = memory.computeIfAbsent(conversationId, ignored -> new ArrayList<>());
        String prompt = turns.isEmpty()
                ? request.message()
                : String.join("\n", turns) + "\nuser: " + request.message();

        String reply = chatClient.prompt().user(prompt).call().content();
        turns.add("user: " + request.message());
        turns.add("assistant: " + reply);
        if (turns.size() > 20) {
            turns.subList(0, turns.size() - 20).clear();
        }
        return new ChatResponse(reply);
    }
}
