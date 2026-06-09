# """Unit tests for retrieval MTEB adapter traces."""

# from types import SimpleNamespace

# from dingo.retrieval.mteb_adapter import SearchClientModel
# from dingo.retrieval.search_client import PaperResult, SearchClient, SearchResponse


# class FakeSearchClient(SearchClient):
#     name = "fake-search"

#     def __init__(self):
#         self.queries = []

#     def search(self, query: str, limit: int = 100) -> SearchResponse:
#         self.queries.append(query)
#         return SearchResponse(
#             query=query,
#             results=[
#                 PaperResult(
#                     paper_id="external-1",
#                     title="Mapped Non Relevant Paper",
#                     score=0.9,
#                 )
#             ],
#             response_time_ms=12.3,
#             status_code=200,
#         )


# def _indexed_model(task_name="FakeTask"):
#     client = FakeSearchClient()
#     model = SearchClientModel(client, search_limit=10)
#     task_metadata = SimpleNamespace(name=task_name)
#     model.index(
#         [{"id": "doc-1", "title": "Mapped Non Relevant Paper", "text": ""}],
#         task_metadata=task_metadata,
#         hf_split="test",
#         hf_subset="default",
#         encode_kwargs={},
#     )
#     return model, client, task_metadata


# def test_trace_distinguishes_mapped_from_relevant_matches():
#     model, client, task_metadata = _indexed_model()
#     model.set_relevant_docs(
#         "FakeTask",
#         "test",
#         "default",
#         {"q1": {"doc-2": 1}},
#     )

#     results = model.search(
#         {"id": ["q1"], "text": ["test query"]},
#         task_metadata=task_metadata,
#         hf_split="test",
#         hf_subset="default",
#         top_k=10,
#         encode_kwargs={},
#     )

#     assert client.queries == ["test query"]
#     assert results == {"q1": {"doc-1": 1.0}}
#     trace_query = model.get_search_traces()[0]["queries"][0]
#     assert trace_query["mapped_count"] == 1
#     assert trace_query["matched_count"] == 0
#     assert trace_query["relevant_matched_count"] == 0
#     assert trace_query["relevant_total"] == 1
#     assert trace_query["gold_doc_ids"] == ["doc-2"]
#     assert trace_query["top_api_results"][0]["is_relevant"] is False


# def test_ifir_task_searches_with_instruction_prefixed_query():
#     model, client, task_metadata = _indexed_model("IFIRScifact")
#     instruction = "Find papers that support the claim."

#     results = model.search(
#         {
#             "id": ["1384_v1"],
#             "text": ["c-MYC maintains pluripotent stem cells."],
#             "instruction": [instruction],
#         },
#         task_metadata=task_metadata,
#         hf_split="test",
#         hf_subset="default",
#         top_k=10,
#         encode_kwargs={},
#     )

#     expected_query = (
#         "Instruction: Find papers that support the claim.\n"
#         "Query: c-MYC maintains pluripotent stem cells."
#     )
#     assert client.queries == [expected_query]
#     assert results == {"1384_v1": {"doc-1": 1.0}}

#     trace_query = model.get_search_traces()[0]["queries"][0]
#     assert trace_query["query_text"] == "c-MYC maintains pluripotent stem cells."
#     assert trace_query["instruction"] == instruction
#     assert trace_query["effective_query_text"] == expected_query


# def test_non_ifir_task_keeps_original_query_even_with_instruction_column():
#     model, client, task_metadata = _indexed_model("SciFact")

#     model.search(
#         {
#             "id": ["q1"],
#             "text": ["plain retrieval query"],
#             "instruction": ["This column should be ignored for non-IFIR tasks."],
#         },
#         task_metadata=task_metadata,
#         hf_split="test",
#         hf_subset="default",
#         top_k=10,
#         encode_kwargs={},
#     )

#     assert client.queries == ["plain retrieval query"]
#     trace_query = model.get_search_traces()[0]["queries"][0]
#     assert trace_query["query_text"] == "plain retrieval query"
#     assert (
#         trace_query["instruction"]
#         == "This column should be ignored for non-IFIR tasks."
#     )
#     assert trace_query["effective_query_text"] == "plain retrieval query"
