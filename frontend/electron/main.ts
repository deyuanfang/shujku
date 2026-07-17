const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const { spawn } = require('child_process');

let mainWindow = null;
let pythonProcess = null;
const isDev = process.env.NODE_ENV !== 'production';
const PYTHON_PORT = 8765;

function startPythonBackend() {
  // In production, use bundled Python; in dev, use system Python
  const pythonCmd = isDev ? 'python' : path.join(process.resourcesPath, 'python', 'python.exe');
  const scriptPath = isDev
    ? path.join(__dirname, '..', '..', 'backend', 'app')
    : path.join(process.resourcesPath, 'backend', 'app');

  console.log(`Starting Python backend: ${pythonCmd} -m uvicorn app.main:app --port ${PYTHON_PORT}`);

  pythonProcess = spawn(pythonCmd, [
    '-m', 'uvicorn',
    'app.main:app',
    '--host', '127.0.0.1',
    '--port', String(PYTHON_PORT),
  ], {
    cwd: isDev ? path.join(__dirname, '..', '..', 'backend') : path.join(process.resourcesPath, 'backend'),
    stdio: ['pipe', 'pipe', 'pipe'],
  });

  pythonProcess.stdout.on('data', (data) => {
    console.log(`[Python] ${data}`);
  });

  pythonProcess.stderr.on('data', (data) => {
    console.error(`[Python Error] ${data}`);
  });

  pythonProcess.on('close', (code) => {
    console.log(`Python backend exited with code ${code}`);
  });

  return new Promise((resolve) => {
    // Wait for backend to be ready
    const checkReady = async () => {
      try {
        const http = require('http');
        const req = http.get(`http://127.0.0.1:${PYTHON_PORT}/health`, (res) => {
          if (res.statusCode === 200) {
            console.log('Python backend is ready!');
            resolve(true);
          } else {
            setTimeout(checkReady, 500);
          }
        });
        req.on('error', () => setTimeout(checkReady, 500));
      } catch {
        setTimeout(checkReady, 500);
      }
    };
    setTimeout(checkReady, 1000);
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 900,
    minHeight: 600,
    title: 'PersonalKB - 个人知识库',
    backgroundColor: '#030712',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
    frame: true,
    titleBarStyle: 'default',
    icon: path.join(__dirname, 'icon.png'),
  });

  if (isDev) {
    mainWindow.loadURL('http://localhost:5173');
    mainWindow.webContents.openDevTools({ mode: 'detach' });
  } else {
    mainWindow.loadFile(path.join(__dirname, '..', 'dist', 'index.html'));
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

app.whenReady().then(async () => {
  await startPythonBackend();
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (pythonProcess) {
    pythonProcess.kill('SIGTERM');
    setTimeout(() => {
      if (pythonProcess && !pythonProcess.killed) {
        pythonProcess.kill('SIGKILL');
      }
    }, 3000);
  }
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  if (pythonProcess) {
    pythonProcess.kill('SIGTERM');
  }
});
