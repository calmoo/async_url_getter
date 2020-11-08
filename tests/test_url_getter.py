import asyncio
import time
from asyncio.exceptions import TimeoutError
from pathlib import Path
from socket import gaierror
from textwrap import dedent
from typing import Any, Iterator

import aiohttp
import pytest
from _pytest.capture import CaptureFixture
from aiohttp import ClientConnectorError, InvalidURL
from aiohttp.client_reqrep import ConnectionKey
from aioresponses import aioresponses
from click.testing import CliRunner

from async_url_getter.main import (
    Metrics,
    RequestInfo,
    cli,
    get,
    run_multiple_requests,
)


@pytest.fixture
def mock_aioresponse() -> Iterator[aioresponses]:
    """
    Yields a mock response object which allow us to make sure that tests do not
    use the real internet.
    Any requests made by ``aiohttp`` will be handled by this mock object.
    """
    with aioresponses() as response:
        yield response


class TestCLI:
    def test_file_input_valid(
        self, tmp_path: Path, mock_aioresponse: aioresponses
    ) -> None:
        """
        A file containing at least one line can be parsed
        """
        url = "http://google.com"
        status = 200
        mock_aioresponse.get(url, status=status)
        example_file = tmp_path / "example_file.txt"
        file_contents = dedent(
            """\
            http://google.com
            """
        )
        example_file.write_text(file_contents)
        runner = CliRunner()
        result = runner.invoke(
            cli, [str(example_file)], catch_exceptions=False
        )
        expected_output = "Request to http://google.com responded with 200"
        assert expected_output in result.output
        assert result.exit_code == 0


    def test_no_metrics(
        self, tmp_path: Path, mock_aioresponse: aioresponses
    ) -> None:
        """
        Metrics are not returned without at least two data points
        """
        url = "http://google.com"
        status = 200
        mock_aioresponse.get(url, status=status)
        example_file = tmp_path / "example_file.txt"
        file_contents = dedent(
            """\
            http://google.com
            """
        )
        example_file.write_text(file_contents)
        runner = CliRunner()
        result = runner.invoke(
            cli, [str(example_file)], catch_exceptions=False
        )
        expected_output = (
            "Two or more successful requests needed to generate metrics."
        )
        assert expected_output in result.output
        assert result.exit_code == 0

    def test_metrics_output(
        self, tmp_path: Path, mock_aioresponse: aioresponses
    ) -> None:
        """
        Metrics are returned with at least two data points
        """
        url_1 = "http://google.com"
        url_2 = "http://test.com"
        status_1 = 200
        status_2 = 201
        mock_aioresponse.get(url_1, status=status_1)
        mock_aioresponse.get(url_2, status=status_2)
        example_file = tmp_path / "example_file.txt"
        file_contents = dedent(
            """\
            http://google.com
            http://test.com
            """
        )
        example_file.write_text(file_contents)
        runner = CliRunner()
        result = runner.invoke(
            cli, [str(example_file)], catch_exceptions=False
        )
        expected_output = "Mean response"
        assert expected_output in result.output
        assert result.exit_code == 0

    def test_timeout_valid(
        self, tmp_path: Path, mock_aioresponse: aioresponses
    ) -> None:
        """
        An integer timeout value can be used
        """
        url = "http://google.com"
        status = 200
        mock_aioresponse.get(url, status=status)
        example_file = tmp_path / "example_file.txt"
        file_contents = dedent(
            """\
            http://google.com
            """
        )
        example_file.write_text(file_contents)
        runner = CliRunner()
        result = runner.invoke(
            cli, [str(example_file), "--timeout", "5"], catch_exceptions=False
        )
        assert result.exit_code == 0

    def test_timeout_invalid(
        self, tmp_path: Path, mock_aioresponse: aioresponses
    ) -> None:
        """
        A non-integer timeout value cannot be used
        """
        url = "http://google.com"
        status = 200
        mock_aioresponse.get(url, status=status)
        example_file = tmp_path / "example_file.txt"
        file_contents = dedent(
            """\
            http://google.com
            """
        )
        example_file.write_text(file_contents)
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [str(example_file), "--timeout", "2.5"],
            catch_exceptions=False,
        )
        assert result.exit_code == 2


class TestGet:
    async def test_valid_url(self, mock_aioresponse: aioresponses) -> None:
        """
        A request to a valid URL can be made
        """
        session = aiohttp.ClientSession()
        valid_url = "https://google.com"
        status = 200
        mock_aioresponse.get(valid_url, status=status)
        timeout = 10
        result = await get(session=session, url=valid_url, timeout=timeout)
        assert result.url == valid_url
        assert result.total_time < timeout
        assert result.status_code == status


class TestRunMultipleRequests:
    async def test_concurrency(self, mock_aioresponse: aioresponses) -> None:
        """
        Multiple non-blocking requests to URLs can be made in parallel.
        """
        request_delay = 1

        async def delay_request(*args: Any, **kwargs: Any) -> None:
            await asyncio.sleep(request_delay)

        url_1 = "foo.com"
        url_2 = "bar.com"
        urls = [url_1, url_2]
        mock_aioresponse.get(url_1, callback=delay_request)
        mock_aioresponse.get(url_2, callback=delay_request)
        start = time.monotonic()
        await run_multiple_requests(url_list=urls, timeout=4)
        end = time.monotonic()
        time_taken = round(end - start)
        assert time_taken == request_delay

    async def test_valid_url(self, mock_aioresponse: aioresponses) -> None:
        """
        Details of a single request can be retrieved
        """
        url = "foo.com"
        status = 200
        mock_aioresponse.get(url, status=status)
        result = await run_multiple_requests(url_list=[url], timeout=1)
        assert len(result) == 1
        request_info = result[0]
        assert request_info.status_code == status
        assert request_info.url == url
        assert request_info.total_time < 1

    async def test_valid_urls(self, mock_aioresponse: aioresponses) -> None:
        """
        Details of multiple requests can be retrieved
        """
        url_1 = "foo.com"
        url_2 = "bar.com"
        status_url_1 = 200
        status_url_2 = 201
        urls = [url_1, url_2]
        mock_aioresponse.get(url_1, status=status_url_1)
        mock_aioresponse.get(url_2, status=status_url_2)
        result = await run_multiple_requests(url_list=urls, timeout=1)

        [request_info_1] = [info for info in result if info.url == url_1]
        [request_info_2] = [info for info in result if info.url == url_2]

        assert request_info_1.total_time < 1
        assert request_info_2.total_time < 1

        assert request_info_1.status_code == status_url_1
        assert request_info_2.status_code == status_url_2

    async def test_connection_error(
        self, mock_aioresponse: aioresponses, capsys: CaptureFixture
    ) -> None:
        """
        An exception can be raised if a request results in failure
        """
        url = "foo.com"
        connection_key = ConnectionKey(
            host=url,
            port=80,
            is_ssl=False,
            ssl=None,
            proxy=None,
            proxy_auth=None,
            proxy_headers_hash=None,
        )
        os_error = gaierror(8, "nodename nor servname provided, or not known")

        exception = ClientConnectorError(
            connection_key=connection_key, os_error=os_error
        )
        mock_aioresponse.get(url, exception=exception)
        result = await run_multiple_requests(url_list=[url], timeout=1)
        assert result == []
        captured = capsys.readouterr()
        assert captured.out == "Connection error resolving foo.com\n"

    async def test_invalid_url(
        self, mock_aioresponse: aioresponses, capsys: CaptureFixture
    ) -> None:
        """
        An exception can be raised a request is made to an invalid URL
        """

        url = "foo.com"
        exception = InvalidURL(url=url)
        mock_aioresponse.get(url, exception=exception)
        result = await run_multiple_requests(url_list=[url], timeout=1)
        assert result == []
        captured = capsys.readouterr()
        assert captured.out == "foo.com is an invalid URL\n"

    async def test_connection_error_then_valid_url(
        self, mock_aioresponse: aioresponses
    ) -> None:
        """
        The program can continue making requests in the event of a connection
        error exception
        """

        invalid_url = "barcom"
        valid_url = "foo.com"
        urls = [invalid_url, valid_url]
        status = 200

        connection_key = ConnectionKey(
            host=invalid_url,
            port=80,
            is_ssl=False,
            ssl=None,
            proxy=None,
            proxy_auth=None,
            proxy_headers_hash=None,
        )
        os_error = gaierror(8, "nodename nor servname provided, or not known")
        exception = ClientConnectorError(
            connection_key=connection_key, os_error=os_error
        )

        mock_aioresponse.get(invalid_url, exception=exception)
        mock_aioresponse.get(valid_url, status=status)
        result = await run_multiple_requests(url_list=urls, timeout=1)
        assert len(result) == 1
        assert result[0].status_code == status
        assert result[0].url == valid_url

    async def test_invalid_url_then_valid_url(
        self, mock_aioresponse: aioresponses
    ) -> None:
        """
        The program can continue making requests in the event of an invalid
        URL exception
        """
        invalid_url = "barcom"
        valid_url = "foo.com"
        urls = [invalid_url, valid_url]
        status = 200
        exception = InvalidURL(url=invalid_url)

        mock_aioresponse.get(invalid_url, exception=exception)
        mock_aioresponse.get(valid_url, status=status)
        result = await run_multiple_requests(url_list=urls, timeout=1)
        assert len(result) == 1
        assert result[0].status_code == status
        assert result[0].url == valid_url

    async def test_timeout(
        self, mock_aioresponse: aioresponses, capsys: CaptureFixture
    ) -> None:
        """
        A request to a valid URL exceeding a timeout raises an exception
        """
        aiohttp.ClientSession()
        url = "https://google.com"
        mock_aioresponse.get(url, exception=TimeoutError)

        result = await run_multiple_requests(url_list=[url], timeout=1)
        assert result == []
        captured = capsys.readouterr()
        assert captured.out == "Requested timed out after 1 seconds\n"


class TestMetrics:
    def test_metrics(self) -> None:
        """
        Metrics can be calculated with two or more data points.
        For cleanliness and avoiding formatting headaches, a manually verified
        print output is read from ``metrics_sample.txt`` and compared to
        the output value from the code.
        """
        request_1 = RequestInfo(
            url="foo",
            status_code=200,
            total_time=0.3534,
        )
        request_2 = RequestInfo(
            url="bar",
            status_code=201,
            total_time=0.3424,
        )
        request_info = [request_1, request_2]
        metrics = Metrics(request_info=request_info)
        expected_contents_file = Path(__file__).parent / "metrics_sample.txt"
        expected_contents = expected_contents_file.read_text()
        assert expected_contents == metrics.summary()
