import { Cascader } from 'antd';
import React, { useState, useMemo } from 'react';
import IconFont from '@/components/icon-font';
import styles from './index.module.scss';
import cls from 'classnames';

interface FilterCascaderProps {
    jsonlFilePaths: string[];
    onFilter: (filePath: string) => void;
}

const FilterCascader: React.FC<FilterCascaderProps> = ({
    jsonlFilePaths,
    onFilter,
}) => {
    const [selectedText, setSelectedText] = useState('');
    const [selectedValue, setSelectedValue] = useState<string[]>(['all']);
    const [isDropdownOpen, setIsDropdownOpen] = useState(false);

    // 将所有 jsonl 文件路径作为一级列表
    const cascaderOptions = useMemo(() => {
        const options: Array<{
            value: string;
            label: string;
        }> = [
            {
                value: 'all',
                label: '全部',
            },
            ...jsonlFilePaths.sort().map(filePath => ({
                value: filePath,
                label: filePath,
            })),
        ];

        return options;
    }, [jsonlFilePaths]);
    const onChange = (value: string | string[] | null) => {
        if (!value || (Array.isArray(value) && value.length === 0)) {
            setSelectedText('');
            setSelectedValue(['all']);
            onFilter('');
            return;
        }

        // 由于是单级列表，value 直接就是文件路径
        const selectedPath = Array.isArray(value) ? value[0] : value;
        setSelectedValue([selectedPath]);

        if (selectedPath === 'all') {
            setSelectedText('');
            onFilter('');
            return;
        }

        setSelectedText(selectedPath);
        onFilter(selectedPath);
    };

    return (
        <span className="text-[#121316] text-[1.2rem]">
            &nbsp;
            <Cascader
                options={cascaderOptions}
                onChange={onChange}
                placeholder="请选择筛选条件"
                changeOnSelect
                style={{ width: 240, height: 600 }}
                allowClear
                value={selectedValue}
                defaultValue={['all']}
                expandTrigger="hover"
                popupClassName={styles.customCascader}
                onDropdownVisibleChange={setIsDropdownOpen}
            >
                <a className="cursor-pointer font-semibold">
                    <span className="font-semibold hover:text-[#0D53DE]">
                        {selectedText || '全部测评数据'}
                    </span>
                    <IconFont
                        type={'icon-arrow-down-filled'}
                        className={cls(
                            'mx-2 text-[1rem] duration-300',
                            isDropdownOpen && 'rotate-180'
                        )}
                    />
                </a>
            </Cascader>
        </span>
    );
};

export default FilterCascader;
