class HfHubHTTPError(Exception):
    def __init__(self, message, *, response=None, server_message=None):
        super().__init__(message)
        self.response = response
