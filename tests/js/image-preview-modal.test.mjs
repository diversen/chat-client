import test from 'node:test';
import assert from 'node:assert/strict';

import {
  IMAGE_PREVIEW_HISTORY_KEY,
  closeImagePreviewModal,
  openImagePreviewModal,
} from '../../chat_client/static/js/image-preview-modal.js';

function createClassList(initialClasses = []) {
  const classes = new Set(initialClasses);
  return {
    add: (...names) => names.forEach((name) => classes.add(name)),
    contains: (name) => classes.has(name),
    remove: (...names) => names.forEach((name) => classes.delete(name)),
  };
}

function createFakeWindow() {
  const listeners = new Map();
  const entries = [{ page: 'chat' }];
  let currentIndex = 0;

  const fakeWindow = {
    location: { href: 'http://example.test/chat/1' },
    addEventListener(type, listener) {
      listeners.set(type, listener);
    },
    removeEventListener(type, listener) {
      if (listeners.get(type) === listener) listeners.delete(type);
    },
    history: {
      get state() {
        return entries[currentIndex];
      },
      pushState(state) {
        entries.splice(currentIndex + 1, entries.length, state);
        currentIndex += 1;
      },
      back() {
        if (currentIndex === 0) return;
        currentIndex -= 1;
        listeners.get('popstate')?.({ state: entries[currentIndex] });
      },
    },
  };

  return fakeWindow;
}

test('browser Back closes an open image preview without leaving the page', () => {
  const originalWindow = globalThis.window;
  const fakeWindow = createFakeWindow();
  globalThis.window = fakeWindow;

  try {
    const modal = { classList: createClassList(['hidden']) };
    const image = { src: '', alt: '' };

    openImagePreviewModal(modal, image, 'data:image/png;base64,image', 'Preview image');

    assert.equal(modal.classList.contains('hidden'), false);
    assert.equal(fakeWindow.history.state[IMAGE_PREVIEW_HISTORY_KEY], true);

    fakeWindow.history.back();

    assert.equal(modal.classList.contains('hidden'), true);
    assert.equal(image.src, '');
    assert.deepEqual(fakeWindow.history.state, { page: 'chat' });
  } finally {
    globalThis.window = originalWindow;
  }
});

test('closing the image preview consumes its temporary history entry', () => {
  const originalWindow = globalThis.window;
  const fakeWindow = createFakeWindow();
  globalThis.window = fakeWindow;

  try {
    const modal = { classList: createClassList(['hidden']) };
    const image = { src: '', alt: '' };

    openImagePreviewModal(modal, image, 'data:image/png;base64,image', 'Preview image');
    closeImagePreviewModal(modal, image);

    assert.equal(modal.classList.contains('hidden'), true);
    assert.deepEqual(fakeWindow.history.state, { page: 'chat' });
  } finally {
    globalThis.window = originalWindow;
  }
});
