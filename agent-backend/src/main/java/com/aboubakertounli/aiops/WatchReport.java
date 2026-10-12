package com.aboubakertounli.aiops;

import java.util.List;

public record WatchReport(boolean enabled, int intervalSeconds, String at, String reply, List<ToolTrace> tools) {
}
