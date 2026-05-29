"""Tests for MinerU content_list.json and content_list_v2.json converters."""

import json
import os

import pytest

from dingo.config import InputArgs
from dingo.data.converter import converters
from dingo.io import Data

TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), "../../data")


class TestMinerUConverter:
    """Tests for the ``mineru`` format (content_list.json)."""

    @pytest.fixture
    def v1_blocks(self):
        path = os.path.join(TEST_DATA_DIR, "test_mineru_content_list.json")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    @pytest.fixture
    def converter(self):
        input_args = InputArgs(
            input_path="dummy.json",
            dataset={"source": "local", "format": "mineru"},
            evaluator=[{"evals": []}],
        )
        return converters["mineru"].convertor(input_args)

    def test_registered(self):
        assert "mineru" in converters

    def test_total_blocks(self, converter, v1_blocks):
        results = list(converter(v1_blocks))
        assert len(results) == 9

    def test_text_block(self, converter, v1_blocks):
        results = list(converter(v1_blocks))
        text_block = results[0]
        assert isinstance(text_block, Data)
        assert text_block.content == "The response of flow duration curves to afforestation"
        assert text_block.data_id == "p0-b0"
        assert text_block.type == "text"
        assert text_block.text_level == 1
        assert text_block.page_idx == 0
        assert text_block.bbox == [62, 480, 946, 904]

    def test_image_block(self, converter, v1_blocks):
        results = list(converter(v1_blocks))
        img_block = results[1]
        assert img_block.type == "image"
        assert img_block.content == ""
        assert img_block.image == ["images/fig1.jpg"]
        assert img_block.image_caption == ["Fig. 1. Annual flow duration curves of daily flows from Pine Creek."]
        assert img_block.data_id == "p1-b1"

    def test_equation_block(self, converter, v1_blocks):
        results = list(converter(v1_blocks))
        eq_block = results[2]
        assert eq_block.type == "equation"
        assert "Q_{\\%}" in eq_block.content
        assert eq_block.image == ["images/eq1.jpg"]
        assert eq_block.text_format == "latex"

    def test_table_block(self, converter, v1_blocks):
        results = list(converter(v1_blocks))
        tbl_block = results[3]
        assert tbl_block.type == "table"
        assert "<table>" in tbl_block.content
        assert tbl_block.image == ["images/table2.jpg"]
        assert tbl_block.table_caption == ["Table 2 Significance of the rainfall and time terms"]
        assert tbl_block.table_footnote == ["P indicates rainfall term significance at 5% level."]

    def test_code_block(self, converter, v1_blocks):
        results = list(converter(v1_blocks))
        code_block = results[4]
        assert code_block.type == "code"
        assert "GETCOORDINATE" in code_block.content
        assert code_block.sub_type == "algorithm"
        assert code_block.code_caption == ["Algorithm 1 Modules for MCTSteg"]

    def test_list_block(self, converter, v1_blocks):
        results = list(converter(v1_blocks))
        list_block = results[5]
        assert list_block.type == "list"
        assert "H.1 Introduction" in list_block.content
        assert "H.3 Example" in list_block.content
        assert list_block.list_items == [
            "H.1 Introduction",
            "H.2 Example: Divide by Zero without Exception Handling",
            "H.3 Example: Divide by Zero with Exception Handling",
        ]

    def test_header_block(self, converter, v1_blocks):
        results = list(converter(v1_blocks))
        header = results[6]
        assert header.type == "header"
        assert header.content == "Journal of Hydrology 310 (2005) 253-265"

    def test_page_footnote_block(self, converter, v1_blocks):
        results = list(converter(v1_blocks))
        footnote = results[7]
        assert footnote.type == "page_footnote"
        assert footnote.content == "* Corresponding author."

    def test_chart_block(self, converter, v1_blocks):
        results = list(converter(v1_blocks))
        chart = results[8]
        assert chart.type == "chart"
        assert "Year" in chart.content
        assert chart.image == ["images/chart1.jpg"]
        assert chart.chart_caption == ["Chart 1. Annual trends"]

    def test_from_json_string(self, converter, v1_blocks):
        raw_str = json.dumps(v1_blocks)
        results = list(converter(raw_str))
        assert len(results) == 9
        assert results[0].content == "The response of flow duration curves to afforestation"


class TestMinerUV2Converter:
    """Tests for the ``mineru_v2`` format (content_list_v2.json)."""

    @pytest.fixture
    def v2_pages(self):
        path = os.path.join(TEST_DATA_DIR, "test_mineru_content_list_v2.json")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    @pytest.fixture
    def converter(self):
        input_args = InputArgs(
            input_path="dummy.json",
            dataset={"source": "local", "format": "mineru_v2"},
            evaluator=[{"evals": []}],
        )
        return converters["mineru_v2"].convertor(input_args)

    def test_registered(self):
        assert "mineru_v2" in converters

    def test_total_blocks(self, converter, v2_pages):
        results = list(converter(v2_pages))
        assert len(results) == 9

    def test_title_block(self, converter, v2_pages):
        results = list(converter(v2_pages))
        title = results[0]
        assert title.type == "title"
        assert title.content == "1 Introduction"
        assert title.text_level == 1
        assert title.data_id == "p0-b0"
        assert title.page_idx == 0

    def test_paragraph_with_inline_equation(self, converter, v2_pages):
        results = list(converter(v2_pages))
        para = results[1]
        assert para.type == "paragraph"
        assert para.content == "This paper examines A = \\pi r^2 in detail."
        assert para.data_id == "p0-b1"

    def test_page_footnote(self, converter, v2_pages):
        results = list(converter(v2_pages))
        fn = results[2]
        assert fn.type == "page_footnote"
        assert fn.content == "* Corresponding author"

    def test_equation_interline(self, converter, v2_pages):
        results = list(converter(v2_pages))
        eq = results[3]
        assert eq.type == "equation_interline"
        assert eq.content == "Q_{\\%} = f(P) + g(T)"
        assert eq.math_type == "latex"
        assert eq.page_idx == 1

    def test_image_block(self, converter, v2_pages):
        results = list(converter(v2_pages))
        img = results[4]
        assert img.type == "image"
        assert img.content == ""
        assert img.image == ["images/fig1.jpg"]
        assert img.image_caption == ["Fig. 1. Flow duration curves."]

    def test_table_block(self, converter, v2_pages):
        results = list(converter(v2_pages))
        tbl = results[5]
        assert tbl.type == "table"
        assert "<table>" in tbl.content
        assert tbl.image == ["images/table1.jpg"]
        assert tbl.table_caption == ["Table 1. Results"]

    def test_code_block(self, converter, v2_pages):
        results = list(converter(v2_pages))
        code = results[6]
        assert code.type == "code"
        assert "def hello():" in code.content
        assert code.code_language == "python"
        assert code.page_idx == 2

    def test_list_block(self, converter, v2_pages):
        results = list(converter(v2_pages))
        lst = results[7]
        assert lst.type == "list"
        assert "Item A\nItem B\nItem C" == lst.content
        assert lst.list_items == ["Item A", "Item B", "Item C"]
        assert lst.sub_type == "text"

    def test_chart_block(self, converter, v2_pages):
        results = list(converter(v2_pages))
        chart = results[8]
        assert chart.type == "chart"
        assert chart.image == ["images/chart1.jpg"]
        assert chart.sub_type == "bar_chart"

    def test_raw_content_preserved(self, converter, v2_pages):
        results = list(converter(v2_pages))
        title = results[0]
        assert hasattr(title, "raw_content")
        assert isinstance(title.raw_content, dict)
        assert "title_content" in title.raw_content

    def test_from_json_string(self, converter, v2_pages):
        raw_str = json.dumps(v2_pages)
        results = list(converter(raw_str))
        assert len(results) == 9
        assert results[0].content == "1 Introduction"


class TestIncludeTypesFilter:
    """Tests for ``include_types`` filtering on both V1 and V2."""

    @pytest.fixture
    def v1_blocks(self):
        path = os.path.join(TEST_DATA_DIR, "test_mineru_content_list.json")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    @pytest.fixture
    def v2_pages(self):
        path = os.path.join(TEST_DATA_DIR, "test_mineru_content_list_v2.json")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def test_v1_include_text_only(self, v1_blocks):
        input_args = InputArgs(
            input_path="dummy.json",
            dataset={"source": "local", "format": "mineru", "mineru_config": {"include_types": ["text"]}},
            evaluator=[{"evals": []}],
        )
        converter = converters["mineru"].convertor(input_args)
        results = list(converter(v1_blocks))
        assert len(results) == 1
        assert results[0].type == "text"

    def test_v1_include_multiple_types(self, v1_blocks):
        input_args = InputArgs(
            input_path="dummy.json",
            dataset={"source": "local", "format": "mineru", "mineru_config": {"include_types": ["text", "table", "image"]}},
            evaluator=[{"evals": []}],
        )
        converter = converters["mineru"].convertor(input_args)
        results = list(converter(v1_blocks))
        types = {r.type for r in results}
        assert types == {"text", "table", "image"}
        assert len(results) == 3

    def test_v1_no_filter(self, v1_blocks):
        input_args = InputArgs(
            input_path="dummy.json",
            dataset={"source": "local", "format": "mineru"},
            evaluator=[{"evals": []}],
        )
        converter = converters["mineru"].convertor(input_args)
        results = list(converter(v1_blocks))
        assert len(results) == 9

    def test_v2_include_title_paragraph(self, v2_pages):
        input_args = InputArgs(
            input_path="dummy.json",
            dataset={"source": "local", "format": "mineru_v2", "mineru_config": {"include_types": ["title", "paragraph"]}},
            evaluator=[{"evals": []}],
        )
        converter = converters["mineru_v2"].convertor(input_args)
        results = list(converter(v2_pages))
        types = {r.type for r in results}
        assert types == {"title", "paragraph"}
        assert len(results) == 2

    def test_v2_include_empty_list_returns_nothing(self, v2_pages):
        input_args = InputArgs(
            input_path="dummy.json",
            dataset={"source": "local", "format": "mineru_v2", "mineru_config": {"include_types": ["nonexistent_type"]}},
            evaluator=[{"evals": []}],
        )
        converter = converters["mineru_v2"].convertor(input_args)
        results = list(converter(v2_pages))
        assert len(results) == 0


class TestV2NonDictContent:
    """Edge cases where V2 block 'content' is null, string, or missing."""

    @pytest.fixture
    def converter(self):
        input_args = InputArgs(
            input_path="dummy.json",
            dataset={"source": "local", "format": "mineru_v2"},
            evaluator=[{"evals": []}],
        )
        return converters["mineru_v2"].convertor(input_args)

    def test_content_is_none(self, converter):
        pages = [[{"type": "paragraph", "content": None, "bbox": [0, 0, 100, 100]}]]
        results = list(converter(pages))
        assert len(results) == 1
        assert results[0].content == ""
        assert results[0].type == "paragraph"

    def test_content_is_string(self, converter):
        pages = [[{"type": "text", "content": "plain text block"}]]
        results = list(converter(pages))
        assert len(results) == 1
        assert results[0].content == "plain text block"

    def test_content_key_missing(self, converter):
        pages = [[{"type": "unknown_type"}]]
        results = list(converter(pages))
        assert len(results) == 1
        assert results[0].content == ""

    def test_content_is_integer(self, converter):
        pages = [[{"type": "foo", "content": 42}]]
        results = list(converter(pages))
        assert len(results) == 1
        assert results[0].content == ""
