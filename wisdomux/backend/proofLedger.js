'use strict';

const { createHash, randomUUID } = require('node:crypto');

class ProofLedger {
  constructor(database, options = {}) {
    if (!database || typeof database.prepare !== 'function') {
      throw new TypeError('database with prepare() is required');
    }
    this.db = database;
    this.now = options.now || (() => new Date().toISOString());
    this.newId = options.newId || randomUUID;
  }

  record({
    projectId,
    taskId = null,
    actorAgent,
    claim,
    truthState,
    evidenceRefs = [],
  }) {
    if (!projectId || !actorAgent || !claim || !truthState) {
      throw new TypeError(
        'projectId, actorAgent, claim, and truthState are required',
      );
    }
    if (
      !Array.isArray(evidenceRefs) ||
      evidenceRefs.some((value) => typeof value !== 'string')
    ) {
      throw new TypeError('evidenceRefs must be an array of strings');
    }
    this.db.exec('BEGIN IMMEDIATE');
    try {
      this.#requireCapability(actorAgent, 'proof.record');
      const previous = this.db.prepare(
        `SELECT entry_hash
           FROM wisdomux_proof_ledger
          ORDER BY sequence DESC
          LIMIT 1`,
      ).get();
      const entry = {
        entry_id: this.newId(),
        project_id: projectId,
        task_id: taskId,
        actor_agent: actorAgent,
        claim,
        truth_state: truthState,
        evidence_refs: evidenceRefs,
        previous_hash: previous ? previous.entry_hash : null,
        created_at: this.now(),
      };
      const entryHash = hashEntry(entry);
      this.db.prepare(
        `INSERT INTO wisdomux_proof_ledger
          (entry_id, project_id, task_id, actor_agent, claim, truth_state,
           evidence_json, previous_hash, entry_hash, created_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      ).run(
        entry.entry_id,
        entry.project_id,
        entry.task_id,
        entry.actor_agent,
        entry.claim,
        entry.truth_state,
        JSON.stringify(entry.evidence_refs),
        entry.previous_hash,
        entryHash,
        entry.created_at,
      );
      this.db.exec('COMMIT');
      return this.db.prepare(
        'SELECT * FROM wisdomux_proof_ledger WHERE entry_id = ?',
      ).get(entry.entry_id);
    } catch (error) {
      this.db.exec('ROLLBACK');
      throw error;
    }
  }

  verify() {
    const entries = this.db.prepare(
      'SELECT * FROM wisdomux_proof_ledger ORDER BY sequence ASC',
    ).all();
    let previousHash = null;
    for (const row of entries) {
      if (row.previous_hash !== previousHash) {
        return {
          ok: false,
          sequence: row.sequence,
          error: 'previous hash mismatch',
        };
      }
      const expected = hashEntry({
        entry_id: row.entry_id,
        project_id: row.project_id,
        task_id: row.task_id,
        actor_agent: row.actor_agent,
        claim: row.claim,
        truth_state: row.truth_state,
        evidence_refs: JSON.parse(row.evidence_json),
        previous_hash: row.previous_hash,
        created_at: row.created_at,
      });
      if (row.entry_hash !== expected) {
        return {
          ok: false,
          sequence: row.sequence,
          error: 'entry hash mismatch',
        };
      }
      previousHash = row.entry_hash;
    }
    return {
      ok: true,
      entries: entries.length,
      head: previousHash,
    };
  }

  #requireCapability(agentId, capability) {
    const agent = this.db.prepare(
      `SELECT status, capability_json
         FROM wisdomux_agents
        WHERE agent_id = ?`,
    ).get(agentId);
    if (!agent || !['ONLINE', 'BUSY'].includes(agent.status)) {
      throw new Error('agent is not available');
    }
    const capabilities = JSON.parse(agent.capability_json || '{}');
    if (
      !Array.isArray(capabilities.grants) ||
      !capabilities.grants.includes(capability)
    ) {
      throw new Error(`missing capability: ${capability}`);
    }
  }
}

function hashEntry(entry) {
  return createHash('sha256')
    .update(JSON.stringify(entry))
    .digest('hex');
}

module.exports = { ProofLedger, hashEntry };
