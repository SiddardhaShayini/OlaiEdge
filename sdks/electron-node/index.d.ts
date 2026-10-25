export interface DaemonOptions {
  modelPath?: string;
  port?: number;
  memoryBudgetMb?: number;
  licenseKey?: string;
  daemonBinaryPath?: string;
}

export declare class FastAgentDaemonProcess {
  constructor(options?: DaemonOptions);
  start(): Promise<string>;
  stop(): void;
  on(event: 'ready', listener: (url: string) => void): this;
  on(event: 'log', listener: (log: string) => void): this;
  on(event: 'error', listener: (err: Error) => void): this;
  on(event: 'exit', listener: (info: { code: number; signal: string }) => void): this;
}

export interface TurnOptions {
  sessionId?: string;
  grammar?: string;
  jsonSchema?: Record<string, any>;
  maxTokens?: number;
  temperature?: number;
}

export interface TurnResponse {
  output: string;
  parsed_json?: any;
  session_id: string;
  prompt_eval_ms: number;
  turn_count: number;
}

export declare class FastAgentClient {
  constructor(config?: { baseUrl?: string });
  registerTool(name: string, description: string, fn: Function): void;
  session(sessionId: string): {
    turn(prompt: string, options?: TurnOptions): Promise<TurnResponse>;
    stream(prompt: string, onToken: (token: string) => void, options?: TurnOptions): Promise<void>;
    ask(prompt: string, options?: { maxSteps?: number; useGrammar?: boolean }): Promise<string>;
    evict(): Promise<any>;
  };
  turn(prompt: string, options?: TurnOptions): Promise<TurnResponse>;
  runStructured<T = any>(prompt: string, jsonSchema: Record<string, any>, options?: TurnOptions): Promise<T>;
  stream(prompt: string, onToken: (token: string) => void, options?: TurnOptions): Promise<void>;
  ask(prompt: string, options?: { sessionId?: string; maxSteps?: number; useGrammar?: boolean }): Promise<string>;
  getStatus(): Promise<any>;
  manageSlot(action?: 'list' | 'compact' | 'evict', sessionId?: string): Promise<any>;
  activateLicense(licenseKey: string): Promise<any>;
}
