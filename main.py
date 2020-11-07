import asyncio
import textwrap
import click
import sys
from statistics import mean, quantiles, median

import aiohttp
from asyncio.exceptions import TimeoutError

import click_pathlib
from aiohttp.client_exceptions import ClientConnectorError
import time
from typing import List
from pathlib import Path


class RequestInfo:
    """
    Details of a request.
    """

    def __init__(self, url: str, total_time: float, status_code: int) -> None:
        self.url = url
        self.status_code = status_code
        self.total_time = total_time

    def __repr__(self) -> str:
        return '<RequestInfo: ' + self.url + '>'


async def get(session: aiohttp.ClientSession, url: str, timeout: int) -> RequestInfo:
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


async def main(url_list: List[str], timeout: int) -> List[RequestInfo]:
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
                print(f"Invalid url")
            else:
                line_printer(result)
                results.append(result)

        return results


def line_printer(result: RequestInfo) -> None:
    rounded_time_millis = round(result.total_time * 1000, 3)
    output_string = (
        f"Request to {result.url} responded with "
        f"{result.status_code} "
        f"and took {rounded_time_millis}ms to complete"
    )
    print(output_string)


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
        mean_millis = round(self.mean * 1000, 3)
        median_millis = round(self.median * 1000, 3)
        ninetieth_percentile_millis = round(self.ninetieth_percentile * 1000, 3)
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
@click.option("--timeout", "-t", default=15, help="Maximum time for a request to finish")
def cli(file: Path, timeout: int) -> None:
    url_list = file.read_text().splitlines()
    if len(url_list) < 1:
        sys.exit("File is empty")

    request_info = asyncio.run(main(url_list=url_list, timeout=timeout))
    if len(request_info) > 1:
        metrics = Metrics(request_info=request_info)
        print(metrics.summary())


if __name__ == "__main__":
    cli()
