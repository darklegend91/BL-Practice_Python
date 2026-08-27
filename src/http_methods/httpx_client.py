import asyncio
import json
import os
import time
from typing import Dict, List

import httpx

RTX_URLS = [
    "https://www.nvidia.com/en-in/geforce/graphics-cards/50-series/rtx-5090/",
    "https://www.nvidia.com/en-in/geforce/graphics-cards/50-series/rtx-5080/",
    "https://www.nvidia.com/en-in/geforce/graphics-cards/50-series/rtx-5060-family/",
]

# testing urls added 
ERROR_TEST_URLS = [
    # Success
    "https://www.nvidia.com/en-in/geforce/graphics-cards/50-series/rtx-5090/",

    # 404
    "https://httpbin.org/status/404",

    # 500
    "https://httpbin.org/status/500",

    # Invalid URL
    "not-a-valid-url",

    # Connection failure
    "http://invalid-domain-123456789-example.com",
]
MAX_RETRIES = 3
RETRY_DELAY = 1

# We can skip this part but some website behave differenctly towards the python based headers
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/151.0 Safari/537.36"
    )
}


async def async_fetch(
    client: httpx.AsyncClient,
    url: str
) -> Dict:
    """
    Fetch one webpage asynchronously using httpx.AsyncClient.

    Parameters
    ----------
    client : httpx.AsyncClient
        Shared asynchronous HTTP client.

    url : str
        URL to fetch.

    Returns
    -------
    dict
        HTTP response information.
    """

    start_time = time.perf_counter()
    
    for attempt in range(
        1,
        MAX_RETRIES+1
    ):

        try:

            response = await client.get(url)

            elapsed_time = time.perf_counter() - start_time


            if response.status_code == 200:

                return {
                    "url": url,
                    "status": "success",
                    "status_code": response.status_code,
                    "content": response.text,
                    "content_length": len(response.content),
                    "content_type": response.headers.get(
                        "Content-Type"
                    ),
                    "elapsed_time": round(elapsed_time, 3),
                    "error": None,
                    "retry_count" : attempt -1
                }


            if 400 <= response.status_code < 500:

                return {
                    "url": url,
                    "status": "failed",
                    "status_code": response.status_code,
                    "content": None,
                    "content_length": 0,
                    "content_type": response.headers.get(
                        "Content-Type"
                    ),
                    "elapsed_time": round(elapsed_time, 3),
                    "retry_count" : attempt -1,
                    "error": (
                        f"Client error: HTTP "
                        f"{response.status_code}"
                    ),
                }


            if 500 <= response.status_code < 600:

                if attempt < MAX_RETRIES:

                    print(
                        f"Server error HTTP "
                        f"{response.status_code}. Retrying..."
                    )

                    await asyncio.sleep(
                        RETRY_DELAY
                    )

                    continue

                elapsed_time = (
                    time.perf_counter()
                    - start_time
                )

                return {
                    "url": url,
                    "status": "failed",
                    "status_code": response.status_code,
                    "content": None,
                    "content_length": 0,
                    "content_type": response.headers.get(
                        "Content-Type"
                    ),
                    "elapsed_time": round(
                        elapsed_time,
                        3
                    ),
                    "retry_count": attempt - 1,
                    "error": (
                        f"Server error: HTTP "
                        f"{response.status_code}"
                    ),
                }



            return {
                "url": url,
                "status": "failed",
                "status_code": response.status_code,
                "content": None,
                "content_length": 0,
                "content_type": response.headers.get(
                    "Content-Type"
                ),
                "elapsed_time": round(elapsed_time, 3),
                "error": (
                    f"Unexpected HTTP status: "
                    f"{response.status_code}"
                ),
            }

        except (httpx.InvalidURL, httpx.UnsupportedProtocol) as error:

            elapsed_time = time.perf_counter() - start_time

            return {
                "url": url,
                "status": "failed",
                "status_code": None,
                "content": None,
                "content_length": 0,
                "content_type": None,
                "elapsed_time": round(elapsed_time, 3),
                "retry_count": attempt - 1,
                "error": f"Invalid URL: {error}",
            }

        except httpx.TimeoutException:

            if attempt < MAX_RETRIES:

                print(
                    "Request timed out. Retrying..."
                )

                await asyncio.sleep(
                    RETRY_DELAY
                )

                continue

            elapsed_time = (
                time.perf_counter()
                - start_time
            )

            return {
                "url": url,
                "status": "failed",
                "status_code": None,
                "content": None,
                "content_length": 0,
                "content_type": None,
                "elapsed_time": round(
                    elapsed_time,
                    3
                ),
                "retry_count": attempt - 1,
                "error": "Request timed out",
            }
    
        except httpx.ConnectError as error:

            if attempt < MAX_RETRIES:

                print(
                    "Connection failed. "
                    "Retrying..."
                )

                await asyncio.sleep(
                    RETRY_DELAY
                )

                continue

            elapsed_time = (
                time.perf_counter()
                - start_time
            )

            return {
                "url": url,
                "status": "failed",
                "status_code": None,
                "content": None,
                "content_length": 0,
                "content_type": None,
                "elapsed_time": round(
                    elapsed_time,
                    3
                ),
                "retry_count": attempt - 1,
                "error": (
                    f"Connection failed: "
                    f"{error}"
                ),
            }


        except httpx.HTTPError as error:

            elapsed_time = time.perf_counter() - start_time

            return {
                "url": url,
                "status": "failed",
                "status_code": None,
                "content": None,
                "content_length": 0,
                "content_type": None,
                "elapsed_time": round(elapsed_time, 3),
                "retry_count": attempt - 1,
                "error": str(error),
            }

# # This function use async io but still fetch data in sequential manner 
# async def async_fetch_many(
#     urls: List[str]
# ) -> List[Dict]:

#     results = []

#     timeout = httpx.Timeout(10.0)

#     async with httpx.AsyncClient(
#         headers=HEADERS,
#         timeout=timeout,
#         follow_redirects=True
#     ) as client:

#         for index, url in enumerate(urls, start=1):

#             print(f"\nFetching {index}/{len(urls)}")
#             print(url)

#             result = await async_fetch(
#                 client,
#                 url
#             )

#             results.append(result)

#             print(
#                 f"Status       : "
#                 f"{result['status']}"
#             )

#             print(
#                 f"HTTP Code    : "
#                 f"{result['status_code']}"
#             )

#             print(
#                 f"Time         : "
#                 f"{result['elapsed_time']} sec"
#             )

#             if result["status"] == "success":

#                 print(
#                     f"Content Size : "
#                     f"{result['content_length']} bytes"
#                 )

#             else:

#                 print(
#                     f"Error        : "
#                     f"{result['error']}"
#                 )

#     return results

# # This task make full use of concurrency by making tasks in this code
# async def async_fetch_many(
#     urls: List[str]
# ) -> List[Dict]:
    
#     results = []
    
#     timeout = httpx.Timeout(10.0)
    
#     async with httpx.AsyncClient(
#         headers= HEADERS,
#         timeout= timeout,
#         follow_redirects= True,
#     ) as client:
        
#         print("\n Starting Concurrent requests ... \n")
        
#         tasks = [
#             async_fetch(client , url)
#             for url in urls
#         ]
        
#         # results = await asyncio.gather(*tasks)
        
#         raw_results = await asyncio.gather( *tasks,  return_exceptions=True )        
#     return results
 #new update Async fetch many 
async def async_fetch_many(
    urls: List[str]
) -> List[Dict]:

    timeout = httpx.Timeout(10.0)

    async with httpx.AsyncClient(
        headers=HEADERS,
        timeout=timeout,
        follow_redirects=True,
    ) as client:

        print(
            "\nStarting Concurrent requests...\n"
        )

        tasks = [
            async_fetch(client, url)
            for url in urls
        ]

        raw_results = await asyncio.gather(
            *tasks,
            return_exceptions=True
        )

    results = []

    for url, result in zip(
        urls,
        raw_results
    ):

        # Unexpected exception which escaped async_fetch()
        if isinstance(result, Exception):

            results.append({
                "url": url,
                "status": "failed",
                "status_code": None,
                "content": None,
                "content_length": 0,
                "content_type": None,
                "elapsed_time": 0,
                "retry_count": 0,
                "error": (
                    f"Unexpected error: {result}"
                ),
            })

        else:

            results.append(
                result
            )

    return results           

def save_results_to_file(
    results: List[Dict],
    filename: str = "output/async_results.json"
) -> None:

    os.makedirs(
        "output",
        exist_ok=True
    )

    with open(
        filename,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            results,
            file,
            indent=4,
            ensure_ascii=False
        )

    print(
        f"\nResults saved to: {filename}"
    )

# async def main():

#     print("=" * 60)
#     print("ASYNCHRONOUS RTX HTTP CLIENT")
#     print("=" * 60)

#     start = time.perf_counter()

#     results = await async_fetch_many(
#         RTX_URLS
#     )

#     total_time = (
#         time.perf_counter() - start
#     )

#     successful = sum(
#         1
#         for result in results
#         if result["status"] == "success"
#     )

#     failed = (
#         len(results) - successful
#     )

#     print("\n" + "=" * 60)
#     print("SUMMARY")
#     print("=" * 60)

#     print(
#         f"URLs Processed : "
#         f"{len(results)}"
#     )

#     print(
#         f"Successful     : "
#         f"{successful}"
#     )

#     print(
#         f"Failed         : "
#         f"{failed}"
#     )

#     print(
#         f"Total Time     : "
#         f"{total_time:.3f} seconds"
#     )

#     save_results_to_file(
#         results
#     )

async def main():

    print("=" * 60)
    print("CONCURRENT RTX HTTP CLIENT")
    print("=" * 60)

    start = time.perf_counter()

    results = await async_fetch_many(
        RTX_URLS
        # ERROR_TEST_URLS
    )

    total_time = (
        time.perf_counter() - start
    )

    # -----------------------------------------------------
    # Count successful / failed requests
    # -----------------------------------------------------

    successful = sum(
        1
        for result in results
        if result["status"] == "success"
    )

    failed = (
        len(results) - successful
    )

    # -----------------------------------------------------
    # Display individual results
    # -----------------------------------------------------

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)

    for index, result in enumerate(
        results,
        start=1
    ):

        print(f"\nResult {index}")

        print(
            f"URL          : "
            f"{result['url']}"
        )

        print(
            f"Status       : "
            f"{result['status']}"
        )

        print(
            f"HTTP Code    : "
            f"{result['status_code']}"
        )

        print(
            f"Request Time : "
            f"{result['elapsed_time']} sec"
        )

        # Retry count should be shown
        # for EACH individual request
        print(
            f"Retries      : "
            f"{result.get('retry_count', 0)}"
        )

        if result["status"] == "success":

            print(
                f"Content Size : "
                f"{result['content_length']} bytes"
            )

        else:

            print(
                f"Error        : "
                f"{result['error']}"
            )

    # -----------------------------------------------------
    # Calculate timing information
    # -----------------------------------------------------

    individual_time_sum = sum(
        result["elapsed_time"]
        for result in results
    )

    # -----------------------------------------------------
    # Calculate total number of retries
    # -----------------------------------------------------

    total_retries = sum(
        result.get(
            "retry_count",
            0
        )
        for result in results
    )

    # -----------------------------------------------------
    # Summary
    # -----------------------------------------------------

    print("\n" + "=" * 60)
    print("CONCURRENT EXECUTION SUMMARY")
    print("=" * 60)

    print(
        f"URLs Processed       : "
        f"{len(results)}"
    )

    print(
        f"Successful           : "
        f"{successful}"
    )

    print(
        f"Failed               : "
        f"{failed}"
    )

    print(
        f"Total Retries        : "
        f"{total_retries}"
    )

    print(
        f"Sum Individual Times : "
        f"{individual_time_sum:.3f} seconds"
    )

    print(
        f"Actual Total Time    : "
        f"{total_time:.3f} seconds"
    )

    # -----------------------------------------------------
    # Save results
    # -----------------------------------------------------

    save_results_to_file(
        results,
        "output/concurrent_results.json"
    )


if __name__ == "__main__":
    asyncio.run(main())
    
if __name__ == "__main__":

    asyncio.run(main())