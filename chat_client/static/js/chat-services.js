import { createDialog, generateDialogTitle, getMessages, getDialogUsage, createMessage, createAssistantTurnEvents, updateMessage, uploadAttachment } from '/static/js/app-dialog.js';

const storageService = {
    createDialog,
    generateDialogTitle,
    createMessage,
    createAssistantTurnEvents,
    updateMessage,
    getMessages,
    getDialogUsage,
    uploadAttachment,
};

function asRecord(value) {
    return value && typeof value === 'object' ? value : {};
}

async function getStreamingChatResponse(payload, signal) {
    const response = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        signal,
    });

    if (response.ok) {
        return response;
    }

    let responseJson = {};
    try {
        responseJson = asRecord(await response.json());
    } catch (_) {
        responseJson = {};
    }

    const error = new Error(
        responseJson.message || `Server returned error: ${response.status} ${response.statusText}`,
    );
    if (responseJson.redirect) {
        error.redirect = responseJson.redirect;
    }
    error.status = response.status;
    throw error;
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

const chatService = {
    async *stream(payload, signal) {
        const response = await getStreamingChatResponse(payload, signal);
        if (!response.body) {
            throw new Error('Response body is empty. Try again later.');
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let reasoningOpen = false;
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() ?? '';

            for (const rawLine of lines) {
                const parsedLine = parseStreamLine(rawLine);
                if (!parsedLine) continue;
                if (parsedLine.doneSentinel) {
                    if (reasoningOpen) {
                        yield { reasoning: null, reasoningOpenClose: 'close' };
                        reasoningOpen = false;
                    }
                    return;
                }

                const normalized = normalizeStreamEvents(parsedLine.data, reasoningOpen);
                reasoningOpen = normalized.reasoningOpen;
                for (const event of normalized.events) {
                    yield event;
                }
            }
        }

        const tail = parseStreamLine(buffer);
        if (!tail || tail.doneSentinel) {
            if (reasoningOpen) {
                yield { reasoning: null, reasoningOpenClose: 'close' };
            }
            return;
        }

        const normalized = normalizeStreamEvents(tail.data, reasoningOpen);
        for (const event of normalized.events) {
            yield event;
        }
    },
};

export { storageService, chatService };
