import asyncio
import sys
import textwrap
import time
from asyncio.exceptions import TimeoutError
from pathlib import Path
from statistics import mean, median, quantiles
from typing import List

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


async def get(
    session: aiohttp.ClientSession, url: str, timeout: int
) -> RequestInfo:
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
    async with session.get(url=url, timeout=timeout) as response:
        await response.read()
    end_time_monotonic = time.monotonic()
    total_time = end_time_monotonic - start_time_monotonic
    status_code = response.status
    request_stats = RequestInfo(
        url=url,
        status_code=status_code,
        total_time=total_time,
    )

    return request_stats


async def run_multiple_requests(
    url_list: List[str], timeout: int
) -> List[RequestInfo]:
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

        for task in asyncio.as_completed(tasks):
            try:
                result = await task
            except TimeoutError:
                print(f"Requested timed out after {timeout} seconds")
            except ClientConnectorError as e:
                url = e.host
                print(f"Connection error resolving {url}")
            except InvalidURL as e:
                url = e.url
                print(f"{url} is an invalid URL")
            else:
                print(get_request_details(result))
                results.append(result)

        return results


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


@click.command()
@click.argument("file", type=click_pathlib.Path(exists=True))
@click.option(
    "--timeout", "-t", default=15, help="Maximum time for a request to finish"
)
def cli(file: Path, timeout: int) -> None:
    """
    We use click to ingest a text ``file`` of newline separated URLs.
    A ``timeout`` is specified for the maximum time a request can take to
    complete.
    The program exits if the file is empty, and a message is printed if there
    are less than two data points to calculate metrics.
    """
    url_list = file.read_text().splitlines()
    request_info = asyncio.run(
        run_multiple_requests(url_list=url_list, timeout=timeout)
    )
    if len(request_info) > 1:
        metrics = Metrics(request_info=request_info)
        print(metrics.summary())
    else:
        print("Two or more successful requests needed to generate metrics.")


if __name__ == "__main__":  # pragma: no cover
    cli()
