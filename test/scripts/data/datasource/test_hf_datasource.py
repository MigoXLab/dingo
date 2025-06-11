import pytest
from dingo.data.datasource.huggingface import HuggingFaceSource
from dingo.io import InputArgs


class TestHfDataset:
    def test_hf_datasource_get_data(self):
        path = "chupei/format-text"
        ri = InputArgs(
            eval_group='default',
            input_path=path,
            output_path='data/outputs/',
            data_format='plaintext',
            column_content='text',
            custom_config=None
        )
        source = HuggingFaceSource(input_args=ri)
        data_iter = source.load()
        for i in data_iter:
            print(i)

    def test_hf_datasource_get_data_2(self):
        path = "chupei/format-json"
        ri = InputArgs(
            eval_group='default',
            input_path=path,
            output_path='data/outputs/',
            data_format='json',
            column_content='prediction',
            column_prompt='origin_prompt',
            custom_config=None
        )
        source = HuggingFaceSource(input_args=ri)
        data_iter = source.load()
        for i in data_iter:
            print(i)

    def test_hf_datasource_get_data_3(self):
        path = "chupei/format-jsonl"
        ri = InputArgs(
            eval_group='default',
            input_path=path,
            output_path='data/outputs/',
            data_format='jsonl',
            column_content='content',
            custom_config=None
        )
        source = HuggingFaceSource(input_args=ri)
        data_iter = source.load()
        for i in data_iter:
            print(i)

    def test_hf_datasource_get_data_4(self):
        path = "chupei/format-listjson"
        ri = InputArgs(
            eval_group='default',
            input_path=path,
            output_path='data/outputs/',
            data_format='listjson',
            column_content='output',
            column_prompt="instruction",
            custom_config=None
        )
        source = HuggingFaceSource(input_args=ri)
        data_iter = source.load()
        for i in data_iter:
            print(i)

    def test_hf_datasource_get_data_5(self):
        path = "lmms-lab/LLaVA-OneVision-Data"
        ri = InputArgs(
            eval_group='default',
            input_path=path,
            output_path='./test/outputs/',
            column_image=['image'],
            column_content='conversations',
            custom_config=None
        )
        source = HuggingFaceSource(input_args=ri, config_name='CLEVR-Math(MathV360K)')
        data_iter = source.load()
        print(data_iter[0])


if __name__ == "__main__":
    pytest.main(["-s", "-q"])
