package com.aboubakertounli.aiops;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.time.Instant;
import java.util.List;
import java.util.concurrent.atomic.AtomicBoolean;

@Component
public class ClusterWatch {
    static final String PROMPT = """
            Inspect the cluster. List the pods, then use metrics and diagnostics on any application pod that is failing or close to its memory limit. Delete that one pod only when the evidence supports it and a controller will recreate it. If the cause is node or OpenStack capacity, recommend the change and do not delete anything.
            """;

    private final AgentService agentService;
    private final int intervalSeconds;
    private final AtomicBoolean running = new AtomicBoolean(false);
    private volatile Instant lastRun = Instant.EPOCH;
    private volatile String at;
    private volatile String reply;
    private volatile List<ToolTrace> tools = List.of();

    public ClusterWatch(AgentService agentService, @Value("${agent.watch-seconds:0}") int intervalSeconds) {
        this.agentService = agentService;
        this.intervalSeconds = Math.max(0, intervalSeconds);
    }

    @Scheduled(fixedDelay = 15_000, initialDelay = 30_000)
    public void tick() {
        if (intervalSeconds <= 0) {
            return;
        }
        if (Instant.now().isBefore(lastRun.plusSeconds(intervalSeconds))) {
            return;
        }
        if (!running.compareAndSet(false, true)) {
            return;
        }
        lastRun = Instant.now();
        try {
            ChatResponse response = agentService.chat(new ChatRequest("watch", PROMPT));
            at = Instant.now().toString();
            reply = response.reply();
            tools = response.tools();
        }
        finally {
            running.set(false);
        }
    }

    public WatchReport status() {
        return new WatchReport(intervalSeconds > 0, intervalSeconds, at, reply, tools);
    }
}
