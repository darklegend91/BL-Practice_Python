import asyncio
import time

from http_methods.requests_client import fetch_page
from http_methods.httpx_client import async_fetch_many


RTX_URLS = [
    "https://www.nvidia.com/en-in/geforce/graphics-cards/50-series/rtx-5090/",
    "https://www.nvidia.com/en-in/geforce/graphics-cards/50-series/rtx-5080/",
    "https://www.nvidia.com/en-in/geforce/graphics-cards/50-series/rtx-5060-family/",
]


def fetch_sequential(urls: list[str]):

    results = []

    start_time = time.perf_counter()

    for url in urls:

        result = fetch_page(url)

        results.append(result)

    end_time = time.perf_counter()

    execution_time = (
        end_time - start_time
    )

    return results, execution_time


async def fetch_concurrent(urls: list[str]):

    start_time = time.perf_counter()

    results = await async_fetch_many(
        urls
    )

    end_time = time.perf_counter()

    execution_time = (
        end_time - start_time
    )

    return results, execution_time


def calculate_improvement(
    sequential_time,
    async_time
):

    if sequential_time == 0:
        return 0

    improvement = (
        (
            sequential_time
            - async_time
        )
        / sequential_time
    ) * 100

    return improvement


async def main():

    print("=" * 60)
    print("SYNC VS ASYNC BENCHMARK")
    print("=" * 60)

    print(
        f"\nNumber of URLs: "
        f"{len(RTX_URLS)}"
    )

    # ---------------------------------
    # Sequential benchmark
    # ---------------------------------

    print(
        "\nRunning sequential requests..."
    )

    sequential_results, sequential_time = (
        fetch_sequential(
            RTX_URLS
        )
    )

    # ---------------------------------
    # Concurrent benchmark
    # ---------------------------------

    print(
        "\nRunning concurrent requests..."
    )

    async_results, async_time = (
        await fetch_concurrent(
            RTX_URLS
        )
    )

    # ---------------------------------
    # Calculate improvement
    # ---------------------------------

    improvement = calculate_improvement(
        sequential_time,
        async_time
    )

    # ---------------------------------
    # Count successful requests
    # ---------------------------------

    sequential_success = sum(
        1
        for result in sequential_results
        if result["status"] == "success"
    )

    async_success = sum(
        1
        for result in async_results
        if result["status"] == "success"
    )

    # ---------------------------------
    # Display benchmark
    # ---------------------------------

    print("\n" + "=" * 60)
    print("BENCHMARK RESULTS")
    print("=" * 60)

    print(
        f"Number of URLs        : "
        f"{len(RTX_URLS)}"
    )

    print(
        f"Sequential execution  : "
        f"{sequential_time:.2f} seconds"
    )

    print(
        f"Async execution       : "
        f"{async_time:.2f} seconds"
    )

    print(
        f"Improvement           : "
        f"{improvement:.2f}%"
    )

    print(
        f"Sequential successful : "
        f"{sequential_success}"
    )

    print(
        f"Async successful      : "
        f"{async_success}"
    )


if __name__ == "__main__":
    asyncio.run(main())