import pytest
from dingo.data.dataset.huggingface import HuggingFaceDataset
from dingo.data.datasource.huggingface import HuggingFaceSource
from dingo.io import InputArgs


class TestHfDataset:
    def test_hf_dataset_get_data(self):
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
        dataset: HuggingFaceDataset = HuggingFaceDataset(source=source, name="chupei_text")
        data_iter = dataset.get_data()
        for i in data_iter:
            print(i)

    def test_hf_dataset_get_data_1(self):
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
        dataset: HuggingFaceDataset = HuggingFaceDataset(source=source, name="chupei_json")
        data_iter = dataset.get_data()
        for i in data_iter:
            print(i)

    def test_hf_dataset_get_data_2(self):
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
        dataset: HuggingFaceDataset = HuggingFaceDataset(source=source, name="chupei_jsonl")
        data_iter = dataset.get_data()
        for i in data_iter:
            print(i)

    def test_hf_dataset_get_data_3(self):
        path = "chupei/format-listjson"
        ri = InputArgs(
            eval_group='default',
            input_path=path,
            output_path='./test/outputs/',
            data_format='listjson',
            column_content='output',
            column_prompt="instruction",
            custom_config=None
        )
        source = HuggingFaceSource(input_args=ri)
        dataset: HuggingFaceDataset = HuggingFaceDataset(source=source, name="chupei_listjson")
        data_iter = dataset.get_data()
        for i in data_iter:
            print(i)
            break

    def test_hf_dataset_get_data_4(self):
        path = "lmms-lab/LLaVA-OneVision-Data"
        ri = InputArgs(
            eval_group='default',
            input_path=path,
            output_path='./test/outputs/',
            data_format='hf-image',
            column_image=['image'],
            custom_config=None
        )
        source = HuggingFaceSource(input_args=ri, config_name='CLEVR-Math(MathV360K)')
        dataset: HuggingFaceDataset = HuggingFaceDataset(source=source, name="LLaVA-OneVision-Data")
        data_iter = dataset.get_data()
        first_ele = next(data_iter)
        print(first_ele)

    def test_hf_dataset_get_data_5(self):
        path = "HuggingFaceM4/Docmatix"
        ri = InputArgs(
            eval_group='default',
            input_path=path,
            output_path='./test/outputs/',
            data_format='hf-image',
            column_image=['images'],
            custom_config=None,
            huggingface_split='test'
        )
        source = HuggingFaceSource(input_args=ri, config_name='zero-shot-exp')
        dataset: HuggingFaceDataset = HuggingFaceDataset(source=source, name="Docmatix")
        data_iter = dataset.get_data()
        first_ele = next(data_iter)
        print(first_ele)


if __name__ == "__main__":
    pytest.main(["-s", "-q"])
