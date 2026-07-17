// PersonalKB Preload Script
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  getVersion: () => ipcRenderer.invoke('get-version'),
  openFileDialog: (opts) => ipcRenderer.invoke('open-file-dialog', opts),
  minimizeWindow: () => ipcRenderer.send('window-minimize'),
  maximizeWindow: () => ipcRenderer.send('window-maximize'),
  closeWindow: () => ipcRenderer.send('window-close'),

  // Listen for main process events
  onQuickNote: (cb) => ipcRenderer.on('quick-note', () => cb()),
  onQuickSearch: (cb) => ipcRenderer.on('quick-search', () => cb()),
});
