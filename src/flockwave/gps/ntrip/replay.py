"""Replaying recorded NTRIP streams from JSON files."""

from __future__ import annotations

import click

from base64 import b64decode


@click.command()
@click.argument("file")
@click.option(
    "-p",
    "--port",
    metavar="PORT",
    default=5555,
    help="the port to listen on",
)
def ntrip_replayer(file, port):
    """Replays a recorded NTRIP stream from JSON format to clients connecting
    to the given TCP port, looped infinitely.
    """
    from json import loads

    try:
        from trio import BrokenResourceError, Path, run, serve_tcp, sleep
    except ImportError:
        raise ImportError(
            "You need to install 'trio' to use the NTRIP replayer"
        ) from None

    async def handle_request(stream):
        print("Connection open")
        finished = False
        while not finished:
            fp = await Path(file).open("r")  # type: ignore
            async with fp:
                async for line in fp:
                    obj = loads(line)
                    await sleep(obj["dt"] / 1000)
                    try:
                        await stream.send_all(b64decode(obj["data"]))
                    except BrokenResourceError:
                        finished = True
                        break
        print("Connection closed")

    async def main():
        host = ""
        print(f"Listening on {host}:{port}...")
        await serve_tcp(handle_request, port=port, host=host)

    run(main)


if __name__ == "__main__":
    ntrip_replayer()  # type: ignore
