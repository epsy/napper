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
