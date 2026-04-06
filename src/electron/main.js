const { app, BrowserWindow, ipcMain } = require("electron");
const { spawn } = require("child_process");
const http = require("http");
const path = require("path");

const isDev = process.env.NODE_ENV === "development";

const BackendState = {
  STARTING: "starting",
  READY: "ready",
  ERROR: "error",
  STOPPED: "stopped",
};

let pythonProcess = null;
let mainWindow = null;
let backendState = BackendState.STOPPED;
let backendMessage = null;
let backendLaunchId = 0;
let backendStartupPromise = null;
const backendStateSubscribers = new Set();
const backendReadyResolvers = new Set();
let backendDiagnostics = createBackendDiagnostics(0);

function createBackendDiagnostics(launchId) {
  return {
    launchId,
    startedAt: null,
    readyAt: null,
    startupDurationMs: null,
    healthCheckAttempts: 0,
    lastHealthCheckAt: null,
    lastHealthCheckDurationMs: null,
    healthCheckTotalDurationMs: null,
    lastExitCode: null,
    lastExitSignal: null,
    events: [],
  };
}

function appendBackendEvent(type, data = {}) {
  const entry = {
    type,
    at: new Date().toISOString(),
    message: null,
    ...data,
  };
  backendDiagnostics.events = [entry, ...backendDiagnostics.events].slice(0, 25);
  console.log(`[BackendLifecycle] ${JSON.stringify(entry)}`);
}

function getBackendStatus() {
  return {
    state: backendState,
    message: backendMessage,
    diagnostics: {
      ...backendDiagnostics,
      events: [...backendDiagnostics.events],
    },
  };
}

function broadcastBackendState() {
  const payload = getBackendStatus();
  for (const contents of backendStateSubscribers) {
    if (contents.isDestroyed()) {
      backendStateSubscribers.delete(contents);
      continue;
    }
    contents.send("backend:state", payload);
  }
}

function resolveBackendReady() {
  if (backendState === BackendState.STARTING) return;
  const payload = getBackendStatus();
  for (const resolve of backendReadyResolvers) {
    resolve(payload);
  }
  backendReadyResolvers.clear();
}

function setBackendState(state, message = null) {
  backendState = state;
  backendMessage = message;
  broadcastBackendState();
  resolveBackendReady();
}

function getBackendCommand() {
  if (isDev) {
    const scriptPath = path.join(app.getAppPath(), "src/python/main.py");
    return {
      executable: "python3",
      args: [scriptPath],
      cwd: app.getAppPath(),
      env: {
        ...process.env,
        PYTHONPATH: path.dirname(scriptPath),
      },
    };
  }

  const resourcesPath = process.resourcesPath;
  const isWin = process.platform === "win32";
  const pythonExe = isWin
    ? path.join(resourcesPath, "backend", "python.exe")
    : path.join(resourcesPath, "backend", "bin", "python");
  const backendEntry = path.join(
    resourcesPath,
    "backend",
    "app",
    "src",
    "python",
    "main.py"
  );

  return {
    executable: pythonExe,
    args: [backendEntry],
    cwd: path.join(resourcesPath, "backend"),
    env: {
      ...process.env,
      STUDYBOT_USER_DATA: app.getPath("userData"),
      STUDYBOT_APP_ROOT: resourcesPath,
      STUDYBOT_HOST: "127.0.0.1",
      STUDYBOT_PORT: "7777",
      PYTHONPATH: [
        path.join(resourcesPath, "backend", "lib"),
        path.join(resourcesPath, "backend", "app", "src", "python"),
      ].join(isWin ? ";" : ":"),
      PYTHONHOME: path.join(resourcesPath, "backend"),
    },
  };
}

function startPython(launchId) {
  const cmd = getBackendCommand();

  pythonProcess = spawn(cmd.executable, cmd.args, {
    cwd: cmd.cwd,
    env: cmd.env,
  });

  appendBackendEvent("spawn", {
    message: "Python backend spawned",
    pid: pythonProcess.pid ?? null,
    scriptPath: cmd.args[0],
  });

  pythonProcess.on("error", (err) => {
    if (launchId !== backendLaunchId) {
      return;
    }
    appendBackendEvent("spawn-error", {
      message: err.message,
    });
    setBackendState(BackendState.ERROR, err.message);
    console.error(`[Python] failed to start: ${err.message}`);
    console.error("[Python] Ensure python3 is installed and on PATH.");
  });

  pythonProcess.stdout.on("data", (data) => {
    console.log(`[Python] ${data.toString().trim()}`);
  });

  pythonProcess.stderr.on("data", (data) => {
    console.error(`[Python stderr] ${data.toString().trim()}`);
  });

  pythonProcess.on("close", (code, signal) => {
    if (launchId !== backendLaunchId) {
      return;
    }
    pythonProcess = null;
    backendDiagnostics.lastExitCode = code;
    backendDiagnostics.lastExitSignal = signal ?? null;
    const message = `Exited with code ${code}`;
    appendBackendEvent("exit", {
      message,
      signal: signal ?? null,
    });
    if (backendState === BackendState.READY) {
      setBackendState(BackendState.ERROR, message);
    } else {
      setBackendState(BackendState.STOPPED, message);
    }
    console.log(`[Python] process exited with code ${code}`);
  });
}

async function bootBackend() {
  if (backendStartupPromise) {
    return backendStartupPromise;
  }

  const launchId = backendLaunchId + 1;
  backendLaunchId = launchId;
  backendDiagnostics = createBackendDiagnostics(launchId);
  backendDiagnostics.startedAt = new Date().toISOString();

  if (pythonProcess) {
    pythonProcess.kill();
    pythonProcess = null;
  }

  appendBackendEvent("launch", {
    message: "Launching backend",
  });
  setBackendState(BackendState.STARTING, "Launching backend");
  startPython(launchId);

  backendStartupPromise = (async () => {
    try {
      const result = await waitForBackend();
      if (launchId === backendLaunchId) {
        backendDiagnostics.readyAt = new Date().toISOString();
        backendDiagnostics.startupDurationMs = result.totalDurationMs;
        setBackendState(BackendState.READY, null);
        appendBackendEvent("ready", {
          message: "Backend ready",
          attempt: result.attempts,
          durationMs: result.totalDurationMs,
        });
        console.log("[Electron] Backend ready");
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      if (launchId === backendLaunchId) {
        appendBackendEvent("startup-error", {
          message,
        });
        setBackendState(BackendState.ERROR, message);
        console.error(`[Electron] ${message}`);
      }
    } finally {
      if (launchId === backendLaunchId) {
        backendStartupPromise = null;
      }
    }

    return getBackendStatus();
  })();

  return backendStartupPromise;
}

function waitForBackend(maxAttempts = 30, intervalMs = 1000) {
  return new Promise((resolve, reject) => {
    let attempts = 0;
    const check = () => {
      attempts++;
      const attemptStartedAt = Date.now();
      const req = http.get("http://127.0.0.1:7777/health", (res) => {
        const durationMs = Date.now() - attemptStartedAt;
        backendDiagnostics.healthCheckAttempts = attempts;
        backendDiagnostics.lastHealthCheckAt = new Date().toISOString();
        backendDiagnostics.lastHealthCheckDurationMs = durationMs;
        backendDiagnostics.healthCheckTotalDurationMs =
          backendDiagnostics.startedAt === null
            ? durationMs
            : Date.now() - new Date(backendDiagnostics.startedAt).getTime();
        appendBackendEvent("health-check", {
          message: `Health check status ${res.statusCode}`,
          attempt: attempts,
          durationMs,
          statusCode: res.statusCode,
        });
        if (res.statusCode === 200) {
          resolve({
            attempts,
            totalDurationMs: backendDiagnostics.healthCheckTotalDurationMs ?? durationMs,
          });
        } else if (attempts < maxAttempts) {
          setTimeout(check, intervalMs);
        } else {
          reject(new Error(`Backend health check failed after ${maxAttempts} attempts`));
        }
      });
      req.on("error", (error) => {
        const durationMs = Date.now() - attemptStartedAt;
        backendDiagnostics.healthCheckAttempts = attempts;
        backendDiagnostics.lastHealthCheckAt = new Date().toISOString();
        backendDiagnostics.lastHealthCheckDurationMs = durationMs;
        backendDiagnostics.healthCheckTotalDurationMs =
          backendDiagnostics.startedAt === null
            ? durationMs
            : Date.now() - new Date(backendDiagnostics.startedAt).getTime();
        appendBackendEvent("health-check-error", {
          message: error.message,
          attempt: attempts,
          durationMs,
        });
        if (attempts < maxAttempts) {
          setTimeout(check, intervalMs);
        } else {
          reject(new Error(`Backend unreachable after ${maxAttempts} attempts`));
        }
      });
      req.end();
    };
    check();
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  const url = isDev
    ? "http://localhost:5173"
    : `file://${path.join(app.getAppPath(), "dist/index.html")}`;

  mainWindow.loadURL(url);
}

ipcMain.handle("backend:getState", () => getBackendStatus());

ipcMain.handle("backend:waitForReady", () => {
  if (backendState !== BackendState.STARTING) {
    return getBackendStatus();
  }
  return new Promise((resolve) => {
    backendReadyResolvers.add(resolve);
  });
});

ipcMain.handle("backend:restart", async () => {
  return bootBackend();
});

ipcMain.on("backend:subscribe", (event) => {
  const contents = event.sender;
  backendStateSubscribers.add(contents);
  const remove = () => backendStateSubscribers.delete(contents);
  contents.once("destroyed", remove);
  contents.send("backend:state", getBackendStatus());
});

app.whenReady().then(async () => {
  await bootBackend();
  createWindow();
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("quit", () => {
  if (pythonProcess) {
    pythonProcess.kill();
  }
});
