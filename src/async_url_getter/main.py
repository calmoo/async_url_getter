import asyncio
import sys
import textwrap
import time
from asyncio.exceptions import TimeoutError
from pathlib import Path
from statistics import mean, median, quantiles
from typing import List, Union

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

class RequestErrorInfo:
    """
    """

    def __init__(self, exception: Exception, url: str, timeout: int) -> None:
        self.exception = exception
        self.url = url
        self.timeout = timeout


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
            status_code = response.status
            end_time_monotonic = time.monotonic()
            total_time = end_time_monotonic - start_time_monotonic
            return RequestInfo(
                url=url,
                status_code=status_code,
                total_time=total_time,
            )
    except Exception as exc:
        return RequestErrorInfo(
            exception=exc,
            url=url,
            timeout=timeout
        )


async def run_multiple_requests(
    url_list: List[str], timeout: int
) -> List[Union[RequestInfo, RequestErrorInfo]]:
    """
    This parses a list of urls from ``url_list`` and schedules a request
    for each url to be made asynchronously. As each request completes, a
    RequestInfo object is added to a list. Once all requests have
    completed or the ``timeout`` value specified has been exceeded, the list
    of RequestInfo objects is returned.
    Any exceptions raised from the get requests are handled here, and prints
    a message to stdout.
    """
    async with aiohttp.ClientSession(auto_decompress=False) as session:
        tasks = []
        results = []
        for url in url_list:
            tasks.append(get(session=session, url=url, timeout=timeout))

        return tasks


        #return results


def get_error_details(error_info: RequestErrorInfo) -> str:

    exception = error_info.exception
    if isinstance(exception, TimeoutError):
        message = (
            f"Requested timed out after {error_info.timeout} seconds"
        )
    elif isinstance(exception, ClientConnectorError):
        url = error_info.url
        message = f"Connection error resolving {url}"
    elif isinstance(exception, InvalidURL):
        url = error_info.url
        message = f"{url} is an invalid URL"
    else:
        url = error_info.url
        message = f"Unknown error for {url}"

    return message



def get_request_details(result: RequestInfo) -> str:
    """
    Returns a human readable string using the details from ``RequestInfo``
    """
    rounded_time_millis = round(result.total_time * 1000, 3)
    output_string = (
        f"Request to {result.url} responded with "
        f"{result.status_code} "
        f"and took {rounded_time_millis}ms to complete"
    )
    return output_string


class Metrics:
    """
    Creates statistics based on response times of all requests
    """

    def __init__(self, request_info: List[RequestInfo]):
        self.request_info = request_info
        self.response_times = [item.total_time for item in self.request_info]
        self.mean = mean(self.response_times)
        self.median = median(self.response_times)
        self.ninetieth_percentile = quantiles(self.response_times, n=10)[-1]

    def summary(self) -> str:
        """
        Generates metrics of request times and returns a string.
        """
        rounding_factor = 3
        mean_millis = round(self.mean * 1000, rounding_factor)
        median_millis = round(self.median * 1000, rounding_factor)
        ninetieth_percentile_millis = round(
            self.ninetieth_percentile * 1000, rounding_factor
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


async def print_results(url_list, timeout):
    tasks = asyncio.run(
        run_multiple_requests(url_list=url_list, timeout=timeout)
    )
    successful_requests = []
    for result_item_to_await in asyncio.as_completed(tasks):
        result_item = await result_item_to_await
        if isinstance(result_item, RequestInfo):
            successful_requests.append(result_item)
            message = get_request_details(result_item)
        else:
            message = get_error_details(error_info=result_item)

        print(message)

    if len(successful_requests) > 1:
        metrics = Metrics(request_info=successful_requests)
        print(metrics.summary())
    else:
        print("Two or more successful requests needed to generate metrics.")


@click.command(help="Run requests for a given file asynchronously.")
@click.argument("file", type=click_pathlib.Path(exists=True))
@click.option(
    "--timeout",
    "-t",
    default=15,
    help="Maximum number of seconds for a request to finish.",
)
async def cli(file: Path, timeout: int) -> None:
    """
    We use click to ingest a text ``file`` of newline separated URLs.
    A ``timeout`` is specified for the maximum time a request can take to
    complete.
    The program exits if the file is empty, and a message is printed if there
    are less than two data points to calculate metrics.
    """
    url_list = file.read_text().splitlines()

    await print_results(url_list, timeout)



if __name__ == "__main__":  # pragma: no cover
    cli()
