import asyncio
import aiohttp
from asyncio.exceptions import TimeoutError
import time


class RequestStats:
    """
    Details of a process.
    Total time is separate from start time and end time because there could be
    system clock changes while running the process.
    """
    def __init__(
        self, url: str, start_time: float, end_time: float, total_time: float,
            response_status: int
    ):
        self.url = url
        self.response_status = response_status
        self.total_time = total_time

async def get(session: aiohttp.ClientSession, url: str) -> RequestStats:

    try:
        async with session.request('GET', url=url, timeout=30) as response:
            start_time_monotonic = time.monotonic()
            await response.text(errors="replace")
            end_time_monotonic = time.monotonic()
            total_time = end_time_monotonic - start_time_monotonic
            request_stats = RequestStats(
                url=url,
                response_status=response.status,
                start_time=start_time,
                end_time=end_time,
                total_time=total_time,
            )
            return request_stats
    except TimeoutError:
        print(f"{url} timed out")


async def main(url_list) -> None:
    async with aiohttp.ClientSession() as session:
        tasks = []
        for c in url_list:
            tasks.append(get(session=session, url=c))
        for t in asyncio.as_completed(tasks):
            result = await t
            print(result)
        # results = await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == '__main__':
    with open('url_list.txt') as f:
        urls = f.read().splitlines()
    url_list = urls
    asyncio.run(main(url_list))
