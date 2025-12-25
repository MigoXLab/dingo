import { create } from 'zustand';
import { isElectron } from '@/utils/env';
import { WEB_DATA_SOURCE } from '@/constant';

interface DALStore {
    dal: DataAccessLayer | null;
    initDAL: () => void;
}

// 定义数据类型常量
export const DATA_TYPES = {
    INPUT_PATH: 'getInputPath',
    SUMMARY: 'getSummary',
    EVALUATION_LIST: 'getEvaluationList',
    EVALUATION_DETAIL: 'getEvaluationDetail',
} as const;

// 定义 ErrorTypeRatio 接口
interface ErrorTypeRatio {
    QUALITY_INEFFECTIVENESS: number;
    QUALITY_BAD_COMPLETENESS: number;
    QUALITY_BAD_UNDERSTANDABILITY: number;
    QUALITY_BAD_SIMILARITY: number;
    QUALITY_BAD_FLUENCY: number;
    QUALITY_BAD_RELEVANCE: number;
    QUALITY_BAD_SECURITY: number;
}

// 定义 Summary 接口
interface Summary {
    task_id: string;
    task_name: string;
    eval_group: string;
    input_path: string;
    output_path: string;
    create_time: string;
    score: number;
    num_good: number;
    num_bad: number;
    total: number;
    type_ratio: ErrorTypeRatio;
    name_ratio: Record<string, number>;
}

// 定义 EvaluationCategory 接口
interface EvaluationCategory {
    name: string;
    files: string[];
}

// 定义评估详情项的接口
interface EvaluationDetailItem {
    data_id: string;
    prompt: string;
    content: string;
    type_list: string[];
    name_list: string[];
    reason_list: string[];
}

// 定义每个方法的参数类型
type DataTypeParams = {
    [DATA_TYPES.INPUT_PATH]: undefined;
    [DATA_TYPES.SUMMARY]: { path: string };
    [DATA_TYPES.EVALUATION_LIST]: { dirPath: string };
    [DATA_TYPES.EVALUATION_DETAIL]: {
        currentPath: string;
        primaryName: string;
        secondaryNameList: string[];
    };
};

export interface DataAccessLayer {
    getData<K extends keyof DataTypeParams>(
        dataType: K,
        params: DataTypeParams[K]
    ): Promise<
        K extends typeof DATA_TYPES.SUMMARY
            ? Summary
            : K extends typeof DATA_TYPES.EVALUATION_LIST
              ? EvaluationCategory[]
              : K extends typeof DATA_TYPES.EVALUATION_DETAIL
                ? EvaluationDetailItem[]
                : any
    >;
    preloadData(dataTypes: (keyof DataTypeParams)[]): Promise<void>;

    getInputPath(): Promise<string>;
    getSummary(params: { path: string }): Promise<Summary>;
    getEvaluationList(params: {
        dirPath: string;
    }): Promise<EvaluationCategory[]>;
    getEvaluationDetail(params: {
        currentPath: string;
        primaryName: string;
        secondaryNameList: string[];
    }): Promise<EvaluationDetailItem[]>;
    getAllJsonlFiles(params: {
        currentPath: string;
    }): Promise<EvaluationDetailItem[]>;
    getAllJsonlFilePaths(params: {
        currentPath: string;
    }): Promise<string[]>;
}

// Electron 环境的实现
export class ElectronDAL implements DataAccessLayer {
    private cache: Map<string, any> = new Map();

    async getData<K extends keyof DataTypeParams>(
        dataType: K,
        params: DataTypeParams[K]
    ): Promise<any> {
        const cacheKey = this.getCacheKey(dataType, params);
        if (this.cache.has(cacheKey)) {
            return this.cache.get(cacheKey);
        }

        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const data = await (this as any)[dataType](params);
        this.cache.set(cacheKey, data);
        return data;
    }

    async preloadData(dataTypes: (keyof DataTypeParams)[]): Promise<void> {
        await Promise.all(
            dataTypes.map(type => this.getData(type, undefined as any))
        );
    }

    private getCacheKey(dataType: string, params?: any): string {
        return `${dataType}:${JSON.stringify(params)}`;
    }

    async getInputPath(): Promise<string> {
        return await window.electronAPI.getInputPath();
    }

    async getSummary(params: { path: string }): Promise<Summary> {
        return (await window.electronAPI.readJsonFile(params.path)) as Summary;
    }

    async getEvaluationList(params: {
        dirPath: string;
    }): Promise<EvaluationCategory[]> {
        return (await window.electronAPI.readDirectoryDingo(
            params.dirPath
        )) as EvaluationCategory[];
    }

    async getEvaluationDetail(params: {
        currentPath: string;
        primaryName: string;
        secondaryNameList: string[];
    }): Promise<EvaluationDetailItem[]> {
        return (await window.electronAPI.readJsonlFiles(
            params.currentPath,
            params.primaryName,
            params.secondaryNameList
        )) as EvaluationDetailItem[];
    }

    async getAllJsonlFiles(params: {
        currentPath: string;
    }): Promise<EvaluationDetailItem[]> {
        if (!window.electronAPI?.readAllJsonlFiles) {
            throw new Error(
                'readAllJsonlFiles is not available. Please restart the application.'
            );
        }
        return (await window.electronAPI.readAllJsonlFiles(
            params.currentPath
        )) as EvaluationDetailItem[];
    }

    async getAllJsonlFilePaths(params: {
        currentPath: string;
    }): Promise<string[]> {
        if (!window.electronAPI?.getAllJsonlFilePaths) {
            throw new Error(
                'getAllJsonlFilePaths is not available. Please restart the application.'
            );
        }
        return (await window.electronAPI.getAllJsonlFilePaths(
            params.currentPath
        )) as string[];
    }
}

interface DataSource {
    inputPath: string;
    data: {
        summary: {
            dataset_id: string;
            input_model: string;
            task_name: string;
            input_path: string;
            output_path: string;
            score: number;
            num_good: number;
            num_bad: number;
            total: number;
            type_ratio: {
                [key: string]: number;
            };
            name_ratio: {
                [key: string]: number;
            };
        };
        evaluationFileStructure: {
            name: string;
            files: string[];
        }[];
        evaluationDetailList: {
            [key: string]: {
                data_id: string;
                prompt: string;
                content: string;
                type_list: string[];
                name_list: string[];
                reason_list: string[];
            }[];
        };
    };
}

// Web 环境的实现
export class WebDAL implements DataAccessLayer {
    private dataSource: DataSource;

    constructor(dataSource: DataSource) {
        this.dataSource = dataSource;
    }

    async getData<K extends keyof DataTypeParams>(
        dataType: K,
        params: DataTypeParams[K]
    ): Promise<any> {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        return (this as any)[dataType](params);
    }

    async preloadData(dataTypes: (keyof DataTypeParams)[]): Promise<void> {
        // 在 Web 环境中，所有数据都已预加载，所以这里不需要做任何事情
    }

    async getInputPath(): Promise<string> {
        return this.dataSource.inputPath;
    }

    async getSummary(params: { path: string }): Promise<Summary> {
        return this.dataSource?.data?.summary as unknown as Summary;
    }

    async getEvaluationList(params: {
        dirPath: string;
    }): Promise<EvaluationCategory[]> {
        return this.dataSource?.data
            ?.evaluationFileStructure as EvaluationCategory[];
    }

    async getEvaluationDetail(params: {
        currentPath: string;
        primaryName: string;
        secondaryNameList: string[];
    }): Promise<EvaluationDetailItem[]> {
        let res = [] as EvaluationDetailItem[];
        if (this.dataSource?.data?.evaluationDetailList) {
            params.secondaryNameList.forEach(secondaryName => {
                res = res.concat(
                    this.dataSource?.data?.evaluationDetailList?.[
                        `${params.primaryName + '/' + secondaryName}` as string
                    ]
                );
            });
        }
        return res;
    }

    async getAllJsonlFiles(params: {
        currentPath: string;
    }): Promise<EvaluationDetailItem[]> {
        // 在 Web 环境中，返回所有 evaluationDetailList 中的数据
        let res = [] as EvaluationDetailItem[];
        if (this.dataSource?.data?.evaluationDetailList) {
            Object.entries(this.dataSource.data.evaluationDetailList).forEach(
                ([key, items]) => {
                    const itemsWithPath = items.map(item => ({
                        ...item,
                        _filePath: key,
                    }));
                    res = res.concat(itemsWithPath);
                }
            );
        }
        return res;
    }

    async getAllJsonlFilePaths(params: {
        currentPath: string;
    }): Promise<string[]> {
        // 在 Web 环境中，返回所有 evaluationDetailList 的键
        if (this.dataSource?.data?.evaluationDetailList) {
            return Object.keys(this.dataSource.data.evaluationDetailList);
        }
        return [];
    }
}

export function createDAL(
    isElectron: boolean,
    webDataSource?: any
): DataAccessLayer {
    if (isElectron) {
        return new ElectronDAL();
    } else {
        if (!webDataSource) {
            throw new Error('Web data source is required for web environment');
        }
        return new WebDAL(webDataSource);
    }
}

export const useDALStore = create<DALStore>(set => ({
    dal: null,
    initDAL: () => {
        const webDataSource = (window as any)?.[WEB_DATA_SOURCE];
        const dal = createDAL(isElectron(), webDataSource || {});
        set({ dal });
    },
}));
