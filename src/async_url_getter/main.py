import asyncio
import textwrap
import time
from asyncio import Future
from asyncio.exceptions import TimeoutError
from pathlib import Path
from statistics import mean, median, quantiles
from typing import List, Union, Iterator

import aiohttp
import click
import click_pathlib
from aiohttp.client_exceptions import ClientConnectorError, InvalidURL


class RequestInfo:
    """
    Details of a request.
    """

    def __init__(self, url: str, total_time: float, status_code: int) -> None:
        self.url = url
        self.status_code = status_code
        self.total_time = total_time

    def __str__(self) -> str:
        """
        Returns a human readable string using the details from ``RequestInfo``
        """
        rounded_time_millis = round(self.total_time * 1000, 3)
        output_string = (
            f"Request to {self.url} responded with "
            f"{self.status_code} "
            f"and took {rounded_time_millis}ms to complete"
        )
        return output_string


class RequestErrorInfo:
    """
    Details of an error
    """

    def __init__(self, exception: Exception, url: str, timeout: int) -> None:
        self.exception = exception
        self.url = url
        self.timeout = timeout

    def __str__(self):
        exception = self.exception
        if isinstance(exception, TimeoutError):
            message = f"Requested timed out after {self.timeout} seconds"
        elif isinstance(exception, ClientConnectorError):
            url = self.url
            message = f"Connection error resolving {url}"
        elif isinstance(exception, InvalidURL):
            url = self.url
            message = f"{url} is an invalid URL"
        else:
            url = self.url
            message = f"Unknown error for {url}: {str(exception)}"

        return message


async def get(
    session: aiohttp.ClientSession, url: str, timeout: int
) -> Union[RequestInfo, RequestErrorInfo]:
    """
    This makes a non-blocking get request to the ``url`` provided.
    It times out after ``timeout`` seconds.
    It returns ``RequestInfo`` containing the url the request was made to,
    the status code of the request and total time taken for the request to
    complete. If the request does not complete, an exception is raised and does
    not return ``RequestInfo``. ``time.monotonic`` is used to avoid the
    effects of system clock changes during timing.
    """
    start_time_monotonic = time.monotonic()
    try:
        async with session.get(url=url, timeout=timeout) as response:
            await response.read()
    except Exception as exc:
        return RequestErrorInfo(exception=exc, url=url, timeout=timeout)
    status_code = response.status
    end_time_monotonic = time.monotonic()
    total_time = end_time_monotonic - start_time_monotonic
    return RequestInfo(
        url=url,
        status_code=status_code,
        total_time=total_time,
    )


async def run_multiple_requests(
    session: aiohttp.ClientSession, url_list: List[str], timeout: int
) -> Iterator[Future]:
    """
    This parses a list of urls from ``url_list`` and schedules a request
    for each url to be made asynchronously. As each request completes, a
    RequestInfo object is added to a list. Once all requests have
    completed or the ``timeout`` value specified has been exceeded, the list
    of RequestInfo objects is returned.
    Any exceptions raised from the get requests are handled here, and prints
    a message to stdout.
    """
    tasks = []
    for url in url_list:
        tasks.append(get(session=session, url=url, timeout=timeout))

    return asyncio.as_completed(tasks)


class Metrics:
    """
    Creates statistics based on response times of all requests
    """

    def __init__(self, request_info: List[RequestInfo]):
        self.request_info = request_info

    def summary(self) -> str:
        """
        Generates metrics of request times and returns a string.
        """
        if len(self.request_info) < 2:
            return (
                "Two or more successful requests needed to generate metrics."
            )

        response_times = [item.total_time for item in self.request_info]
        mean_response = mean(response_times)
        median_response = median(response_times)
        ninetieth_percentile = quantiles(response_times, n=10)[-1]

        rounding_factor = 3
        mean_millis = round(mean_response * 1000, rounding_factor)
        median_millis = round(median_response * 1000, rounding_factor)
        ninetieth_percentile_millis = round(
            ninetieth_percentile * 1000, rounding_factor
        )
        output_summary = textwrap.dedent(
            f"""\
            -----
            Mean response time = {mean_millis}ms
            Median response time = {median_millis}ms
            90th percentile of response times = {ninetieth_percentile_millis}ms
            """  # noqa: E501
        )
        return output_summary


async def make_requests_and_print_results(url_list, timeout):
    async with aiohttp.ClientSession(auto_decompress=False) as session:
        tasks = await run_multiple_requests(
            url_list=url_list,
            timeout=timeout,
            session=session,
        )

        successful_results = []

        for task in tasks:
            result = await task
            message = str(result)
            print(message)
            if isinstance(result, RequestInfo):
                successful_results.append(result)

        metrics = Metrics(request_info=successful_results)
        print(metrics.summary())


@click.command(help="Run requests for a given file asynchronously.")
@click.argument("file", type=click_pathlib.Path(exists=True))
@click.option(
    "--timeout",
    "-t",
    default=15,
    type=click.IntRange(min=0),
    help="Maximum number of seconds for a request to finish.",
)
def cli(file: Path, timeout: int) -> None:
    """
    We use click to ingest a text ``file`` of newline separated URLs.
    A ``timeout`` is specified for the maximum time a request can take to
    complete.
    """
    url_list = file.read_text().splitlines()
    asyncio.run(make_requests_and_print_results(url_list, timeout))


if __name__ == "__main__":  # pragma: no cover
    cli()
