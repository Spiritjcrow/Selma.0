'use strict';

const { createHash } = require('node:crypto');
const { isIP } = require('node:net');

class SelmaOSRuntimeError extends Error {
  constructor(message, { status = null, runtimeResult = null } = {}) {
    super(message);
    this.name = 'SelmaOSRuntimeError';
    this.status = status;
    this.runtimeResult = runtimeResult;
  }
}

class SelmaOSAdapter {
  constructor(options = {}) {
    const url = new URL(
      options.baseUrl || 'http://127.0.0.1:8765',
    );
    if (url.protocol !== 'http:') {
      throw new TypeError('SelmaOS adapter requires an HTTP loopback endpoint');
    }
    if (
      url.username ||
      url.password ||
      url.pathname !== '/' ||
      url.search ||
      url.hash ||
      !isLoopback(url.hostname)
    ) {
      throw new TypeError('SelmaOS adapter requires a clean loopback base URL');
    }
    this.baseUrl = url.origin;
    this.fetch = options.fetch || globalThis.fetch;
    this.timeoutMs = options.timeoutMs || 5000;
    if (typeof this.fetch !== 'function') {
      throw new TypeError('fetch implementation is required');
    }
  }

  status() {
    return this.#request('/api/selma0/status/v1', {
      method: 'GET',
    });
  }

  execute({
    taskId,
    tool,
    arguments: toolArguments = {},
    approvalState = 'NOT_REQUIRED',
  }) {
    if (!taskId || !tool) {
      throw new TypeError('taskId and tool are required');
    }
    if (
      !toolArguments ||
      typeof toolArguments !== 'object' ||
      Array.isArray(toolArguments)
    ) {
      throw new TypeError('arguments must be an object');
    }
    return this.#request('/api/selma0/tools/execute/v1', {
      method: 'POST',
      body: JSON.stringify({
        tool,
        arguments: toolArguments,
        approved: approvalState === 'APPROVED',
        request_id: requestIdForTask(taskId),
      }),
    });
  }

  async #request(path, options) {
    const response = await this.fetch(this.baseUrl + path, {
      ...options,
      headers: {
        accept: 'application/json',
        'content-type': 'application/json',
        origin: new URL(this.baseUrl).origin,
        ...(options.headers || {}),
      },
      signal: AbortSignal.timeout(this.timeoutMs),
    });
    let result;
    try {
      result = await response.json();
    } catch (error) {
      throw new SelmaOSRuntimeError('SelmaOS returned invalid JSON', {
        status: response.status,
      });
    }
    if (!response.ok) {
      throw new SelmaOSRuntimeError(
        result.error || `SelmaOS request failed with HTTP ${response.status}`,
        { status: response.status, runtimeResult: result },
      );
    }
    return result;
  }
}

function isLoopback(hostname) {
  const value = String(hostname || '').toLowerCase();
  if (value === 'localhost' || value === '::1') {
    return true;
  }
  if (isIP(value) === 4) {
    return value.split('.')[0] === '127';
  }
  return false;
}

function requestIdForTask(taskId) {
  const value = `wisdomux:${String(taskId).trim()}`;
  if (value.length <= 128) {
    return value;
  }
  const digest = createHash('sha256').update(value).digest('hex');
  return `wisdomux:${digest}`;
}

module.exports = {
  SelmaOSAdapter,
  SelmaOSRuntimeError,
  isLoopback,
  requestIdForTask,
};
