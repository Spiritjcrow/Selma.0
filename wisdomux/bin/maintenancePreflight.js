#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { DatabaseSync } = require('node:sqlite');

const REQUIRED_TABLES = [
  'wisdomux_agents',
  'wisdomux_tasks',
  'wisdomux_events',
  'wisdomux_proof_ledger',
];
const REQUIRED_CAPABILITIES = [
  'agent.monitor',
  'task.recover_stale',
];

function parseArguments(argv) {
  const options = {};
  for (let index = 0; index < argv.length; index += 2) {
    const flag = argv[index];
    const value = argv[index + 1];
    if (!['--db', '--coordinator'].includes(flag) || !value) {
      throw new TypeError(`invalid argument: ${flag || '<missing>'}`);
    }
    options[flag.slice(2)] = value;
  }
  if (!options.db || !options.coordinator) {
    throw new TypeError('--db and --coordinator are required');
  }
  return options;
}

function main(argv = process.argv.slice(2)) {
  let database;
  try {
    const options = parseArguments(argv);
    const databasePath = path.resolve(options.db);
    if (!fs.existsSync(databasePath)) {
      throw new Error(`database does not exist: ${databasePath}`);
    }
    database = new DatabaseSync(databasePath, { readOnly: true });
    const tables = new Set(database.prepare(
      "SELECT name FROM sqlite_master WHERE type = 'table'",
    ).all().map((row) => row.name));
    const missingTables = REQUIRED_TABLES.filter((name) => !tables.has(name));
    const integrityRows = database.prepare('PRAGMA integrity_check').all();
    const foreignKeyRows = database.prepare('PRAGMA foreign_key_check').all();
    const agent = database.prepare(
      `SELECT agent_id, status, capability_json
         FROM wisdomux_agents
        WHERE agent_id = ?`,
    ).get(options.coordinator);
    if (!agent) {
      throw new Error(`coordinator is not registered: ${options.coordinator}`);
    }
    const grants = JSON.parse(agent.capability_json || '{}').grants || [];
    const blockers = missingTables.map((name) => `missing table: ${name}`);
    if (foreignKeyRows.length > 0) {
      blockers.push(`foreign key violations: ${foreignKeyRows.length}`);
    }
    if (!['ONLINE', 'BUSY'].includes(agent.status)) {
      blockers.push(`coordinator status is not available: ${agent.status}`);
    }
    blockers.push(...REQUIRED_CAPABILITIES
      .filter((capability) => !grants.includes(capability))
      .map((capability) => `missing capability: ${capability}`));
    const report = {
      ready: blockers.length === 0,
      database: databasePath,
      coordinator: {
        agentId: agent.agent_id,
        status: agent.status,
        grants,
      },
      checks: {
        schema: missingTables.length === 0 ? 'ok' : 'failed',
        integrity: integrityRows.every((row) => row.integrity_check === 'ok')
          ? 'ok'
          : 'failed',
        foreignKeys: foreignKeyRows.length === 0 ? 'ok' : 'failed',
      },
      blockers,
    };
    process.stdout.write(`${JSON.stringify(report)}\n`);
    process.exitCode = report.ready ? 0 : 2;
  } catch (error) {
    process.stderr.write(`wisdomux preflight failed: ${error.message}\n`);
    process.exitCode = 1;
  } finally {
    database?.close();
  }
}

if (require.main === module) {
  main();
}

module.exports = {
  REQUIRED_CAPABILITIES,
  REQUIRED_TABLES,
  main,
  parseArguments,
};
