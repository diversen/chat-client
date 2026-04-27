function asRecord(value) {
    return value && typeof value === 'object' ? value : {};
}

function parseStreamLine(rawLine) {
    const line = String(rawLine || '').replace(/^data:\s*/, '').trim();
    if (!line) {
        return null;
    }
    if (line === '[DONE]') {
        return { doneSentinel: true };
    }

    try {
        return { data: JSON.parse(line) };
    } catch (_) {
        return null;
    }
}

function normalizeStreamEvents(data, reasoningOpen) {
    const payload = asRecord(data);
    if (typeof payload.error === 'string' && payload.error.trim()) {
        throw new Error(payload.error.trim());
    }

    if (payload.tool_status) {
        return {
            events: [{ toolStatus: payload.tool_status }],
            reasoningOpen,
        };
    }

    if (payload.tool_call) {
        return {
            events: [{ toolCall: payload.tool_call }],
            reasoningOpen,
        };
    }

    if (typeof payload.turn_id === 'string' && payload.turn_id.trim()) {
        return {
            events: [{ turnId: payload.turn_id.trim() }],
            reasoningOpen,
        };
    }

    const events = [];
    const firstChoice = Array.isArray(payload.choices) && payload.choices[0] && typeof payload.choices[0] === 'object'
        ? payload.choices[0]
        : {};
    const delta = asRecord(firstChoice.delta);
    const finishReason = firstChoice.finish_reason;

    if (delta.reasoning) {
        if (!reasoningOpen) {
            events.push({ reasoning: null, reasoningOpenClose: 'open' });
        }
        events.push({ reasoning: delta.reasoning });
        reasoningOpen = true;
    } else if (reasoningOpen) {
        events.push({ reasoning: null, reasoningOpenClose: 'close' });
        reasoningOpen = false;
    }

    if (delta.content) {
        events.push({ content: delta.content });
    }
    if (finishReason) {
        events.push({ done: true });
    }

    return { events, reasoningOpen };
}

export {
    asRecord,
    normalizeStreamEvents,
    parseStreamLine,
};
