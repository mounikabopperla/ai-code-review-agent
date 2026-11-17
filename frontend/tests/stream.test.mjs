import { test } from 'node:test';
import assert from 'node:assert/strict';
import { consumeAnswerStream } from '../../work/stream-tests/stream.js';

function responseFromBytes(bytes, width = 1) {
  return new Response(new ReadableStream({start(controller) {
    for (let i = 0; i < bytes.length; i += width) controller.enqueue(bytes.slice(i, i + width));
    controller.close();
  }}));
}
const encode = text => new TextEncoder().encode(text);

test('streams split JSON frames and multibyte text without corruption', async () => {
  const text = 'data: {"type":"delta","text":"Hi 👋"}\n\ndata: {"type":"delta","text":" there"}\n\ndata: {"type":"done"}\n\n';
  const updates = [];
  assert.equal(await consumeAnswerStream(responseFromBytes(encode(text)), x => updates.push(x)), 'Hi 👋 there');
  assert.deepEqual(updates, ['Hi 👋', 'Hi 👋 there']);
});

test('does not call an incomplete stream successful', async () => {
  const response = responseFromBytes(encode('data: {"type":"delta","text":"partial"}\n\n'));
  await assert.rejects(consumeAnswerStream(response, () => {}), /before the answer finished/);
});

test('surfaces server error after partial text', async () => {
  const response = responseFromBytes(encode('data: {"type":"delta","text":"partial"}\n\ndata: {"type":"error","message":"Please retry"}\n\n'));
  const updates = [];
  await assert.rejects(consumeAnswerStream(response, x => updates.push(x)), /Please retry/);
  assert.deepEqual(updates, ['partial']);
});
