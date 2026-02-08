#!/usr/bin/env node

const fs = require("fs");
const path = require("path");
const os = require("os");

const SKILL_DIR = path.join(os.homedir(), ".claude", "skills", "savethetokens");

// Resolve the package root (one level up from bin/)
const PKG_ROOT = path.resolve(__dirname, "..");

function copyDirSync(src, dest) {
  fs.mkdirSync(dest, { recursive: true });
  for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
    const srcPath = path.join(src, entry.name);
    const destPath = path.join(dest, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === "__pycache__") continue;
      copyDirSync(srcPath, destPath);
    } else {
      if (entry.name.endsWith(".pyc")) continue;
      fs.copyFileSync(srcPath, destPath);
    }
  }
}

function install() {
  console.log("Installing savethetokens skill...\n");

  // Create skill directory
  fs.mkdirSync(SKILL_DIR, { recursive: true });

  // Copy SKILL.md
  const skillMdSrc = path.join(PKG_ROOT, "SKILL.md");
  if (fs.existsSync(skillMdSrc)) {
    fs.copyFileSync(skillMdSrc, path.join(SKILL_DIR, "SKILL.md"));
  } else {
    console.error("Error: SKILL.md not found in package. Installation may be incomplete.");
    process.exit(1);
  }

  // Copy scripts/
  const scriptsSrc = path.join(PKG_ROOT, "scripts");
  if (fs.existsSync(scriptsSrc)) {
    copyDirSync(scriptsSrc, path.join(SKILL_DIR, "scripts"));
  }

  // Copy docs/
  const docsSrc = path.join(PKG_ROOT, "docs");
  if (fs.existsSync(docsSrc)) {
    copyDirSync(docsSrc, path.join(SKILL_DIR, "docs"));
  }

  // Copy .claude/settings.local.json only if user doesn't already have one
  const settingsSrc = path.join(PKG_ROOT, ".claude", "settings.local.json");
  const settingsDest = path.join(os.homedir(), ".claude", "settings.local.json");
  if (fs.existsSync(settingsSrc) && !fs.existsSync(settingsDest)) {
    fs.mkdirSync(path.dirname(settingsDest), { recursive: true });
    fs.copyFileSync(settingsSrc, settingsDest);
    console.log("  Copied default settings.local.json to ~/.claude/");
  }

  console.log(`  Skill installed to ${SKILL_DIR}\n`);
  console.log("Done! The savethetokens skill is now available in Claude Code.\n");
  console.log("Quick start:");
  console.log("  python ~/.claude/skills/savethetokens/scripts/govern.py --budget 8000");
  console.log("  python ~/.claude/skills/savethetokens/scripts/cost_calculator.py --developers 5\n");
  console.log("Requires Python 3.8+");
}

install();
