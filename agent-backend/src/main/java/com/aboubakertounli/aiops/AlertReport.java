package com.aboubakertounli.aiops;

import java.util.List;

public record AlertReport(boolean received, String at, String reply, List<ToolTrace> tools) {
}
