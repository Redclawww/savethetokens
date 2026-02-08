#!/usr/bin/env node

const fs = require("fs");
const path = require("path");
const os = require("os");

const SKILL_DIR = path.join(os.homedir(), ".claude", "skills", "savethetokens");

function rmDirSync(dir) {
  if (!fs.existsSync(dir)) return;
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      rmDirSync(fullPath);
    } else {
      fs.unlinkSync(fullPath);
    }
  }
  fs.rmdirSync(dir);
}

function uninstall() {
  if (!fs.existsSync(SKILL_DIR)) {
    console.log("savethetokens skill is not installed. Nothing to remove.");
    return;
  }

  rmDirSync(SKILL_DIR);
  console.log(`Removed ${SKILL_DIR}`);
  console.log("\nsavethetokens skill has been uninstalled.");
  console.log("To fully remove, also run: npm uninstall -g savethetokens");
}

uninstall();
