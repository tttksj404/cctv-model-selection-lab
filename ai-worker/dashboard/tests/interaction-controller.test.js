import assert from "node:assert/strict";
import test from "node:test";

import { createLatestRequestRunner } from "../interaction-controller.js";

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

test("latest request wins when an older scenario load finishes later", async () => {
  const first = deferred();
  const second = deferred();
  const rendered = [];
  const pendingStates = [];
  const errors = [];
  const runLatest = createLatestRequestRunner({
    loadScenario: (key) => (key === "first" ? first.promise : second.promise),
    onPendingChange: (pending) => pendingStates.push(pending),
    onError: (error) => errors.push(error),
  });

  const firstRun = runLatest("first", (value) => rendered.push(value));
  const secondRun = runLatest("second", (value) => rendered.push(value));
  second.resolve("second-result");
  await secondRun;
  first.resolve("first-result");
  await firstRun;

  assert.deepEqual(rendered, ["second-result"]);
  assert.deepEqual(pendingStates, [true, true, false]);
  assert.deepEqual(errors, []);
});

test("stale request errors do not replace the latest successful render", async () => {
  const first = deferred();
  const second = deferred();
  const rendered = [];
  const errors = [];
  const runLatest = createLatestRequestRunner({
    loadScenario: (key) => (key === "first" ? first.promise : second.promise),
    onPendingChange: () => {},
    onError: (error) => errors.push(error),
  });

  const firstRun = runLatest("first", (value) => rendered.push(value));
  const secondRun = runLatest("second", (value) => rendered.push(value));
  second.resolve("second-result");
  await secondRun;
  first.reject(new Error("stale failure"));
  await firstRun;

  assert.deepEqual(rendered, ["second-result"]);
  assert.deepEqual(errors, []);
});

test("latest request errors are surfaced and clear the pending state", async () => {
  const pendingStates = [];
  const errors = [];
  const runLatest = createLatestRequestRunner({
    loadScenario: () => Promise.reject(new Error("latest failure")),
    onPendingChange: (pending) => pendingStates.push(pending),
    onError: (error) => errors.push(error),
  });

  const applied = await runLatest("latest", () => {});

  assert.equal(applied, false);
  assert.deepEqual(pendingStates, [true, false]);
  assert.equal(errors.length, 1);
  assert.equal(errors[0].message, "latest failure");
});

