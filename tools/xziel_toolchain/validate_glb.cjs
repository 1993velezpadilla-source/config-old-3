#!/usr/bin/env node
const fs = require("fs");
const path = require("path");

const input = process.argv[2];
const output = process.argv[3];
if (!input || !output) {
  console.error("usage: validate_glb.cjs INPUT.glb REPORT.json");
  process.exit(2);
}

const root = process.env.XZIEL_TOOL_ROOT || path.resolve(".xziel-tools");
const validator = require(path.join(root, "node", "node_modules", "gltf-validator"));
const bytes = new Uint8Array(fs.readFileSync(input));

validator.validateBytes(bytes, {
  uri: path.basename(input),
  format: path.extname(input).toLowerCase() === ".glb" ? "glb" : undefined,
  writeTimestamp: false,
  maxIssues: 0
}).then((report) => {
  fs.writeFileSync(output, JSON.stringify(report, null, 2));
  const issues = report.issues || {};
  const errors = issues.numErrors || 0;
  const warnings = issues.numWarnings || 0;
  const infos = issues.numInfos || 0;
  const hints = issues.numHints || 0;
  console.log("XZIEL_GLTF_VALIDATION", JSON.stringify({errors,warnings,infos,hints}));
  if (errors > 0) process.exit(3);
}).catch((err) => {
  console.error("XZIEL_GLTF_VALIDATOR_CRASH", err);
  process.exit(4);
});
