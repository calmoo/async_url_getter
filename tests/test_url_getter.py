import asyncio
import textwrap
import time
from asyncio.exceptions import TimeoutError
from pathlib import Path
from socket import gaierror
from textwrap import dedent
from typing import Any, Iterator

import aiohttp
import pytest
from _pytest.capture import CaptureFixture
from aiohttp import ClientConnectorError, InvalidURL, WebSocketError
from aiohttp.client_reqrep import ConnectionKey
from aioresponses import aioresponses
from click.testing import CliRunner

from async_url_getter.main import (RequestInfo, cli, get, get_metrics,
                                   make_requests_and_print_results)


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
        Metrics are not returned without at least two data points.
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
        Metrics are returned with at least two data points.
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
        An integer timeout value can be used.
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

    def test_timeout_float_invalid(
        self, tmp_path: Path, mock_aioresponse: aioresponses
    ) -> None:
        """
        A non-integer timeout value cannot be used.
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

    def test_timeout_range(
        self, tmp_path: Path, mock_aioresponse: aioresponses
    ) -> None:
        """
        A non-integer timeout value cannot be used.
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
            [str(example_file), "--timeout", "-1"],
            catch_exceptions=False,
        )
        assert result.exit_code == 2


class TestGet:
    async def test_valid_url(self, mock_aioresponse: aioresponses) -> None:
        """
        A request to a valid URL can be made.
        """
        session = aiohttp.ClientSession()
        valid_url = "https://google.com"
        status = 200
        mock_aioresponse.get(valid_url, status=status)
        timeout = 10
        result = await get(session=session, url=valid_url, timeout=timeout)
        if isinstance(result, RequestInfo):
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
        await make_requests_and_print_results(url_list=urls, timeout=4)
        end = time.monotonic()
        time_taken = round(end - start)
        assert time_taken == request_delay

    async def test_valid_url(
        self, mock_aioresponse: aioresponses, capsys: CaptureFixture
    ) -> None:
        """
        Details of a single request can be retrieved.
        """
        url = "foo.com"
        status = 200
        mock_aioresponse.get(url, status=status)
        await make_requests_and_print_results(url_list=[url], timeout=1)
        captured = capsys.readouterr()
        expected_output = "Request to foo.com responded with 200"
        assert expected_output in captured.out

    async def test_valid_urls(
        self, mock_aioresponse: aioresponses, capsys: CaptureFixture
    ) -> None:
        """
        Details of multiple requests can be retrieved.
        """
        url_1 = "foo.com"
        url_2 = "bar.com"
        status_url_1 = 200
        status_url_2 = 201
        urls = [url_1, url_2]
        mock_aioresponse.get(url_1, status=status_url_1)
        mock_aioresponse.get(url_2, status=status_url_2)
        await make_requests_and_print_results(url_list=urls, timeout=1)
        captured = capsys.readouterr()
        expected_output_1 = "Request to foo.com responded with 200"
        expected_output_2 = "Request to bar.com responded with 201"
        assert expected_output_1 in captured.out
        assert expected_output_2 in captured.out

    async def test_connection_error(
        self, mock_aioresponse: aioresponses, capsys: CaptureFixture
    ) -> None:
        """
        An exception can be raised if a request results in failure.
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
        await make_requests_and_print_results(url_list=[url], timeout=1)
        captured = capsys.readouterr()
        expected_output = "Connection error resolving foo.com\n"
        assert expected_output in captured.out

    async def test_invalid_url(
        self, mock_aioresponse: aioresponses, capsys: CaptureFixture
    ) -> None:
        """
        An exception can be raised a request is made to an invalid URL.
        """

        url = "foo.com"
        exception = InvalidURL(url=url)
        mock_aioresponse.get(url, exception=exception)
        await make_requests_and_print_results(url_list=[url], timeout=1)
        captured = capsys.readouterr()
        expected_output = "foo.com is an invalid URL\n"
        assert expected_output in captured.out

    async def test_connection_error_then_valid_url(
        self, mock_aioresponse: aioresponses, capsys: CaptureFixture
    ) -> None:
        """
        The program can continue making requests in the event of a connection
        error exception.
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
        await make_requests_and_print_results(url_list=urls, timeout=1)
        expected_output_invalid = "Connection error resolving barcom\n"
        expected_output_valid = "Request to foo.com responded with 200"
        captured = capsys.readouterr()
        assert expected_output_invalid in captured.out
        assert expected_output_valid in captured.out

    async def test_invalid_url_then_valid_url(
        self, mock_aioresponse: aioresponses, capsys: CaptureFixture
    ) -> None:
        """
        The program can continue making requests in the event of an invalid
        URL exception.
        """
        invalid_url = "barcom"
        valid_url = "foo.com"
        urls = [invalid_url, valid_url]
        status = 200
        exception = InvalidURL(url=invalid_url)

        mock_aioresponse.get(invalid_url, exception=exception)
        mock_aioresponse.get(valid_url, status=status)
        await make_requests_and_print_results(url_list=urls, timeout=1)
        expected_output_invalid = "barcom is an invalid URL\n"
        expected_output_valid = "Request to foo.com responded with 200"
        captured = capsys.readouterr()
        assert expected_output_invalid in captured.out
        assert expected_output_valid in captured.out

    async def test_timeout(
        self, mock_aioresponse: aioresponses, capsys: CaptureFixture
    ) -> None:
        """
        A request to a valid URL exceeding a timeout raises an exception.
        """
        aiohttp.ClientSession()
        url = "https://google.com"
        mock_aioresponse.get(url, exception=TimeoutError)

        await make_requests_and_print_results(url_list=[url], timeout=2)
        captured = capsys.readouterr()
        expected_output = (
            "Request to https://google.com timed out after 2 seconds\n"
        )
        assert expected_output in captured.out

    async def test_unknown_error(
        self, mock_aioresponse: aioresponses, capsys: CaptureFixture
    ) -> None:
        """
        An exception that isn't handled is printed as an unknown error, with
        the details of the exception. A WebSocketError is used as an example
        here.
        """
        aiohttp.ClientSession()
        url = "https://google.com"
        exception = WebSocketError(code=200, message="test")
        mock_aioresponse.get(url, exception=exception)
        await make_requests_and_print_results(url_list=[url], timeout=1)
        captured = capsys.readouterr()
        expected_output = "Unknown error for https://google.com: test\n"
        assert expected_output in captured.out


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
        metrics = get_metrics(request_info=request_info)

        expected_metrics = textwrap.dedent(
            """\
            Mean response time = 347.9ms
            Median response time = 347.9ms
            90th percentile of response times = 361.1ms"""
            # noqa: E501
        )
        assert expected_metrics == metrics

    def test_no_metrics(self) -> None:
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
        request_info = [request_1]
        metrics = get_metrics(request_info=request_info)
        expected_output = (
            "Two or more successful requests needed to generate metrics."
        )
        assert expected_output == metrics
