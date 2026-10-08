'use strict';

const { randomUUID } = require('node:crypto');

class CrewAllocator {
  constructor(database, options = {}) {
    if (!database || typeof database.prepare !== 'function') {
      throw new TypeError('database with prepare() is required');
    }
    this.db = database;
    this.now = options.now || (() => new Date().toISOString());
    this.newId = options.newId || randomUUID;
  }

  assign({ taskId, requestedBy }) {
    if (!taskId || !requestedBy) {
      throw new TypeError('taskId and requestedBy are required');
    }
    this.db.exec('BEGIN IMMEDIATE');
    try {
      this.#requireCapability(requestedBy, 'crew.assign');
      const task = this.db.prepare(
        'SELECT * FROM wisdomux_tasks WHERE task_id = ?',
      ).get(taskId);
      if (!task) {
        throw new Error('task does not exist');
      }
      if (
        !['OBSERVED', 'DEFERRED'].includes(task.state) ||
        task.claimed_by_agent
      ) {
        throw new Error('task is not available for crew assignment');
      }
      const candidates = this.#eligibleAgents(task.required_capability);
      if (candidates.length === 0) {
        this.db.exec('COMMIT');
        return null;
      }
      candidates.sort(
        (left, right) =>
          left.active_count - right.active_count ||
          left.agent_id.localeCompare(right.agent_id),
      );
      const selected = candidates[0];
      const timestamp = this.now();
      const update = this.db.prepare(
        `UPDATE wisdomux_tasks
            SET state = 'CLAIMED',
                claimed_by_agent = ?,
                updated_at = ?
          WHERE task_id = ?
            AND claimed_by_agent IS NULL
            AND state IN ('OBSERVED', 'DEFERRED')`,
      ).run(selected.agent_id, timestamp, taskId);
      if (Number(update.changes) !== 1) {
        throw new Error('task assignment lost to another coordinator');
      }
      this.db.prepare(
        `INSERT INTO wisdomux_events
          (event_id, project_id, task_id, sender_agent, event_type,
           truth_state, payload_json, evidence_json, created_at)
         VALUES (?, ?, ?, ?, 'CREW_ROLE_ASSIGNED', ?, ?, '[]', ?)`,
      ).run(
        this.newId(),
        task.project_id,
        task.task_id,
        requestedBy,
        task.truth_state,
        JSON.stringify({
          assigned_agent: selected.agent_id,
          assigned_role: selected.role,
          required_capability: task.required_capability,
          active_task_count: selected.active_count,
        }),
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

  #eligibleAgents(requiredCapability) {
    const rows = this.db.prepare(
      `SELECT agent.agent_id,
              agent.role,
              agent.capability_json,
              COUNT(task.task_id) AS active_count
         FROM wisdomux_agents AS agent
         LEFT JOIN wisdomux_tasks AS task
           ON task.claimed_by_agent = agent.agent_id
          AND task.state IN ('CLAIMED', 'PLANNED', 'EXECUTING', 'VERIFYING')
        WHERE agent.status = 'ONLINE'
        GROUP BY agent.agent_id, agent.role, agent.capability_json`,
    ).all();
    return rows.filter((row) => {
      if (!requiredCapability) return true;
      const capabilities = JSON.parse(row.capability_json || '{}');
      return (
        Array.isArray(capabilities.grants) &&
        capabilities.grants.includes(requiredCapability)
      );
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
    const capabilities = JSON.parse(agent.capability_json || '{}');
    if (
      !Array.isArray(capabilities.grants) ||
      !capabilities.grants.includes(capability)
    ) {
      throw new Error(`missing capability: ${capability}`);
    }
  }
}

module.exports = { CrewAllocator };
