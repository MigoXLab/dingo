---
name: dingo-saas
description: Operate Dingo SaaS through conversation by mapping user requests to backend API actions. Use for Dingo SaaS dataset, metric, experiment, and report workflows.
---

# Dingo SaaS

Translate the user's request into one or more actions, then execute them in dependency order through the corresponding backend APIs.

## Implemented Modules

- Datasets: use `scripts/dataset_actions.mjs` and the actions below.
- Experiments: use `scripts/experiment_actions.mjs` and the actions below.
- Reports: use `scripts/report_actions.mjs` and the actions below.
- Metrics: use `scripts/metric_actions.mjs` and the actions below.

Use only implemented actions. Do not claim that an unimplemented Dingo SaaS page is available through this skill.

## Connection

Before any Dingo SaaS action, check the saved connection:

```powershell
node scripts/connection_actions.mjs connection_status
```

If the response says `configured: false`, immediately ask the user for both the Dingo SaaS
website URL and API key. Save them with:

```powershell
node scripts/connection_actions.mjs configure --url <URL> --key <KEY>
```

The script persists them in `config.json` in this skill directory. Once saved, reuse that
connection for every action without asking again. If an API returns 401, ask the user for a
new URL and key and overwrite the saved configuration with `configure`.

Never print or repeat the complete key. `configure` and `connection_status` return only a
masked key prefix. When the user explicitly asks to forget the connection, run:

```powershell
node scripts/connection_actions.mjs clear_config
```

Run an action with its page module script:

```powershell
node scripts/dataset_actions.mjs <action> [options]
node scripts/experiment_actions.mjs <action> [options]
node scripts/report_actions.mjs <action> [options]
node scripts/metric_actions.mjs <action> [options]
```

Resolve the script path relative to this `SKILL.md` file.

## Dataset Actions

| User intent | Action | Backend API |
|---|---|---|
| List, search, or locate datasets | `list_datasets` | `GET /api/v1/datasets/` |
| View dataset details | `get_dataset` | `GET /api/v1/datasets/{dataset_id}` |
| Preview dataset rows | `preview_dataset` | `GET /api/v1/datasets/{dataset_id}/preview` |
| Initialize example data | `initialize_demo_data` | `POST /api/v1/demo/initialize` |
| Upload a local source file | `upload_dataset_file` | `POST /api/v1/datasets/upload` |
| Create a dataset | `create_dataset` | `POST /api/v1/datasets/` |
| Edit or rename a dataset | `update_dataset` | `PUT /api/v1/datasets/{dataset_id}` |
| Copy or clone a dataset | `copy_dataset` | `POST /api/v1/datasets/{dataset_id}/copy` |
| Delete a dataset | `delete_dataset` | `DELETE /api/v1/datasets/{dataset_id}` |

Use `node scripts/dataset_actions.mjs actions` to see parameters.

`create_dataset` accepts the backend `DatasetCreate` JSON body. For a local upload, use at least:

```json
{
  "name": "Dataset name",
  "source": "local",
  "format": "jsonl",
  "temp_file_paths": ["temp_path returned by upload_dataset_file"],
  "relative_paths": ["original-file.jsonl"]
}
```

`update_dataset` accepts any of `name`, `description`, `config`, and `status`.

## Experiment Actions

| User intent | Action | Backend API |
|---|---|---|
| List, filter, or locate experiments | `list_experiments` | `GET /api/v1/experiments/` |
| View or edit experiment details | `get_experiment`, `update_experiment` | `GET/PUT /api/v1/experiments/{experiment_id}` |
| Create an experiment | `create_experiment` | `POST /api/v1/experiments/` |
| Copy an experiment | `copy_experiment` | `POST /api/v1/experiments/{experiment_id}/copy` |
| Delete an experiment | `delete_experiment` | `DELETE /api/v1/experiments/{experiment_id}` |
| Start an experiment | `start_experiment` | `POST /api/v1/experiments/{experiment_id}/start` |
| Stop a running experiment | `stop_experiment` | `POST /api/v1/experiments/{experiment_id}/stop` |
| View, create, or edit a schedule | `get_experiment_schedule`, `upsert_experiment_schedule` | `GET/PUT /api/v1/experiments/{experiment_id}/schedule` |
| Enable or disable a schedule | `toggle_experiment_schedule` | `POST /api/v1/experiments/{experiment_id}/schedule/toggle` |
| Delete a schedule | `delete_experiment_schedule` | `DELETE /api/v1/experiments/{experiment_id}/schedule` |
| View generated Dingo input | `get_experiment_dingo_input` | `GET /api/v1/experiments/{experiment_id}/dingo-input` |

Use `node scripts/experiment_actions.mjs actions` to see parameters.

`create_experiment` accepts the backend `ExperimentCreate` JSON body. Common fields are
`name`, `description`, `dataset_id`, `task_type`, `evaluators`, `dingo_config`, `config_yaml`,
and `retrieval_config`. `update_experiment` accepts the corresponding editable fields.

`upsert_experiment_schedule` accepts:

```json
{
  "start_date": "2026-09-11",
  "end_date": "2026-09-30",
  "weekdays": [1, 3, 5],
  "start_time": "09:30",
  "timezone": "Asia/Shanghai",
  "enabled": true,
  "schedule_node": "optional-node"
}
```

Weekdays use `1` for Monday through `7` for Sunday.

## Report Actions

Reports have three distinct page scopes. Keep them separate when interpreting the user's request.

### Report List Page

| User intent | Action | Backend API |
|---|---|---|
| List, search, or filter reports | `list_reports` | `GET /api/v1/outputs/` |
| Delete a report | `delete_report` | `DELETE /api/v1/outputs/{report_id}` |
| View a report's execution log | `get_report_log` | `GET /api/v1/outputs/{report_id}` |
| Get the public share URL | `get_report_share_url` | Local URL composition: `/share/{report_id}` |
| Download the report archive | `download_report` | `GET /api/v1/outputs/{report_id}/download` |

### Report Detail Page

| User intent | Action | Backend API |
|---|---|---|
| View basic information, Dingo input, and execution metadata | `get_report_detail` | `GET /api/v1/outputs/{report_id}` |
| Rename a report or edit its description | `update_report` | `PUT /api/v1/outputs/{report_id}` |
| Delete a report | `delete_report` | `DELETE /api/v1/outputs/{report_id}` |
| Download the report archive | `download_report` | `GET /api/v1/outputs/{report_id}/download` |

### Report Results Page

| User intent | Action | Backend API |
|---|---|---|
| Open or summarize the complete results page | `get_report_results` | Report detail + result-row list |
| List or filter result rows only | `list_report_results` | `GET /api/v1/output-items/output/{report_id}` |
| View one result row | `get_report_result` | `GET /api/v1/output-items/{item_id}` |
| Get the public results URL | `get_report_share_url` | Local URL composition: `/share/{report_id}` |
| Download the report archive | `download_report` | `GET /api/v1/outputs/{report_id}/download` |

Use `node scripts/report_actions.mjs actions` to see parameters.

`list_reports` supports experiment, status, creation-date, and pagination filters. Its optional
`--search` matches report ID, name, or description within the returned page, like the report page.
`list_report_results` supports `eval_status` (`all`, `true`, or `false`) and label filtering.

The detail page and results page are not interchangeable. `get_report_detail` returns report
metadata, Dingo input, execution status, and `dingo_result`. The results page additionally needs
the paginated records from `output-items`; use `get_report_results` to retrieve both parts. Treat
`dingo_result.summary` as the results-page summary, not as the individual result rows.

`update_report` accepts a JSON body containing only the page-editable fields `name` and/or
`description`. `get_report_log` returns the persisted log, or the report message when no log was
captured. `get_report_share_url` only constructs the existing public URL; it does not create a
share token or change server state. `download_report` requires `--output PATH` and saves the ZIP
archive to that location without overwriting an existing file.

## Metric Actions

The Metrics page has three tabs. Do not treat the read-only SDK metric catalog, user metric
groups, and user-defined custom LLM metrics as the same resource.

### Metric List Tab

| User intent | Action | Backend API |
|---|---|---|
| List, search, or filter available SDK metrics | `list_metrics` | `GET /api/v1/metrics/list` |

Use `--type rule` or `--type llm` to filter by metric type. `--search` matches metric name,
display name, or description within the returned catalog. This tab is read-only; global metric
configuration belongs to the separate administrator configuration page and is not part of this
module.

### Metric Groups Tab

| User intent | Action | Backend API |
|---|---|---|
| List or search metric groups | `list_metric_groups` | `GET /api/v1/metric-groups/` |
| View a group and its metrics | `get_metric_group_detail` | Group detail + group-item list |
| Create a metric group | `create_metric_group` | `POST /api/v1/metric-groups/` |
| Rename or edit a metric group | `update_metric_group` | `PUT /api/v1/metric-groups/{group_id}` |
| Delete a metric group | `delete_metric_group` | `DELETE /api/v1/metric-groups/{group_id}` |
| Add a metric to a group | `add_metric_to_group` | `POST /api/v1/metric-group-items/` |
| Add a saved custom metric to a group | `add_custom_metric_to_group` | Custom metric detail + group-item create |
| Edit a grouped metric's configuration | `update_group_metric` | `PUT /api/v1/metric-group-items/{item_id}` |
| Remove a metric from a group | `remove_metric_from_group` | `DELETE /api/v1/metric-group-items/{item_id}` |

`create_metric_group` accepts `name` and optional `description`. If the user also specifies
metrics, create the group first and then call `add_metric_to_group` once for each selected metric
using the returned group ID. A group item body contains `group_id`, metric `name`, and optional
`config`.

### Custom Metrics Tab

| User intent | Action | Backend API |
|---|---|---|
| List or search custom metrics | `list_custom_metrics` | `GET /api/v1/custom-llm-metrics/` |
| View a custom metric | `get_custom_metric` | `GET /api/v1/custom-llm-metrics/{metric_id}` |
| Create a custom metric | `create_custom_metric` | `POST /api/v1/custom-llm-metrics/` |
| Edit a custom metric | `update_custom_metric` | `PUT /api/v1/custom-llm-metrics/{metric_id}` |
| Delete a custom metric | `delete_custom_metric` | `DELETE /api/v1/custom-llm-metrics/{metric_id}` |
| Ask the assistant to draft a custom metric | `draft_custom_metric` | `POST /api/v1/custom-llm-metrics/assistant` |
| Start or check a custom metric quick try | `start_custom_metric_quick_try`, `get_metric_quick_try` | Custom metric detail + `POST/GET /api/v1/quick-eval/...` |

A custom metric body uses `metric`, `description`, `criteria`, `input_fields`, and `llm_config`.
`criteria` and `input_fields` are non-empty string arrays. `llm_config` contains `model`, `key`,
and `api_url`; system defaults are `SYSTEM_LLM_MODEL`, `SYSTEM_LLM_KEY`, and
`SYSTEM_LLM_API_URL`. Treat an explicit LLM key as a credential: pass the body through `--stdin`
and never repeat the key in the response.

`draft_custom_metric` accepts `messages` plus `current_metric` and only returns a proposed draft;
do not create or update the metric until the user asks to save or apply it.
`start_custom_metric_quick_try` accepts the input-field values as its JSON body, loads the saved
custom metric, builds the `LLMCustomMetric` evaluator snapshot, and submits the job. Poll
`get_metric_quick_try` every 2 seconds until status is `done` or `error`, stopping after 5 minutes.

Use `node scripts/metric_actions.mjs actions` to see all parameters.

## Execution

1. Map the request to the smallest ordered action list.
2. When a dataset, experiment, or report ID is missing, call its list action and match the user's name against `name`. If multiple records match, ask the user which one they mean.
3. For a local file, call `upload_dataset_file`, then pass its `temp_path` in `temp_file_paths` to `create_dataset`.
4. Pass JSON request bodies with `--body`, `--body-file`, or `--stdin`. Prefer `--stdin` when a body contains credentials; never echo secrets in the response.
5. Before deleting a dataset, experiment, experiment schedule, report, metric group, grouped metric, or custom metric, identify the exact target and obtain confirmation unless the user explicitly requested deletion of that exact target in the current message. Use soft dataset deletion by default; use `--hard-delete` only when explicitly requested.
6. For `start_experiment`, use the user's report name and description. If no report name is provided, get the experiment and generate `<experiment_name>_YYYYMMDD_HHMMSS`; use an empty description when omitted.
7. After starting an experiment, use `get_experiment` to check status. Stop polling when status is no longer `running`.
8. When the user asks to follow a running report's log, call `get_report_log` every 3 seconds and stop when its status is `success`, `failed`, `error`, or `stopped`.
9. Execute actions in order. If one fails, stop dependent actions and report the API error.
10. Return the completed actions and important result fields, such as resource name, ID, and status.

Examples of composition:

- “Create a dataset from this local file” → `upload_dataset_file`, then `create_dataset`.
- “Copy dataset A and rename it B” → `list_datasets` when needed, `copy_dataset`, then `update_dataset` using the copied dataset ID.
- “Run experiment A” → `list_experiments` when needed, `get_experiment`, `start_experiment`, then check its status.
- “Schedule experiment A on weekdays” → `list_experiments` when needed, then `upsert_experiment_schedule`.
- “Show failed reports from experiment A” → `list_experiments` when needed, then `list_reports` with its experiment ID and failed status.
- “View the log for report R” → `list_reports` when needed, then `get_report_log`.
- “Download report R” → `list_reports` when needed, then `download_report` to the requested local path.
- “Create metric group G with metrics A and B” → `create_metric_group`, then `add_metric_to_group` for A and B.
- “Draft a custom relevance metric” → `draft_custom_metric`; create it only after the user asks to save it.
