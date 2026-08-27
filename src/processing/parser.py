import json
import os
import re


INPUT_FILE = "output/crawled_data.md"
OUTPUT_FILE = "output/parsed_results.json"


def read_markdown(path: str) -> str:
    """
    Read crawled markdown file.
    """

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as file:

        return file.read()


def split_gpu_pages(content: str) -> list[dict]:
    """
    Split crawled markdown into individual source pages.
    """

    pages = []

    sections = content.split("## Source")

    for section in sections[1:]:

        lines = section.strip().splitlines()

        if not lines:
            continue

        url = lines[0].strip()

        page_content = "\n".join(
            lines[1:]
        )

        pages.append({
            "url": url,
            "content": page_content
        })

    return pages


def search_pattern(
    pattern: str,
    text: str
):
    """
    Search a regex pattern and return
    the first captured value.
    """

    match = re.search(
        pattern,
        text,
        re.IGNORECASE
    )

    if match:
        return match.group(1).strip()

    return None


def parse_gpu_page(page: dict) -> dict:
    """
    Extract meaningful GPU information
    from one NVIDIA markdown page.
    """

    text = page["content"]

    # ---------------------------------------------------
    # GPU model
    # ---------------------------------------------------

    model = search_pattern(
        r"(GeForce\s+RTX\s+\d{4}(?:\s+Ti)?)",
        text
    )

    # ---------------------------------------------------
    # Architecture
    # ---------------------------------------------------

    architecture = search_pattern(
        r"(Blackwell|Ada Lovelace|Ampere|Turing)",
        text
    )

    # ---------------------------------------------------
    # CUDA cores
    # Handles:
    # 21760 CUDA Cores
    # 21,760 CUDA Cores
    # ---------------------------------------------------

    cuda_cores = search_pattern(
        r"([\d,]+)\s*CUDA\s*Cores",
        text
    )

    # ---------------------------------------------------
    # VRAM and memory type
    # Example:
    # 32 GB GDDR7
    # ---------------------------------------------------

    vram_match = re.search(
        r"(\d+)\s*GB\s*(GDDR\dX?)",
        text,
        re.IGNORECASE
    )

    if vram_match:

        vram = vram_match.group(1)
        memory_type = vram_match.group(2)

    else:

        vram = None
        memory_type = None

    # ---------------------------------------------------
    # AI TOPS
    # ---------------------------------------------------

    ai_tops = search_pattern(
        r"([\d,.]+)\s*AI\s*TOPS",
        text
    )

    # ---------------------------------------------------
    # Boost clock
    # ---------------------------------------------------

    boost_clock = search_pattern(
        r"Boost Clock[^0-9]*([\d.]+\s*GHz)",
        text
    )

    # ---------------------------------------------------
    # Base clock
    # ---------------------------------------------------

    base_clock = search_pattern(
        r"Base Clock[^0-9]*([\d.]+\s*GHz)",
        text
    )

    # ---------------------------------------------------
    # Graphics power
    # ---------------------------------------------------

    graphics_power = search_pattern(
        r"(?:Total Graphics Power|TGP)[^0-9]*(\d+\s*W)",
        text
    )

    return {
        "source_url": page["url"],
        "model": model,
        "architecture": architecture,
        "cuda_cores": cuda_cores,
        "vram": vram,
        "memory_type": memory_type,
        "ai_tops": ai_tops,
        "base_clock": base_clock,
        "boost_clock": boost_clock,
        "graphics_power": graphics_power
    }


def parse_all_pages(
    pages: list[dict]
) -> list[dict]:

    parsed_results = []

    for page in pages:

        gpu_data = parse_gpu_page(
            page
        )

        parsed_results.append(
            gpu_data
        )

    return parsed_results


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

    content = read_markdown(
        INPUT_FILE
    )

    pages = split_gpu_pages(
        content
    )

    print(
        f"GPU pages found: {len(pages)}"
    )

    results = parse_all_pages(
        pages
    )

    for gpu in results:

        print("\n----------------------")

        print(
            f"Model        : {gpu['model']}"
        )

        print(
            f"CUDA Cores   : {gpu['cuda_cores']}"
        )

        print(
            f"VRAM         : {gpu['vram']}"
        )

        print(
            f"Memory Type  : {gpu['memory_type']}"
        )

    save_results(
        results,
        OUTPUT_FILE
    )

    print(
        f"\nParsed results saved to: "
        f"{OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()