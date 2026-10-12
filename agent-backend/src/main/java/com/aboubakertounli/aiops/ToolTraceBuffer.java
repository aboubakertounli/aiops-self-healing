package com.aboubakertounli.aiops;

import java.util.ArrayList;
import java.util.List;

final class ToolTraceBuffer {
    static final ThreadLocal<List<ToolTrace>> CURRENT = new ThreadLocal<>();

    private ToolTraceBuffer() {
    }

    static void remember(String name, String arguments, String result) {
        List<ToolTrace> current = CURRENT.get();
        if (current == null) {
            return;
        }
        current.add(new ToolTrace(name, cap(arguments, 4000), cap(result, 4000)));
    }

    static List<ToolTrace> take() {
        List<ToolTrace> current = CURRENT.get();
        return current == null ? List.of() : List.copyOf(current);
    }

    static void open() {
        CURRENT.set(new ArrayList<>());
    }

    static void close() {
        CURRENT.remove();
    }

    static String cap(String value, int limit) {
        if (value == null || value.isBlank()) {
            return "";
        }
        String trimmed = value.strip();
        return trimmed.length() <= limit ? trimmed : trimmed.substring(0, limit) + "\n… truncated";
    }
}
