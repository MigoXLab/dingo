import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { createServer } from "node:http";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";
import test from "node:test";

const execFileAsync = promisify(execFile);
const scriptPath = join(dirname(fileURLToPath(import.meta.url)), "metric_actions.mjs");

async function withMockApi(run) {
  const requests = [];
  const directory = await mkdtemp(join(tmpdir(), "dingo-saas-metric-test-"));
  const configPath = join(directory, "config.json");
  const server = createServer(async (request, response) => {
    const chunks = [];
    for await (const chunk of request) chunks.push(chunk);
    requests.push({
      method: request.method,
      url: request.url,
      authorization: request.headers.authorization,
      body: Buffer.concat(chunks).toString("utf8"),
    });

    response.writeHead(200, { "Content-Type": "application/json" });
    if (request.url === "/api/v1/metrics/list") {
      response.end(JSON.stringify({
        rule: [{ name: "RuleLength", description: "Checks length" }],
        llm: [{ name: "LLMQuality", description: "Quality score" }],
      }));
      return;
    }
    if (
      request.method === "GET" &&
      (request.url === "/api/v1/custom-llm-metrics/m1" ||
        request.url === "/api/v1/custom-llm-metrics/metric%2F1")
    ) {
      response.end(JSON.stringify({
        id: "m1",
        metric: "quality",
        description: "Quality check",
        criteria: ["good"],
        input_fields: ["content"],
        llm_config: {
          model: "gpt-test",
          key: "sk-****1234",
          api_url: "https://example.test/v1",
        },
      }));
      return;
    }
    response.end(JSON.stringify({ ok: true }));
  });

  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const { port } = server.address();
  await writeFile(configPath, JSON.stringify({
    url: `http://127.0.0.1:${port}`,
    key: "sk-metric-test",
  }));

  try {
    await run({ requests, env: { ...process.env, DINGO_SAAS_CONFIG_PATH: configPath } });
  } finally {
    await new Promise((resolve, reject) =>
      server.close((error) => (error ? reject(error) : resolve())),
    );
    await rm(directory, { recursive: true, force: true });
  }
}

async function runAction(env, ...args) {
  const { stdout } = await execFileAsync(process.execPath, [scriptPath, ...args], { env });
  return JSON.parse(stdout);
}

test("maps metric page actions to backend APIs", async () => {
  await withMockApi(async ({ requests, env }) => {
    const catalog = await runAction(env, "list_metrics", "--search", "quality");
    await runAction(env, "list_metric_groups", "--name", "Core", "--skip", "1", "--limit", "5");
    await runAction(env, "create_metric_group", "--body", '{"name":"Core","description":"Checks"}');
    await runAction(env, "update_metric_group", "--group-id", "group/1", "--body", '{"name":"Core v2"}');
    await runAction(env, "delete_metric_group", "--group-id", "g1");
    await runAction(env, "add_metric_to_group", "--body", '{"group_id":"g1","name":"RuleLength","config":null}');
    await runAction(env, "add_custom_metric_to_group", "--group-id", "g1", "--metric-id", "m1");
    await runAction(env, "update_group_metric", "--item-id", "item/1", "--body", '{"config":{"min":1}}');
    await runAction(env, "remove_metric_from_group", "--item-id", "i1");
    await runAction(env, "list_custom_metrics", "--metric", "quality", "--skip", "2", "--limit", "4");
    await runAction(env, "get_custom_metric", "--metric-id", "metric/1");
    await runAction(env, "create_custom_metric", "--body", '{"metric":"quality","criteria":["good"],"input_fields":["content"]}');
    await runAction(env, "update_custom_metric", "--metric-id", "m1", "--body", '{"description":"Updated"}');
    await runAction(env, "delete_custom_metric", "--metric-id", "m1");
    await runAction(env, "draft_custom_metric", "--body", '{"messages":[{"role":"user","content":"Draft a metric"}],"current_metric":{}}');
    await runAction(env, "start_custom_metric_quick_try", "--metric-id", "m1", "--body", '{"content":"hello"}');
    await runAction(env, "get_metric_quick_try", "--job-id", "job/1");

    assert.equal(catalog.total, 1);
    assert.equal(catalog.rule.length, 0);
    assert.equal(catalog.llm[0].name, "LLMQuality");
    assert.deepEqual(
      requests.map(({ method, url }) => ({ method, url })),
      [
        { method: "GET", url: "/api/v1/metrics/list" },
        { method: "GET", url: "/api/v1/metric-groups/?name=Core&skip=1&limit=5" },
        { method: "POST", url: "/api/v1/metric-groups/" },
        { method: "PUT", url: "/api/v1/metric-groups/group%2F1" },
        { method: "DELETE", url: "/api/v1/metric-groups/g1" },
        { method: "POST", url: "/api/v1/metric-group-items/" },
        { method: "GET", url: "/api/v1/custom-llm-metrics/m1" },
        { method: "POST", url: "/api/v1/metric-group-items/" },
        { method: "PUT", url: "/api/v1/metric-group-items/item%2F1" },
        { method: "DELETE", url: "/api/v1/metric-group-items/i1" },
        { method: "GET", url: "/api/v1/custom-llm-metrics/?metric=quality&skip=2&limit=4" },
        { method: "GET", url: "/api/v1/custom-llm-metrics/metric%2F1" },
        { method: "POST", url: "/api/v1/custom-llm-metrics/" },
        { method: "PUT", url: "/api/v1/custom-llm-metrics/m1" },
        { method: "DELETE", url: "/api/v1/custom-llm-metrics/m1" },
        { method: "POST", url: "/api/v1/custom-llm-metrics/assistant" },
        { method: "GET", url: "/api/v1/custom-llm-metrics/m1" },
        { method: "POST", url: "/api/v1/quick-eval/" },
        { method: "GET", url: "/api/v1/quick-eval/job%2F1" },
      ],
    );
    assert.ok(requests.every((request) => request.authorization === "Bearer sk-metric-test"));
    assert.deepEqual(JSON.parse(requests[5].body), {
      group_id: "g1",
      name: "RuleLength",
      config: null,
    });
    assert.equal(JSON.parse(requests[7].body).name, "LLMCustomMetric");
    assert.equal(JSON.parse(requests[7].body).config.key, "CUSTOM_LLM_METRIC_KEY");
    assert.deepEqual(JSON.parse(requests[17].body).data, { content: "hello" });
    assert.equal(
      JSON.parse(requests[17].body).evaluators[0].config.key,
      "CUSTOM_LLM_METRIC_KEY",
    );
  });
});

test("loads a metric group with its metrics", async () => {
  await withMockApi(async ({ requests, env }) => {
    const detail = await runAction(
      env,
      "get_metric_group_detail",
      "--group-id",
      "group/1",
      "--limit",
      "20",
    );
    assert.deepEqual(detail, { group: { ok: true }, metrics: { ok: true } });
    assert.deepEqual(
      requests.map(({ method, url }) => ({ method, url })).sort((a, b) => a.url.localeCompare(b.url)),
      [
        { method: "GET", url: "/api/v1/metric-group-items/?group_id=group%2F1&skip=0&limit=20" },
        { method: "GET", url: "/api/v1/metric-groups/group%2F1" },
      ],
    );
  });
});

test("rejects invalid metric types before calling the API", async () => {
  await withMockApi(async ({ requests, env }) => {
    await assert.rejects(runAction(env, "list_metrics", "--type", "custom"), /--type must be/);
    assert.equal(requests.length, 0);
  });
});
