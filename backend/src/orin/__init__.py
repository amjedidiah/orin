"""Orin: routes each task to the best-fit model or agent."""


def main() -> None:
    import uvicorn

    uvicorn.run("orin.main:app", host="127.0.0.1", port=8000, reload=True)
