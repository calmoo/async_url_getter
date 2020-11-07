import pytest
from aiohttp import ClientConnectorError, InvalidURL
import time
from main import get, main, cli
import aiohttp
from aioresponses import aioresponses
from socket import gaierror
from aiohttp.client_reqrep import ConnectionKey
import asyncio
from click.testing import CliRunner
from textwrap import dedent


@pytest.fixture
def mock_aioresponse():
    with aioresponses() as response:
        yield response


class TestCLI:
    def test_file_input_valid(self, tmp_path, mock_aioresponse) -> None:
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

    def test_file_input_invalid(self, tmp_path) -> None:
        example_file = tmp_path / "example_file.txt"
        file_contents = ""
        example_file.write_text(file_contents)
        runner = CliRunner()
        result = runner.invoke(
            cli, [str(example_file)], catch_exceptions=False
        )
        expected_output = "File is empty\n"
        assert expected_output in result.output
        assert result.exit_code == 1

    def test_no_metrics(self, tmp_path, mock_aioresponse) -> None:
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

    def test_metrics_output(self, tmp_path, mock_aioresponse) -> None:
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

    def test_timeout_valid(self, tmp_path, mock_aioresponse) -> None:
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

    def test_timeout_invalid(self, tmp_path, mock_aioresponse) -> None:
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
    async def test_valid_url(self, mock_aioresponse) -> None:
        session = aiohttp.ClientSession()
        valid_url = "https://google.com"
        status = 200
        mock_aioresponse.get(valid_url, status=status)
        timeout = 10
        result = await get(session=session, url=valid_url, timeout=timeout)
        assert result.url == valid_url
        assert result.total_time < timeout
        assert result.status_code == status

    async def test_timeout(self, mock_aioresponse) -> None:

        session = aiohttp.ClientSession()
        url = "https://google.com"
        mock_aioresponse.get(url, exception=TimeoutError)

        timeout = 2
        with pytest.raises(TimeoutError):
            result = await get(session=session, url=url, timeout=timeout)


class TestMain:
    async def test_concurrency(self, mock_aioresponse) -> None:

        request_delay = 1

        async def delay_request(*args, **kwargs):
            await asyncio.sleep(request_delay)

        url_1 = "foo.com"
        url_2 = "bar.com"
        urls = [url_1, url_2]
        for url in urls:
            mock_aioresponse.get(url, callback=delay_request)
            mock_aioresponse.get(url, callback=delay_request)
        start = time.monotonic()
        await main(url_list=urls, timeout=4)
        end = time.monotonic()
        time_taken = round(end - start)
        assert time_taken == request_delay

    async def test_valid_url(self, mock_aioresponse) -> None:
        url = "foo.com"
        urls = [url]
        status = 200
        mock_aioresponse.get(url, status=status)
        result = await main(url_list=urls, timeout=1)
        assert len(result) == 1
        request_info = result[0]
        assert request_info.status_code == status
        assert request_info.url == url
        assert request_info.total_time < 1

    async def test_valid_urls(self, mock_aioresponse) -> None:
        url_1 = "foo.com"
        url_2 = "bar.com"
        status_url_1 = 200
        status_url_2 = 201
        urls = [url_1, url_2]
        mock_aioresponse.get(url_1, status=status_url_1)
        mock_aioresponse.get(url_2, status=status_url_2)
        result = await main(url_list=urls, timeout=1)

        [request_info_1] = [info for info in result if info.url == url_1]
        [request_info_2] = [info for info in result if info.url == url_2]

        assert request_info_1.total_time < 1
        assert request_info_2.total_time < 1

        assert request_info_1.status_code == status_url_1
        assert request_info_2.status_code == status_url_2

    async def test_connection_error(self, mock_aioresponse, capsys) -> None:

        url_1 = "foo.com"
        urls = [url_1]
        connection_key = ConnectionKey(
            host=url_1,
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
        mock_aioresponse.get(url_1, exception=exception)
        result = await main(url_list=urls, timeout=1)
        assert result == []
        captured = capsys.readouterr()
        assert captured.out == "Connection error\n"

    async def test_invalid_url(self, mock_aioresponse, capsys) -> None:

        url = "foo.com"
        urls = [url]
        exception = InvalidURL(url=url)
        mock_aioresponse.get(url, exception=exception)
        result = await main(url_list=urls, timeout=1)
        assert result == []
        captured = capsys.readouterr()
        assert captured.out == "Invalid URL\n"

    async def test_connection_error_then_valid_url(
        self, mock_aioresponse
    ) -> None:

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
        result = await main(url_list=urls, timeout=1)
        assert len(result) == 1
        assert result[0].status_code == status
        assert result[0].url == valid_url

    async def test_invalid_url_then_valid_url(self, mock_aioresponse) -> None:

        invalid_url = "barcom"
        valid_url = "foo.com"
        urls = [invalid_url, valid_url]
        status = 200
        exception = InvalidURL(url=invalid_url)

        mock_aioresponse.get(invalid_url, exception=exception)
        mock_aioresponse.get(valid_url, status=status)
        result = await main(url_list=urls, timeout=1)
        assert len(result) == 1
        assert result[0].status_code == status
        assert result[0].url == valid_url

    def test_timeout(self) -> None:
        pass


class TestMetrics:
    def test_statistics(self) -> None:
        pass

    def test_string_output(self) -> None:
        pass
