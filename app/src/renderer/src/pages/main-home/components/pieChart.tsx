import { useMemo, useState } from 'react';
import ReactECharts from 'echarts-for-react';
import cls from 'classnames';
import IconFont from '@/components/icon-font';
import { SummaryData } from './summary-data-table';
import tinycolor from 'tinycolor2';
import { TextTooltip } from '@/components/text-tooltip';
import { Select } from 'antd';

export const getColorByRatioHover = (_parentIndex: number) => {
    const colors = [
        '#e6f2ff',
        '#E8F5FF',
        '#E3F9E9',
        '#FFF5E4',
        '#FFF1E9',
        '#FFF0ED',
        '#FFF0F6',
    ];

    const getMode = (idx: number, length) => idx % (length - 1) || 0;

    const _res = colors[getMode(_parentIndex, colors?.length)];

    return _res;
};

export const getColorByRatio = (_parentIndex: number, isSecondary: boolean) => {
    const colors = [
        '#0D53DE',
        '#0080B0',
        '#008858',
        '#B38500',
        '#BE5A00',
        '#D54941',
        '#C43695',
    ];

    const secondaryColors = [
        '#5E9BF7',
        '#41B8F2',
        '#56C08D',
        '#F5BA18',
        '#FA9550',
        '#FF988E',
        '#FF79CD',
    ];

    const getMode = (idx: number, length) => idx % (length - 1) || 0;

    const _res =
        isSecondary && _parentIndex !== undefined
            ? secondaryColors[_parentIndex]
            : colors[getMode(_parentIndex, colors?.length)];
    return _res;
};

interface ICustomLegendProps {
    firstLevelData: {
        name: string;
        value: unknown;
        itemStyle: {
            color: string;
            hoverColor: string;
        };
    }[];
    secondLevelData: {
        name: string;
        value: unknown;
        itemStyle: {
            color: string;
        };
    }[];
    activeFirstLevel: string;
    onFirstLevelClick: (name?: string) => void;
    data: SummaryData;
    className?: string;
}

const CustomLegend = ({
    firstLevelData = [],
    secondLevelData = [],
    activeFirstLevel,
    onFirstLevelClick,
    data,
    className = '',
}: ICustomLegendProps) => {
    // 获取二级数据的函数

    // 检查是否有二级数据
    const hasSecondLevel = firstLevelType => {
        return Object.keys(data.type_ratio?.content||{}).some(key =>
            key.startsWith(firstLevelType + '-')
        );
    };

    return (
        <div
            className={cls(
                'flex justify-center justify-center gap-0',
                activeFirstLevel && 'grid !grid-cols-2 gap-6',
                className
            )}
        >
            {/* 一级图例 */}
            <div className="space-y-1 max-h-[60vh] overflow-y-auto scrollbar-thin">
                {firstLevelData?.map((item, index) => {
                    const hasChildren = hasSecondLevel(item?.name);
                    return (
                        <div
                            key={index}
                            className={cls(
                                'flex items-center justify-start p-2.5 rounded-md rounded overflow-x-hidden',
                                hasChildren
                                    ? 'cursor-pointer hover:bg-gray-50'
                                    : '',
                                activeFirstLevel === item.name && 'text-white'
                            )}
                            onClick={() => {
                                if (hasChildren) {
                                    onFirstLevelClick(item.name);
                                }
                            }}
                            style={{
                                background:
                                    activeFirstLevel === item.name
                                        ? item?.itemStyle?.hoverColor
                                        : 'transparent',
                            }}
                        >
                            <span
                                className="min-w-2.5 h-2.5 rounded-full mr-2"
                                style={{
                                    backgroundColor: item.itemStyle.color,
                                }}
                            />
                            <TextTooltip
                                str={item.name}
                                trigger="hover"
                                placement="top"
                                offset={[0, -10]}
                                textClassName="!text-[12px]"
                            />

                            {hasChildren && (
                                <IconFont
                                    type={'icon-more'}
                                    style={{ color: item.itemStyle.color }}
                                />
                            )}
                        </div>
                    );
                })}
            </div>

            {/* 二级图例 */}
            {activeFirstLevel && secondLevelData?.length > 0 && (
                <div className="space-y-1 max-h-[100%] overflow-y-auto scrollbar-thin">
                    {secondLevelData.map((item, index) => (
                        <div
                            key={index}
                            className="flex items-center p-2.5 rounded-md"
                        >
                            <span
                                className="min-w-2 h-2 rounded-full mr-2"
                                style={{
                                    background: item?.itemStyle?.color,
                                }}
                            />
                            <TextTooltip
                                str={item.name}
                                trigger="hover"
                                placement="top"
                                offset={[0, -10]}
                                textClassName="!text-[12px]"
                            />
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
};

const PieChart = ({ data }: { data: SummaryData }) => {
    // 存储当前选中的一级标签
    const [activeFirstLevel, setActiveFirstLevel] = useState<string>('');
    // 我要取得data.type_ratio的第一个key
    const [selected, setSelected] = useState<string>(Object.keys(data.type_ratio || {})[0] || '');


    // 安全获取 type_ratio，支持 content 属性或直接使用 type_ratio
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const typeRatioData = (data.type_ratio as any)?.content || data.type_ratio || {};
    const typeRatio = data.type_ratio || {};
    const selectList = Object.keys(data.type_ratio || {}).map((key) => ({
        value: key,
        label: key,
    }));

    // 获取二级数据的函数
    const getSecondLevelData = (firstLevelType: string) => {
        if (!typeRatioData || typeof typeRatioData !== 'object') {
            return [];
        }
        return Object.entries(typeRatioData)
            .filter(([key]) => key.startsWith(firstLevelType + '-'))
            .map(([key, value], idx) => ({
                name: key.split('-')[1],
                value,
                itemStyle: {
                    // 使用对应一级标签的颜色
                    color: tinycolor(getColorByRatio(idx, true))
                        ?.setAlpha(1)
                        .toRgbString(),
                },
            }));
    };

    //根据筛选获得扇形图的右侧展示的一级目录
    const firstLevelData = useMemo(()=>{
        return Object.entries(typeRatio[selected] || {}).map(
            ([key, value], index) => ({
                name: key,
                value,
                itemStyle: {
                    color: tinycolor(getColorByRatio(index, false))
                        ?.setAlpha(0.8)
                        .toRgbString(),
                    hoverColor: getColorByRatioHover(index),
                },
            })
        );
    },[selected]);

    // 图例点击事件处理
    const onEvents = {
        legendselectchanged: params => {
            // 获取被点击的图例名称
            const clickedName = Object.entries(params.selected).find(
                ([, selected]) => selected
            )?.[0];

            // 如果点击的是当前活动的一级标签，则关闭二级展示
            if (activeFirstLevel === clickedName) {
                setActiveFirstLevel('');
            } else {
                setActiveFirstLevel(clickedName!);
            }
        },
    };
    const secondLevelData = useMemo(
        () => getSecondLevelData(activeFirstLevel),
        [activeFirstLevel]
    );

    // 图表配置
    const option = {
        legend: {
            type: 'scroll',
            show: false,
            orient: 'vertical',
            right: '5%',
            top: 'middle',
            width: 180,
            itemGap: 12,
            textStyle: {
                fontSize: 12,
                color: '#333',
            },
            // 自定义图例样式
            formatter: function (name) {
                const data =
                    firstLevelData.find(item => item.name === name) ||
                    (activeFirstLevel &&
                        getSecondLevelData(activeFirstLevel).find(
                            item => item.name === name
                        ));
                if (data) {
                    return `${name} (${data.value})`;
                }
                return name;
            },
            // 图例选中状态的样式
            selectedMode: true,
            select: {
                itemStyle: {
                    shadowBlur: 2,
                    shadowColor: 'rgba(0,0,0,0.2)',
                },
                textStyle: {
                    color: '#333',
                    fontWeight: 'bold',
                },
            },
        },
        series: [
            {
                type: 'pie',
                radius: ['0%', '60%'],
                center: ['50%', '50%'],
                data: activeFirstLevel
                    ? getSecondLevelData(activeFirstLevel)
                    : firstLevelData,
                label: {
                    show: true,
                    position: 'outside',
                    // alignTo: 'edge',
                    margin: 20,

                    formatter: function (params) {
                        return [
                            `{dot|●}{name|${params.name}}`, // 添加圆点和空格
                            `{value|${(params.value * 100)?.toFixed(2)}%}`,
                        ].join('\n');
                    },
                    rich: {
                        name: {
                            align: 'left',
                            fontSize: 12,
                            color: 'rgba(18, 19, 22, 0.80)',
                        },

                        value: {
                            align: 'left',
                            fontSize: 12,
                            color: 'rgba(18, 19, 22, 0.65)',
                            padding: [2, 0, 0, 14], // 添加左侧padding 10px
                        },
                        // 添加圆点样式
                        dot: {
                            color: 'inherit', // 继承对应的系列颜色
                            fontSize: 10,
                            padding: [0, 4, 0, 0],
                        },
                    },
                },

                labelLine: {
                    show: true,
                    length: 32, // 第一段引导线长度
                    length2: 10, // 几乎没有第二段
                    minTurnAngle: 60, // 控制转角
                    smooth: false,
                },

                labelLayout: {
                    hideOverlap: true,
                    verticalAlign: 'bottom', // 垂直对齐方式
                },

                emphasis: {
                    itemStyle: {
                        shadowBlur: 10,
                        shadowOffsetX: 0,
                        shadowColor: 'rgba(0,0,0,0.5)',
                    },
                },
            },
        ],
    };
    const handleLegendClick = name => {
        setActiveFirstLevel(name === activeFirstLevel ? null : name);
    };

    return (
        <div
            style={{ height: '100%', width: '100%', minWidth: 800 }}
            className="flex justify-center"
        >
            <div className="absolute top-4 left-4">
                <Select
                    placeholder="Underlined"
                    variant="borderless"
                    style={{ flex: 1 }}
                    options={selectList}
                    onChange={(value)=>{setSelected(value)}}
                    value={selected}
                />
            </div>

            <ReactECharts
                option={option}
                style={{
                    height: '100%',
                    flex: 1,
                    minWidth: '400px',
                    maxWidth: '800px',
                }}
                onEvents={onEvents}
            />
            <CustomLegend
                firstLevelData={firstLevelData}
                secondLevelData={secondLevelData}
                activeFirstLevel={activeFirstLevel}
                onFirstLevelClick={handleLegendClick}
                data={data}
                className="min-w-[400px] max-w-[600px]"
            />
        </div>
    );
};

export default PieChart;
