import asyncio
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
    """

    """
    start_time_monotonic = time.monotonic()
    async with session.get(url=url, timeout=timeout, allow_redirects=False) as response:
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
    async with aiohttp.ClientSession(connector=connector, auto_decompress=False) as session:
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
    rounded_time = round(result.total_time, 4)
    output_string = (
        f"Request to {result.url} responded with "
        f"{result.status_code} "
        f"and took {rounded_time} seconds to complete"
    )
    print(output_string)


if __name__ == "__main__":
    p = Path('url_list.txt')
    url_list = p.read_text().splitlines()
    print(asyncio.run(main(url_list=url_list, timeout=10)))
