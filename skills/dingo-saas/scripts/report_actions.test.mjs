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
const scriptPath = join(dirname(fileURLToPath(import.meta.url)), "report_actions.mjs");

async function withMockApi(run) {
  const requests = [];
  const directory = await mkdtemp(join(tmpdir(), "dingo-saas-report-test-"));
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

    if (request.url?.endsWith("/download")) {
      response.writeHead(200, { "Content-Type": "application/zip" });
      response.end(Buffer.from("zip-contents"));
      return;
    }
    if (request.url?.startsWith("/api/v1/outputs/?")) {
      response.writeHead(200, { "Content-Type": "application/json" });
      response.end(JSON.stringify({
        total: 2,
        items: [
          { id: "r1", name: "Alpha report", description: "first" },
          { id: "r2", name: "Beta", description: "second" },
        ],
      }));
      return;
    }
    if (request.url === "/api/v1/outputs/r1") {
      response.writeHead(200, { "Content-Type": "application/json" });
      response.end(JSON.stringify({ id: "r1", status: "failed", log: "trace output", message: "fallback" }));
      return;
    }

    response.writeHead(200, { "Content-Type": "application/json" });
    response.end(JSON.stringify({ ok: true }));
  });

  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const { port } = server.address();
  const url = `http://127.0.0.1:${port}`;
  await writeFile(configPath, JSON.stringify({ url, key: "sk-report-test" }));

  try {
    await run({
      requests,
      directory,
      url,
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

test("maps report page actions to backend APIs", async () => {
  await withMockApi(async ({ requests, directory, env, url }) => {
    const reports = await runAction(
      env,
      "list_reports",
      "--experiment-id",
      "experiment/1",
      "--status",
      "success",
      "--created-at",
      "2026-09-11",
      "--search",
      "alpha",
      "--skip",
      "2",
      "--limit",
      "5",
    );
    await runAction(env, "get_report_detail", "--report-id", "report/1");
    await runAction(env, "update_report", "--report-id", "r1", "--body", '{"name":"Renamed","description":"Updated"}');
    await runAction(env, "delete_report", "--report-id", "r1");
    await runAction(env, "list_report_results", "--report-id", "report/1", "--eval-status", "false", "--label", "bad", "--skip", "3", "--limit", "7");
    await runAction(env, "get_report_result", "--item-id", "item/1");
    const log = await runAction(env, "get_report_log", "--report-id", "r1");
    const share = await runAction(env, "get_report_share_url", "--report-id", "report/1");
    const outputPath = join(directory, "report.zip");
    const download = await runAction(env, "download_report", "--report-id", "r1", "--output", outputPath);

    assert.equal(reports.total, 1);
    assert.equal(reports.source_total, 2);
    assert.equal(reports.items[0].id, "r1");
    assert.deepEqual(log, { report_id: "r1", status: "failed", log: "trace output" });
    assert.deepEqual(share, { report_id: "report/1", url: `${url}/share/report%2F1` });
    assert.equal(download.bytes, 12);
    assert.equal(await readFile(outputPath, "utf8"), "zip-contents");
    assert.deepEqual(
      requests.map(({ method, url: requestUrl }) => ({ method, url: requestUrl })),
      [
        { method: "GET", url: "/api/v1/outputs/?experiment_id=experiment%2F1&status=success&created_at=2026-09-11&skip=2&limit=5" },
        { method: "GET", url: "/api/v1/outputs/report%2F1" },
        { method: "PUT", url: "/api/v1/outputs/r1" },
        { method: "DELETE", url: "/api/v1/outputs/r1" },
        { method: "GET", url: "/api/v1/output-items/output/report%2F1?skip=3&limit=7&eval_status=false&label=bad" },
        { method: "GET", url: "/api/v1/output-items/item%2F1" },
        { method: "GET", url: "/api/v1/outputs/r1" },
        { method: "GET", url: "/api/v1/outputs/r1/download" },
      ],
    );
    assert.ok(requests.every((request) => request.authorization === "Bearer sk-report-test"));
    assert.deepEqual(JSON.parse(requests[2].body), { name: "Renamed", description: "Updated" });
  });
});

test("validates report item filters before calling the API", async () => {
  await withMockApi(async ({ requests, env }) => {
    await assert.rejects(
      runAction(env, "list_report_results", "--report-id", "r1", "--eval-status", "maybe"),
      /--eval-status must be all, true, or false/,
    );
    assert.equal(requests.length, 0);
  });
});

test("loads the report results page as report summary plus result rows", async () => {
  await withMockApi(async ({ requests, env }) => {
    const page = await runAction(
      env,
      "get_report_results",
      "--report-id",
      "report/1",
      "--eval-status",
      "true",
      "--label",
      "quality",
      "--limit",
      "10",
    );

    assert.deepEqual(page, { report: { ok: true }, results: { ok: true } });
    assert.deepEqual(
      requests.map(({ method, url }) => ({ method, url })).sort((a, b) => a.url.localeCompare(b.url)),
      [
        { method: "GET", url: "/api/v1/output-items/output/report%2F1?skip=0&limit=10&eval_status=true&label=quality" },
        { method: "GET", url: "/api/v1/outputs/report%2F1" },
      ],
    );
  });
});

test("does not overwrite an existing report download", async () => {
  await withMockApi(async ({ requests, directory, env }) => {
    const outputPath = join(directory, "existing.zip");
    await writeFile(outputPath, "keep-me");
    await assert.rejects(
      runAction(env, "download_report", "--report-id", "r1", "--output", outputPath),
      /Download target already exists/,
    );
    assert.equal(await readFile(outputPath, "utf8"), "keep-me");
    assert.equal(requests.length, 1);
  });
});
