import json
import os
import re


INPUT_FILE = "output/parsed_results.json"
OUTPUT_FILE = "output/normalized_results.json"


def load_data(
    path: str
) -> list[dict]:

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(file)


def normalize_integer(value):

    if value is None:
        return None

    value = value.replace(
        ",",
        ""
    )

    try:
        return int(value)

    except ValueError:
        return None


def normalize_float(value):

    if value is None:
        return None

    match = re.search(
        r"[\d.]+",
        str(value)
    )

    if not match:
        return None

    try:
        return float(
            match.group()
        )

    except ValueError:
        return None


def normalize_gpu(
    gpu: dict
) -> dict:

    return {

        "type": "hardware",

        "category": "GPU",

        "manufacturer": "NVIDIA",

        "model": gpu.get(
            "model"
        ),

        "generation": "RTX 50 Series",

        "architecture": gpu.get(
            "architecture"
        ),

        "cuda_cores": normalize_integer(
            gpu.get(
                "cuda_cores"
            )
        ),

        "ai_tops": normalize_float(
            gpu.get(
                "ai_tops"
            )
        ),

        "vram_gb": normalize_integer(
            gpu.get(
                "vram"
            )
        ),

        "memory_type": gpu.get(
            "memory_type"
        ),

        "base_clock_ghz": normalize_float(
            gpu.get(
                "base_clock"
            )
        ),

        "boost_clock_ghz": normalize_float(
            gpu.get(
                "boost_clock"
            )
        ),

        "graphics_power_w": normalize_integer(
            gpu.get(
                "graphics_power"
            )
        ),

        "source_url": gpu.get(
            "source_url"
        )
    }


def normalize_all(
    results: list[dict]
) -> list[dict]:

    normalized = []

    for gpu in results:

        normalized.append(
            normalize_gpu(gpu)
        )

    return normalized


def save_results(
    results: list[dict],
    path: str
):

    os.makedirs(
        "output",
        exist_ok=True
    )

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            results,
            file,
            indent=4,
            ensure_ascii=False
        )


def main():

    parsed_data = load_data(
        INPUT_FILE
    )

    normalized_data = normalize_all(
        parsed_data
    )

    save_results(
        normalized_data,
        OUTPUT_FILE
    )

    print(
        f"Normalized results saved to: "
        f"{OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()