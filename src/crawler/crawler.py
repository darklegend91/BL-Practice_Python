import asyncio
import os
from crawl4ai import AsyncWebCrawler, BrowserConfig

RTX_URLS = [
    "https://www.nvidia.com/en-in/geforce/graphics-cards/50-series/rtx-5090/",
    "https://www.nvidia.com/en-in/geforce/graphics-cards/50-series/rtx-5080/",
    "https://www.nvidia.com/en-in/geforce/graphics-cards/50-series/rtx-5060-family/",
]
browser_config = BrowserConfig(
    headless=False
    )

async def crawl_page(urls : list[str]):
    results = []
    async with AsyncWebCrawler(config = browser_config) as crawler:
            for url in urls:
                result = await crawler.arun(url = url)
                results.append(result)
    
    return results


def save_to_file(path , results):
    
    os.makedirs(
            "output",
            exist_ok=True
        )
    
    with open(path , 'w') as md_file:
        md_file.write("# This is the crwaled Extracted Data")
        for result in results:
            
            if result.success:
                md_file.write(
                    f" ## Source :\n{result.url}\n\n"
                )
                md_file.write(
                    result.markdown.raw_markdown + "\n\n"
                    )
            
            else:
                md_file.write(
                    f"Failed Url \n"
                    f"{result.url}\n\n"
                )
                
                md_file.write(
                    f"Error: \n"
                    f"{result.error_message}\n\n"
                )
        print("Written Data to markdown file")
    

async def main():
    
    data = await crawl_page(RTX_URLS)
    save_to_file('output/crawled_data.md' , data)
        
if __name__ == "__main__":
    asyncio.run(main())