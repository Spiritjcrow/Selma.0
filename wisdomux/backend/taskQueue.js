'use strict';

const { randomUUID } = require('node:crypto');

const CLAIMABLE_STATES = ['OBSERVED', 'DEFERRED'];

class TaskQueue {
  constructor(database, options = {}) {
    if (!database || typeof database.prepare !== 'function') {
      throw new TypeError('database with prepare() is required');
    }
    this.db = database;
    this.now = options.now || (() => new Date().toISOString());
    this.newId = options.newId || randomUUID;
  }

  enqueue(task) {
    if (!task || !task.taskId || !task.projectId || !task.title) {
      throw new TypeError('taskId, projectId, and title are required');
    }
    const createdAt = this.now();
    const dependencies = [...new Set(task.dependencies || [])];
    this.db.exec('BEGIN IMMEDIATE');
    try {
      this.db.prepare(
        `INSERT INTO wisdomux_tasks
          (task_id, project_id, parent_task_id, title, description, state,
           truth_state, priority, required_capability, approval_state,
           created_at, updated_at)
         VALUES (?, ?, ?, ?, ?, 'OBSERVED', ?, ?, ?, ?, ?, ?)`,
      ).run(
        task.taskId,
        task.projectId,
        task.parentTaskId || null,
        task.title,
        task.description || '',
        task.truthState || 'UNVERIFIED',
        task.priority ?? 50,
        task.requiredCapability || null,
        task.approvalState || 'NOT_REQUIRED',
        createdAt,
        createdAt,
      );
      const dependencyInsert = this.db.prepare(
        `INSERT INTO wisdomux_task_dependencies
          (task_id, depends_on_task_id, created_at)
         VALUES (?, ?, ?)`,
      );
      for (const dependencyId of dependencies) {
        dependencyInsert.run(task.taskId, dependencyId, createdAt);
      }
      this.#appendEvent({
        projectId: task.projectId,
        taskId: task.taskId,
        eventType: 'TASK_ENQUEUED',
        truthState: task.truthState || 'UNVERIFIED',
        payload: { priority: task.priority ?? 50, dependencies },
        createdAt,
      });
      this.db.exec('COMMIT');
      return this.#getTask(task.taskId);
    } catch (error) {
      this.db.exec('ROLLBACK');
      throw error;
    }
  }

  claimNext({ projectId, agentId }) {
    if (!projectId || !agentId) {
      throw new TypeError('projectId and agentId are required');
    }
    this.db.exec('BEGIN IMMEDIATE');
    try {
      const agent = this.db.prepare(
        `SELECT agent_id, status, capability_json
           FROM wisdomux_agents
          WHERE agent_id = ?`,
      ).get(agentId);
      if (!agent || !['ONLINE', 'BUSY'].includes(agent.status)) {
        throw new Error('agent is not available');
      }
      const grants = new Set(
        JSON.parse(agent.capability_json || '{}').grants || [],
      );
      const candidates = this.db.prepare(
        `SELECT *
           FROM wisdomux_tasks
          WHERE project_id = ?
            AND claimed_by_agent IS NULL
            AND state IN ('OBSERVED', 'DEFERRED')
          ORDER BY priority DESC, created_at ASC, task_id ASC`,
      ).all(projectId);
      let selected = null;
      for (const candidate of candidates) {
        if (
          candidate.required_capability &&
          !grants.has(candidate.required_capability)
        ) {
          continue;
        }
        const unfinished = this.db.prepare(
          `SELECT 1
             FROM wisdomux_task_dependencies AS dependency
             JOIN wisdomux_tasks AS prerequisite
               ON prerequisite.task_id = dependency.depends_on_task_id
            WHERE dependency.task_id = ?
              AND prerequisite.state <> 'COMPLETED'
            LIMIT 1`,
        ).get(candidate.task_id);
        if (!unfinished) {
          selected = candidate;
          break;
        }
      }
      if (!selected) {
        this.db.exec('COMMIT');
        return null;
      }
      const updatedAt = this.now();
      const result = this.db.prepare(
        `UPDATE wisdomux_tasks
            SET state = 'CLAIMED',
                claimed_by_agent = ?,
                updated_at = ?
          WHERE task_id = ?
            AND claimed_by_agent IS NULL
            AND state IN ('OBSERVED', 'DEFERRED')`,
      ).run(agentId, updatedAt, selected.task_id);
      if (Number(result.changes) !== 1) {
        throw new Error('task claim lost to another worker');
      }
      this.#appendEvent({
        projectId,
        taskId: selected.task_id,
        senderAgent: agentId,
        eventType: 'TASK_CLAIMED',
        truthState: selected.truth_state,
        payload: { previous_state: selected.state },
        createdAt: updatedAt,
      });
      this.db.exec('COMMIT');
      return this.#getTask(selected.task_id);
    } catch (error) {
      this.db.exec('ROLLBACK');
      throw error;
    }
  }

  #getTask(taskId) {
    return this.db.prepare(
      'SELECT * FROM wisdomux_tasks WHERE task_id = ?',
    ).get(taskId);
  }

  #appendEvent({
    projectId,
    taskId,
    senderAgent = null,
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
      projectId,
      taskId,
      senderAgent,
      eventType,
      truthState,
      JSON.stringify(payload || {}),
      createdAt,
    );
  }
}

module.exports = { CLAIMABLE_STATES, TaskQueue };
