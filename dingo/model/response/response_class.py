from pydantic import BaseModel


class ResponseScoreReason(BaseModel):
    score: int
    reason: str = ''

    class Config:
        extra = 'forbid'
        validate_assignment = True


class ResponseNameReason(BaseModel):
    name: str
    reason: str = ''

    class Config:
        extra = 'forbid'
        validate_assignment = True


class ResponseScoreTypeNameReason(BaseModel):
    score: int
    type: str = 'Type'
    name: str = 'Name'
    reason: str = ''

    class Config:
        extra = 'forbid'
        validate_assignment = True
