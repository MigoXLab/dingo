import React, { useState, useEffect, useMemo } from 'react';
import { Table, Tooltip, Pagination, Switch } from 'antd';
import { ColumnsType } from 'antd/es/table';
import { useDALStore } from '@/store/dal';
import { FormattedMessage } from 'react-intl';
import { SummaryData } from '@/pages/main-home/components/summary-data-table';
import { EyeOutlined, EyeInvisibleOutlined } from '@ant-design/icons';
import { uniqBy } from 'lodash';
import FilterCascader from './filter-cascader';
import DetailCard from './detail-card';
import Empty from '@/components/empty';
import IconFont from './icon-font';
import cls from 'classnames';
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
    data_id: string;
    prompt: string;
    content: string;
    type_list: string[];
    name_list: string[];
    reason_list: (string | string[])[];
}

const DetailTable: React.FC<DetailTableProps> = ({
    summary,
    currentPath,
    detailPathList,
    allDataPath,
    defaultErrorTypes,
    defaultErrorNames,
}) => {
    const [data, setData] = useState<DataItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [errorTypes, setErrorTypes] = useState<string[]>([]);
    const [selectedErrorTypes, setSelectedErrorTypes] = useState<string[]>([]);
    const [selectedErrorNames, setSelectedErrorNames] = useState<string[]>([]);
    const [errorNames, setErrorNames] = useState<string[]>([]);
    const [showHighlight, setShowHighlight] = useState(true);
    const dal = useDALStore(state => state.dal);
    const [viewMode, setViewMode] = useState<'table' | 'grid'>('table');
    const [current, setCurrent] = useState({
        currentPage: 1,
        pageSize: 10,
    });
    const [filter, setFilter] = useState<{
        primaryName?: string;
        secondaryName?: string;
    }>({});

    // console.log('test-data', summary, detailPathList, allDataPath);
    useEffect(() => {
        const loadData = async () => {
            try {
                setLoading(true);

                setErrorNames(Object.keys(summary.name_ratio));
                setErrorTypes(Object.keys(summary.type_ratio));
                let allData: DataItem[] = [];
                for (const { primaryName, secondaryNameList } of allDataPath) {
                    const result = await dal?.getEvaluationDetail?.({
                        currentPath,
                        primaryName,
                        secondaryNameList,
                    });
                    if (result) {
                        allData = allData.concat(result);
                    }
                }

                setData(uniqBy(allData, 'data_id'));
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
    }, [currentPath, detailPathList]);

    const columns: ColumnsType<DataItem> = [
        {
            title: '数据 ID',
            dataIndex: 'data_id',
            key: 'data_id',
            minWidth: 100,
        },
        {
            title: <span className="font-semibold">一级维度</span>,
            dataIndex: 'type_list',
            key: 'type_list',
            render: types => JSON.stringify(types),
            // filters: errorTypes.map(type => ({ text: type, value: type })),
            // onFilter: (value, record) =>
            //     record.type_list.includes(value.toString()),
            // filterIcon: filtered => (
            //     <FilterFilled
            //         style={{ color: filtered ? '#1890ff' : undefined }}
            //     />
            // ),
            // filteredValue: selectedErrorTypes,
        },
        {
            title: () => <span className="font-semibold">二级维度</span>,
            dataIndex: 'name_list',
            key: 'name_list',
            render: names => JSON.stringify(names),
            // filters: errorNames.map(name => ({ text: name, value: name })),
            // onFilter: (value, record) =>
            //     record.name_list.includes(value.toString()),
            // filteredValue: selectedErrorNames,
            // filterIcon: filtered => (
            //     <FilterFilled
            //         style={{
            //             color: filtered ? '#1890ff' : undefined,
            //         }}
            //     />
            // ),
        },
        {
            title: (
                <span className="flex justify-between font-semibold">内容</span>
            ),
            dataIndex: 'content',
            key: 'content',
            render: (text, record) => {
                return (
                    <HighlightText
                        text={text?.slice?.(0, 10000) || '-'}
                        highlight={record.reason_list}
                        showHighlight={showHighlight}
                    />
                );
            },
        },

        {
            title: '原因',
            dataIndex: 'reason_list',
            key: 'reason_list',
            minWidth: 300,
            render: reasons => (
                <span className="select-text">{JSON.stringify(reasons)}</span>
            ),
        },
    ];

    const handleFilter = (primaryName: string, secondaryName: string) => {
        setFilter({ primaryName, secondaryName });
        setCurrent({
            ...current,
            currentPage: 1,
        });
    };

    const hiddenClass = 'w-0 h-0 z-[-1] overflow-hidden';

    useEffect(() => {
        setSelectedErrorTypes(defaultErrorTypes || []);
    }, [defaultErrorTypes]);
    useEffect(() => {
        setSelectedErrorNames(defaultErrorNames || []);
    }, [defaultErrorNames]);

    const filterData = useMemo(() => {
        const _primaryName = filter?.primaryName;
        if (_primaryName) {
            const _secondaryName = filter?.secondaryName;
            const _res = data?.filter(i =>
                i?.type_list?.includes(_primaryName)
            );
            return _secondaryName
                ? _res?.filter(i => i?.name_list?.includes(_secondaryName))
                : _res;
        } else {
            return data;
        }
    }, [data, filter]);

    const filterCardListData = useMemo(() => {
        const startIndex = (current.currentPage - 1) * current.pageSize;
        const endIndex = startIndex + current.pageSize;
        return filterData.slice(startIndex, endIndex);
    }, [filterData, current.currentPage, current.pageSize]);

    return (
        <>
            <div className="flex items-center">
                <FilterCascader summary={summary} onFilter={handleFilter} />
                <span className="text-[#121316]/[0.8] text-base ml-2">{`${filterData?.length || 0} 条数据`}</span>
                <span className="ml-auto mr-2 text-[#121316]/[0.8] text-[14px]">
                    命中内容高亮
                </span>
                <Switch
                    className="mr-8"
                    checked={showHighlight}
                    onChange={setShowHighlight}
                />
                <div
                    className="flex items-center text-lg gap-2 bg-blue/[0.05] p-1 px-2 rounded-md cursor-pointer"
                    onClick={e => e.stopPropagation()}
                >
                    {[
                        { value: 'table', icon: 'icon-listViewOutlined' },
                        {
                            value: 'grid',
                            icon: 'icon-SwitchViewOutlined',
                        },
                    ]?.map(i => (
                        <span
                            key={i.value}
                            className={cls(
                                'p-1 flex text-[#121316]',
                                viewMode === i.value &&
                                    '!text-[#0D53DE] rounded bg-blue/[0.1]'
                            )}
                        >
                            <IconFont
                                type={i.icon}
                                onClick={() => setViewMode(i.value)}
                            />
                        </span>
                    ))}
                </div>
            </div>
            <div
                className={cls(
                    'mt-1 flex flex-col inline',
                    viewMode !== 'grid' && hiddenClass
                )}
            >
                {filterCardListData?.length ? (
                    filterCardListData?.map(i => {
                        return (
                            <DetailCard
                                data={i}
                                key={i?.data_id}
                                showHighlight={showHighlight}
                            />
                        );
                    })
                ) : (
                    <Empty className="mt-[8rem]" title={'暂无数据'}></Empty>
                )}
                <Pagination
                    total={filterData?.length}
                    className="self-end mt-2"
                    current={current?.currentPage}
                    pageSize={current?.pageSize}
                    showQuickJumper
                    showTotal={total => (
                        <FormattedMessage id="total.data" values={{ total }} />
                    )}
                    onChange={(_page, _pageSize) => {
                        setCurrent({
                            currentPage: _page,
                            pageSize: _pageSize,
                        });
                    }}
                />
            </div>
            <Table<DataItem>
                columns={columns}
                dataSource={filterData}
                loading={loading}
                className={cls('mt-4', viewMode !== 'table' && hiddenClass)}
                rowKey={record => `${record?.data_id}_${record?.content}`}
                pagination={{
                    pageSize: current?.pageSize,
                    showQuickJumper: true,
                    current: current?.currentPage,
                    showTotal: total => (
                        <FormattedMessage id="total.data" values={{ total }} />
                    ),
                }}
                onChange={(pagination, filters) => {
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
                scroll={{ x: '100%' }}
            />
        </>
    );
};

export default DetailTable;
