# @fastagent/edge-sdk (Electron & Node.js)

Drop-in embeddable Edge Agent Engine for Electron desktop applications (VS Code forks, Obsidian plugins, custom productivity tools).

## Key Features

- **Zero Cloud Costs:** Local LLM execution with zero tokens billed.
- **No Consumer OOMs:** Automatic memory budgeting (`memoryBudgetMb`) and watchdog eviction.
- **Multi-Tab Slot Caching:** Tab-isolated conversation states with ~0ms system prompt cache hits.
- **Strict Grammar Outputs:** 100% syntactically valid JSON output for file edits and desktop UI controls.
- **Parent Process Watchdog:** Daemon automatically terminates when Electron exits.

## Quickstart in Electron

### 1. In `main.js` (Electron Main Process)

```javascript
const { app, BrowserWindow, ipcMain } = require('electron');
const { FastAgentDaemonProcess, FastAgentClient } = require('@fastagent/edge-sdk');
const path = require('path');

let daemon;
let client;

app.whenReady().then(async () => {
  // 1. Boot headless Edge Daemon bound to this process
  daemon = new FastAgentDaemonProcess({
    modelPath: path.join(__dirname, 'models/qwen2.5-1.5b-instruct-q4_k_m.gguf'),
    port: 8085,
    memoryBudgetMb: 2048, // Cap engine memory to 2GB
  });

  const endpoint = await daemon.start();
  console.log('FastAgent Edge Engine Online at:', endpoint);

  client = new FastAgentClient({ baseUrl: endpoint });

  createWindow();
});

// IPC Handler: Streaming AI completion to Renderer
ipcMain.handle('ai:stream', async (event, { prompt, tabId }) => {
  const tab = client.session(tabId);
  await tab.stream(prompt, (token) => {
    event.sender.send(`ai:token:${tabId}`, token);
  });
});

// IPC Handler: Grammar-constrained file diff
ipcMain.handle('ai:editCode', async (event, { prompt }) => {
  const schema = {
    type: 'object',
    properties: {
      file: { type: 'string' },
      action: { type: 'string', enum: ['replace', 'insert', 'delete'] },
      lines: { type: 'string' },
      diff: { type: 'string' }
    },
    required: ['file', 'action', 'diff']
  };
  return client.runStructured(prompt, schema);
});

app.on('before-quit', () => {
  if (daemon) daemon.stop();
});
```

### 2. In `renderer.js` (UI Layer)

```javascript
// Stream token chunks directly into the active editor or chat panel
window.api.onToken('tab-editor-1', (chunk) => {
  editor.insertAtCursor(chunk);
});
```
