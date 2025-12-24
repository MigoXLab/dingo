import { app, shell, BrowserWindow, ipcMain, dialog } from 'electron';
import { join } from 'path';
import path from 'path';
import { electronApp, optimizer, is } from '@electron-toolkit/utils';
import icon from '../../resources/logo.svg?asset';
import fs from 'fs/promises';
import minimist from 'minimist';

function createWindow(): void {
    // Create the browser window.
    const mainWindow = new BrowserWindow({
        width: 1520,
        height: 960,
        show: false,
        autoHideMenuBar: true,
        title: 'Dingo',
        ...(process.platform === 'linux' ? { icon } : {}),
        webPreferences: {
            preload: join(__dirname, '../preload/index.js'),
            sandbox: false,
            contextIsolation: true,
        },
    });

    mainWindow.on('ready-to-show', () => {
        mainWindow.show();
    });

    mainWindow.webContents.setWindowOpenHandler(details => {
        shell.openExternal(details.url);
        return { action: 'deny' };
    });

    // HMR for renderer base on electron-vite cli.
    // Load the remote URL for development or the local html file for production.

    try {
        if (is.dev && process?.env?.['ELECTRON_RENDERER_URL']) {
            mainWindow.loadURL(process.env['ELECTRON_RENDERER_URL']);
        } else {
            mainWindow.loadFile(join(__dirname, '../renderer/index.html'));
        }
    } catch (error) {
        console.error('Error loading window:', error);
        // 确保加载本地文件作为后备方案
        mainWindow
            .loadFile(join(__dirname, '../renderer/index.html'))
            .catch(err => {
                console.error('Failed to load local file:', err);
            });
    }

    ipcMain.handle('open-external', (event, url: string) => {
        mainWindow.webContents.setWindowOpenHandler(details => {
            shell.openExternal(details.url);
            return { action: 'deny' };
        });
    });
}

// This method will be called when Electron has finished
// initialization and is ready to create browser windows.
// Some APIs can only be used after this event occurs.
app.whenReady().then(() => {
    // Set app user model id for windows
    electronApp.setAppUserModelId('com.electron');

    // Default open or close DevTools by F12 in development
    // and ignore CommandOrControl + R in production.
    // see https://github.com/alex8088/electron-toolkit/tree/master/packages/utils
    app.on('browser-window-created', (_, window) => {
        optimizer.watchWindowShortcuts(window);
    });

    // IPC test
    ipcMain.on('ping', () => console.log('pong'));

    ipcMain.handle('read-file', async (event, filePath: string) => {
        try {
            const content = await fs.readFile(filePath, 'utf-8');
            return content;
        } catch (error) {
            console.error('Error reading file:', error);
            throw error;
        }
    });

    // Add IPC handlers for file explorer
    ipcMain.handle('read-directory', async (event, dirPath) => {
        try {
            const files = await fs.readdir(dirPath);
            const itemsInfo = await Promise.all(
                files.map(async file => {
                    const fullPath = join(dirPath, file);
                    const stats = await fs.stat(fullPath);
                    return {
                        name: file,
                        isDirectory: stats.isDirectory(),
                        size: stats.size,
                        mtime: stats.mtime,
                    };
                })
            );
            return itemsInfo;
        } catch (error) {
            console.error('Error reading directory:', error);
            throw error;
        }
    });

    ipcMain.handle('select-directory', async () => {
        const result = await dialog.showOpenDialog({
            properties: ['openDirectory'],
        });
        if (result.canceled) {
            return null;
        }
        return result.filePaths[0];
    });

    ipcMain.handle('read-json-file', async (event, filePath: string) => {
        try {
            const content = await fs.readFile(filePath, 'utf-8');
            return JSON.parse(content);
        } catch (error) {
            console.error('Error reading JSON file:', error);
            throw error;
        }
    });

    ipcMain.handle('read-directory-dingo', async (event, dirPath) => {
        try {
            console.log('read-directory-dingo', dirPath);
            const items = await fs.readdir(dirPath, { withFileTypes: true });
            console.log('read-directory-dingo-items', items);
            const structure = [] as unknown[];

            for (const item of items) {
                if (item.isDirectory()) {
                    const files = await fs.readdir(
                        path.join(dirPath, item.name)
                    );
                    const jsonlFiles = files.filter(file =>
                        file.endsWith('.jsonl')
                    );
                    structure.push({
                        name: item.name,
                        files: jsonlFiles,
                    });
                }
            }
            console.log('read-directory-dingo-finish', items);
            return structure;
        } catch (error) {
            console.error('Error reading directory:', error);
            throw error;
        }
    });

    ipcMain.handle(
        'read-jsonl-files',
        async (event, dirPath, primaryName, secondaryNameList) => {
            try {
                let allData = [] as unknown[];
                for (const secondaryName of secondaryNameList) {
                    const filePath = path.join(
                        dirPath,
                        primaryName,
                        `${secondaryName}`
                    );
                    const fileContent = await fs.readFile(filePath, 'utf-8');
                    const lines = fileContent.trim().split('\n');
                    const parsedData = lines.map(line => JSON.parse(line));
                    allData = [...allData, ...parsedData];
                }
                return allData;
            } catch (error) {
                console.error('Error reading JSONL files:', error);
                throw error;
            }
        }
    );

    // 通用的递归遍历 jsonl 文件的辅助函数
    async function traverseJsonlFiles<T>(
        dirPath: string,
        processFile: (
            fullPath: string,
            relativePath: string
        ) => Promise<T | null>
    ): Promise<T[]> {
        const results: T[] = [];

        async function traverseDirectory(
            currentPath: string,
            relativePath: string = ''
        ): Promise<void> {
            try {
                const items = await fs.readdir(currentPath, {
                    withFileTypes: true,
                });

                for (const item of items) {
                    const fullPath = path.join(currentPath, item.name);
                    const newRelativePath = relativePath
                        ? `${relativePath}/${item.name}`
                        : item.name;

                    if (item.isDirectory()) {
                        // 递归遍历子目录
                        await traverseDirectory(fullPath, newRelativePath);
                    } else if (
                        item.isFile() &&
                        item.name.endsWith('.jsonl') &&
                        item.name !== 'summary.json'
                    ) {
                        // 处理 jsonl 文件
                        try {
                            const result = await processFile(
                                fullPath,
                                newRelativePath
                            );
                            if (result !== null) {
                                results.push(result);
                            }
                        } catch (error) {
                            console.error(
                                `Error processing file ${fullPath}:`,
                                error
                            );
                        }
                    }
                }
            } catch (error) {
                console.error(`Error reading directory ${currentPath}:`, error);
            }
        }

        await traverseDirectory(dirPath);
        return results;
    }

    // 递归获取所有 jsonl 文件的路径列表（相对路径）
    async function getAllJsonlFilePathsRecursive(
        dirPath: string
    ): Promise<string[]> {
        const filePaths = await traverseJsonlFiles<string>(
            dirPath,
            async (_, relativePath) => relativePath
        );
        return filePaths.sort();
    }

    ipcMain.handle(
        'get-all-jsonl-file-paths',
        async (event, dirPath: string) => {
            try {
                return await getAllJsonlFilePathsRecursive(dirPath);
            } catch (error) {
                console.error('Error getting all JSONL file paths:', error);
                throw error;
            }
        }
    );

    // 修改 readAllJsonlFilesRecursive，为每个数据项添加文件路径信息
    async function readAllJsonlFilesRecursiveWithPath(
        dirPath: string
    ): Promise<any[]> {
        const allDataArrays = await traverseJsonlFiles<any[]>(
            dirPath,
            async (fullPath, relativePath) => {
                try {
                    const fileContent = await fs.readFile(fullPath, 'utf-8');
                    const lines = fileContent
                        .trim()
                        .split('\n')
                        .filter(line => line.trim());
                    const parsedData = lines
                        .map(line => {
                            try {
                                const data = JSON.parse(line);
                                // 为每个数据项添加文件路径信息
                                return {
                                    ...data,
                                    _filePath: relativePath,
                                };
                            } catch (e) {
                                console.error(
                                    `Error parsing line in ${fullPath}:`,
                                    e
                                );
                                return null;
                            }
                        })
                        .filter(item => item !== null);
                    return parsedData;
                } catch (error) {
                    console.error(`Error reading file ${fullPath}:`, error);
                    return null;
                }
            }
        );

        // 展平所有数组
        return allDataArrays.flat();
    }

    ipcMain.handle('read-all-jsonl-files', async (event, dirPath: string) => {
        try {
            return await readAllJsonlFilesRecursiveWithPath(dirPath);
        } catch (error) {
            console.error('Error reading all JSONL files:', error);
            throw error;
        }
    });

    ipcMain.handle('get-input-path', () => {
        const argv = minimist(process?.argv?.slice(2));
        const inputPath = argv.input;
        return inputPath || null;
    });

    createWindow();

    app.on('activate', function () {
        // On macOS it's common to re-create a window in the app when the
        // dock icon is clicked and there are no other windows open.
        if (BrowserWindow.getAllWindows().length === 0) createWindow();
    });
});

// Quit when all windows are closed, except on macOS. There, it's common
// for applications and their menu bar to stay active until the user quits
// explicitly with Cmd + Q.
app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
        app.quit();
    }
});

// In this file you can include the rest of your app"s specific main process
// code. You can also put them in separate files and require them here.
