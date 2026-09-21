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
const scriptPath = join(dirname(fileURLToPath(import.meta.url)), "experiment_actions.mjs");

async function withMockApi(run) {
  const requests = [];
  const directory = await mkdtemp(join(tmpdir(), "dingo-saas-experiment-test-"));
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
    response.end(JSON.stringify({ ok: true }));
  });

  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const { port } = server.address();
  const url = `http://127.0.0.1:${port}`;
  await writeFile(configPath, JSON.stringify({ url, key: "sk-experiment-test" }));

  try {
    await run({
      requests,
      env: { ...process.env, DINGO_SAAS_CONFIG_PATH: configPath },
    });
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

test("maps experiment page actions to backend APIs", async () => {
  await withMockApi(async ({ requests, env }) => {
    await runAction(env, "list_experiments", "--dataset-id", "dataset/1", "--skip", "2", "--limit", "5");
    await runAction(env, "get_experiment", "--experiment-id", "experiment/1");
    await runAction(env, "create_experiment", "--body", '{"name":"New","dataset_id":"d1"}');
    await runAction(env, "update_experiment", "--experiment-id", "e1", "--body", '{"name":"Renamed"}');
    await runAction(env, "copy_experiment", "--experiment-id", "e1", "--name", "Copied");
    await runAction(env, "delete_experiment", "--experiment-id", "e1");
    await runAction(env, "start_experiment", "--experiment-id", "e1", "--report-name", "Report", "--report-description", "Description");
    await runAction(env, "stop_experiment", "--experiment-id", "e1");
    await runAction(env, "get_experiment_schedule", "--experiment-id", "e1");
    await runAction(env, "upsert_experiment_schedule", "--experiment-id", "e1", "--body", '{"start_date":"2026-09-11","end_date":"2026-09-30","weekdays":[1,3,5],"start_time":"09:30","timezone":"Asia/Shanghai","enabled":true}');
    await runAction(env, "toggle_experiment_schedule", "--experiment-id", "e1", "--enabled", "false");
    await runAction(env, "delete_experiment_schedule", "--experiment-id", "e1");
    await runAction(env, "get_experiment_dingo_input", "--experiment-id", "e1");

    assert.deepEqual(
      requests.map(({ method, url }) => ({ method, url })),
      [
        { method: "GET", url: "/api/v1/experiments/?dataset_id=dataset%2F1&skip=2&limit=5" },
        { method: "GET", url: "/api/v1/experiments/experiment%2F1" },
        { method: "POST", url: "/api/v1/experiments/" },
        { method: "PUT", url: "/api/v1/experiments/e1" },
        { method: "POST", url: "/api/v1/experiments/e1/copy" },
        { method: "DELETE", url: "/api/v1/experiments/e1" },
        { method: "POST", url: "/api/v1/experiments/e1/start" },
        { method: "POST", url: "/api/v1/experiments/e1/stop" },
        { method: "GET", url: "/api/v1/experiments/e1/schedule" },
        { method: "PUT", url: "/api/v1/experiments/e1/schedule" },
        { method: "POST", url: "/api/v1/experiments/e1/schedule/toggle" },
        { method: "DELETE", url: "/api/v1/experiments/e1/schedule" },
        { method: "GET", url: "/api/v1/experiments/e1/dingo-input" },
      ],
    );
    assert.ok(requests.every((request) => request.authorization === "Bearer sk-experiment-test"));
    assert.deepEqual(JSON.parse(requests[4].body), { name: "Copied" });
    assert.deepEqual(JSON.parse(requests[6].body), {
      report_name: "Report",
      report_description: "Description",
    });
    assert.deepEqual(JSON.parse(requests[10].body), { enabled: false });
  });
});

test("rejects invalid schedule toggle values before calling the API", async () => {
  await withMockApi(async ({ requests, env }) => {
    await assert.rejects(
      runAction(env, "toggle_experiment_schedule", "--experiment-id", "e1", "--enabled", "yes"),
      /--enabled must be true or false/,
    );
    assert.equal(requests.length, 0);
  });
});
