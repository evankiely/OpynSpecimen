class Generic:
    def __init__(self):
        pass


class Extension:

    #  needs to default to dict or recieve this error: {"code":"INVALID_REQUEST","message":"JSON parse error: null; nested exception is com.fasterxml.jackson.databind.JsonMappingException: N/A\n at [Source: "}
    def __init__(self, attrsMap=dict):
        self.attrsMap = attrsMap