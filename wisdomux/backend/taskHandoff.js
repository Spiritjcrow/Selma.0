'use strict';

const { randomUUID } = require('node:crypto');

const HANDOFF_STATES = [
  'CLAIMED',
  'PLANNED',
  'EXECUTING',
  'VERIFYING',
  'REPORTED',
];

class TaskHandoff {
  constructor(database, options = {}) {
    if (!database || typeof database.prepare !== 'function') {
      throw new TypeError('database with prepare() is required');
    }
    this.db = database;
    this.now = options.now || (() => new Date().toISOString());
    this.newId = options.newId || randomUUID;
  }

  transfer({ taskId, fromAgent, toAgent, reason, evidenceRefs }) {
    if (!taskId || !fromAgent || !toAgent || !reason) {
      throw new TypeError(
        'taskId, fromAgent, toAgent, and reason are required',
      );
    }
    if (fromAgent === toAgent) {
      throw new Error('handoff target must differ from source agent');
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
      const source = this.#agent(fromAgent);
      if (!source || !['ONLINE', 'BUSY'].includes(source.status)) {
        throw new Error('source agent is not available');
      }
      const sourceGrants = new Set(
        JSON.parse(source.capability_json || '{}').grants || [],
      );
      if (!sourceGrants.has('task.handoff')) {
        throw new Error('missing capability: task.handoff');
      }

      const task = this.db.prepare(
        'SELECT * FROM wisdomux_tasks WHERE task_id = ?',
      ).get(taskId);
      if (
        !task ||
        task.claimed_by_agent !== fromAgent ||
        !HANDOFF_STATES.includes(task.state)
      ) {
        throw new Error('task is not claimed by source agent');
      }

      const target = this.#agent(toAgent);
      if (!target || target.status !== 'ONLINE') {
        throw new Error('target agent is not available');
      }
      const targetGrants = new Set(
        JSON.parse(target.capability_json || '{}').grants || [],
      );
      if (
        task.required_capability &&
        !targetGrants.has(task.required_capability)
      ) {
        throw new Error(
          `target missing capability: ${task.required_capability}`,
        );
      }

      const timestamp = this.now();
      const updated = this.db.prepare(
        `UPDATE wisdomux_tasks
            SET state = 'CLAIMED', claimed_by_agent = ?, updated_at = ?
          WHERE task_id = ?
            AND claimed_by_agent = ?
            AND state IN ('CLAIMED', 'PLANNED', 'EXECUTING',
                          'VERIFYING', 'REPORTED')`,
      ).run(toAgent, timestamp, taskId, fromAgent);
      if (Number(updated.changes) !== 1) {
        throw new Error('task handoff lost to another coordinator');
      }
      this.db.prepare(
        `INSERT INTO wisdomux_events
          (event_id, project_id, task_id, sender_agent, event_type,
           truth_state, payload_json, evidence_json, created_at)
         VALUES (?, ?, ?, ?, 'TASK_HANDED_OFF', ?, ?, ?, ?)`,
      ).run(
        this.newId(),
        task.project_id,
        taskId,
        fromAgent,
        task.truth_state,
        JSON.stringify({
          from_agent: fromAgent,
          to_agent: toAgent,
          reason,
        }),
        JSON.stringify(evidenceRefs),
        timestamp,
      );
      this.db.exec('COMMIT');
      return this.db.prepare(
        'SELECT * FROM wisdomux_tasks WHERE task_id = ?',
      ).get(taskId);
    } catch (error) {
      this.db.exec('ROLLBACK');
      throw error;
    }
  }

  #agent(agentId) {
    return this.db.prepare(
      `SELECT status, capability_json
         FROM wisdomux_agents
        WHERE agent_id = ?`,
    ).get(agentId);
  }
}

module.exports = { HANDOFF_STATES, TaskHandoff };
