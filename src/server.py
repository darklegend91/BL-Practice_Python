# src/server.py

from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import asyncio

from http_methods.httpx_client import async_fetch_many


HOST = "localhost"
PORT = 8000


class IntelligenceHandler(BaseHTTPRequestHandler):

    def send_json(
        self,
        data,
        status_code=200
    ):

        response = json.dumps(
            data,
            indent=4
        ).encode("utf-8")

        self.send_response(
            status_code
        )

        self.send_header(
            "Content-Type",
            "application/json"
        )

        self.send_header(
            "Content-Length",
            str(len(response))
        )

        self.end_headers()

        self.wfile.write(
            response
        )

    
    def do_GET(self):
        
        # --------------------------------
        # GET /
        # --------------------------------
        
        if self.path == "/":
            self.send_json(
                {
                "Server Status" : "Running"
                })

            return

        # --------------------------------
        # GET /health
        # --------------------------------

        if self.path == "/health":

            self.send_json({
                "status": "healthy"
            })

            return


        # --------------------------------
        # GET /results
        # --------------------------------

        if self.path == "/results":

            try:

                with open(
                    "output/normalized_results.json",
                    "r",
                    encoding="utf-8"
                ) as file:

                    results = json.load(
                        file
                    )

                self.send_json({
                    "count": len(results),
                    "results": results
                })

            except FileNotFoundError:

                self.send_json({
                    "count": 0,
                    "results": []
                })

            return


        # --------------------------------
        # Unknown endpoint
        # --------------------------------

        self.send_json(
            {
                "error": "Endpoint not found"
            },
            404
        )


    def do_POST(self):

        # --------------------------------
        # POST /crawl
        # --------------------------------

        if self.path == "/crawl":

            content_length = int(
                self.headers.get(
                    "Content-Length",
                    0
                )
            )

            body = self.rfile.read(
                content_length
            )

            try:

                request_data = json.loads(
                    body
                )

            except json.JSONDecodeError:

                self.send_json(
                    {
                        "error": "Invalid JSON"
                    },
                    400
                )

                return


            urls = request_data.get(
                "urls"
            )


            if not urls:

                self.send_json(
                    {
                        "error": (
                            "urls field is required"
                        )
                    },
                    400
                )

                return


            results = asyncio.run(
                async_fetch_many(
                    urls
                )
            )


            successful = sum(
                1
                for result in results
                if result["status"]
                == "success"
            )


            response = {

                "total_urls": len(
                    results
                ),

                "successful": successful,

                "failed": (
                    len(results)
                    - successful
                ),

                "results": results
            }


            self.send_json(
                response
            )

            return


        self.send_json(
            {
                "error": "Endpoint not found"
            },
            404
        )


def run_server():

    server = HTTPServer(
        (HOST, PORT),
        IntelligenceHandler
    )

    print(
        f"Server running at "
        f"http://{HOST}:{PORT}"
    )

    server.serve_forever()


if __name__ == "__main__":
    run_server()
