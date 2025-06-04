from fastapi import HTTPException

# tokens


class TokensException(HTTPException):
    pass


class ExceedMaxTokens(TokensException):
    status_code = 400

    def __init__(self, detail='Exceeded maximum allowed tokens.'):
        self.detail = detail


# convert


class ConvertError(HTTPException):
    pass


class ConvertJsonError(ConvertError):
    status_code = 500

    def __init__(self, detail='Failed to convert JSON data.'):
        self.detail = detail
