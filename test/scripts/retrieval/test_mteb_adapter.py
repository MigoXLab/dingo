# """Unit tests for retrieval MTEB adapter traces."""

# from types import SimpleNamespace

# from dingo.retrieval.mteb_adapter import SearchClientModel
# from dingo.retrieval.search_client import PaperResult, SearchClient, SearchResponse


# class FakeSearchClient(SearchClient):
#     name = "fake-search"

#     def search(self, query: str, limit: int = 100) -> SearchResponse:
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


# def test_trace_distinguishes_mapped_from_relevant_matches():
#     model = SearchClientModel(FakeSearchClient(), search_limit=10)
#     task_metadata = SimpleNamespace(name="FakeTask")
#     corpus = [
#         {"id": "doc-1", "title": "Mapped Non Relevant Paper", "text": ""},
#         {"id": "doc-2", "title": "Gold Paper", "text": ""},
#     ]
#     queries = {"id": ["q1"], "text": ["test query"]}

#     model.set_relevant_docs(
#         "FakeTask",
#         "test",
#         "default",
#         {"q1": {"doc-2": 1}},
#     )
#     model.index(
#         corpus,
#         task_metadata=task_metadata,
#         hf_split="test",
#         hf_subset="default",
#         encode_kwargs={},
#     )

#     results = model.search(
#         queries,
#         task_metadata=task_metadata,
#         hf_split="test",
#         hf_subset="default",
#         top_k=10,
#         encode_kwargs={},
#     )

#     assert results == {"q1": {"doc-1": 1.0}}
#     trace_query = model.get_search_traces()[0]["queries"][0]
#     assert trace_query["mapped_count"] == 1
#     assert trace_query["matched_count"] == 0
#     assert trace_query["relevant_matched_count"] == 0
#     assert trace_query["relevant_total"] == 1
#     assert trace_query["gold_doc_ids"] == ["doc-2"]
#     assert trace_query["top_api_results"][0]["is_relevant"] is False
