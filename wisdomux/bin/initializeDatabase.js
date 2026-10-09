#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { DatabaseSync } = require('node:sqlite');

const MIGRATIONS = [
  '001_coordination_core.sql',
  '002_proof_ledger.sql',
];

function main(argv = process.argv.slice(2)) {
  let database;
  try {
    if (argv.length !== 2 || argv[0] !== '--db' || !argv[1]) {
      throw new TypeError('--db is required');
    }
    const databasePath = path.resolve(argv[1]);
    let reservation;
    try {
      reservation = fs.openSync(databasePath, 'wx', 0o600);
    } catch (error) {
      if (error.code === 'EEXIST') {
        throw new Error(`database already exists: ${databasePath}`);
      }
      throw error;
    } finally {
      if (reservation !== undefined) {
        fs.closeSync(reservation);
      }
    }
    database = new DatabaseSync(databasePath);
    database.exec('PRAGMA foreign_keys = ON');
    database.exec('BEGIN IMMEDIATE');
    for (const migration of MIGRATIONS) {
      const sql = fs.readFileSync(
        path.join(__dirname, '..', 'db', 'migrations', migration),
        'utf8',
      );
      database.exec(sql);
    }
    database.exec('COMMIT');
    process.stdout.write(`${JSON.stringify({
      database: databasePath,
      migrations: MIGRATIONS,
    })}\n`);
  } catch (error) {
    process.stderr.write(`wisdomux initialization failed: ${error.message}\n`);
    process.exitCode = 1;
  } finally {
    database?.close();
  }
}

if (require.main === module) {
  main();
}

module.exports = { MIGRATIONS, main };
