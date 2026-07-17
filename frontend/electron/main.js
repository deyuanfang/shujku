// PersonalKB Electron Main Process
const { app, BrowserWindow, globalShortcut, Tray, Menu, nativeImage, ipcMain, dialog } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const http = require('http');

const isDev = process.argv.includes('--dev');
const PYTHON_PORT = 18765;
let mainWindow = null;
let pythonProcess = null;
let tray = null;

// ── Python Backend ──────────────────────────────────

function startPython() {
  const pythonCmd = isDev ? 'python' : path.join(process.resourcesPath, 'python', 'python.exe');
  const cwd = isDev
    ? path.join(__dirname, '..', '..', 'backend')
    : path.join(process.resourcesPath, 'backend');

  console.log(`Starting Python: ${pythonCmd} on port ${PYTHON_PORT}`);

  pythonProcess = spawn(pythonCmd, [
    '-m', 'uvicorn', 'app.main:app',
    '--host', '127.0.0.1', '--port', String(PYTHON_PORT),
    '--log-level', 'warning',
  ], { cwd, stdio: ['pipe', 'pipe', 'pipe'] });

  pythonProcess.stdout.on('data', d => console.log(`[Py] ${d}`));
  pythonProcess.stderr.on('data', d => console.error(`[Py] ${d}`));

  return new Promise(resolve => {
    const check = () => {
      http.get(`http://127.0.0.1:${PYTHON_PORT}/health`, res => {
        if (res.statusCode === 200) { console.log('Backend ready'); resolve(true); }
        else setTimeout(check, 500);
      }).on('error', () => setTimeout(check, 500));
    };
    setTimeout(check, 1000);
  });
}

function stopPython() {
  if (pythonProcess) { pythonProcess.kill(); pythonProcess = null; }
}

// ── Window ──────────────────────────────────────────

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400, height: 900, minWidth: 800, minHeight: 500,
    title: 'PersonalKB - 个人知识库',
    backgroundColor: '#030712',
    icon: path.join(__dirname, 'icon.png'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
    show: false,
  });

  const url = isDev ? 'http://localhost:5173' : `file://${path.join(__dirname, '..', 'dist', 'index.html')}`;
  mainWindow.loadURL(url);

  mainWindow.once('ready-to-show', () => mainWindow.show());

  mainWindow.on('close', e => {
    if (tray) { e.preventDefault(); mainWindow.hide(); }
  });

  mainWindow.on('closed', () => { mainWindow = null; });
}

// ── System Tray ─────────────────────────────────────

function createTray() {
  // Create a simple 16x16 icon programmatically
  const icon = nativeImage.createEmpty();
  tray = new Tray(icon.resize({ width: 16, height: 16 }));

  const contextMenu = Menu.buildFromTemplate([
    { label: '打开 PersonalKB', click: () => { if (mainWindow) mainWindow.show(); else createWindow(); } },
    { label: '快速笔记', click: () => { if (mainWindow) { mainWindow.show(); mainWindow.webContents.send('quick-note'); } } },
    { type: 'separator' },
    { label: '退出', click: () => { tray = null; app.quit(); } },
  ]);

  tray.setToolTip('PersonalKB - 个人知识库');
  tray.setContextMenu(contextMenu);
  tray.on('double-click', () => { if (mainWindow) mainWindow.show(); else createWindow(); });
}

// ── Global Shortcut ─────────────────────────────────

function registerShortcuts() {
  // Ctrl+Shift+N: quick note
  globalShortcut.register('CommandOrControl+Shift+N', () => {
    if (mainWindow) {
      mainWindow.show();
      mainWindow.webContents.send('quick-note');
    }
  });
  // Ctrl+Shift+K: search
  globalShortcut.register('CommandOrControl+Shift+K', () => {
    if (mainWindow) {
      mainWindow.show();
      mainWindow.webContents.send('quick-search');
    }
  });
}

// ── IPC Handlers ────────────────────────────────────

ipcMain.handle('get-version', () => app.getVersion());
ipcMain.handle('open-file-dialog', async (_, options) => {
  const result = await dialog.showOpenDialog(mainWindow, options || { properties: ['openFile', 'multiSelections'] });
  return result;
});

ipcMain.on('window-minimize', () => mainWindow?.minimize());
ipcMain.on('window-maximize', () => {
  if (mainWindow?.isMaximized()) mainWindow.unmaximize();
  else mainWindow?.maximize();
});
ipcMain.on('window-close', () => mainWindow?.close());

// ── App Lifecycle ───────────────────────────────────

app.whenReady().then(async () => {
  await startPython();
  createWindow();
  createTray();
  registerShortcuts();

  app.on('activate', () => {
    if (!mainWindow) createWindow();
    else mainWindow.show();
  });
});

app.on('window-all-closed', () => {
  stopPython();
  globalShortcut.unregisterAll();
  if (process.platform !== 'darwin') app.quit();
});

app.on('before-quit', () => {
  stopPython();
  globalShortcut.unregisterAll();
});

app.on('will-quit', () => {
  stopPython();
});
