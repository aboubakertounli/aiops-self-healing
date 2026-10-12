package com.aboubakertounli.aiops;

import org.springframework.ai.tool.ToolCallback;
import org.springframework.ai.tool.ToolCallbackProvider;

final class RecordingToolCallbackProvider implements ToolCallbackProvider {
    private final ToolCallbackProvider delegate;

    RecordingToolCallbackProvider(ToolCallbackProvider delegate) {
        this.delegate = delegate;
    }

    @Override
    public ToolCallback[] getToolCallbacks() {
        ToolCallback[] callbacks = delegate.getToolCallbacks();
        ToolCallback[] wrapped = new ToolCallback[callbacks.length];
        for (int i = 0; i < callbacks.length; i++) {
            wrapped[i] = new RecordingToolCallback(callbacks[i]);
        }
        return wrapped;
    }
}
