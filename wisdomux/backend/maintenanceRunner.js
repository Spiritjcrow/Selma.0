'use strict';

const { AgentRegistry, HEARTBEAT_STATUSES } = require('./agentRegistry');
const { RECOVERABLE_CLAIM_STATES, TaskRecovery } = require('./taskRecovery');

class MaintenanceRunner {
  constructor(database, options = {}) {
    if (!database || typeof database.prepare !== 'function') {
      throw new TypeError('database with prepare() is required');
    }
    const sharedOptions = {
      now: options.now,
      newId: options.newId,
    };
    this.registry = new AgentRegistry(database, sharedOptions);
    this.recovery = new TaskRecovery(database, {
      ...sharedOptions,
      sweepLimit: options.sweepLimit,
    });
    this.db = database;
    this.sweepLimit = options.sweepLimit ?? 50;
  }

  runOnce({ projectId, requestedBy, cutoff }) {
    if (!projectId || !requestedBy || !cutoff) {
      throw new TypeError('projectId, requestedBy, and cutoff are required');
    }
    const cutoffDate = new Date(cutoff);
    if (Number.isNaN(cutoffDate.getTime())) {
      throw new TypeError('cutoff must be a valid timestamp');
    }
    const normalizedCutoff = cutoffDate.toISOString();
    const preview = this.previewOnce({
      projectId,
      requestedBy,
      cutoff: normalizedCutoff,
    });
    if (!preview.ready) {
      throw new Error(preview.blockers.join('; '));
    }
    const expiredAgents = this.registry.expireStale({
      projectId,
      requestedBy,
      cutoff: normalizedCutoff,
    });
    const recoveredTasks = this.recovery.sweepStale({
      projectId,
      requestedBy,
      reason: `owner heartbeat expired before ${normalizedCutoff}`,
      evidenceRefs: [
        `maintenance://stale-agent-sweep/${normalizedCutoff}`,
      ],
    });
    return {
      cutoff: normalizedCutoff,
      expiredAgents,
      recoveredTasks,
    };
  }

  previewOnce({ projectId, requestedBy, cutoff }) {
    if (!projectId || !requestedBy || !cutoff) {
      throw new TypeError('projectId, requestedBy, and cutoff are required');
    }
    const cutoffDate = new Date(cutoff);
    if (Number.isNaN(cutoffDate.getTime())) {
      throw new TypeError('cutoff must be a valid timestamp');
    }
    const normalizedCutoff = cutoffDate.toISOString();
    const coordinator = this.db.prepare(
      `SELECT status, capability_json
         FROM wisdomux_agents
        WHERE agent_id = ?`,
    ).get(requestedBy);
    if (!coordinator || !['ONLINE', 'BUSY'].includes(coordinator.status)) {
      throw new Error('agent is not available');
    }
    const grants = new Set(
      JSON.parse(coordinator.capability_json || '{}').grants || [],
    );
    for (const capability of ['agent.monitor', 'task.recover_stale']) {
      if (!grants.has(capability)) {
        throw new Error(`missing capability: ${capability}`);
      }
    }
    const activePlaceholders = HEARTBEAT_STATUSES.map(() => '?').join(', ');
    const expiredRows = this.db.prepare(
      `SELECT agent_id, status, last_seen_at
         FROM wisdomux_agents
        WHERE status IN (${activePlaceholders})
          AND (last_seen_at IS NULL OR last_seen_at < ?)
        ORDER BY agent_id`,
    ).all(...HEARTBEAT_STATUSES, normalizedCutoff);
    const expiredIds = new Set(expiredRows.map((row) => row.agent_id));
    const statePlaceholders = RECOVERABLE_CLAIM_STATES
      .map(() => '?')
      .join(', ');
    const taskRows = this.db.prepare(
      `SELECT task.task_id, task.claimed_by_agent, task.state,
              task.truth_state, task.approval_state, agent.status
         FROM wisdomux_tasks AS task
         JOIN wisdomux_agents AS agent
           ON agent.agent_id = task.claimed_by_agent
        WHERE task.project_id = ?
          AND task.state IN (${statePlaceholders})
          AND (
            agent.status IN ('OFFLINE', 'REVOKED')
            OR (
              agent.status IN (${activePlaceholders})
              AND (agent.last_seen_at IS NULL OR agent.last_seen_at < ?)
            )
          )
        ORDER BY task.priority DESC, task.updated_at ASC, task.task_id ASC
        LIMIT ?`,
    ).all(
      projectId,
      ...RECOVERABLE_CLAIM_STATES,
      ...HEARTBEAT_STATUSES,
      normalizedCutoff,
      this.sweepLimit,
    );
    const blockers = expiredIds.has(requestedBy)
      ? ['coordinator would be marked offline before task recovery']
      : [];
    return {
      truthState: 'PREVIEW',
      ready: blockers.length === 0,
      blockers,
      projectId,
      cutoff: normalizedCutoff,
      sweepLimit: this.sweepLimit,
      expiredAgents: expiredRows.map((row) => ({
        agentId: row.agent_id,
        previousStatus: row.status,
        lastSeenAt: row.last_seen_at,
      })),
      recoveredTasks: taskRows.map((row) => ({
        taskId: row.task_id,
        previousOwner: row.claimed_by_agent,
        currentOwnerStatus: row.status,
        projectedOwnerStatus: expiredIds.has(row.claimed_by_agent)
          ? 'OFFLINE'
          : row.status,
        previousState: row.state,
        previousTruthState: row.truth_state,
        approvalState: row.approval_state,
      })),
    };
  }
}

module.exports = { MaintenanceRunner };
