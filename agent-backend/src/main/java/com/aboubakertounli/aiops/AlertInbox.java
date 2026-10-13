package com.aboubakertounli.aiops;

import org.springframework.stereotype.Component;

import java.time.Instant;
import java.util.List;

@Component
public class AlertInbox {
    private volatile AlertReport last = new AlertReport(false, null, null, List.of());

    public void remember(ChatResponse response) {
        last = new AlertReport(true, Instant.now().toString(), response.reply(), response.tools());
    }

    public AlertReport last() {
        return last;
    }
}
