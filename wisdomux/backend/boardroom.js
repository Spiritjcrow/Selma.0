'use strict';

const { randomUUID } = require('node:crypto');

class Boardroom {
  constructor(database, options = {}) {
    if (!database || typeof database.prepare !== 'function') {
      throw new TypeError('database with prepare() is required');
    }
    this.db = database;
    this.now = options.now || (() => new Date().toISOString());
    this.newId = options.newId || randomUUID;
  }

  halt({ taskId, requestedBy, reason, requiresHuman = false }) {
    if (!taskId || !requestedBy || !reason) {
      throw new TypeError('taskId, requestedBy, and reason are required');
    }
    return this.#transaction(() => {
      this.#requireCapability(requestedBy, 'boardroom.halt');
      const task = this.#getTask(taskId);
      if (!task) {
        throw new Error('task does not exist');
      }
      if (['COMPLETED', 'CANCELLED'].includes(task.state)) {
        throw new Error('terminal task cannot be halted');
      }
      if (task.state === 'BLOCKED') {
        throw new Error('task is already halted');
      }
      const timestamp = this.now();
      this.db.prepare(
        `UPDATE wisdomux_tasks
            SET state = 'BLOCKED',
                truth_state = 'BLOCKED',
                approval_state = ?,
                updated_at = ?
          WHERE task_id = ?`,
      ).run(requiresHuman ? 'PENDING' : 'NOT_REQUIRED', timestamp, taskId);
      this.#appendEvent({
        task,
        senderAgent: requestedBy,
        eventType: 'BOARDROOM_HALTED',
        truthState: 'BLOCKED',
        payload: {
          previous_state: task.state,
          reason,
          requires_human: Boolean(requiresHuman),
        },
        createdAt: timestamp,
      });
      return this.#getTask(taskId);
    });
  }

  resume({
    taskId,
    resolvedBy,
    resolution,
    humanApproved = false,
  }) {
    if (!taskId || !resolvedBy || !resolution) {
      throw new TypeError('taskId, resolvedBy, and resolution are required');
    }
    return this.#transaction(() => {
      this.#requireCapability(resolvedBy, 'boardroom.resume');
      const task = this.#getTask(taskId);
      if (!task) {
        throw new Error('task does not exist');
      }
      if (task.state !== 'BLOCKED') {
        throw new Error('task is not halted');
      }
      if (task.approval_state === 'PENDING' && !humanApproved) {
        throw new Error('human approval is required');
      }
      const approvalState =
        task.approval_state === 'PENDING' ? 'APPROVED' : 'NOT_REQUIRED';
      const timestamp = this.now();
      this.db.prepare(
        `UPDATE wisdomux_tasks
            SET state = 'DEFERRED',
                truth_state = 'UNVERIFIED',
                approval_state = ?,
                claimed_by_agent = NULL,
                updated_at = ?
          WHERE task_id = ?`,
      ).run(approvalState, timestamp, taskId);
      this.#appendEvent({
        task,
        senderAgent: resolvedBy,
        eventType: 'BOARDROOM_RESUMED',
        truthState: 'UNVERIFIED',
        payload: {
          resolution,
          human_approved: Boolean(humanApproved),
          resumed_state: 'DEFERRED',
        },
        createdAt: timestamp,
      });
      return this.#getTask(taskId);
    });
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

  #getTask(taskId) {
    return this.db.prepare(
      'SELECT * FROM wisdomux_tasks WHERE task_id = ?',
    ).get(taskId);
  }

  #appendEvent({
    task,
    senderAgent,
    eventType,
    truthState,
    payload,
    createdAt,
  }) {
    this.db.prepare(
      `INSERT INTO wisdomux_events
        (event_id, project_id, task_id, sender_agent, event_type, truth_state,
         payload_json, evidence_json, created_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, '[]', ?)`,
    ).run(
      this.newId(),
      task.project_id,
      task.task_id,
      senderAgent,
      eventType,
      truthState,
      JSON.stringify(payload),
      createdAt,
    );
  }

  #transaction(operation) {
    this.db.exec('BEGIN IMMEDIATE');
    try {
      const result = operation();
      this.db.exec('COMMIT');
      return result;
    } catch (error) {
      this.db.exec('ROLLBACK');
      throw error;
    }
  }
}

module.exports = { Boardroom };
