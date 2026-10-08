'use strict';

const { randomUUID } = require('node:crypto');

const { hashEntry } = require('./proofLedger');

const COMPLETABLE_STATES = [
  'CLAIMED',
  'PLANNED',
  'EXECUTING',
  'VERIFYING',
  'REPORTED',
];

class TaskCompletion {
  constructor(database, options = {}) {
    if (!database || typeof database.prepare !== 'function') {
      throw new TypeError('database with prepare() is required');
    }
    this.db = database;
    this.now = options.now || (() => new Date().toISOString());
    this.newId = options.newId || randomUUID;
  }

  complete({ taskId, agentId, claim, truthState, evidenceRefs }) {
    if (!taskId || !agentId || !claim || !truthState) {
      throw new TypeError(
        'taskId, agentId, claim, and truthState are required',
      );
    }
    if (
      !Array.isArray(evidenceRefs) ||
      evidenceRefs.length === 0 ||
      evidenceRefs.some((value) => typeof value !== 'string' || !value)
    ) {
      throw new TypeError('at least one evidence reference is required');
    }

    this.db.exec('BEGIN IMMEDIATE');
    try {
      const agent = this.db.prepare(
        `SELECT status, capability_json
           FROM wisdomux_agents
          WHERE agent_id = ?`,
      ).get(agentId);
      if (!agent || !['ONLINE', 'BUSY'].includes(agent.status)) {
        throw new Error('agent is not available');
      }
      const grants = new Set(
        JSON.parse(agent.capability_json || '{}').grants || [],
      );
      for (const capability of ['task.complete', 'proof.record']) {
        if (!grants.has(capability)) {
          throw new Error(`missing capability: ${capability}`);
        }
      }

      const task = this.db.prepare(
        'SELECT * FROM wisdomux_tasks WHERE task_id = ?',
      ).get(taskId);
      if (
        !task ||
        task.claimed_by_agent !== agentId ||
        !COMPLETABLE_STATES.includes(task.state)
      ) {
        throw new Error('task is not claimed by agent');
      }

      const createdAt = this.now();
      this.db.prepare(
        `UPDATE wisdomux_tasks
            SET state = 'COMPLETED', truth_state = ?, updated_at = ?
          WHERE task_id = ?`,
      ).run(truthState, createdAt, taskId);
      this.db.prepare(
        `INSERT INTO wisdomux_events
          (event_id, project_id, task_id, sender_agent, event_type,
           truth_state, payload_json, evidence_json, created_at)
         VALUES (?, ?, ?, ?, 'TASK_COMPLETED', ?, ?, ?, ?)`,
      ).run(
        this.newId(),
        task.project_id,
        taskId,
        agentId,
        truthState,
        JSON.stringify({ claim, previous_state: task.state }),
        JSON.stringify(evidenceRefs),
        createdAt,
      );

      const previous = this.db.prepare(
        `SELECT entry_hash
           FROM wisdomux_proof_ledger
          ORDER BY sequence DESC
          LIMIT 1`,
      ).get();
      const entry = {
        entry_id: this.newId(),
        project_id: task.project_id,
        task_id: taskId,
        actor_agent: agentId,
        claim,
        truth_state: truthState,
        evidence_refs: evidenceRefs,
        previous_hash: previous ? previous.entry_hash : null,
        created_at: createdAt,
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
      return {
        task: this.db.prepare(
          'SELECT * FROM wisdomux_tasks WHERE task_id = ?',
        ).get(taskId),
        proof: this.db.prepare(
          'SELECT * FROM wisdomux_proof_ledger WHERE entry_id = ?',
        ).get(entry.entry_id),
      };
    } catch (error) {
      this.db.exec('ROLLBACK');
      throw error;
    }
  }
}

module.exports = { COMPLETABLE_STATES, TaskCompletion };
