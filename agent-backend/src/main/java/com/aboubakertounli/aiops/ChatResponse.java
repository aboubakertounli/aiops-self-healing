package com.aboubakertounli.aiops;

import java.util.List;

public record ChatResponse(String reply, String model, List<ToolTrace> tools) {
}
