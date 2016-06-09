import asyncio
import socket
from contextlib import contextmanager, closing

from .. import response
from .util import Tests, FakeTextResponse


class DrippingResponseTests(Tests):
    async def mock_dripping_response(self, chunks, **kwargs):
        ip = iter(chunks)

        loop = asyncio.get_event_loop()
        rsock, wsock = socket.socketpair()
        resp = FakeTextResponse('', **kwargs)
        resp.content, readtr = await asyncio.open_connection(sock=rsock)

        def send_next():
            try:
                to_send = next(ip)
            except StopIteration:
                wsock.close()
                return
            wsock.send(to_send)
            loop.call_soon(send_next)

        loop.call_soon(send_next)

        return self._cm(resp, readtr)

    @contextmanager
    def _cm(self, resp, transport):
        with closing(transport), self.mock_responses(resp):
            yield resp

    async def consume_request(self, resp):
        result = []
        async with await self.req as dripping_response:
            async for line in dripping_response:
                result.append(line)
        self.assertTrue(resp.closed)
        return result

    async def test_text_response(self):
        p = [b"abcdef\n",
             b"abc",
             b"def\n",
             b"abcdef\nabcdef\na",
             b"bcdef"]

        self.req.response_type = \
            response.DrippingResponse(response.TextResponse())

        with await self.mock_dripping_response(p) as resp:
            result = await self.consume_request(resp)

        expected_result = ["abcdef\n"] * 4
        expected_result.append("abcdef")
        self.assertEqual(result, expected_result)

    async def test_bytes_response(self):
        p = [b"abcdef\n",
             b"abc",
             b"def\n",
             b"abcdef\nabcdef\na",
             b"bcdef"]

        self.req.response_type = \
            response.DrippingResponse(response.BytesResponse())

        with await self.mock_dripping_response(p) as resp:
            result = await self.consume_request(resp)

        expected_result = [b"abcdef\n"] * 4
        expected_result.append(b"abcdef")
        self.assertEqual(result, expected_result)

    async def test_json_response(self):
        p = [b'{"id": 1}\n',
             b'{"id": ',
             b'2}\n',
             b'{"id": 3}\n',
             b'{"id": 4}\n{"id": 5}']

        self.req.response_type = \
            response.DrippingResponse(response.JsonResponse())

        with await self.mock_dripping_response(p) as resp:
            result = await self.consume_request(resp)

        expected_result = [{"id": i} for i in range(1, 6)]
        self.assertEqual(result, expected_result)

    async def test_return_remainder_no_remainder(self):
        p = [b'abc\n', b'abc\n']

        self.req.response_type = \
            response.DrippingResponse(response.TextResponse())

        with await self.mock_dripping_response(p) as resp:
            result = await self.consume_request(resp)

        expected_result = ['abc\n'] * 2
        self.assertEqual(result, expected_result)

    async def test_ignore_remainder(self):
        p = [b'abc\n', b'abc']

        self.req.response_type = \
            response.DrippingResponse(response.TextResponse(), remainder='ignore')

        with await self.mock_dripping_response(p) as resp:
            result = await self.consume_request(resp)

        expected_result = ['abc\n']
        self.assertEqual(result, expected_result)

    async def test_error_on_remainder(self):
        p = [b'abc\n', b'extra']

        self.req.response_type = \
            response.DrippingResponse(response.TextResponse(), remainder='error')

        with await self.mock_dripping_response(p) as resp:
            async with await self.req as dripping_response:
                itor = await type(dripping_response).__aiter__(dripping_response)
                self.assertEqual('abc\n', await type(itor).__anext__(itor))
                with self.assertRaises(ValueError):
                    await type(itor).__anext__(itor)
            self.assertTrue(resp.closed)

    async def test_encoding_missing(self):
        n = 10
        p = [b'abcdef\n'] * n

        self.req.response_type = \
            response.DrippingResponse(response.TextResponse())

        with await self.mock_dripping_response(p, charset=None) as resp:
            result = await self.consume_request(resp)

        expected_result = ['abcdef\n'] * n
        self.assertEqual(result, expected_result)

    async def test_encoding_missing_bom_present(self):
        n = 10
        p = [b'\xef\xbb\xbf'] + [b'abcdef\n'] * n

        self.req.response_type = \
            response.DrippingResponse(response.TextResponse())

        with await self.mock_dripping_response(p, charset=None) as resp:
            result = await self.consume_request(resp)

        expected_result = ['abcdef\n'] * n
        self.assertEqual(result, expected_result)
