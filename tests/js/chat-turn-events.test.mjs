import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildAssistantMessagesFromTurnEvents,
  classifyFinalizedAssistantSegment,
  createAssistantSegmentTurnEvent,
  createToolCallTurnEvent,
  hasVisibleText,
} from '../../chat_client/static/js/chat-turn-events.js';

test('hasVisibleText returns false for blank text and true for visible text', () => {
  assert.equal(hasVisibleText(''), false);
  assert.equal(hasVisibleText('   '), false);
  assert.equal(hasVisibleText('hello'), true);
});

test('createAssistantSegmentTurnEvent normalizes thinking and answer payloads', () => {
  assert.deepEqual(
    createAssistantSegmentTurnEvent({ reasoningText: 'thinking', contentText: 'answer' }),
    {
      event_type: 'assistant_segment',
      reasoning_text: 'thinking',
      content_text: 'answer',
    },
  );
});

test('createToolCallTurnEvent normalizes persisted tool call payloads', () => {
  assert.deepEqual(
    createToolCallTurnEvent({
      tool_call_id: 'call_1',
      tool_name: 'search',
      arguments_json: '{"q":"hello"}',
      content: 'result text',
      error_text: '',
    }),
    {
      event_type: 'tool_call',
      tool_call_id: 'call_1',
      tool_name: 'search',
      arguments_json: '{"q":"hello"}',
      result_text: 'result text',
      error_text: '',
    },
  );
});

test('classifyFinalizedAssistantSegment distinguishes answer, thinking, and discard cases', () => {
  assert.deepEqual(
    classifyFinalizedAssistantSegment({ kind: 'Answer', text: 'done', isVisible: true }),
    { action: 'answer', text: 'done' },
  );
  assert.deepEqual(
    classifyFinalizedAssistantSegment({ kind: 'Thinking', text: 'chain of thought', isVisible: true }),
    { action: 'thinking', text: 'chain of thought' },
  );
  assert.deepEqual(
    classifyFinalizedAssistantSegment({ kind: 'Tool', text: 'ignored', isVisible: true }),
    { action: 'discard', text: 'ignored' },
  );
  assert.deepEqual(
    classifyFinalizedAssistantSegment({ kind: 'Answer', text: '   ', isVisible: true }),
    { action: 'discard', text: '   ' },
  );
});

test('buildAssistantMessagesFromTurnEvents returns assistant history only for visible answer segments', () => {
  const events = [
    createAssistantSegmentTurnEvent({ reasoningText: 'thinking only' }),
    createAssistantSegmentTurnEvent({ contentText: 'Final answer' }),
    createToolCallTurnEvent({
      tool_call_id: 'call_2',
      tool_name: 'search',
      arguments_json: '{}',
      content: 'tool result',
      error_text: '',
    }),
    createAssistantSegmentTurnEvent({ contentText: '  ' }),
  ];

  assert.deepEqual(buildAssistantMessagesFromTurnEvents(events), [
    { role: 'assistant', content: 'Final answer' },
  ]);
});
