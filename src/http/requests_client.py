import time
from typing import Dict, List

import json
import os

import requests
from requests.exceptions import (
    ConnectionError,
    RequestException,
    Timeout,
)


# ==============================
# RTX URLs selected in Task 1
#  ==============================

RTX_URLS = [
    "https://www.nvidia.com/en-in/geforce/graphics-cards/50-series/rtx-5090/",
    "https://www.nvidia.com/en-in/geforce/graphics-cards/50-series/rtx-5080/",
    "https://www.nvidia.com/en-in/geforce/graphics-cards/50-series/rtx-5060-family/",
]


#  ==============================
# Common headers
#  ==============================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/151.0 Safari/537.36"
    )
}


def fetch_page(url: str, timeout: int = 10) -> Dict:
    """
    Fetch a single webpage using the requests library.

    This function performs synchronous HTTP communication.

    Parameters
    ----------
    url : str
        URL that should be fetched.

    timeout : int
        Maximum number of seconds to wait for the response.

    Returns
    -------
    dict
        Information about the HTTP request and response.
    """

    start_time = time.perf_counter()

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=timeout
        )

        total_time = time.perf_counter() - start_time

        

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
                "total_time": round(total_time, 3),
                "error": None,
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
                "total_time": round(total_time, 3),
                "error": (
                    f"Client error: HTTP "
                    f"{response.status_code}"
                ),
            }


        if 500 <= response.status_code < 600:
            return {
                "url": url,
                "status": "failed",
                "status_code": response.status_code,
                "content": None,
                "content_length": 0,
                "content_type": response.headers.get(
                    "Content-Type"
                ),
                "total_time": round(total_time, 3),
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
            "total_time": round(total_time, 3),
            "error": (
                f"Unexpected HTTP status: "
                f"{response.status_code}"
            ),
        }


    except Timeout:

        total_time = time.perf_counter() - start_time

        return {
            "url": url,
            "status": "failed",
            "status_code": None,
            "content": None,
            "content_length": 0,
            "content_type": None,
            "total_time": round(total_time, 3),
            "error": "Request timed out",
        }


    except ConnectionError:

        total_time = time.perf_counter() - start_time

        return {
            "url": url,
            "status": "failed",
            "status_code": None,
            "content": None,
            "content_length": 0,
            "content_type": None,
            "total_time": round(total_time, 3),
            "error": "Connection failed",
        }



    except RequestException as error:

        total_time = time.perf_counter() - start_time

        return {
            "url": url,
            "status": "failed",
            "status_code": None,
            "content": None,
            "content_length": 0,
            "content_type": None,
            "total_time": round(total_time, 3),
            "error": str(error),
        }




def fetch_rtx_pages(urls: List[str]) -> List[Dict]:
    """
    Fetch multiple RTX URLs sequentially.

    Each request starts only after the previous request
    has completed.
    """

    results = []

    for index, url in enumerate(urls, start=1):

        print(f"\nFetching {index}/{len(urls)}")
        print(url)

        result = fetch_page(url)

        results.append(result)

        print(f"Status       : {result['status']}")
        print(f"HTTP Code    : {result['status_code']}")
        print(f"Time         : {result['total_time']} sec")

        if result["status"] == "success":
            print(
                f"Content Size : "
                f"{result['content_length']} bytes"
            )
        else:
            print(f"Error        : {result['error']}")

    return results

def save_results_to_file(
    results: List[Dict],
    filename: str = "output/synchronous_results.json"
) -> None:
    """
    Save synchronous HTTP request results to a JSON file.
    """

    # Create output directory if it does not already exist
    os.makedirs("output", exist_ok=True)

    with open(filename, "w", encoding="utf-8") as file:
        json.dump(
            results,
            file,
            indent=4,
            ensure_ascii=False
        )

    print(f"\nResults saved to: {filename}")

if __name__ == "__main__":

    print("=" * 60)
    print("SYNCHRONOUS RTX WEB REQUEST CLIENT")
    print("=" * 60)

    start = time.perf_counter()

    results = fetch_rtx_pages(RTX_URLS)

    total_time = time.perf_counter() - start

    successful = sum(
        1 for result in results
        if result["status"] == "success"
    )

    failed = len(results) - successful

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    print(f"URLs Processed : {len(results)}")
    print(f"Successful     : {successful}")
    print(f"Failed         : {failed}")
    print(f"Total Time     : {total_time:.3f} seconds")

    # Save collected data
    save_results_to_file(results)