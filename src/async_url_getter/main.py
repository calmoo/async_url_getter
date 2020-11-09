import asyncio
import textwrap
import time
from asyncio import Future
from asyncio.exceptions import TimeoutError
from pathlib import Path
from statistics import mean, median, quantiles
from typing import Iterator, List, Union

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
        Returns a human readable string using the details from ``RequestInfo``.
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
    Details of an error.
    """

    def __init__(self, exception: Exception, url: str, timeout: int) -> None:
        self.exception = exception
        self.url = url
        self.timeout = timeout

    def __str__(self) -> str:
        exception = self.exception
        plural = ""
        if self.timeout > 1:
            plural = "s"
        if isinstance(exception, TimeoutError):
            url = self.url
            timeout = self.timeout
            message = (
                f"Request to {url} timed out after {timeout} second{plural}"
            )
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
    complete. If the request does not complete, an exception is raised and
    returns ``RequestErrorInfo``.
    ``time.monotonic`` is used to avoid the effects of system clock changes
    during timing.
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
    Here each task is executed and an Iterator ``asyncio.as_completed`` is
    returned.
    A ``session`` object, ``url_list`` and ``timeout`` are needed to make
    the requests.
    """
    tasks = []
    for url in url_list:
        tasks.append(get(session=session, url=url, timeout=timeout))

    return asyncio.as_completed(tasks)


def get_metrics(request_info: List[RequestInfo]) -> str:
    """
    Generates metrics of request times and returns a string.
    """
    if len(request_info) < 2:
        return "Two or more successful requests needed to generate metrics."

    response_times = [item.total_time for item in request_info]
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
        Mean response time = {mean_millis}ms
        Median response time = {median_millis}ms
        90th percentile of response times = {ninetieth_percentile_millis}ms"""  # noqa: E501
    )
    return output_summary


async def make_requests_and_print_results(
    url_list: List[str], timeout: int
) -> None:
    """
    This handled all responses returned from ``run_multiple_requests``
    ``url_list`` and specified ``timeout`` is passed up the stack from here.
    Each request is printed, and every successful request is added to a list
    and a summary is generated after all requests have completed.
    """
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
        print("-------")
        print(get_metrics(request_info=successful_results))


def validate_and_add_scheme_to_urls(url_list: List[str]) -> List[str]:
    """
    This checks each URL in the list and prepends "http://" to the URL
    if it does not already exist.
    """
    for i, url in enumerate(url_list):
        if not (url.startswith("http://") or url.startswith("https://")):
            url_list[i] = "http://" + url
    return url_list


@click.command(help="Run requests for a given file asynchronously.")
@click.argument("file", type=click_pathlib.Path(exists=True))
@click.option(
    "--timeout",
    "-t",
    default=15,
    type=click.IntRange(min=1),
    help="Maximum number of seconds for a request to finish.",
)
def cli(file: Path, timeout: int) -> None:
    """
    We use click to ingest a text ``file`` of newline separated URLs.
    A ``timeout`` is specified for the maximum time a request can take to
    complete.
    """
    url_list = file.read_text().splitlines()
    url_list_parsed = validate_and_add_scheme_to_urls(url_list)
    asyncio.run(make_requests_and_print_results(url_list_parsed, timeout))
