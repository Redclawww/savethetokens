#!/usr/bin/env node

const path = require("path");

const args = process.argv.slice(2);
const command = args[0];

function printHelp() {
  const pkg = require(path.join(__dirname, "..", "package.json"));
  console.log(`savethetokens v${pkg.version}`);
  console.log("\nClaude Code skill to reduce token burn with proactive compacting,");
  console.log("context pruning, and session hygiene.\n");
  console.log("Usage:");
  console.log("  savethetokens install     Install skill to ~/.claude/skills/savethetokens/");
  console.log("  savethetokens uninstall   Remove skill from ~/.claude/skills/savethetokens/");
  console.log("  savethetokens --version   Print version");
  console.log("  savethetokens --help      Show this help\n");
  console.log("Learn more: https://github.com/Redclawww/save-the-tokens");
}

if (!command || command === "--help" || command === "-h" || command === "help") {
  printHelp();
} else if (command === "--version" || command === "-v" || command === "version") {
  const pkg = require(path.join(__dirname, "..", "package.json"));
  console.log(pkg.version);
} else if (command === "install") {
  require("./install.js");
} else if (command === "uninstall") {
  require("./uninstall.js");
} else {
  console.error(`Unknown command: ${command}\n`);
  printHelp();
  process.exit(1);
}
