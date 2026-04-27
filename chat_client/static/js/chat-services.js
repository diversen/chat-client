import { createDialog, generateDialogTitle, getMessages, getDialogUsage, createMessage, createAssistantTurnEvents, updateMessage, uploadAttachment } from '/static/js/app-dialog.js';
import { asRecord, normalizeStreamEvents, parseStreamLine } from '/static/js/chat-stream-events.js';

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

export {
    chatService,
    storageService,
};
