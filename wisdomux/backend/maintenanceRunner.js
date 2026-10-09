'use strict';

const { AgentRegistry } = require('./agentRegistry');
const { TaskRecovery } = require('./taskRecovery');

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
}

module.exports = { MaintenanceRunner };
