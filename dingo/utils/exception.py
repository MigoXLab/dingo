# tokens


class TokensException(Exception):
    pass


class ExceedMaxTokens(TokensException):

    def __init__(self, detail="Exceeded maximum allowed tokens."):
        self.detail = detail
        super().__init__(detail)


# convert


class ConvertError(Exception):
    pass


class ConvertJsonError(ConvertError):

    def __init__(self, detail="Failed to convert JSON data."):
        self.detail = detail
        super().__init__(detail)
