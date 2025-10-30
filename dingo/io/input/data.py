from pydantic import BaseModel


class Data(BaseModel):
    """
    Data, output of converter.
    Flexible data structure that allows any fields to be configured.
    """

    class Config:
        extra = "allow"
