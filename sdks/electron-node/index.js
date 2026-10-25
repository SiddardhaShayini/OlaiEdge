/**
 * @fastagent/edge-sdk
 * Drop-in Edge Agent Engine for Electron and Node.js Desktop Applications.
 * Zero external dependencies.
 */

const { spawn } = require('child_process');
const http = require('http');
const path = require('path');
const fs = require('fs');
const EventEmitter = require('events');

/**
 * Manages the background FastAgent Edge daemon child process.
 * Ties daemon lifecycle to parent Electron process (auto-terminates on crash/exit).
 */
class FastAgentDaemonProcess extends EventEmitter {
  /**
   * @param {Object} options
   * @param {string} [options.modelPath] Path to .gguf model or model ID
   * @param {number} [options.port=8085] Port to bind daemon
   * @param {number} [options.memoryBudgetMb] Maximum RAM ceiling in MB
   * @param {string} [options.licenseKey] Commercial developer license key
   * @param {string} [options.daemonBinaryPath] Path to fastagent-edge executable or python script
   */
  constructor(options = {}) {
    super();
    this.modelPath = options.modelPath || 'gemma-2b-q4.gguf';
    this.port = options.port || 8085;
    this.memoryBudgetMb = options.memoryBudgetMb;
    this.licenseKey = options.licenseKey;
    this.daemonBinaryPath = options.daemonBinaryPath || 'fastagent-edge';
    this.process = null;
    this.isReady = false;
  }

  /**
   * Spawns the headless daemon with parent-pid monitoring.
   * Resolves when HTTP /health is active.
   * @returns {Promise<string>} Base URL of daemon
   */
  start() {
    return new Promise((resolve, reject) => {
      const args = [
        'serve',
        '--model', this.modelPath,
        '--port', String(this.port),
        '--parent-pid', String(process.pid),
      ];

      if (this.memoryBudgetMb) {
        args.push('--memory-budget-mb', String(this.memoryBudgetMb));
      }
      if (this.licenseKey) {
        args.push('--license-key', this.licenseKey);
      }

      const isPython = this.daemonBinaryPath.endsWith('.py');
      const bin = isPython ? (process.platform === 'win32' ? 'python' : 'python3') : this.daemonBinaryPath;
      const cmdArgs = isPython ? [this.daemonBinaryPath, ...args] : args;

      this.process = spawn(bin, cmdArgs, {
        stdio: ['ignore', 'pipe', 'pipe'],
        detached: false,
      });

      this.process.stdout.on('data', (chunk) => {
        const text = chunk.toString();
        if (text.includes('Engine Status: ONLINE') || text.includes('Serving at http')) {
          this.isReady = true;
          this.emit('ready', `http://127.0.0.1:${this.port}`);
          resolve(`http://127.0.0.1:${this.port}`);
        }
      });

      this.process.stderr.on('data', (chunk) => {
        this.emit('log', chunk.toString());
      });

      this.process.on('error', (err) => {
        this.emit('error', err);
        reject(err);
      });

      this.process.on('exit', (code, signal) => {
        this.isReady = false;
        this.emit('exit', { code, signal });
      });

      // Poll health endpoint as fallback
      let retries = 30;
      const checkInterval = setInterval(() => {
        if (this.isReady) {
          clearInterval(checkInterval);
          return;
        }
        retries--;
        const req = http.get(`http://127.0.0.1:${this.port}/health`, (res) => {
          if (res.statusCode === 200) {
            this.isReady = true;
            clearInterval(checkInterval);
            resolve(`http://127.0.0.1:${this.port}`);
          }
        });
        req.on('error', () => {});
        req.end();

        if (retries <= 0) {
          clearInterval(checkInterval);
          reject(new Error(`Timed out waiting for FastAgent daemon on port ${this.port}`));
        }
      }, 500);
    });
  }

  /**
   * Gracefully stops the engine daemon.
   */
  stop() {
    if (this.process) {
      this.process.kill('SIGTERM');
      this.process = null;
      this.isReady = false;
    }
  }
}

/**
 * High-level FastAgent Client for desktop applications.
 * Communicates with the local Edge Agent Engine over loopback HTTP/SSE.
 */
class FastAgentClient {
  /**
   * @param {Object} [config]
   * @param {string} [config.baseUrl='http://127.0.0.1:8085']
   */
  constructor(config = {}) {
    this.baseUrl = config.baseUrl || 'http://127.0.0.1:8085';
    this.tools = new Map();
  }

  /**
   * Registers a client-side JavaScript tool executable by the agent.
   * @param {string} name Tool identifier
   * @param {string} description Tool purpose and argument format
   * @param {Function} fn Executable handler
   */
  registerTool(name, description, fn) {
    this.tools.set(name, { description, fn });
  }

  /**
   * Creates a tab/session-scoped client helper for multi-tab apps.
   * @param {string} sessionId Unique document or tab ID
   */
  session(sessionId) {
    return {
      turn: (prompt, options) => this.turn(prompt, { ...options, sessionId }),
      stream: (prompt, onToken, options) => this.stream(prompt, onToken, { ...options, sessionId }),
      ask: (prompt, options) => this.ask(prompt, { ...options, sessionId }),
      evict: () => this.manageSlot('evict', sessionId),
    };
  }

  /**
   * Runs a single conversational turn with slot cache reuse.
   */
  async turn(prompt, options = {}) {
    const payload = {
      prompt,
      session_id: options.sessionId || 'default',
      grammar: options.grammar,
      json_schema: options.jsonSchema,
      max_tokens: options.maxTokens || 160,
      temperature: options.temperature !== undefined ? options.temperature : 0.1,
    };
    return this._post('/v1/agent/turn', payload);
  }

  /**
   * Runs a structured prompt guaranteed to conform to the supplied JSON schema.
   */
  async runStructured(prompt, jsonSchema, options = {}) {
    const res = await this.turn(prompt, { ...options, jsonSchema });
    return res.parsed_json;
  }

  /**
   * Streams generation token-by-token via Server-Sent Events (SSE).
   * @param {string} prompt User message
   * @param {Function} onToken Callback(token: string)
   * @param {Object} [options]
   */
  stream(prompt, onToken, options = {}) {
    return new Promise((resolve, reject) => {
      const url = new URL(`${this.baseUrl}/v1/chat/completions`);
      const payload = JSON.stringify({
        prompt,
        stream: true,
        session_id: options.sessionId || 'default',
        grammar: options.grammar,
        json_schema: options.jsonSchema,
      });

      const req = http.request(
        url,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Content-Length': Buffer.byteLength(payload),
          },
        },
        (res) => {
          let buffer = '';
          res.on('data', (chunk) => {
            buffer += chunk.toString();
            const lines = buffer.split('\n');
            buffer = lines.pop(); // Keep trailing incomplete line

            for (const line of lines) {
              const trimmed = line.trim();
              if (trimmed.startsWith('data: ')) {
                const dataStr = trimmed.slice(6);
                if (dataStr === '[DONE]') {
                  resolve();
                  return;
                }
                try {
                  const parsed = JSON.parse(dataStr);
                  const token = parsed.choices?.[0]?.delta?.content;
                  if (token) onToken(token);
                } catch (e) {}
              }
            }
          });

          res.on('end', () => resolve());
        }
      );

      req.on('error', reject);
      req.write(payload);
      req.end();
    });
  }

  /**
   * Executes autonomous ReAct multi-step problem solving loop.
   */
  async ask(prompt, options = {}) {
    const payload = {
      prompt,
      session_id: options.sessionId || 'default',
      max_steps: options.maxSteps || 5,
      use_grammar: options.useGrammar || false,
    };
    const res = await this._post('/v1/agent/ask', payload);
    return res.result;
  }

  /**
   * Retrieves daemon status, memory budget consumption, and slot metrics.
   */
  async getStatus() {
    return this._get('/v1/status');
  }

  /**
   * Manages slot cache (list, compact, evict).
   */
  async manageSlot(action = 'list', sessionId = null) {
    return this._post('/v1/slots/manage', { action, session_id: sessionId });
  }

  /**
   * Activates commercial developer license.
   */
  async activateLicense(licenseKey) {
    return this._post('/v1/license/activate', { license_key: licenseKey });
  }

  _post(endpoint, body) {
    return new Promise((resolve, reject) => {
      const url = new URL(`${this.baseUrl}${endpoint}`);
      const data = JSON.stringify(body);
      const req = http.request(
        url,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Content-Length': Buffer.byteLength(data),
          },
        },
        (res) => {
          let raw = '';
          res.on('data', (c) => (raw += c.toString()));
          res.on('end', () => {
            try {
              const parsed = JSON.parse(raw);
              if (res.statusCode >= 400) {
                reject(new Error(parsed.message || parsed.error || `HTTP ${res.statusCode}`));
              } else {
                resolve(parsed);
              }
            } catch (e) {
              reject(e);
            }
          });
        }
      );
      req.on('error', reject);
      req.write(data);
      req.end();
    });
  }

  _get(endpoint) {
    return new Promise((resolve, reject) => {
      http.get(`${this.baseUrl}${endpoint}`, (res) => {
        let raw = '';
        res.on('data', (c) => (raw += c.toString()));
        res.on('end', () => {
          try {
            resolve(JSON.parse(raw));
          } catch (e) {
            reject(e);
          }
        });
      }).on('error', reject);
    });
  }
}

// Export both OlaiEdge (primary) and FastAgent (legacy) aliases
module.exports = {
  OlaiDaemonProcess: FastAgentDaemonProcess,
  OlaiClient: FastAgentClient,
  FastAgentDaemonProcess,
  FastAgentClient,
};
