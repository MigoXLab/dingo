from enum import Enum


class RequiredField(Enum):
    CONTENT = "content"
    PROMPT = "prompt"
    CONTEXT = "context"
    IMAGE = "image"
    METADATA = "metadata"
    TYPE = "type"
    DT = "dt"
    SOURCE = "source"
    SOURCE_DETAILS = "source_details"
    ANNOTATION = "annotation"
    DATA_CONTENT = "data_content"
    TRACK_ID = "track_id"
    LANGUAGE = "language"
