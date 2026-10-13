package com.aboubakertounli.aiops;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

import java.util.List;
import java.util.Map;

@JsonIgnoreProperties(ignoreUnknown = true)
public record AlertmanagerWebhook(String status, String receiver, List<Alert> alerts) {

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record Alert(String status, Map<String, String> labels, Map<String, String> annotations) {
    }

    public List<Alert> firing() {
        if (alerts == null) {
            return List.of();
        }
        return alerts.stream()
                .filter(alert -> alert != null && "firing".equalsIgnoreCase(alert.status()))
                .toList();
    }

    public String toPrompt() {
        StringBuilder text = new StringBuilder();
        text.append("Alertmanager fired the following alerts. Investigate with the tools. ");
        text.append("Delete one application pod only when metrics and logs show it is failing or about to hit its memory limit, ");
        text.append("and only when a controller will recreate it. ");
        text.append("If the cause is node or OpenStack capacity, recommend the change and do not delete anything.\n");
        for (Alert alert : firing()) {
            Map<String, String> labels = alert.labels() == null ? Map.of() : alert.labels();
            Map<String, String> notes = alert.annotations() == null ? Map.of() : alert.annotations();
            text.append("\n- ")
                    .append(labels.getOrDefault("alertname", "alert"))
                    .append(" namespace=")
                    .append(labels.getOrDefault("namespace", ""))
                    .append(" pod=")
                    .append(labels.getOrDefault("pod", ""));
            if (notes.get("description") != null) {
                text.append("\n  ").append(notes.get("description"));
            }
        }
        return text.toString();
    }
}
