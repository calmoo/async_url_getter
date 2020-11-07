import pytest
from aiohttp import ClientConnectorError
import time
from main import get, main
import aiohttp
from aioresponses import aioresponses, CallbackResult
from socket import gaierror
from aiohttp.client_reqrep import ConnectionKey
import asyncio



class TestCLI:
    def test_file_input_valid(self) -> None:
        pass

    def test_file_input_invalid(self) -> None:
        pass

    def test_limit_valid(self) -> None:
        pass

    def test_limit__invalid(self) -> None:
        pass

    def test_timeout_valid(self) -> None:
        pass

    def test_timeout_invalid(self) -> None:
        pass


@pytest.fixture
def mock_aioresponse():
    with aioresponses() as m:
        yield m

class TestGet:
    async def test_valid_url(self, mock_aioresponse) -> None:
        session = aiohttp.ClientSession()
        valid_url = 'https://google.com'
        status = 200
        mock_aioresponse.get(valid_url, status=status)
        timeout = 10
        result = await get(session=session, url=valid_url, timeout=timeout)
        assert result.url == valid_url
        assert result.total_time < timeout
        assert result.status_code == status

    async def test_invalid_url(self, mock_aioresponse) -> None:
        session = aiohttp.ClientSession()
        valid_url = 'https://google.com'
        connection_key = ConnectionKey(host=valid_url, port=80, is_ssl=False, ssl=None, proxy=None, proxy_auth=None, proxy_headers_hash=None)
        os_error = gaierror(8, 'nodename nor servname provided, or not known')

        exception = ClientConnectorError(connection_key=connection_key, os_error=os_error)
        mock_aioresponse.get(valid_url, exception=exception)
        timeout = 10
        with pytest.raises(ClientConnectorError):
            result = await get(session=session, url=valid_url, timeout=timeout)

    async def test_timeout(self, mock_aioresponse) -> None:

        session = aiohttp.ClientSession()
        url = 'https://google.com'
        mock_aioresponse.get(url, exception=TimeoutError)

        timeout = 2
        with pytest.raises(TimeoutError):
            result = await get(session=session, url=url, timeout=timeout)


class TestMain:
    async def test_start_time(self, mock_aioresponse) -> None:

        request_delay = 1
        async def delay_request(*args, **kwargs):
            await asyncio.sleep(request_delay)

        url_1 = 'foo.com'
        url_2 = 'bar.com'
        urls = [url_1, url_2]
        for url in urls:
            mock_aioresponse.get(url, callback=delay_request)
        start = time.monotonic()
        await main(url_list=urls, timeout=4)
        end = time.monotonic()
        time_taken = round(end - start)
        assert time_taken == request_delay

    def test_invalid_url(self) -> None:
        pass

    def test_timeout(self) -> None:
        pass

    def test_limit__invalid(self) -> None:
        pass


class TestMetrics:
    def test_statistics(self) -> None:
        pass

    def test_string_output(self) -> None:
        pass