import test from 'node:test';
import assert from 'node:assert/strict';

import {
  asRecord,
  normalizeStreamEvents,
  parseStreamLine,
} from '../../chat_client/static/js/chat-stream-events.js';

test('asRecord normalizes non-object values to empty objects', () => {
  assert.deepEqual(asRecord(null), {});
  assert.deepEqual(asRecord('x'), {});
  assert.deepEqual(asRecord({ ok: true }), { ok: true });
});

test('parseStreamLine parses SSE payload lines and done sentinels', () => {
  assert.deepEqual(parseStreamLine('data: {"turn_id":"turn-1"}'), {
    data: { turn_id: 'turn-1' },
  });
  assert.deepEqual(parseStreamLine('data: [DONE]'), { doneSentinel: true });
  assert.equal(parseStreamLine(''), null);
  assert.equal(parseStreamLine('data: not-json'), null);
});

test('normalizeStreamEvents handles turn id, tool status, and tool call payloads', () => {
  assert.deepEqual(
    normalizeStreamEvents({ turn_id: 'turn-1' }, false),
    { events: [{ turnId: 'turn-1' }], reasoningOpen: false },
  );
  assert.deepEqual(
    normalizeStreamEvents({ tool_status: { tool_name: 'search' } }, false),
    { events: [{ toolStatus: { tool_name: 'search' } }], reasoningOpen: false },
  );
  assert.deepEqual(
    normalizeStreamEvents({ tool_call: { tool_name: 'search', content: 'ok' } }, false),
    { events: [{ toolCall: { tool_name: 'search', content: 'ok' } }], reasoningOpen: false },
  );
});

test('normalizeStreamEvents opens reasoning, emits content, and marks completion', () => {
  assert.deepEqual(
    normalizeStreamEvents({
      choices: [
        {
          delta: { reasoning: 'thinking', content: 'answer' },
          finish_reason: 'stop',
        },
      ],
    }, false),
    {
      events: [
        { reasoning: null, reasoningOpenClose: 'open' },
        { reasoning: 'thinking' },
        { content: 'answer' },
        { done: true },
      ],
      reasoningOpen: true,
    },
  );
});

test('normalizeStreamEvents closes reasoning when later payload omits it', () => {
  assert.deepEqual(
    normalizeStreamEvents({
      choices: [
        {
          delta: { content: 'final' },
          finish_reason: null,
        },
      ],
    }, true),
    {
      events: [
        { reasoning: null, reasoningOpenClose: 'close' },
        { content: 'final' },
      ],
      reasoningOpen: false,
    },
  );
});

test('normalizeStreamEvents throws on streamed error payloads', () => {
  assert.throws(
    () => normalizeStreamEvents({ error: 'Bad stream' }, false),
    /Bad stream/,
  );
});
