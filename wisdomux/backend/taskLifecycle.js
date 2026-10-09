'use strict';

const { randomUUID } = require('node:crypto');

const LIFECYCLE_TRANSITIONS = Object.freeze({
  CLAIMED: Object.freeze({
    toState: 'PLANNED',
    capability: 'task.plan',
  }),
  PLANNED: Object.freeze({
    toState: 'EXECUTING',
    capability: 'task.execute',
  }),
  EXECUTING: Object.freeze({
    toState: 'VERIFYING',
    capability: 'task.verify',
  }),
  VERIFYING: Object.freeze({
    toState: 'REPORTED',
    capability: 'task.report',
  }),
});

class TaskLifecycle {
  constructor(database, options = {}) {
    if (!database || typeof database.prepare !== 'function') {
      throw new TypeError('database with prepare() is required');
    }
    this.db = database;
    this.now = options.now || (() => new Date().toISOString());
    this.newId = options.newId || randomUUID;
  }

  transition({ taskId, agentId, toState, summary, evidenceRefs }) {
    if (!taskId || !agentId || !toState || !summary) {
      throw new TypeError(
        'taskId, agentId, toState, and summary are required',
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

      const task = this.db.prepare(
        'SELECT * FROM wisdomux_tasks WHERE task_id = ?',
      ).get(taskId);
      if (!task || task.claimed_by_agent !== agentId) {
        throw new Error('task is not claimed by agent');
      }

      const transition = LIFECYCLE_TRANSITIONS[task.state];
      if (!transition || transition.toState !== toState) {
        throw new Error(
          `invalid lifecycle transition: ${task.state} -> ${toState}`,
        );
      }
      const grants = new Set(
        JSON.parse(agent.capability_json || '{}').grants || [],
      );
      if (!grants.has(transition.capability)) {
        throw new Error(`missing capability: ${transition.capability}`);
      }
      if (
        ['EXECUTING', 'VERIFYING', 'REPORTED'].includes(toState) &&
        !['NOT_REQUIRED', 'APPROVED'].includes(task.approval_state)
      ) {
        throw new Error('task approval does not allow execution');
      }

      const timestamp = this.now();
      const updated = this.db.prepare(
        `UPDATE wisdomux_tasks
            SET state = ?, updated_at = ?
          WHERE task_id = ?
            AND claimed_by_agent = ?
            AND state = ?`,
      ).run(toState, timestamp, taskId, agentId, task.state);
      if (Number(updated.changes) !== 1) {
        throw new Error('task transition lost to another coordinator');
      }
      this.db.prepare(
        `INSERT INTO wisdomux_events
          (event_id, project_id, task_id, sender_agent, event_type,
           truth_state, payload_json, evidence_json, created_at)
         VALUES (?, ?, ?, ?, 'TASK_STATE_TRANSITIONED', ?, ?, ?, ?)`,
      ).run(
        this.newId(),
        task.project_id,
        taskId,
        agentId,
        task.truth_state,
        JSON.stringify({
          from_state: task.state,
          to_state: toState,
          summary,
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
}

module.exports = { LIFECYCLE_TRANSITIONS, TaskLifecycle };
