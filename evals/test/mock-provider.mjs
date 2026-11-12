// A scripted OpenAI-compatible model server for testing the runner without API keys.
// A prompt holding `MOCK-BASH: <command>` gets one bash tool call, then "done";
// `MOCK-TOOLS: [{"name": ..., "arguments": {...}}, ...]` gets those tool calls one per turn, then "done";
// `MOCK-REPLY: <text>` gets that text back.
// It also stands in for a gateway: each completion gets a generation ID, `GET /v1/generation?id=` reports
// MOCK_BILLED dollars for it (answering "not found" once first, as a gateway does before usage is recorded),
// and every request body is kept in `requests` so a test can check the privacy and routing fields.
import { createServer } from "node:http";

const USAGE = { prompt_tokens: 100, completion_tokens: 10, total_tokens: 110 };
export const MOCK_BILLED = 0.0002;
export const MOCK_HOST = "mock-host";

function reply(body) {
  const messages = body.messages ?? [];
  const prompt = messages.filter((m) => m.role === "user").map((m) => (typeof m.content === "string" ? m.content : m.content.map((c) => c.text ?? "").join(""))).join("\n");
  const bash = prompt.match(/MOCK-BASH: (.+)/);
  const script = bash ? [{ name: "bash", arguments: { command: bash[1] } }] : JSON.parse(prompt.match(/MOCK-TOOLS: (.+)/)?.[1] ?? "[]");
  const done = messages.filter((m) => m.role === "tool").length;
  if (process.env.MOCK_LOG_TOOLS && done) console.error(`mock tool result: ${JSON.stringify(messages.at(-1).content).slice(0, 400)}`);
  const next = script[done];
  if (next && body.tools?.length) {
    const call = { index: 0, id: `call_${done + 1}`, type: "function", function: { name: next.name, arguments: JSON.stringify(next.arguments) } };
    return { tool_calls: [call], finish: "tool_calls" };
  }
  return { content: prompt.match(/MOCK-REPLY: (.+)/)?.[1] ?? "done", finish: "stop" };
}

export function startMock() {
  const requests = [];
  const looked = new Set();
  let n = 0;
  const server = createServer((req, res) => {
    const url = new URL(req.url, "http://mock");
    if (req.method === "GET" && url.pathname.endsWith("/generation")) {
      const id = url.searchParams.get("id");
      const known = /^gen_mock-\d+$/.test(id ?? "") && Number(id.split("-")[1]) <= n;
      if (!known || !looked.has(id)) {
        looked.add(id);
        res.writeHead(404, { "content-type": "application/json" });
        res.end(JSON.stringify({ error: { message: "Usage event not found" } }));
        return;
      }
      res.writeHead(200, { "content-type": "application/json" });
      res.end(JSON.stringify({ data: { id, total_cost: MOCK_BILLED, provider_name: MOCK_HOST } }));
      return;
    }
    let raw = "";
    req.on("data", (c) => (raw += c));
    req.on("end", () => {
      const body = JSON.parse(raw || "{}");
      requests.push(body);
      if (process.env.MOCK_LOG_TOOLS) console.error(`mock tools: ${(body.tools ?? []).map((t) => t.function?.name).join(",")}`);
      const r = reply(body);
      const base = { id: `gen_mock-${++n}`, object: "chat.completion", created: 0, model: body.model };
      if (!body.stream) {
        res.writeHead(200, { "content-type": "application/json" });
        res.end(JSON.stringify({ ...base, choices: [{ index: 0, message: { role: "assistant", content: r.content ?? null, tool_calls: r.tool_calls }, finish_reason: r.finish }], usage: { ...USAGE, cost: 0.0001 } }));
        return;
      }
      res.writeHead(200, { "content-type": "text/event-stream" });
      const send = (o) => res.write(`data: ${JSON.stringify({ ...base, object: "chat.completion.chunk", ...o })}\n\n`);
      send({ choices: [{ index: 0, delta: { role: "assistant", ...(r.content ? { content: r.content } : { tool_calls: r.tool_calls }) }, finish_reason: null }] });
      send({ choices: [{ index: 0, delta: {}, finish_reason: r.finish }] });
      send({ choices: [], usage: USAGE });
      res.end("data: [DONE]\n\n");
    });
  });
  return new Promise((resolve) => server.listen(0, "127.0.0.1", () => resolve({ server, requests, url: `http://127.0.0.1:${server.address().port}/v1` })));
}
