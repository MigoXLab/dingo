import { ElectronAPI } from '@electron-toolkit/preload';

declare global {
    interface Window {
        electronAPI: {
            readDirectory: (dirPath: string) => Promise<string[]>;
            selectDirectory: () => Promise<string>;
            readFile: (filePath: string) => Promise<string>;
            readJsonFile: (filePath: string) => Promise<Record<string, any>>;
            readDirectoryDingo: (dirPath: string) => Promise<any>;
            readJsonlFiles: (
                dirPath: string,
                primaryName: string,
                secondaryNameList: string[]
            ) => Promise<any[]>;
            readAllJsonlFiles: (dirPath: string) => Promise<any[]>;
            getAllJsonlFilePaths: (dirPath: string) => Promise<string[]>;
            getInputPath: () => Promise<string>;
        };
    }
}
