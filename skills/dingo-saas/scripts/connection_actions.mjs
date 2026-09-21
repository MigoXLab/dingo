#!/usr/bin/env node

import {
  clearConnection,
  configureConnection,
  getConnectionStatus,
  parseArgs,
  writeError,
  writeResult,
} from "./lib/dingo_client.mjs";

const ACTIONS = {
  configure: "--url URL --key KEY",
  connection_status: "",
  clear_config: "",
};

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const action = args._[0];

  if (!action || action === "actions" || action === "help") {
    writeResult(
      Object.entries(ACTIONS).map(([name, options]) => ({ action: name, options })),
    );
    return;
  }

  switch (action) {
    case "configure":
      writeResult(await configureConnection(args));
      return;
    case "connection_status":
      writeResult(await getConnectionStatus());
      return;
    case "clear_config":
      writeResult(await clearConnection());
      return;
    default:
      throw new Error(`Unknown action: ${action}. Run with 'actions' to list supported actions.`);
  }
}

main().catch(writeError);
