"""Replaying recorded NTRIP streams from JSON files."""

from __future__ import annotations

from typing import AsyncIterator

import click
import sys

from base64 import b64decode


@click.command()
@click.argument("file")
@click.option(
    "-p",
    "--port",
    metavar="PORT",
    default=5555,
    help="the port to listen on; zero or negative if no TCP port is needed",
)
@click.option(
    "--stdout/--no-stdout",
    default=False,
    help="dump the recorded NTRIP stream to the standard output",
)
def ntrip_replayer(file, port: int = 5555, stdout: bool = False):
    """Replays a recorded NTRIP stream from JSON format to clients connecting
    to the given TCP port, looped infinitely.
    """
    from json import loads

    try:
        from trio import BrokenResourceError, Path, open_nursery, run, serve_tcp, sleep
    except ImportError:
        raise ImportError(
            "You need to install 'trio' to use the NTRIP replayer"
        ) from None

    def log(msg: str) -> None:
        print(msg, file=sys.stderr)

    async def iter_contents_of(file: str) -> AsyncIterator[bytes]:
        while True:
            fp = await Path(file).open("r")  # type: ignore
            async with fp:
                async for line in fp:
                    obj = loads(line)
                    await sleep(obj["dt"] / 1000)
                    yield b64decode(obj["data"])

    async def handle_request(stream):
        log("Connection open")
        async for _chunk in iter_contents_of(file):
            try:
                await stream.send_all(_chunk)
            except BrokenResourceError:
                break
        log("Connection closed")

    async def handle_tcp_socket():
        host = "0.0.0.0"
        log(f"Listening on {host}:{port}...")
        await serve_tcp(handle_request, port=port, host=host)

    async def handle_stdout():
        log("Dumping stream to standard output...")
        async for chunk in iter_contents_of(file):
            sys.stdout.buffer.write(chunk)
            sys.stdout.buffer.flush()

    async def main():
        async with open_nursery() as nursery:
            if port > 0:
                nursery.start_soon(handle_tcp_socket)
            if stdout:
                nursery.start_soon(handle_stdout)

    run(main)


if __name__ == "__main__":
    ntrip_replayer()  # type: ignore
