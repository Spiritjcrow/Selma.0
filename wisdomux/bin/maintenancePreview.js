#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { DatabaseSync } = require('node:sqlite');

const { MaintenanceRunner } = require('../backend/maintenanceRunner');

const FLAG_NAMES = new Set([
  'db',
  'project',
  'coordinator',
  'cutoff',
  'sweep-limit',
]);

function parseArguments(argv) {
  const options = {};
  for (let index = 0; index < argv.length; index += 2) {
    const flag = argv[index];
    const value = argv[index + 1];
    if (!flag?.startsWith('--') || !FLAG_NAMES.has(flag.slice(2)) || !value) {
      throw new TypeError(`invalid argument: ${flag || '<missing>'}`);
    }
    options[flag.slice(2)] = value;
  }
  for (const required of ['db', 'project', 'coordinator', 'cutoff']) {
    if (!options[required]) {
      throw new TypeError(`--${required} is required`);
    }
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
    const runner = new MaintenanceRunner(database, {
      sweepLimit: options['sweep-limit'] === undefined
        ? undefined
        : Number(options['sweep-limit']),
    });
    const report = runner.previewOnce({
      projectId: options.project,
      requestedBy: options.coordinator,
      cutoff: options.cutoff,
    });
    process.stdout.write(`${JSON.stringify(report)}\n`);
    process.exitCode = report.ready ? 0 : 2;
  } catch (error) {
    process.stderr.write(`wisdomux maintenance preview failed: ${error.message}\n`);
    process.exitCode = 1;
  } finally {
    database?.close();
  }
}

if (require.main === module) {
  main();
}

module.exports = { main, parseArguments };
