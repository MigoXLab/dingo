#!/usr/bin/env node

import { resolve } from "node:path";

import {
  callApi,
  downloadApiFile,
  loadConnection,
  parseArgs,
  parseIntegerOption,
  readJsonBody,
  requireOption,
  writeError,
  writeResult,
} from "./lib/dingo_client.mjs";

const ACTIONS = {
  list_reports: {
    page: "report_list",
    method: "GET",
    path: "/api/v1/outputs/",
    options:
      "[--experiment-id ID] [--status STATUS] [--created-at YYYY-MM-DD] [--search TEXT] [--skip N] [--limit N]",
  },
  get_report_detail: {
    page: "report_detail",
    method: "GET",
    path: "/api/v1/outputs/{report_id}",
    options: "--report-id ID",
  },
  update_report: {
    page: "report_detail",
    method: "PUT",
    path: "/api/v1/outputs/{report_id}",
    options: "--report-id ID (--body JSON | --body-file PATH | --stdin)",
  },
  delete_report: {
    page: "report_list_or_detail",
    method: "DELETE",
    path: "/api/v1/outputs/{report_id}",
    options: "--report-id ID",
  },
  get_report_results: {
    page: "report_results",
    method: "COMPOSITE",
    path: "/api/v1/outputs/{report_id} + /api/v1/output-items/output/{report_id}",
    options: "--report-id ID [--eval-status all|true|false] [--label TEXT] [--skip N] [--limit N]",
  },
  list_report_results: {
    page: "report_results",
    method: "GET",
    path: "/api/v1/output-items/output/{report_id}",
    options: "--report-id ID [--eval-status all|true|false] [--label TEXT] [--skip N] [--limit N]",
  },
  get_report_result: {
    page: "report_results",
    method: "GET",
    path: "/api/v1/output-items/{item_id}",
    options: "--item-id ID",
  },
  get_report_log: {
    page: "report_list",
    method: "GET",
    path: "/api/v1/outputs/{report_id}",
    options: "--report-id ID",
  },
  get_report_share_url: {
    page: "report_list_or_results",
    method: "LOCAL",
    path: "/share/{report_id}",
    options: "--report-id ID",
  },
  download_report: {
    page: "report_list_or_detail_or_results",
    method: "GET",
    path: "/api/v1/outputs/{report_id}/download",
    options: "--report-id ID --output PATH",
  },
};

function showActions() {
  writeResult(
    Object.entries(ACTIONS).map(([action, definition]) => ({ action, ...definition })),
  );
}

function reportPath(action, args) {
  const reportId = encodeURIComponent(requireOption(args, "report-id"));
  return ACTIONS[action].path.replace("{report_id}", reportId);
}

function parseEvalStatus(args) {
  const value = String(args["eval-status"] || "all").toLowerCase();
  if (!["all", "true", "false"].includes(value)) {
    throw new Error("--eval-status must be all, true, or false");
  }
  return value;
}

function filterReports(result, search) {
  const keyword = String(search || "").trim().toLowerCase();
  if (!keyword || !Array.isArray(result?.items)) return result;
  const items = result.items.filter((report) =>
    [report?.id, report?.name, report?.description].some((value) =>
      String(value || "").toLowerCase().includes(keyword),
    ),
  );
  return { ...result, source_total: result.total, total: items.length, items };
}

async function execute(action, args) {
  switch (action) {
    case "list_reports": {
      const result = await callApi("GET", ACTIONS[action].path, {
        query: {
          experiment_id: args["experiment-id"],
          status: args.status,
          created_at: args["created-at"],
          skip: parseIntegerOption(args, "skip", 0),
          limit: parseIntegerOption(args, "limit", 100),
        },
      });
      return filterReports(result, args.search);
    }
    case "get_report_detail":
    case "delete_report":
      return callApi(ACTIONS[action].method, reportPath(action, args));
    case "update_report":
      return callApi("PUT", reportPath(action, args), { json: await readJsonBody(args) });
    case "get_report_results": {
      const reportId = encodeURIComponent(requireOption(args, "report-id"));
      const itemQuery = {
        skip: parseIntegerOption(args, "skip", 0),
        limit: parseIntegerOption(args, "limit", 100),
        eval_status: parseEvalStatus(args),
        label: args.label,
      };
      const [report, results] = await Promise.all([
        callApi("GET", `/api/v1/outputs/${reportId}`),
        callApi("GET", `/api/v1/output-items/output/${reportId}`, { query: itemQuery }),
      ]);
      return { report, results };
    }
    case "list_report_results":
      return callApi("GET", reportPath(action, args), {
        query: {
          skip: parseIntegerOption(args, "skip", 0),
          limit: parseIntegerOption(args, "limit", 100),
          eval_status: parseEvalStatus(args),
          label: args.label,
        },
      });
    case "get_report_result": {
      const itemId = encodeURIComponent(requireOption(args, "item-id"));
      return callApi("GET", ACTIONS[action].path.replace("{item_id}", itemId));
    }
    case "get_report_log": {
      const report = await callApi("GET", reportPath(action, args));
      return {
        report_id: report.id,
        status: report.status,
        log: report.log || report.message || null,
      };
    }
    case "get_report_share_url": {
      const connection = await loadConnection();
      return { report_id: requireOption(args, "report-id"), url: `${connection.url}${reportPath(action, args)}` };
    }
    case "download_report":
      return downloadApiFile(
        reportPath(action, args),
        resolve(requireOption(args, "output")),
      );
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
