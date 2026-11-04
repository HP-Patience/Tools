class ApiError(Exception):
    def __init__(self, code, message, status=422, fields=None):
        self.code = code
        self.message = message
        self.status = status
        self.fields = fields or {}


def missing():
    return ApiError("not_found", "记录不存在", 404)
