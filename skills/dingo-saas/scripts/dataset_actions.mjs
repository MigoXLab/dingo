#!/usr/bin/env node

import { openAsBlob } from "node:fs";
import { basename, resolve } from "node:path";

import {
  callApi,
  parseArgs,
  parseIntegerOption,
  readJsonBody,
  requireOption,
  writeError,
  writeResult,
} from "./lib/dingo_client.mjs";

const ACTIONS = {
  list_datasets: {
    method: "GET",
    path: "/api/v1/datasets/",
    options: "[--source SOURCE] [--skip N] [--limit N]",
  },
  get_dataset: {
    method: "GET",
    path: "/api/v1/datasets/{dataset_id}",
    options: "--dataset-id ID",
  },
  preview_dataset: {
    method: "GET",
    path: "/api/v1/datasets/{dataset_id}/preview",
    options: "--dataset-id ID",
  },
  initialize_demo_data: {
    method: "POST",
    path: "/api/v1/demo/initialize",
    options: "",
  },
  upload_dataset_file: {
    method: "POST",
    path: "/api/v1/datasets/upload",
    options: "--file PATH [--relative-path PATH]",
  },
  create_dataset: {
    method: "POST",
    path: "/api/v1/datasets/",
    options: "--body JSON | --body-file PATH | --stdin",
  },
  update_dataset: {
    method: "PUT",
    path: "/api/v1/datasets/{dataset_id}",
    options: "--dataset-id ID (--body JSON | --body-file PATH | --stdin)",
  },
  copy_dataset: {
    method: "POST",
    path: "/api/v1/datasets/{dataset_id}/copy",
    options: "--dataset-id ID",
  },
  delete_dataset: {
    method: "DELETE",
    path: "/api/v1/datasets/{dataset_id}",
    options: "--dataset-id ID [--hard-delete]",
  },
};

function showActions() {
  const rows = Object.entries(ACTIONS).map(([name, definition]) => ({
    action: name,
    method: definition.method,
    path: definition.path,
    options: definition.options,
  }));
  writeResult(rows);
}

async function execute(action, args) {
  switch (action) {
    case "list_datasets":
      return callApi("GET", ACTIONS[action].path, {
        query: {
          source: args.source,
          skip: parseIntegerOption(args, "skip", 0),
          limit: parseIntegerOption(args, "limit", 100),
        },
      });
    case "get_dataset":
    case "preview_dataset":
    case "copy_dataset": {
      const datasetId = encodeURIComponent(requireOption(args, "dataset-id"));
      return callApi(ACTIONS[action].method, ACTIONS[action].path.replace("{dataset_id}", datasetId));
    }
    case "initialize_demo_data":
      return callApi("POST", ACTIONS[action].path);
    case "upload_dataset_file": {
      const filePath = resolve(requireOption(args, "file"));
      const form = new FormData();
      form.append("file", await openAsBlob(filePath), basename(filePath));
      form.append("relative_path", String(args["relative-path"] || basename(filePath)));
      return callApi("POST", ACTIONS[action].path, { form });
    }
    case "create_dataset":
      return callApi("POST", ACTIONS[action].path, { json: await readJsonBody(args) });
    case "update_dataset": {
      const datasetId = encodeURIComponent(requireOption(args, "dataset-id"));
      return callApi("PUT", ACTIONS[action].path.replace("{dataset_id}", datasetId), {
        json: await readJsonBody(args),
      });
    }
    case "delete_dataset": {
      const datasetId = encodeURIComponent(requireOption(args, "dataset-id"));
      return callApi("DELETE", ACTIONS[action].path.replace("{dataset_id}", datasetId), {
        query: { hard_delete: args["hard-delete"] === true },
      });
    }
    default:
      throw new Error(`Unknown action: ${action}. Run with 'actions' to list supported actions.`);
  }
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const action = args._[0];
  if (!action || action === "actions" || action === "--help" || action === "help") {
    showActions();
    return;
  }

  const result = await execute(action, args);
  writeResult(result);
}

main().catch(writeError);
