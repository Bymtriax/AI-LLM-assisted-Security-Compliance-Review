import assert from "node:assert/strict";
import test from "node:test";

import { ChatClient } from "../../src/web_ui/chat_client.mjs";

test("sends full history and appends retrieval messages in order", async () => {
  const requests = [];
  const responses = [
    [{ role: "assistant", content: "Hello." }],
    [
      { role: "system", content: "Regulation search: S17\nSearch results:\nClause." },
      { role: "assistant", content: "The clause says..." },
    ],
  ];
  const client = new ChatClient({
    apiUrl: "http://example.test/api/chat",
    fetchImpl: async (url, options) => {
      assert.equal(url, "http://example.test/api/chat");
      assert.equal(options.method, "POST");
      assert.equal(options.headers["Content-Type"], "application/json");
      requests.push(JSON.parse(options.body));
      return { ok: true, json: async () => ({ messages: responses.shift() }) };
    },
  });

  assert.deepEqual(await client.send("  hi  "), [
    { role: "assistant", content: "Hello." },
  ]);
  assert.deepEqual(await client.send("S17?"), [
    { role: "system", content: "Regulation search: S17\nSearch results:\nClause." },
    { role: "assistant", content: "The clause says..." },
  ]);
  assert.deepEqual(requests, [
    { messages: [{ role: "user", content: "hi" }] },
    {
      messages: [
        { role: "user", content: "hi" },
        { role: "assistant", content: "Hello." },
        { role: "user", content: "S17?" },
      ],
    },
  ]);
  assert.deepEqual(client.messages, [
    { role: "user", content: "hi" },
    { role: "assistant", content: "Hello." },
    { role: "user", content: "S17?" },
    { role: "system", content: "Regulation search: S17\nSearch results:\nClause." },
    { role: "assistant", content: "The clause says..." },
  ]);
});

test("appends every returned message and includes it in the next request", async () => {
  const replies = [
    { role: "system", content: "First retrieval result." },
    { role: "system", content: "Second retrieval result." },
    { role: "assistant", content: "Answer using both results." },
  ];
  const requests = [];
  const client = new ChatClient({
    fetchImpl: async (_url, options) => {
      requests.push(JSON.parse(options.body));
      return {
        ok: true,
        json: async () => ({
          messages:
            requests.length === 1
              ? replies
              : [{ role: "assistant", content: "Follow-up answer." }],
        }),
      };
    },
  });

  assert.deepEqual(await client.send("question"), replies);
  assert.deepEqual(client.messages, [
    { role: "user", content: "question" },
    ...replies,
  ]);
  await client.send("follow-up");
  assert.deepEqual(requests[1], {
    messages: [
      { role: "user", content: "question" },
      ...replies,
      { role: "user", content: "follow-up" },
    ],
  });
  assert.deepEqual(client.messages, [
    ...requests[1].messages,
    { role: "assistant", content: "Follow-up answer." },
  ]);
});

test("failed request keeps history ready for a retry", async () => {
  const client = new ChatClient({
    fetchImpl: async () => ({ ok: false, status: 500 }),
  });

  await assert.rejects(client.send("question"), /HTTP 500/);
  assert.deepEqual(client.messages, []);
});

test("uses the browser fetch method with its required context", async () => {
  const previousFetch = globalThis.fetch;
  globalThis.fetch = function () {
    assert.equal(this, globalThis);
    return Promise.resolve({
      ok: true,
      json: async () => ({ messages: [{ role: "assistant", content: "Hello." }] }),
    });
  };

  try {
    const client = new ChatClient();
    assert.deepEqual(await client.send("hi"), [
      { role: "assistant", content: "Hello." },
    ]);
  } finally {
    globalThis.fetch = previousFetch;
  }
});

test("invalid server messages do not enter history", async () => {
  const client = new ChatClient({
    fetchImpl: async () => ({
      ok: true,
      json: async () => ({ messages: [{ role: "assistant", content: " " }] }),
    }),
  });

  await assert.rejects(client.send("question"), /消息格式无效/);
  assert.deepEqual(client.messages, []);
});
