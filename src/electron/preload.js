const { contextBridge, ipcRenderer } = require("electron");

const backendApi = {
  getStatus: () => ipcRenderer.invoke("backend:getState"),
  waitForReady: () => ipcRenderer.invoke("backend:waitForReady"),
  restart: () => ipcRenderer.invoke("backend:restart"),
  onStatusChange: (callback) => {
    ipcRenderer.send("backend:subscribe");
    const listener = (_event, status) => {
      callback(status);
    };
    ipcRenderer.on("backend:state", listener);
    return () => {
      ipcRenderer.removeListener("backend:state", listener);
    };
  },
};

contextBridge.exposeInMainWorld("api", {
  backend: backendApi,
});
