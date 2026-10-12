package com.aboubakertounli.aiops;

import org.springframework.ai.chat.model.ToolContext;
import org.springframework.ai.tool.ToolCallback;
import org.springframework.ai.tool.definition.ToolDefinition;
import org.springframework.ai.tool.metadata.ToolMetadata;

final class RecordingToolCallback implements ToolCallback {
    private final ToolCallback delegate;

    RecordingToolCallback(ToolCallback delegate) {
        this.delegate = delegate;
    }

    @Override
    public ToolDefinition getToolDefinition() {
        return delegate.getToolDefinition();
    }

    @Override
    public ToolMetadata getToolMetadata() {
        return delegate.getToolMetadata();
    }

    @Override
    public String call(String toolInput) {
        return record(toolInput, () -> delegate.call(toolInput));
    }

    @Override
    public String call(String toolInput, ToolContext toolContext) {
        return record(toolInput, () -> delegate.call(toolInput, toolContext));
    }

    private String record(String toolInput, ToolCall call) {
        try {
            String result = call.run();
            ToolTraceBuffer.remember(delegate.getToolDefinition().name(), toolInput, result);
            return result;
        }
        catch (RuntimeException ex) {
            ToolTraceBuffer.remember(delegate.getToolDefinition().name(), toolInput, ex.getMessage());
            throw ex;
        }
    }

    @FunctionalInterface
    private interface ToolCall {
        String run();
    }
}
