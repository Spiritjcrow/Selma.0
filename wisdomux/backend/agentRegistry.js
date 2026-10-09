'use strict';

const { randomUUID } = require('node:crypto');

const HEARTBEAT_STATUSES = Object.freeze(['ONLINE', 'BUSY', 'DEGRADED']);

class AgentRegistry {
  constructor(database, options = {}) {
    if (!database || typeof database.prepare !== 'function') {
      throw new TypeError('database with prepare() is required');
    }
    this.db = database;
    this.now = options.now || (() => new Date().toISOString());
    this.newId = options.newId || randomUUID;
  }

  register({
    projectId,
    requestedBy,
    agentId,
    displayName,
    role,
    grants,
  }) {
    if (!projectId || !requestedBy || !agentId || !displayName || !role) {
      throw new TypeError(
        'projectId, requestedBy, agentId, displayName, and role are required',
      );
    }
    if (
      !Array.isArray(grants) ||
      grants.some((grant) => typeof grant !== 'string' || !grant)
    ) {
      throw new TypeError('grants must contain non-empty strings');
    }
    const normalizedGrants = [...new Set(grants)];

    this.db.exec('BEGIN IMMEDIATE');
    try {
      this.#requireCapability(requestedBy, 'agent.register');
      const timestamp = this.now();
      this.db.prepare(
        `INSERT INTO wisdomux_agents
          (agent_id, display_name, role, capability_json, status,
           last_seen_at, created_at)
         VALUES (?, ?, ?, ?, 'ONLINE', ?, ?)`,
      ).run(
        agentId,
        displayName,
        role,
        JSON.stringify({ grants: normalizedGrants }),
        timestamp,
        timestamp,
      );
      this.#appendEvent({
        projectId,
        senderAgent: requestedBy,
        eventType: 'AGENT_REGISTERED',
        payload: {
          agent_id: agentId,
          display_name: displayName,
          role,
          grants: normalizedGrants,
        },
        createdAt: timestamp,
      });
      this.db.exec('COMMIT');
      return this.#agent(agentId);
    } catch (error) {
      this.db.exec('ROLLBACK');
      throw error;
    }
  }

  heartbeat({ agentId, authenticatedAgentId, status = 'ONLINE' }) {
    if (!agentId || !authenticatedAgentId) {
      throw new TypeError('agentId and authenticatedAgentId are required');
    }
    if (agentId !== authenticatedAgentId) {
      throw new Error('heartbeat identity mismatch');
    }
    if (!HEARTBEAT_STATUSES.includes(status)) {
      throw new Error(`invalid heartbeat status: ${status}`);
    }

    this.db.exec('BEGIN IMMEDIATE');
    try {
      const agent = this.#agent(agentId);
      if (!agent) {
        throw new Error('agent is not registered');
      }
      if (agent.status === 'REVOKED') {
        throw new Error('revoked agent cannot send heartbeat');
      }
      const updated = this.db.prepare(
        `UPDATE wisdomux_agents
            SET status = ?, last_seen_at = ?
          WHERE agent_id = ?
            AND status <> 'REVOKED'`,
      ).run(status, this.now(), agentId);
      if (Number(updated.changes) !== 1) {
        throw new Error('heartbeat lost to another coordinator');
      }
      this.db.exec('COMMIT');
      return this.#agent(agentId);
    } catch (error) {
      this.db.exec('ROLLBACK');
      throw error;
    }
  }

  expireStale({ projectId, requestedBy, cutoff }) {
    if (!projectId || !requestedBy || !cutoff) {
      throw new TypeError('projectId, requestedBy, and cutoff are required');
    }
    const cutoffDate = new Date(cutoff);
    if (Number.isNaN(cutoffDate.getTime())) {
      throw new TypeError('cutoff must be a valid timestamp');
    }
    const normalizedCutoff = cutoffDate.toISOString();

    this.db.exec('BEGIN IMMEDIATE');
    try {
      this.#requireCapability(requestedBy, 'agent.monitor');
      const stale = this.db.prepare(
        `SELECT agent_id, status, last_seen_at
           FROM wisdomux_agents
          WHERE status IN ('ONLINE', 'BUSY', 'DEGRADED')
            AND (last_seen_at IS NULL OR last_seen_at < ?)
          ORDER BY agent_id`,
      ).all(normalizedCutoff);
      const timestamp = this.now();
      const expired = [];
      for (const agent of stale) {
        const updated = this.db.prepare(
          `UPDATE wisdomux_agents
              SET status = 'OFFLINE'
            WHERE agent_id = ?
              AND status = ?
              AND (last_seen_at IS NULL OR last_seen_at < ?)`,
        ).run(agent.agent_id, agent.status, normalizedCutoff);
        if (Number(updated.changes) !== 1) {
          throw new Error('stale-agent update lost to another coordinator');
        }
        this.#appendEvent({
          projectId,
          senderAgent: requestedBy,
          eventType: 'AGENT_MARKED_STALE',
          payload: {
            agent_id: agent.agent_id,
            previous_status: agent.status,
            cutoff: normalizedCutoff,
            last_seen_at: agent.last_seen_at,
          },
          createdAt: timestamp,
        });
        expired.push(agent.agent_id);
      }
      this.db.exec('COMMIT');
      return expired;
    } catch (error) {
      this.db.exec('ROLLBACK');
      throw error;
    }
  }

  #agent(agentId) {
    return this.db.prepare(
      'SELECT * FROM wisdomux_agents WHERE agent_id = ?',
    ).get(agentId);
  }

  #requireCapability(agentId, capability) {
    const agent = this.#agent(agentId);
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

  #appendEvent({
    projectId,
    senderAgent,
    eventType,
    payload,
    createdAt,
  }) {
    this.db.prepare(
      `INSERT INTO wisdomux_events
        (event_id, project_id, sender_agent, event_type, truth_state,
         payload_json, evidence_json, created_at)
       VALUES (?, ?, ?, ?, 'REAL', ?, '[]', ?)`,
    ).run(
      this.newId(),
      projectId,
      senderAgent,
      eventType,
      JSON.stringify(payload),
      createdAt,
    );
  }
}

module.exports = { AgentRegistry, HEARTBEAT_STATUSES };
