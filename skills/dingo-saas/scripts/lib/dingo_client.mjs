import { readFile, rm, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const LIB_DIR = dirname(fileURLToPath(import.meta.url));
const DEFAULT_CONFIG_PATH = resolve(LIB_DIR, "..", "..", "config.json");

export const CONFIG_PATH = process.env.DINGO_SAAS_CONFIG_PATH || DEFAULT_CONFIG_PATH;

export function parseArgs(argv) {
  const parsed = { _: [] };
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (!token.startsWith("--")) {
      parsed._.push(token);
      continue;
    }

    const key = token.slice(2);
    const next = argv[index + 1];
    if (next === undefined || next.startsWith("--")) {
      parsed[key] = true;
      continue;
    }

    parsed[key] = next;
    index += 1;
  }
  return parsed;
}

export function requireOption(args, name) {
  const value = args[name];
  if (value === undefined || value === true || String(value).trim() === "") {
    throw new Error(`Missing required option --${name}`);
  }
  return String(value);
}

export function parseIntegerOption(args, name, fallback) {
  if (args[name] === undefined) return fallback;
  const value = Number.parseInt(String(args[name]), 10);
  if (!Number.isInteger(value) || value < 0) {
    throw new Error(`--${name} must be a non-negative integer`);
  }
  return value;
}

async function readStdin() {
  const chunks = [];
  for await (const chunk of process.stdin) chunks.push(chunk);
  return Buffer.concat(chunks).toString("utf8");
}

export async function readJsonBody(args) {
  const sources = [args.body !== undefined, args["body-file"] !== undefined, args.stdin === true];
  if (sources.filter(Boolean).length !== 1) {
    throw new Error("Provide exactly one of --body, --body-file, or --stdin");
  }

  let raw;
  if (args.body !== undefined) {
    raw = String(args.body);
  } else if (args["body-file"] !== undefined) {
    raw = await readFile(resolve(String(args["body-file"])), "utf8");
  } else {
    raw = await readStdin();
  }

  try {
    return JSON.parse(raw);
  } catch (error) {
    throw new Error(`Invalid JSON body: ${error.message}`);
  }
}

function normalizeBaseUrl(value) {
  let url;
  try {
    url = new URL(String(value).trim());
  } catch {
    throw new Error("--url must be a valid Dingo SaaS website URL");
  }
  if (url.protocol !== "http:" && url.protocol !== "https:") {
    throw new Error("--url must use http or https");
  }
  return url.origin;
}

export function maskKey(key) {
  return key.length <= 10 ? "***" : `${key.slice(0, 10)}...`;
}

export async function loadConnection({ allowMissing = false } = {}) {
  let raw;
  try {
    raw = await readFile(CONFIG_PATH, "utf8");
  } catch (error) {
    if (allowMissing && error.code === "ENOENT") return null;
    if (error.code === "ENOENT") {
      throw new Error("Dingo SaaS is not configured. Ask the user for the website URL and API key, then run configure.");
    }
    throw error;
  }

  let config;
  try {
    config = JSON.parse(raw);
  } catch {
    throw new Error("The saved Dingo SaaS config.json is invalid. Ask the user for the website URL and API key again.");
  }

  if (!config?.url || !config?.key) {
    throw new Error("The saved Dingo SaaS configuration is incomplete. Ask the user for the website URL and API key again.");
  }

  return { url: normalizeBaseUrl(config.url), key: String(config.key) };
}

export async function configureConnection(args) {
  const url = normalizeBaseUrl(requireOption(args, "url"));
  const key = requireOption(args, "key");
  await writeFile(CONFIG_PATH, `${JSON.stringify({ url, key }, null, 2)}\n`, {
    encoding: "utf8",
    mode: 0o600,
  });
  return { configured: true, url, key_prefix: maskKey(key) };
}

export async function clearConnection() {
  await rm(CONFIG_PATH, { force: true });
  return { configured: false };
}

function buildUrl(baseUrl, path, query = {}) {
  const url = new URL(`${baseUrl}${path}`);
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null && value !== "") {
      url.searchParams.set(key, String(value));
    }
  }
  return url;
}

function formatErrorDetail(responseBody, fallback) {
  const detail = responseBody?.detail ?? responseBody ?? fallback;
  return typeof detail === "string" ? detail : JSON.stringify(detail);
}

export async function callApi(method, path, { query, json, form } = {}) {
  const connection = await loadConnection();
  const headers = { Authorization: `Bearer ${connection.key}`, Accept: "application/json" };
  const request = { method, headers };
  if (json !== undefined) {
    headers["Content-Type"] = "application/json";
    request.body = JSON.stringify(json);
  } else if (form !== undefined) {
    request.body = form;
  }

  const response = await fetch(buildUrl(connection.url, path, query), request);
  const responseText = await response.text();
  let responseBody = null;
  if (responseText) {
    try {
      responseBody = JSON.parse(responseText);
    } catch {
      responseBody = responseText;
    }
  }

  if (!response.ok) {
    throw new Error(
      `${method} ${path} failed (${response.status}): ${formatErrorDetail(responseBody, response.statusText)}`,
    );
  }

  return responseBody ?? { success: true, status: response.status };
}

export async function downloadApiFile(path, outputPath) {
  const connection = await loadConnection();
  const response = await fetch(buildUrl(connection.url, path), {
    method: "GET",
    headers: {
      Authorization: `Bearer ${connection.key}`,
      Accept: "application/zip",
    },
  });

  if (!response.ok) {
    const responseText = await response.text();
    let responseBody = responseText;
    if (responseText) {
      try {
        responseBody = JSON.parse(responseText);
      } catch {
        // Keep the plain-text response body.
      }
    }
    throw new Error(
      `GET ${path} failed (${response.status}): ${formatErrorDetail(responseBody, response.statusText)}`,
    );
  }

  const resolvedPath = resolve(outputPath);
  const contents = Buffer.from(await response.arrayBuffer());
  try {
    await writeFile(resolvedPath, contents, { flag: "wx" });
  } catch (error) {
    if (error.code === "EEXIST") {
      throw new Error(`Download target already exists: ${resolvedPath}`);
    }
    throw error;
  }
  return {
    downloaded: true,
    path: resolvedPath,
    bytes: contents.length,
    content_type: response.headers.get("content-type"),
  };
}

export async function getConnectionStatus() {
  const connection = await loadConnection({ allowMissing: true });
  if (!connection) return { configured: false };
  const user = await callApi("GET", "/api/v1/auth/me");
  return {
    configured: true,
    url: connection.url,
    key_prefix: maskKey(connection.key),
    user,
  };
}

export function writeResult(result) {
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
}

export function writeError(error) {
  process.stderr.write(`${JSON.stringify({ error: error.message }, null, 2)}\n`);
  process.exitCode = 1;
}
