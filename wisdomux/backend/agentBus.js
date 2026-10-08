'use strict';

const TRUTH_STATES = new Set([
  'REAL',
  'PREVIEW',
  'INFERRED',
  'UNVERIFIED',
  'BLOCKED',
  'DEGRADED',
]);

class AgentBus {
  constructor(options = {}) {
    this.now = options.now || (() => new Date().toISOString());
    this.maxSeenMessages = options.maxSeenMessages || 4096;
    this.connections = new Map();
    this.seenMessages = new Set();
    this.seenOrder = [];
  }

  attach(socket, { agentId, projectIds }) {
    if (!socket || typeof socket.send !== 'function') {
      throw new TypeError('socket with send() is required');
    }
    if (!agentId || !Array.isArray(projectIds) || projectIds.length === 0) {
      throw new TypeError('agentId and at least one projectId are required');
    }
    this.connections.set(socket, {
      agentId,
      projectIds: new Set(projectIds),
    });
  }

  detach(socket) {
    this.connections.delete(socket);
  }

  receive(socket, rawMessage) {
    const owner = this.connections.get(socket);
    if (!owner) {
      return this.#reject(socket, 1008, 'connection is not registered');
    }
    let message;
    try {
      message = JSON.parse(rawMessage);
    } catch {
      return this.#reject(socket, 1007, 'message is not valid JSON');
    }
    const validationError = this.#validateEnvelope(message);
    if (validationError) {
      return this.#reject(socket, 1008, validationError);
    }
    if (message.sender_agent !== owner.agentId) {
      return this.#reject(socket, 1008, 'sender does not own connection');
    }
    if (!owner.projectIds.has(message.project_id)) {
      return this.#reject(socket, 1008, 'sender is not authorized for project');
    }
    if (
      message.expires_at &&
      Date.parse(message.expires_at) <= Date.parse(this.now())
    ) {
      return this.#reject(socket, 1008, 'message has expired');
    }
    if (this.seenMessages.has(message.message_id)) {
      return { delivered: 0, duplicate: true };
    }

    const recipients = [];
    for (const [candidateSocket, candidate] of this.connections.entries()) {
      if (candidateSocket === socket) {
        continue;
      }
      if (!candidate.projectIds.has(message.project_id)) {
        continue;
      }
      if (
        message.recipient_agent &&
        candidate.agentId === message.recipient_agent
      ) {
        recipients.push(candidateSocket);
      } else if (
        !message.recipient_agent &&
        message.broadcast_scope === 'PROJECT'
      ) {
        recipients.push(candidateSocket);
      }
    }

    this.#remember(message.message_id);
    const encoded = JSON.stringify(message);
    for (const recipient of recipients) {
      recipient.send(encoded);
    }
    return { delivered: recipients.length, duplicate: false };
  }

  #validateEnvelope(message) {
    if (!message || typeof message !== 'object' || Array.isArray(message)) {
      return 'message must be an object';
    }
    if (message.protocol_version !== 'wisdomux.agent-message.v1') {
      return 'unsupported protocol version';
    }
    for (const field of [
      'message_id',
      'project_id',
      'task_id',
      'sender_agent',
      'intent',
      'created_at',
    ]) {
      if (typeof message[field] !== 'string' || message[field].length === 0) {
        return `${field} is required`;
      }
    }
    if (!TRUTH_STATES.has(message.truth_state)) {
      return 'truth_state is invalid';
    }
    const hasRecipient =
      typeof message.recipient_agent === 'string' &&
      message.recipient_agent.length > 0;
    const hasBroadcast =
      typeof message.broadcast_scope === 'string' &&
      message.broadcast_scope.length > 0;
    if (hasRecipient === hasBroadcast) {
      return 'exactly one recipient or broadcast scope is required';
    }
    if (hasBroadcast && message.broadcast_scope !== 'PROJECT') {
      return 'broadcast scope is not authorized';
    }
    if (Number.isNaN(Date.parse(message.created_at))) {
      return 'created_at is invalid';
    }
    if (
      message.expires_at != null &&
      Number.isNaN(Date.parse(message.expires_at))
    ) {
      return 'expires_at is invalid';
    }
    return null;
  }

  #remember(messageId) {
    this.seenMessages.add(messageId);
    this.seenOrder.push(messageId);
    while (this.seenOrder.length > this.maxSeenMessages) {
      this.seenMessages.delete(this.seenOrder.shift());
    }
  }

  #reject(socket, code, reason) {
    if (socket && typeof socket.close === 'function') {
      socket.close(code, reason);
    }
    throw new Error(reason);
  }
}

module.exports = { AgentBus };
