'use strict';

const { randomUUID } = require('node:crypto');

class TaskRecovery {
  constructor(database, options = {}) {
    if (!database || typeof database.prepare !== 'function') {
      throw new TypeError('database with prepare() is required');
    }
    const maxRetries = options.maxRetries ?? 3;
    if (!Number.isInteger(maxRetries) || maxRetries < 1) {
      throw new TypeError('maxRetries must be a positive integer');
    }
    this.db = database;
    this.maxRetries = maxRetries;
    this.now = options.now || (() => new Date().toISOString());
    this.newId = options.newId || randomUUID;
  }

  retry({ taskId, requestedBy, reason, evidenceRefs }) {
    if (!taskId || !requestedBy || !reason) {
      throw new TypeError('taskId, requestedBy, and reason are required');
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
      this.#requireCapability(requestedBy, 'task.retry');
      const task = this.db.prepare(
        'SELECT * FROM wisdomux_tasks WHERE task_id = ?',
      ).get(taskId);
      if (!task || !['BLOCKED', 'DEFERRED'].includes(task.state)) {
        throw new Error('task is not recoverable');
      }
      if (!['NOT_REQUIRED', 'APPROVED'].includes(task.approval_state)) {
        throw new Error('task approval does not allow retry');
      }

      const previousRetries = Number(this.db.prepare(
        `SELECT COUNT(*) AS count
           FROM wisdomux_events
          WHERE task_id = ?
            AND event_type = 'TASK_RETRY_QUEUED'`,
      ).get(taskId).count);
      if (previousRetries >= this.maxRetries) {
        throw new Error('retry limit reached');
      }
      const attempt = previousRetries + 1;
      const timestamp = this.now();
      this.db.prepare(
        `UPDATE wisdomux_tasks
            SET state = 'DEFERRED',
                truth_state = 'UNVERIFIED',
                claimed_by_agent = NULL,
                updated_at = ?
          WHERE task_id = ?
            AND state IN ('BLOCKED', 'DEFERRED')`,
      ).run(timestamp, taskId);
      this.db.prepare(
        `INSERT INTO wisdomux_events
          (event_id, project_id, task_id, sender_agent, event_type,
           truth_state, payload_json, evidence_json, created_at)
         VALUES (?, ?, ?, ?, 'TASK_RETRY_QUEUED', 'UNVERIFIED', ?, ?, ?)`,
      ).run(
        this.newId(),
        task.project_id,
        taskId,
        requestedBy,
        JSON.stringify({
          attempt,
          previous_state: task.state,
          previous_truth_state: task.truth_state,
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

  #requireCapability(agentId, capability) {
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
    if (!grants.has(capability)) {
      throw new Error(`missing capability: ${capability}`);
    }
  }
}

module.exports = { TaskRecovery };
