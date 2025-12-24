import React, { useState, useEffect, useMemo } from 'react';
import { Table } from 'antd';
import { ColumnsType } from 'antd/es/table';
import { useDALStore } from '@/store/dal';
import { FormattedMessage } from 'react-intl';
import { SummaryData } from '@/pages/main-home/components/summary-data-table';
import FilterCascader from './filter-cascader';
import HighlightText from './HightLightText';

interface DetailTableProps {
    summary: SummaryData;
    currentPath: string;
    detailPathList: {
        primaryName: string;
        secondaryNameList: string[];
    }[];
    allDataPath: {
        primaryName: string;
        secondaryNameList: string[];
    }[];
    defaultErrorTypes?: string[];
    defaultErrorNames?: string[];
}

interface DataItem {
    [key: string]: any; // eslint-disable-line @typescript-eslint/no-explicit-any
}

const DetailTable: React.FC<DetailTableProps> = ({ currentPath }) => {
    const [data, setData] = useState<DataItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [jsonlFilePaths, setJsonlFilePaths] = useState<string[]>([]);
    const dal = useDALStore(state => state.dal);
    const [current, setCurrent] = useState({
        currentPage: 1,
        pageSize: 20,
    });
    const [filter, setFilter] = useState<{
        filePath?: string;
    }>({});

    useEffect(() => {
        const loadData = async () => {
            try {
                setLoading(true);

                // 获取所有 jsonl 文件路径列表
                const filePaths =
                    (await dal?.getAllJsonlFilePaths?.({
                        currentPath,
                    })) || [];
                setJsonlFilePaths(filePaths);

                // 直接读取所有 jsonl 文件（排除 summary.json）
                const allData: DataItem[] =
                    ((await dal?.getAllJsonlFiles?.({
                        currentPath,
                    })) as DataItem[]) || [];

                setData(allData);
                setCurrent({
                    ...current,
                    currentPage: 1,
                });
            } catch (error) {
                console.error('Error loading data:', error);
            } finally {
                setLoading(false);
            }
        };

        loadData();
    }, [currentPath]);

    const handleFilter = (filePath: string) => {
        setFilter({ filePath });
        setCurrent({
            ...current,
            currentPage: 1,
        });
    };

    const filterData = useMemo(() => {
        const selectedFilePath = filter?.filePath;
        if (selectedFilePath && selectedFilePath !== 'all') {
            // 根据文件路径筛选数据
            return data?.filter(i => {
                const itemFilePath = i?._filePath;
                return itemFilePath === selectedFilePath;
            });
        } else {
            // 显示全部数据
            return data;
        }
    }, [data, filter]);

    // 动态生成列配置
    const columns: ColumnsType<DataItem> = useMemo(() => {
        if (!filterData || filterData.length === 0) {
            return [];
        }

        // 收集所有唯一的键，排除 _filePath 字段
        const allKeys = new Set<string>();
        filterData.forEach(item => {
            Object.keys(item).forEach(key => {
                // 过滤掉 _filePath 字段
                if (key !== '_filePath') {
                    allKeys.add(key);
                }
            });
        });

        // 生成列配置
        const generatedColumns: ColumnsType<DataItem> = Array.from(allKeys).map(
            key => {
                return {
                    title: key,
                    dataIndex: key,
                    key: key,
                    render: (value: unknown, record) => {
                        if (key === 'content') {
                            return (
                                <HighlightText
                                    text={
                                        typeof value === 'string'
                                            ? value.slice(0, 10000)
                                            : '-'
                                    }
                                    highlight={record.reason_list || ''}
                                    showHighlight={false}
                                />
                            );
                        }
                        // 如果是对象，显示为格式化的 JSON
                        if (
                            typeof value === 'object' &&
                            value !== null &&
                            !Array.isArray(value)
                        ) {
                            return (
                                <HighlightText
                                    text={JSON.stringify(value).slice(0, 10000)}
                                    highlight={record.reason_list || ''}
                                    showHighlight={false}
                                />
                            );
                        }
                        // 如果是数组，显示为 JSON
                        if (Array.isArray(value)) {
                            return (
                                <span
                                    className="select-text"
                                    style={{
                                        wordBreak: 'break-word',
                                        whiteSpace: 'pre-wrap',
                                    }}
                                >
                                    {JSON.stringify(value)}
                                </span>
                            );
                        }
                        // 如果是字符串，直接显示
                        if (typeof value === 'string') {
                            return (
                                <span
                                    style={{
                                        wordBreak: 'break-word',
                                        whiteSpace: 'pre-wrap',
                                    }}
                                >
                                    {value || '-'}
                                </span>
                            );
                        }
                        // 其他类型直接显示
                        return (
                            <span
                                style={{
                                    wordBreak: 'break-word',
                                    whiteSpace: 'pre-wrap',
                                }}
                            >
                                {String(value ?? '-')}
                            </span>
                        );
                    },
                };
            }
        );

        return generatedColumns;
    }, [filterData]);

    return (
        <>
            <div className="flex items-center">
                <FilterCascader
                    jsonlFilePaths={jsonlFilePaths}
                    onFilter={handleFilter}
                />
                <span className="text-[#121316]/[0.8] text-base ml-2">{`${filterData?.length || 0} 条数据`}</span>
            </div>
            <Table<DataItem>
                columns={columns}
                dataSource={filterData}
                loading={loading}
                className="mt-4"
                rowKey={(record, index) => {
                    return `${record?._filePath}_${index}`;
                }}
                pagination={{
                    pageSize: current?.pageSize,
                    showQuickJumper: true,
                    current: current?.currentPage,
                    showTotal: total => (
                        <FormattedMessage id="total.data" values={{ total }} />
                    ),
                }}
                onChange={pagination => {
                    if (current?.pageSize !== pagination.pageSize) {
                        setCurrent({
                            currentPage: 1,
                            pageSize: pagination.pageSize || 10,
                        });
                    } else {
                        setCurrent({
                            currentPage: pagination.current || 1,
                            pageSize: pagination.pageSize || 10,
                        });
                    }
                }}
                scroll={{ x: 'max-content' }}
                components={{
                    body: {
                        cell: (
                            props: React.TdHTMLAttributes<HTMLTableCellElement>
                        ) => (
                            <td
                                {...props}
                                style={{
                                    ...props.style,
                                    whiteSpace: 'normal',
                                    wordBreak: 'break-word',
                                    maxWidth: '500px',
                                    minWidth: '100px',
                                }}
                            />
                        ),
                    },
                }}
            />
        </>
    );
};

export default DetailTable;
