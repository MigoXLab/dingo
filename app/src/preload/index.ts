import { contextBridge, ipcRenderer } from 'electron';

// Custom APIs for renderer
const api = {
    readDirectory: (dirPath: string): Promise<string[]> =>
        ipcRenderer.invoke('read-directory', dirPath),
    selectDirectory: (): Promise<string | undefined> =>
        ipcRenderer.invoke('select-directory'),
    readFile: (filePath: string): Promise<string> =>
        ipcRenderer.invoke('read-file', filePath),
    readJsonFile: (filePath: string): Promise<any> =>
        ipcRenderer.invoke('read-json-file', filePath),
    readDirectoryDingo: (dirPath: string): Promise<string[]> =>
        ipcRenderer.invoke('read-directory-dingo', dirPath),
    readJsonlFiles: (
        dirPath: string,
        primaryName: string,
        secondaryNameList: string[]
    ): Promise<any[]> =>
        ipcRenderer.invoke(
            'read-jsonl-files',
            dirPath,
            primaryName,
            secondaryNameList
        ),
    readAllJsonlFiles: (dirPath: string): Promise<any[]> =>
        ipcRenderer.invoke('read-all-jsonl-files', dirPath),
    getAllJsonlFilePaths: (dirPath: string): Promise<string[]> =>
        ipcRenderer.invoke('get-all-jsonl-file-paths', dirPath),
    getInputPath: (): Promise<string | null> =>
        ipcRenderer.invoke('get-input-path'),
    openExternal: (url: string) => ipcRenderer.invoke('open-external', url),
};

// Use `contextBridge` APIs to expose Electron APIs to
// renderer only if context isolation is enabled, otherwise
// just add to the DOM global.
console.log('process.contextIsolated', process.contextIsolated);
if (process.contextIsolated) {
    try {
        contextBridge.exposeInMainWorld('electron', api);
        contextBridge.exposeInMainWorld('electronAPI', api);
    } catch (error) {
        console.error(error);
    }
} else {
    // @ts-ignore (define in dts)
    window.electron = api;
    // @ts-ignore (define in dts)
    window.electronAPI = api;
}
