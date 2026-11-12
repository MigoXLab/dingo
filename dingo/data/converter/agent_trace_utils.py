"""Lossless splitting of recognized execution-result envelopes."""

import re


_CHUNK = re.compile(r"Chunk ID:[ \t]+\S+[ \t]*")
_WALL = re.compile(r"Wall time:[ \t]+[0-9]+(?:\.[0-9]+)?[ \t]+seconds[ \t]*")
_HEADER = re.compile(
    r"(?:Process running with session ID[ \t]+\S+"
    r"|Process exited with code[ \t]+-?[0-9]+"
    r"|Original token count:[ \t]+[0-9]+"
    r"|Warning: truncated output[^\r\n]*)[ \t]*"
)
_OUTPUT = re.compile(r"Output:[ \t]*")


def split_tool_result(content: str) -> tuple[str, str]:
    """Keep the Output line in headers; headers + body always equals content.

    Ordinary text/JSON and unknown wrappers are kept as a complete body.
    Recognition is based on envelope syntax, never on the tool's name.
    """
    lines = content.splitlines(keepends=True)
    if not lines or not _CHUNK.fullmatch(lines[0].rstrip("\r\n")):
        return "", content
    offset = len(lines[0])
    wall_seen = False
    for line in lines[1:]:
        view = line.rstrip("\r\n")
        offset += len(line)
        if _OUTPUT.fullmatch(view):
            return (content[:offset], content[offset:]) if wall_seen else ("", content)
        if _WALL.fullmatch(view):
            wall_seen = True
        elif view.strip() and not _HEADER.fullmatch(view):
            return "", content
    return "", content
