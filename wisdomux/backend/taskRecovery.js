'use strict';

const { randomUUID } = require('node:crypto');

const RECOVERABLE_CLAIM_STATES = [
  'CLAIMED',
  'PLANNED',
  'EXECUTING',
  'VERIFYING',
  'REPORTED',
];

class TaskRecovery {
  constructor(database, options = {}) {
    if (!database || typeof database.prepare !== 'function') {
      throw new TypeError('database with prepare() is required');
    }
    const maxRetries = options.maxRetries ?? 3;
    if (!Number.isInteger(maxRetries) || maxRetries < 1) {
      throw new TypeError('maxRetries must be a positive integer');
    }
    const sweepLimit = options.sweepLimit ?? 50;
    if (!Number.isInteger(sweepLimit) || sweepLimit < 1 || sweepLimit > 500) {
      throw new TypeError('sweepLimit must be an integer from 1 to 500');
    }
    this.db = database;
    this.maxRetries = maxRetries;
    this.sweepLimit = sweepLimit;
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

  releaseStale({ taskId, requestedBy, reason, evidenceRefs }) {
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
      this.#requireCapability(requestedBy, 'task.recover_stale');
      const task = this.db.prepare(
        `SELECT task.*, agent.status AS owner_status
           FROM wisdomux_tasks AS task
           LEFT JOIN wisdomux_agents AS agent
             ON agent.agent_id = task.claimed_by_agent
          WHERE task.task_id = ?`,
      ).get(taskId);
      if (
        !task ||
        !task.claimed_by_agent ||
        !RECOVERABLE_CLAIM_STATES.includes(task.state)
      ) {
        throw new Error('task has no recoverable stale claim');
      }
      if (!['OFFLINE', 'REVOKED'].includes(task.owner_status)) {
        throw new Error('task owner is not stale');
      }

      const timestamp = this.now();
      const updated = this.db.prepare(
        `UPDATE wisdomux_tasks
            SET state = 'DEFERRED',
                truth_state = 'UNVERIFIED',
                claimed_by_agent = NULL,
                updated_at = ?
          WHERE task_id = ?
            AND claimed_by_agent = ?
            AND state = ?`,
      ).run(timestamp, taskId, task.claimed_by_agent, task.state);
      if (Number(updated.changes) !== 1) {
        throw new Error('stale claim recovery lost to another coordinator');
      }
      this.db.prepare(
        `INSERT INTO wisdomux_events
          (event_id, project_id, task_id, sender_agent, event_type,
           truth_state, payload_json, evidence_json, created_at)
         VALUES (?, ?, ?, ?, 'TASK_STALE_CLAIM_RELEASED',
                 'UNVERIFIED', ?, ?, ?)`,
      ).run(
        this.newId(),
        task.project_id,
        taskId,
        requestedBy,
        JSON.stringify({
          previous_owner: task.claimed_by_agent,
          owner_status: task.owner_status,
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

  sweepStale({ projectId, requestedBy, reason, evidenceRefs }) {
    this.db.exec('BEGIN IMMEDIATE');
    try {
      const recovered = this.sweepStaleInTransaction({
        projectId,
        requestedBy,
        reason,
        evidenceRefs,
      });
      this.db.exec('COMMIT');
      return recovered;
    } catch (error) {
      this.db.exec('ROLLBACK');
      throw error;
    }
  }

  sweepStaleInTransaction({ projectId, requestedBy, reason, evidenceRefs }) {
    if (!projectId || !requestedBy || !reason) {
      throw new TypeError('projectId, requestedBy, and reason are required');
    }
    if (
      !Array.isArray(evidenceRefs) ||
      evidenceRefs.length === 0 ||
      evidenceRefs.some((value) => typeof value !== 'string' || !value)
    ) {
      throw new TypeError('at least one evidence reference is required');
    }

    this.#requireCapability(requestedBy, 'task.recover_stale');
    const staleTasks = this.db.prepare(
      `SELECT task.*, agent.status AS owner_status
         FROM wisdomux_tasks AS task
         JOIN wisdomux_agents AS agent
           ON agent.agent_id = task.claimed_by_agent
        WHERE task.project_id = ?
          AND task.state IN ('CLAIMED', 'PLANNED', 'EXECUTING',
                             'VERIFYING', 'REPORTED')
          AND agent.status IN ('OFFLINE', 'REVOKED')
        ORDER BY task.priority DESC, task.updated_at ASC, task.task_id ASC
        LIMIT ?`,
    ).all(projectId, this.sweepLimit);
    const timestamp = this.now();
    const recovered = [];
    for (const task of staleTasks) {
      const updated = this.db.prepare(
        `UPDATE wisdomux_tasks
            SET state = 'DEFERRED',
                truth_state = 'UNVERIFIED',
                claimed_by_agent = NULL,
                updated_at = ?
          WHERE task_id = ?
            AND claimed_by_agent = ?
            AND state = ?`,
      ).run(timestamp, task.task_id, task.claimed_by_agent, task.state);
      if (Number(updated.changes) !== 1) {
        throw new Error('stale claim recovery lost to another coordinator');
      }
      this.db.prepare(
        `INSERT INTO wisdomux_events
          (event_id, project_id, task_id, sender_agent, event_type,
           truth_state, payload_json, evidence_json, created_at)
         VALUES (?, ?, ?, ?, 'TASK_STALE_CLAIM_RELEASED',
                 'UNVERIFIED', ?, ?, ?)`,
      ).run(
        this.newId(),
        task.project_id,
        task.task_id,
        requestedBy,
        JSON.stringify({
          previous_owner: task.claimed_by_agent,
          owner_status: task.owner_status,
          previous_state: task.state,
          previous_truth_state: task.truth_state,
          reason,
        }),
        JSON.stringify(evidenceRefs),
        timestamp,
      );
      recovered.push(task.task_id);
    }
    return recovered;
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

module.exports = { RECOVERABLE_CLAIM_STATES, TaskRecovery };
