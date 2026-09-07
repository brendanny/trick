/* Exercise the actual pinned Zensical worker, with no browser or network APIs. */
"use strict";

const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.resolve(__dirname, "../..");

async function loadEngine(worker, index) {
  let response;
  const context = vm.createContext({
    self: { postMessage: (message) => { response = message; } },
    performance,
    Intl,
  });
  vm.runInContext(worker, context, { timeout: 10000 });
  async function send(message) {
    response = undefined;
    context.message = message;
    await vm.runInContext("self.onmessage({data: message})", context, { timeout: 10000 });
    assert.ok(response, "Search worker did not respond");
    return response;
  }
  assert.equal((await send({ type: 0, data: index })).type, 1);
  return async (input) => {
    // Same empty tag filter and query envelope used by the bundled UI in 0.0.59.
    const result = await send({ type: 2, data: {
      input,
      filter: {
        input: { type: "operator", data: { operator: "and", operands: [] } },
        aggregation: { input: [{ type: "term", data: { field: "tags" } }] },
      },
    } });
    assert.equal(result.type, 3);
    assert.ok(Array.isArray(result.data.items), "Unexpected search response schema");
    return result.data.items.map(({ id }) => {
      assert.ok(Number.isInteger(id) && index.items[id], "Invalid search result ID");
      return index.items[id].location;
    });
  };
}

function rank(locations, target) {
  const index = locations.findIndex((location) => target.includes("#")
    ? location === target : location.split("#")[0] === target);
  return index === -1 ? null : index + 1;
}

function assertRelevant(locations, test) {
  const actual = rank(locations, test.target);
  assert.ok(actual !== null && actual <= test.max_rank,
    `${test.query}: expected ${test.target} within first ${test.max_rank} worker hits; got rank ${actual}`);
  return actual;
}

async function main() {
  const html = fs.readFileSync(path.join(root, "site/index.html"), "utf8");
  const match = html.match(/<script\b[^>]*\bid="__config"[^>]*>([\s\S]*?)<\/script>/);
  assert.ok(match, "Missing theme runtime configuration");
  const config = JSON.parse(match[1]);
  const workerPath = config.search.replace(/^\.\//, "");
  assert.match(workerPath, /^assets\/javascripts\/workers\/search\.[a-z0-9]+\.min\.js$/);
  const worker = fs.readFileSync(path.join(root, "site", workerPath), "utf8");
  const index = JSON.parse(fs.readFileSync(path.join(root, "site/search.json"), "utf8"));
  const cases = JSON.parse(fs.readFileSync(path.join(__dirname, "search-cases.json"), "utf8"));
  assert.ok(Array.isArray(index.items) && index.items.length > 0, "Empty search index");
  assert.equal(cases.length, 6, "Keep the six migration acceptance queries explicit");
  const search = await loadEngine(worker, index);
  const checks = [];
  for (const test of cases) {
    const locations = await search(test.query);
    const actualRank = assertRelevant(locations, test);
    checks.push({ ...test, rank: actualRank, first_page_locations: locations });
    console.log(`${test.query}: rank ${actualRank} — ${test.target}`);
  }
  // Negative fixtures verify both our rank gate and the real engine's input.
  assert.throws(() => assertRelevant([], cases[0]));
  assert.throws(() => assertRelevant(["missing.html", cases[0].target], { ...cases[0], max_rank: 1 }));
  assert.throws(() => assertRelevant([cases[3].target.split("#")[0]], cases[3]));
  const removed = { ...index, items: index.items.filter((item) =>
    item.location.split("#")[0] !== cases[0].target) };
  const searchWithoutTarget = await loadEngine(worker, removed);
  const awaitedLocations = await searchWithoutTarget(cases[0].query);
  assert.throws(() => assertRelevant(awaitedLocations, cases[0]), /expected/);
  const report = {
    worker: workerPath,
    worker_sha256: crypto.createHash("sha256").update(worker).digest("hex"),
    ranking: "First worker response; individual section hits, before UI page grouping",
    network_apis_available: false,
    negative_fixtures: 4,
    checks,
    browser_validation: "pending: search interaction and highlight navigation",
  };
  const output = path.join(root, ".docs-build/search-report.json");
  fs.writeFileSync(output, JSON.stringify(report, null, 2) + "\n");
  console.log(`Native search checks and four negative fixtures passed. Report: ${output}`);
}

main().catch((error) => { console.error(error.message); process.exitCode = 1; });
