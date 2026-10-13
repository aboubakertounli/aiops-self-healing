package com.aboubakertounli.aiops;

import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.client.advisor.MessageChatMemoryAdvisor;
import org.springframework.ai.chat.memory.ChatMemory;
import org.springframework.ai.chat.memory.MessageWindowChatMemory;
import org.springframework.ai.chat.messages.AssistantMessage;
import org.springframework.ai.tool.ToolCallback;
import org.springframework.ai.tool.ToolCallbackProvider;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class AgentService {
    static final String SYSTEM = """
            You are the AIOps agent for a Kubernetes cluster running on OpenStack.
            Two MCP servers are connected.
            The metrics server reads Prometheus: current CPU and memory, history, predict_linear forecasts, whether memory will hit the limit within an hour, and anomaly checks.
            The infra server reads Kubernetes and OpenStack, collects pod diagnostics, and can delete one application pod with restart_pod. The Deployment then starts a replacement through containerd.
            Use the tools before you state numbers or claim a pod was restarted.
            Delete a pod only when metrics and logs show it is failing or about to hit its memory limit, and only when a controller will recreate it.
            When the cause is node capacity or the OpenStack compute host, recommend the change and stop.
            Do not claim you edited a manifest, launched a VM, or scaled the cluster.
            Do not delete pods in kube-system.
            """;

    private final ChatClient chatClient;
    private final ChatMemory chatMemory;
    private final String model;

    public AgentService(ChatClient.Builder builder,
                        ObjectProvider<ToolCallbackProvider> mcpTools,
                        @Value("${spring.ai.openai.chat.options.model:gpt-4o}") String model) {
        this.model = model;
        this.chatMemory = MessageWindowChatMemory.builder().maxMessages(20).build();
        ToolCallbackProvider tools = mcpTools.getIfAvailable(() -> ToolCallbackProvider.from(new ToolCallback[0]));
        this.chatClient = builder
                .defaultSystem(SYSTEM)
                .defaultToolCallbacks(new RecordingToolCallbackProvider(tools))
                .defaultAdvisors(MessageChatMemoryAdvisor.builder(this.chatMemory).build())
                .build();
    }

    public String model() {
        return model;
    }

    public ChatResponse chat(ChatRequest request) {
        String conversationId = request.conversationId() == null || request.conversationId().isBlank()
                ? "default"
                : request.conversationId();
        ToolTraceBuffer.open();
        try {
            String reply = chatClient.prompt()
                    .user(request.message())
                    .advisors(advisor -> advisor.param(ChatMemory.CONVERSATION_ID, conversationId))
                    .call()
                    .content();
            List<ToolTrace> tools = ToolTraceBuffer.take();
            rememberTools(conversationId, tools);
            return new ChatResponse(reply == null ? "" : reply, model, tools);
        }
        catch (RuntimeException ex) {
            List<ToolTrace> tools = ToolTraceBuffer.take();
            String reply = "The model call failed: " + (ex.getMessage() == null ? ex.getClass().getSimpleName() : ex.getMessage());
            return new ChatResponse(reply, model, tools);
        }
        finally {
            ToolTraceBuffer.close();
        }
    }

    public void clear(String conversationId) {
        chatMemory.clear(conversationId);
    }

    private void rememberTools(String conversationId, List<ToolTrace> tools) {
        if (tools.isEmpty()) {
            return;
        }
        StringBuilder note = new StringBuilder("Tools used:");
        for (ToolTrace tool : tools) {
            note.append("\n")
                    .append(tool.name())
                    .append(" ")
                    .append(ToolTraceBuffer.cap(tool.arguments(), 500))
                    .append(" -> ")
                    .append(ToolTraceBuffer.cap(tool.result(), 500));
        }
        chatMemory.add(conversationId, new AssistantMessage(note.toString()));
    }
}
