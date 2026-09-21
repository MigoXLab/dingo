#!/usr/bin/env node

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
  list_experiments: {
    method: "GET",
    path: "/api/v1/experiments/",
    options: "[--dataset-id ID] [--skip N] [--limit N]",
  },
  get_experiment: {
    method: "GET",
    path: "/api/v1/experiments/{experiment_id}",
    options: "--experiment-id ID",
  },
  create_experiment: {
    method: "POST",
    path: "/api/v1/experiments/",
    options: "--body JSON | --body-file PATH | --stdin",
  },
  update_experiment: {
    method: "PUT",
    path: "/api/v1/experiments/{experiment_id}",
    options: "--experiment-id ID (--body JSON | --body-file PATH | --stdin)",
  },
  copy_experiment: {
    method: "POST",
    path: "/api/v1/experiments/{experiment_id}/copy",
    options: "--experiment-id ID --name NAME",
  },
  delete_experiment: {
    method: "DELETE",
    path: "/api/v1/experiments/{experiment_id}",
    options: "--experiment-id ID",
  },
  start_experiment: {
    method: "POST",
    path: "/api/v1/experiments/{experiment_id}/start",
    options: "--experiment-id ID --report-name NAME [--report-description TEXT]",
  },
  stop_experiment: {
    method: "POST",
    path: "/api/v1/experiments/{experiment_id}/stop",
    options: "--experiment-id ID",
  },
  get_experiment_schedule: {
    method: "GET",
    path: "/api/v1/experiments/{experiment_id}/schedule",
    options: "--experiment-id ID",
  },
  upsert_experiment_schedule: {
    method: "PUT",
    path: "/api/v1/experiments/{experiment_id}/schedule",
    options: "--experiment-id ID (--body JSON | --body-file PATH | --stdin)",
  },
  toggle_experiment_schedule: {
    method: "POST",
    path: "/api/v1/experiments/{experiment_id}/schedule/toggle",
    options: "--experiment-id ID --enabled true|false",
  },
  delete_experiment_schedule: {
    method: "DELETE",
    path: "/api/v1/experiments/{experiment_id}/schedule",
    options: "--experiment-id ID",
  },
  get_experiment_dingo_input: {
    method: "GET",
    path: "/api/v1/experiments/{experiment_id}/dingo-input",
    options: "--experiment-id ID",
  },
};

function showActions() {
  writeResult(
    Object.entries(ACTIONS).map(([action, definition]) => ({ action, ...definition })),
  );
}

function experimentPath(action, args) {
  const experimentId = encodeURIComponent(requireOption(args, "experiment-id"));
  return ACTIONS[action].path.replace("{experiment_id}", experimentId);
}

function parseBooleanOption(args, name) {
  const value = requireOption(args, name).toLowerCase();
  if (value !== "true" && value !== "false") {
    throw new Error(`--${name} must be true or false`);
  }
  return value === "true";
}

async function execute(action, args) {
  switch (action) {
    case "list_experiments":
      return callApi("GET", ACTIONS[action].path, {
        query: {
          dataset_id: args["dataset-id"],
          skip: parseIntegerOption(args, "skip", 0),
          limit: parseIntegerOption(args, "limit", 100),
        },
      });
    case "get_experiment":
    case "stop_experiment":
    case "get_experiment_schedule":
    case "delete_experiment_schedule":
    case "get_experiment_dingo_input":
      return callApi(ACTIONS[action].method, experimentPath(action, args));
    case "create_experiment":
      return callApi("POST", ACTIONS[action].path, { json: await readJsonBody(args) });
    case "update_experiment":
    case "upsert_experiment_schedule":
      return callApi(ACTIONS[action].method, experimentPath(action, args), {
        json: await readJsonBody(args),
      });
    case "copy_experiment":
      return callApi("POST", experimentPath(action, args), {
        json: { name: requireOption(args, "name") },
      });
    case "delete_experiment":
      return callApi("DELETE", experimentPath(action, args));
    case "start_experiment":
      return callApi("POST", experimentPath(action, args), {
        json: {
          report_name: requireOption(args, "report-name"),
          report_description: String(args["report-description"] || ""),
        },
      });
    case "toggle_experiment_schedule":
      return callApi("POST", experimentPath(action, args), {
        json: { enabled: parseBooleanOption(args, "enabled") },
      });
    default:
      throw new Error(`Unknown action: ${action}. Run with 'actions' to list supported actions.`);
  }
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const action = args._[0];
  if (!action || action === "actions" || action === "help") {
    showActions();
    return;
  }

  writeResult(await execute(action, args));
}

main().catch(writeError);
