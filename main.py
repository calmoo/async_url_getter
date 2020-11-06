import asyncio
import aiohttp
from asyncio.exceptions import TimeoutError
from aiohttp.client_exceptions import InvalidURL, ClientConnectorError, ServerDisconnectedError, ClientError
import time
from socket import gaierror


class RequestInfo:
    """
    Details of a process.
    Total time is separate from start time and end time because there could be
    system clock changes while running the process.
    """
    def __init__(
        self, url: str, total_time: float, status_code: int
    ):
        self.url = url
        self.status_code = status_code
        self.total_time = total_time

    def __repr__(self):
        results = f"Request to {self.url} took "
        return f"{self.url} {self.status_code} {self.total_time}"


async def get(session: aiohttp.ClientSession, url: str, timeout: int) -> RequestInfo:
    """
    Raises:
        ...
        ...
    """
    start_time_monotonic = time.monotonic()
    print(time.time())
    try:
        async with session.get(url=url, timeout=timeout) as response:
            await response.read()
    except TimeoutError:
        print(f"{url} timed out")
        return
    except ClientConnectorError:
        print(f"invalid url {url}")
        return

    end_time_monotonic = time.monotonic()
    total_time = end_time_monotonic - start_time_monotonic
    status_code = response.status
    request_stats = RequestInfo(
        url=url,
        status_code=status_code,
        total_time=total_time,
    )

    return request_stats

async def main(url_list) -> None:
    connector = aiohttp.TCPConnector(limit=1000)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = []
        results = []
        for c in url_list:
            tasks.append(get(session=session, url=c, timeout=30))
        for t in asyncio.as_completed(tasks):
            result = await t
            if result:
                line_printer(result)
                results.append(result)

        return results

def line_printer(result: RequestInfo) -> None:
    rounded_time = round(result.total_time, 4)
    output_string = f"Request to {result.url} responded with " \
                    f"{result.status_code} " \
                    f"and took {rounded_time} seconds to complete"
    print(output_string)


if __name__ == '__main__':
    with open('url_list_dup.txt') as f:
        url_list = f.read().splitlines()
    print(asyncio.run(main(url_list[:100])))
