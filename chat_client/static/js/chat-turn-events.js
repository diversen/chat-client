function hasVisibleText(rawText) {
    return String(rawText || '').trim().length > 0;
}

function createAssistantSegmentTurnEvent({ reasoningText = '', contentText = '' } = {}) {
    return {
        event_type: 'assistant_segment',
        reasoning_text: String(reasoningText || ''),
        content_text: String(contentText || ''),
    };
}

function createToolCallTurnEvent(toolCall = {}) {
    return {
        event_type: 'tool_call',
        tool_call_id: String(toolCall.tool_call_id || ''),
        tool_name: String(toolCall.tool_name || ''),
        arguments_json: String(toolCall.arguments_json || '{}'),
        result_text: String(toolCall.content || ''),
        error_text: String(toolCall.error_text || ''),
    };
}

function classifyFinalizedAssistantSegment(finalized) {
    const kind = String(finalized.kind || '').toLowerCase();
    const text = String(finalized.text || '');
    const isVisible = Boolean(finalized.isVisible);
    if (!isVisible || !hasVisibleText(text)) {
        return { action: 'discard', text };
    }
    if (kind === 'answer') {
        return { action: 'answer', text };
    }
    if (kind === 'thinking') {
        return { action: 'thinking', text };
    }
    return { action: 'discard', text };
}

function buildAssistantMessagesFromTurnEvents(events = []) {
    if (!Array.isArray(events)) {
        return [];
    }
    return events
        .filter((event) => event && event.event_type === 'assistant_segment')
        .map((event) => String(event.content_text || ''))
        .filter((contentText) => hasVisibleText(contentText))
        .map((content) => ({ role: 'assistant', content }));
}

export {
    buildAssistantMessagesFromTurnEvents,
    classifyFinalizedAssistantSegment,
    createAssistantSegmentTurnEvent,
    createToolCallTurnEvent,
    hasVisibleText,
};
