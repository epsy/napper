# napper -- A REST Client for Python
# Copyright (C) 2016 by Yann Kaiser and contributors.
# See AUTHORS and COPYING for details.


class CrossOriginRequestError(Exception):
    def __init__(self, origin, method, request, args, kwargs):
        self.origin = origin
        self.method = method
        self.request = request
        self.args = args
        self.kwargs = kwargs

    def __str__(self):
        return '{0.origin} cannot {1} {0.request}'.format(
            self, self.method.upper())


class UnknownParameters(UserWarning):
    pass


class http:
    def __init__(self):
        raise TypeError

    class Any(Exception):
        def __init__(self, request, response):
            self.request = request
            self.response = response
            self.status_code = request._response.status

    code_classes = {
        1: "Informational",
        2: "Success",
        3: "Redirection",
        4: "ClientError",
        5: "ServerError",
    }

    for n, name in code_classes.items():
        locals()[name] = type(name, (Any,), {'code': n})

    del n, name

    status_names ={
        100: "Continue",
        101: "SwichingProtocols",
        200: "OK",
        201: "Created",
        202: "Accepted",
        203: "NonAuthoritativeInformation",
        204: "NoContent",
        205: "ResetContent",
        206: "PartialContent",
        300: "MultipleChoices",
        301: "MovedPermanently",
        302: "Found",
        303: "SeeOther",
        304: "NotModified",
        305: "UseProxy",
        307: "TemporaryRedirect",
        308: "PermanentRedirect",
        400: "BadRequest",
        401: "Unauthorized",
        402: "PaymentRequired",
        403: "Forbidden",
        404: "NotFound",
        405: "MethodNotAllowed",
        406: "NotAcceptable",
        407: "ProxyAuthenticationRequired",
        408: "RequestTimeout",
        409: "Conflict",
        410: "Gone",
        411: "LengthRequired",
        412: "PreconditionFailed",
        413: "PayloadTooLarge",
        414: "UriTooLong",
        415: "UnsupportedMediaType",
        416: "RangeNotSatisfiable",
        417: "ExpectationFailed",
        418: "ImATeapot",
        421: "MisdirectedRequest",
        426: "UpgradeRequired",
        428: "PreconditionRequired",
        429: "TooManyRequests",
        431: "RequestHeaderFieldsTooLarge",
        451: "UnavailableForLegalReasons",
        500: "InternalServerError",
        501: "NotImplemented",
        502: "BadGateway",
        503: "ServiceUnavailable",
        504: "GatewayTimeout",
        505: "HttpVersionNotSupported",
        506: "VariantAlsoNegotiates",
        510: "NotExtended",
        511: "NetworkAuthenticationRequired",
    }

    for code, name in status_names.items():
        code_class = code // 100
        locals()[name] = type(name, (locals()[code_classes[code_class]],), {'code': code})

    del code, name, code_class

    @classmethod
    def cls_for_code(cls, status_code):
        try:
            name = cls.status_names[status_code]
        except KeyError:
            try:
                name = cls.code_classes[status_code // 100]
            except KeyError:
                name = 'Any'
        return getattr(cls, name)
