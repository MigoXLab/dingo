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
  list_metrics: {
    tab: "metric_list",
    method: "GET",
    path: "/api/v1/metrics/list",
    options: "[--type all|rule|llm] [--search TEXT]",
  },
  list_metric_groups: {
    tab: "metric_groups",
    method: "GET",
    path: "/api/v1/metric-groups/",
    options: "[--name TEXT] [--skip N] [--limit N]",
  },
  get_metric_group_detail: {
    tab: "metric_groups",
    method: "COMPOSITE",
    path: "/api/v1/metric-groups/{group_id} + /api/v1/metric-group-items/",
    options: "--group-id ID [--skip N] [--limit N]",
  },
  create_metric_group: {
    tab: "metric_groups",
    method: "POST",
    path: "/api/v1/metric-groups/",
    options: "--body JSON | --body-file PATH | --stdin",
  },
  update_metric_group: {
    tab: "metric_groups",
    method: "PUT",
    path: "/api/v1/metric-groups/{group_id}",
    options: "--group-id ID (--body JSON | --body-file PATH | --stdin)",
  },
  delete_metric_group: {
    tab: "metric_groups",
    method: "DELETE",
    path: "/api/v1/metric-groups/{group_id}",
    options: "--group-id ID",
  },
  add_metric_to_group: {
    tab: "metric_groups",
    method: "POST",
    path: "/api/v1/metric-group-items/",
    options: "--body JSON | --body-file PATH | --stdin",
  },
  add_custom_metric_to_group: {
    tab: "metric_groups",
    method: "COMPOSITE",
    path: "/api/v1/custom-llm-metrics/{metric_id} + /api/v1/metric-group-items/",
    options: "--group-id ID --metric-id ID",
  },
  update_group_metric: {
    tab: "metric_groups",
    method: "PUT",
    path: "/api/v1/metric-group-items/{item_id}",
    options: "--item-id ID (--body JSON | --body-file PATH | --stdin)",
  },
  remove_metric_from_group: {
    tab: "metric_groups",
    method: "DELETE",
    path: "/api/v1/metric-group-items/{item_id}",
    options: "--item-id ID",
  },
  list_custom_metrics: {
    tab: "custom_metrics",
    method: "GET",
    path: "/api/v1/custom-llm-metrics/",
    options: "[--metric TEXT] [--skip N] [--limit N]",
  },
  get_custom_metric: {
    tab: "custom_metrics",
    method: "GET",
    path: "/api/v1/custom-llm-metrics/{metric_id}",
    options: "--metric-id ID",
  },
  create_custom_metric: {
    tab: "custom_metrics",
    method: "POST",
    path: "/api/v1/custom-llm-metrics/",
    options: "--body JSON | --body-file PATH | --stdin",
  },
  update_custom_metric: {
    tab: "custom_metrics",
    method: "PUT",
    path: "/api/v1/custom-llm-metrics/{metric_id}",
    options: "--metric-id ID (--body JSON | --body-file PATH | --stdin)",
  },
  delete_custom_metric: {
    tab: "custom_metrics",
    method: "DELETE",
    path: "/api/v1/custom-llm-metrics/{metric_id}",
    options: "--metric-id ID",
  },
  draft_custom_metric: {
    tab: "custom_metrics",
    method: "POST",
    path: "/api/v1/custom-llm-metrics/assistant",
    options: "--body JSON | --body-file PATH | --stdin",
  },
  start_custom_metric_quick_try: {
    tab: "custom_metrics",
    method: "COMPOSITE",
    path: "/api/v1/custom-llm-metrics/{metric_id} + /api/v1/quick-eval/",
    options: "--metric-id ID (--body JSON | --body-file PATH | --stdin)",
  },
  get_metric_quick_try: {
    tab: "custom_metrics",
    method: "GET",
    path: "/api/v1/quick-eval/{job_id}",
    options: "--job-id ID",
  },
};

function showActions() {
  writeResult(
    Object.entries(ACTIONS).map(([action, definition]) => ({ action, ...definition })),
  );
}

function idPath(action, args, placeholder, option) {
  const id = encodeURIComponent(requireOption(args, option));
  return ACTIONS[action].path.replace(`{${placeholder}}`, id);
}

function parseMetricType(args) {
  const value = String(args.type || "all").toLowerCase();
  if (!["all", "rule", "llm"].includes(value)) {
    throw new Error("--type must be all, rule, or llm");
  }
  return value;
}

function matchesMetric(metric, keyword) {
  return [metric?.name, metric?.display_name, metric?.description].some((value) =>
    String(value || "").toLowerCase().includes(keyword),
  );
}

function filterMetricCatalog(result, metricType, search) {
  const keyword = String(search || "").trim().toLowerCase();
  if (!keyword) return result;

  if (metricType === "all") {
    const rule = (result?.rule || []).filter((metric) => matchesMetric(metric, keyword));
    const llm = (result?.llm || []).filter((metric) => matchesMetric(metric, keyword));
    return { ...result, rule, llm, total: rule.length + llm.length };
  }

  const metrics = (result?.metrics || []).filter((metric) => matchesMetric(metric, keyword));
  return { ...result, metrics, total: metrics.length };
}

function groupPath(action, args) {
  return idPath(action, args, "group_id", "group-id");
}

function groupItemPath(action, args) {
  return idPath(action, args, "item_id", "item-id");
}

function customMetricPath(action, args) {
  return idPath(action, args, "metric_id", "metric-id");
}

function customMetricEvaluator(metric) {
  const llmConfig = metric.llm_config || {};
  const rawKey = String(llmConfig.key || "").trim();
  const key = !rawKey
    ? "SYSTEM_LLM_KEY"
    : rawKey === "SYSTEM_LLM_KEY"
      ? rawKey
      : metric.id && rawKey.includes("*")
        ? "CUSTOM_LLM_METRIC_KEY"
        : rawKey;

  return {
    name: "LLMCustomMetric",
    config: {
      model: String(llmConfig.model || "").trim() || "SYSTEM_LLM_MODEL",
      key,
      api_url: String(llmConfig.api_url || "").trim() || "SYSTEM_LLM_API_URL",
      custom_metric: {
        id: metric.id,
        metric: metric.metric,
        description: metric.description,
        criteria: metric.criteria,
        input_fields: metric.input_fields,
      },
    },
  };
}

async function execute(action, args) {
  switch (action) {
    case "list_metrics": {
      const metricType = parseMetricType(args);
      const result = await callApi("GET", ACTIONS[action].path, {
        query: { metric_type: metricType === "all" ? undefined : metricType },
      });
      return filterMetricCatalog(result, metricType, args.search);
    }
    case "list_metric_groups":
      return callApi("GET", ACTIONS[action].path, {
        query: {
          name: args.name,
          skip: parseIntegerOption(args, "skip", 0),
          limit: parseIntegerOption(args, "limit", 100),
        },
      });
    case "get_metric_group_detail": {
      const groupId = encodeURIComponent(requireOption(args, "group-id"));
      const [group, metrics] = await Promise.all([
        callApi("GET", `/api/v1/metric-groups/${groupId}`),
        callApi("GET", "/api/v1/metric-group-items/", {
          query: {
            group_id: requireOption(args, "group-id"),
            skip: parseIntegerOption(args, "skip", 0),
            limit: parseIntegerOption(args, "limit", 100),
          },
        }),
      ]);
      return { group, metrics };
    }
    case "create_metric_group":
    case "create_custom_metric":
    case "draft_custom_metric":
    case "add_metric_to_group":
      return callApi("POST", ACTIONS[action].path, { json: await readJsonBody(args) });
    case "add_custom_metric_to_group": {
      const metric = await callApi(
        "GET",
        `/api/v1/custom-llm-metrics/${encodeURIComponent(requireOption(args, "metric-id"))}`,
      );
      const evaluator = customMetricEvaluator(metric);
      return callApi("POST", "/api/v1/metric-group-items/", {
        json: {
          group_id: requireOption(args, "group-id"),
          name: evaluator.name,
          config: evaluator.config,
        },
      });
    }
    case "update_metric_group":
      return callApi("PUT", groupPath(action, args), { json: await readJsonBody(args) });
    case "delete_metric_group":
      return callApi("DELETE", groupPath(action, args));
    case "update_group_metric":
      return callApi("PUT", groupItemPath(action, args), { json: await readJsonBody(args) });
    case "remove_metric_from_group":
      return callApi("DELETE", groupItemPath(action, args));
    case "list_custom_metrics":
      return callApi("GET", ACTIONS[action].path, {
        query: {
          metric: args.metric,
          skip: parseIntegerOption(args, "skip", 0),
          limit: parseIntegerOption(args, "limit", 100),
        },
      });
    case "get_custom_metric":
    case "delete_custom_metric":
      return callApi(ACTIONS[action].method, customMetricPath(action, args));
    case "update_custom_metric":
      return callApi("PUT", customMetricPath(action, args), { json: await readJsonBody(args) });
    case "start_custom_metric_quick_try": {
      const metric = await callApi(
        "GET",
        `/api/v1/custom-llm-metrics/${encodeURIComponent(requireOption(args, "metric-id"))}`,
      );
      return callApi("POST", "/api/v1/quick-eval/", {
        json: {
          data: await readJsonBody(args),
          evaluators: [customMetricEvaluator(metric)],
        },
      });
    }
    case "get_metric_quick_try":
      return callApi("GET", idPath(action, args, "job_id", "job-id"));
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
