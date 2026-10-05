const API_URL = "http://127.0.0.1:8000/api/chat";

export class ChatClient {
  #messages = [];

  constructor({ fetchImpl = globalThis.fetch.bind(globalThis), apiUrl = API_URL } = {}) {
    this.fetchImpl = fetchImpl;
    this.apiUrl = apiUrl;
  }

  get messages() {
    return this.#messages.map((message) => ({ ...message }));
  }

  async send(content) {
    const text = content.trim();
    if (!text) {
      throw new Error("请输入消息。");
    }

    const userMessage = { role: "user", content: text };
    const response = await this.fetchImpl(this.apiUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: [...this.#messages, userMessage] }),
    });

    if (!response.ok) {
      throw new Error(`请求失败（HTTP ${response.status}）。`);
    }

    let body;
    try {
      body = await response.json();
    } catch {
      throw new Error("服务返回的内容不是有效 JSON。");
    }

    const replies = body?.messages;
    if (
      !Array.isArray(replies) ||
      replies.length === 0 ||
      replies.at(-1)?.role !== "assistant" ||
      !replies.every(
        (message) =>
          (message.role === "assistant" || message.role === "system") &&
          typeof message.content === "string" &&
          message.content.trim()
      )
    ) {
      throw new Error("服务返回的消息格式无效。");
    }

    this.#messages.push(userMessage, ...replies);
    return replies;
  }
}
