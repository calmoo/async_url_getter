import asyncio
from statistics import mean, quantiles, median

import aiohttp
from asyncio.exceptions import TimeoutError
from aiohttp.client_exceptions import (
    InvalidURL,
    ClientConnectorError,
    ServerDisconnectedError,
    ClientError,
)
import time
from typing import List
from pathlib import Path


class RequestInfo:
    """
    Details of a request.
    """

    def __init__(self, url: str, total_time: float, status_code: int):
        self.url = url
        self.status_code = status_code
        self.total_time = total_time


async def get(
    session: aiohttp.ClientSession, url: str, timeout: int
) -> RequestInfo:

    start_time_monotonic = time.monotonic()
    async with session.get(
        url=url, timeout=timeout, allow_redirects=False
    ) as response:
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
    connector = aiohttp.TCPConnector(limit=1000)
    async with aiohttp.ClientSession(
        connector=connector, auto_decompress=False
    ) as session:
        tasks = []
        results = []
        for url in url_list:
            tasks.append(get(session=session, url=url, timeout=timeout))

        for t in asyncio.as_completed(tasks):
            try:
                result = await t
            except TimeoutError:
                print(f"Requested timed out after {timeout} seconds")
            except ClientConnectorError:
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
        self.response_times = self._response_times()
        self.mean = mean(self.response_times)
        self.median = median(self.response_times)
        self.ninetieth_percentile = quantiles(self.response_times, n=10)[-1]

    def _response_times(self) -> List[float]:
        response_times = []
        for item in self.request_info:
            response_times.append(item.total_time)
        return response_times

    def summary(self) -> None:
        mean_millis = round(self.mean * 1000, 3)
        median_millis = round(self.median * 1000, 3)
        ninetieth_percentile_millis = round(
            self.ninetieth_percentile * 1000, 3
        )
        output_summary = f"""
        Mean response time = {mean_millis}ms
        Median response time = {median_millis}ms
        90th percentile of response times = {ninetieth_percentile_millis}ms
        """
        return output_summary


if __name__ == "__main__":
    p = Path("url_list.txt")
    url_list = p.read_text().splitlines()
    request_info = asyncio.run(main(url_list=url_list, timeout=10))
    metrics = Metrics(request_info=request_info)
    print(metrics.summary())
