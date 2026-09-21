import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { createServer } from "node:http";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";
import test from "node:test";

const execFileAsync = promisify(execFile);
const scriptPath = join(dirname(fileURLToPath(import.meta.url)), "dataset_actions.mjs");
const connectionScriptPath = join(dirname(fileURLToPath(import.meta.url)), "connection_actions.mjs");

async function withMockApi(run) {
  const requests = [];
  const directory = await mkdtemp(join(tmpdir(), "dingo-saas-config-test-"));
  const configPath = join(directory, "config.json");
  const server = createServer(async (request, response) => {
    const chunks = [];
    for await (const chunk of request) chunks.push(chunk);
    requests.push({
      method: request.method,
      url: request.url,
      authorization: request.headers.authorization,
      contentType: request.headers["content-type"],
      body: Buffer.concat(chunks).toString("utf8"),
    });
    response.writeHead(200, { "Content-Type": "application/json" });
    response.end(JSON.stringify({ ok: true }));
  });

  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const { port } = server.address();
  const env = {
    ...process.env,
    DINGO_SAAS_CONFIG_PATH: configPath,
  };

  try {
    await run({ requests, env, configPath, url: `http://127.0.0.1:${port}` });
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

async function runConnectionAction(env, ...args) {
  const { stdout } = await execFileAsync(process.execPath, [connectionScriptPath, ...args], { env });
  return JSON.parse(stdout);
}

test("maps dataset actions to their backend APIs", async () => {
  await withMockApi(async ({ requests, env, configPath, url }) => {
    const configured = await runConnectionAction(
      env,
      "configure",
      "--url",
      url,
      "--key",
      "sk-test-token",
    );
    assert.deepEqual(configured, {
      configured: true,
      url,
      key_prefix: "sk-test-to...",
    });
    assert.equal(JSON.parse(await readFile(configPath, "utf8")).key, "sk-test-token");

    await runAction(env, "list_datasets", "--source", "sql", "--skip", "2", "--limit", "5");
    await runAction(env, "get_dataset", "--dataset-id", "data/id");
    await runAction(env, "preview_dataset", "--dataset-id", "abc");
    await runAction(env, "initialize_demo_data");
    await runAction(env, "create_dataset", "--body", '{"name":"New","source":"local","format":"jsonl"}');
    await runAction(env, "update_dataset", "--dataset-id", "abc", "--body", '{"name":"Renamed"}');
    await runAction(env, "copy_dataset", "--dataset-id", "abc");
    await runAction(env, "delete_dataset", "--dataset-id", "abc", "--hard-delete");

    assert.deepEqual(
      requests.map(({ method, url }) => ({ method, url })),
      [
        { method: "GET", url: "/api/v1/datasets/?source=sql&skip=2&limit=5" },
        { method: "GET", url: "/api/v1/datasets/data%2Fid" },
        { method: "GET", url: "/api/v1/datasets/abc/preview" },
        { method: "POST", url: "/api/v1/demo/initialize" },
        { method: "POST", url: "/api/v1/datasets/" },
        { method: "PUT", url: "/api/v1/datasets/abc" },
        { method: "POST", url: "/api/v1/datasets/abc/copy" },
        { method: "DELETE", url: "/api/v1/datasets/abc?hard_delete=true" },
      ],
    );
    assert.ok(requests.every((request) => request.authorization === "Bearer sk-test-token"));
    assert.equal(JSON.parse(requests[4].body).name, "New");
    assert.equal(JSON.parse(requests[5].body).name, "Renamed");
  });
});

test("uploads a local file as multipart form data", async () => {
  const directory = await mkdtemp(join(tmpdir(), "dingo-saas-test-"));
  const filePath = join(directory, "sample.jsonl");
  await writeFile(filePath, '{"text":"hello"}\n');

  try {
    await withMockApi(async ({ requests, env, url }) => {
      await runConnectionAction(env, "configure", "--url", url, "--key", "sk-test-token");
      await runAction(
        env,
        "upload_dataset_file",
        "--file",
        filePath,
        "--relative-path",
        "folder/sample.jsonl",
      );

      assert.equal(requests[0].method, "POST");
      assert.equal(requests[0].url, "/api/v1/datasets/upload");
      assert.match(requests[0].contentType, /^multipart\/form-data; boundary=/);
      assert.match(requests[0].body, /sample\.jsonl/);
      assert.match(requests[0].body, /folder\/sample\.jsonl/);
    });
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});

test("reports, verifies, and clears the saved connection", async () => {
  await withMockApi(async ({ requests, env, url }) => {
    assert.deepEqual(await runConnectionAction(env, "connection_status"), { configured: false });

    await runConnectionAction(env, "configure", "--url", `${url}/ignored/path`, "--key", "sk-secret-key");
    const status = await runConnectionAction(env, "connection_status");
    assert.deepEqual(status, {
      configured: true,
      url,
      key_prefix: "sk-secret-...",
      user: { ok: true },
    });
    assert.equal(requests[0].url, "/api/v1/auth/me");
    assert.equal(requests[0].authorization, "Bearer sk-secret-key");

    assert.deepEqual(await runConnectionAction(env, "clear_config"), { configured: false });
    assert.deepEqual(await runConnectionAction(env, "connection_status"), { configured: false });
  });
});
