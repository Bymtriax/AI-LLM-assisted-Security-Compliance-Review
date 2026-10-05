import { ChatClient } from "./chat_client.mjs";

const client = new ChatClient();
const conversation = document.querySelector("#conversation");
const emptyState = document.querySelector("#empty-state");
const form = document.querySelector("#chat-form");
const input = document.querySelector("#message-input");
const button = document.querySelector("#send-button");
const errorText = document.querySelector("#error");

const labels = { user: "你", assistant: "AI", system: "检索结果" };
let sending = false;

function showMessage(message) {
  const article = document.createElement("article");
  article.className = `message message--${message.role}`;

  const label = document.createElement("p");
  label.className = "message__label";
  label.textContent = labels[message.role];

  const content = document.createElement("p");
  content.className = "message__content";
  content.textContent = message.content;

  article.append(label, content);
  conversation.append(article);
  emptyState.hidden = true;
  conversation.scrollTop = conversation.scrollHeight;
  return article;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (sending) return;

  const text = input.value.trim();
  if (!text) return;

  sending = true;
  errorText.textContent = "";
  const pendingMessage = showMessage({ role: "user", content: text });
  input.value = "";
  input.disabled = true;
  button.disabled = true;
  button.textContent = "发送中…";

  try {
    const replies = await client.send(text);
    for (const reply of replies) showMessage(reply);
  } catch (error) {
    pendingMessage.remove();
    emptyState.hidden = conversation.querySelector(".message") !== null;
    input.value = text;
    errorText.textContent = error.message || "发送失败，请重试。";
  } finally {
    sending = false;
    input.disabled = false;
    button.disabled = false;
    button.textContent = "发送";
    input.focus();
  }
});

input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    form.requestSubmit();
  }
});
