import { Tabs, Pagination, message } from 'antd';

import { useRef, useState } from 'react';

import IconFont from '@/components/icon-font';
import cls from 'classnames';
import HighlightText from '../HightLightText';
import copy from 'copy-to-clipboard';

interface DataItem {
    data_id: string;
    prompt: string;
    content: string;
    type_list: string[];
    name_list: string[];
    reason_list: (string | string[])[];
}

interface DetailCardProps {
    data: DataItem;
    showHighlight?: boolean;
}
//该组件此次迭代该组件暂时不用了
const DetailCard: React.FC<DetailCardProps> = ({ data, showHighlight }) => {
    const [isExpanded, setIsExpanded] = useState(false);
    const textRef = useRef<any>(null);
    const toggleExpand = () => {
        setIsExpanded(!isExpanded);
    };

    return (
        <div className="bg-[#F4F5F9] rounded-lg shadow-sm mt-4 px-12 py-6 ">
            <div className="h-max-content overflow-hidden flex items-center  mb-2 flex-wrap relative">
                <span className="text-[1rem] font-semibold text-[#121316] mr-4">
                    {data.data_id}
                </span>
                {data?.type_list?.length &&
                    data?.type_list.map((type, index) => (
                        <span
                            key={index}
                            className="mb-1 text-[14px] text-[#3F4043] h-max-content rounded bg-[#fff] px-4 py-1 rounded mr-4"
                        >
                            {type}
                        </span>
                    ))}
                {data?.name_list?.length &&
                    data?.name_list.map((type, index) => (
                        <span
                            key={index}
                            className="mb-1 text-[14px] text-[#3F4043] h-max-content rounded bg-[#fff] px-4 py-1 rounded  mr-4"
                        >
                            {type}
                        </span>
                    ))}
                <div
                    className={cls(
                        'absolute right-0 top-0 mr-1 text-[#121316]/[0.8] cursor-pointer text-[14px]'
                    )}
                    onClick={() => toggleExpand()}
                >
                    <IconFont
                        className={cls(
                            'rotate-90 mr-1 ',
                            isExpanded && '!-rotate-90'
                        )}
                        type="icon-more"
                    />
                    <span className="text-[#121316]/[0.6]">
                        {isExpanded ? '收起' : '展开'}
                    </span>
                </div>
            </div>

            <div className="grid grid-cols-6  gap-4 ">
                <div className="col-span-4 group">
                    <p className="text-[#121316]/[0.35] text-[14px] mb-2 relative">
                        内容
                        <IconFont
                            type={'icon-copy'}
                            onClick={e => {
                                e?.stopPropagation();
                                copy(String(data?.content));
                                message.success('复制成功');
                            }}
                            className="opacity-0 cursor-pointer group-hover:opacity-100 ml-2"
                        />
                    </p>
                    <div
                        className={`text-sm text-[#121316]/[0.8] ${!isExpanded ? 'line-clamp-4' : ''}`}
                    >
                        <HighlightText
                            text={data?.content?.slice(0, 10000) || '-'}
                            highlight={data.reason_list}
                            showHighlight={!!showHighlight}
                            controlIsExpanded={isExpanded}
                            expandable={false}
                            width={'100%'}
                            ellipsisTextClassName={'!max-w-full'}
                            ref={textRef}
                        />
                    </div>
                </div>

                <div className=" col-span-2 group">
                    <p className="text-[#121316]/[0.35] text-[14px] mb-2 relative group">
                        原因
                        <IconFont
                            type={'icon-copy'}
                            onClick={e => {
                                e?.stopPropagation();
                                copy(String(data?.reason_list));
                                message.success('复制成功');
                            }}
                            className="opacity-0 cursor-pointer group-hover:opacity-100 ml-2"
                        />
                    </p>
                    <div className="text-sm text-[#121316] select-text">
                        {String(data?.reason_list)}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default DetailCard;
