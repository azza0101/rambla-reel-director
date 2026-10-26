'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { assertTrusted, validateMediaRecords } = require('../../plugin/ipc_security');

test('rejects untrusted renderer and frame', () => {
  const mainFrame = { url: 'file:///plugin/index.html' };
  const window = { webContents: { mainFrame } };
  assert.throws(() => assertTrusted({ sender: {}, senderFrame: mainFrame }, window, mainFrame.url), /non autorizzata/);
  assert.throws(() => assertTrusted({ sender: window.webContents, senderFrame: { url: mainFrame.url } }, window, mainFrame.url), /non autorizzata/);
});

test('accepts only validated Resolve media records', () => {
  assert.equal(validateMediaRecords([{ media_id: 'm', path: 'X:/clip.mov', duration_frames: 250 }])[0].camera_id, 'camera_1');
  assert.throws(() => validateMediaRecords([{ path: 'X:/attacker', duration_frames: 3 }]), /non valido/);
});
