"""Fetch the publisher's public Drive folder, keeping its Delta directory layout."""
import re
from html.parser import HTMLParser
from pathlib import Path

import requests


class DrivePage(HTMLParser):
    """Read file names from Drive's embedded folder view and large-file confirmation form."""

    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.fields = {}
        self.link = None
        self.label = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a":
            self.link = attrs.get("href")
            self.label = []
        if tag == "input" and attrs.get("type") == "hidden" and "name" in attrs:
            self.fields[attrs["name"]] = attrs.get("value", "")

    def handle_data(self, text):
        if self.link:
            self.label.append(text)

    def handle_endtag(self, tag):
        if tag == "a" and self.link:
            self.links.append((self.link, "".join(self.label).strip()))
            self.link = None


def download_file(session, file_id, path):
    url = "https://drive.usercontent.google.com/download"
    params = {"id": file_id, "export": "download", "confirm": "t"}
    for _ in range(2):
        with session.get(url, params=params, stream=True, timeout=120) as response:
            response.raise_for_status()
            if "attachment" in response.headers.get("Content-Disposition", "").lower():
                with path.open("xb") as output:
                    for block in response.iter_content(1024 * 1024):
                        output.write(block)
                return
            fields = DrivePage(response.text).fields
            if fields.get("id") != file_id or "confirm" not in fields:
                break
            params.update(fields)
    raise ValueError(f"Drive did not serve {path.name} as a download")


def download_folder(session, folder_id, dest, ancestors=()):
    if folder_id in ancestors:
        raise ValueError("folder cycle in Drive release")
    response = session.get("https://drive.google.com/embeddedfolderview",
                           params={"id": folder_id}, timeout=60)
    response.raise_for_status()
    dest.mkdir()
    for href, name in DrivePage(response.text).links:
        match = re.fullmatch(r"https://drive\.google\.com/(file/d|drive/(?:u/\d+/)?folders)/([\w-]+)(?:/view)?(?:[?#].*)?", href)
        if not match:
            continue
        if not name or name in {".", ".."} or Path(name).name != name:
            raise ValueError(f"invalid release filename: {name!r}")
        kind, drive_id = match.groups()
        if kind == "file/d":
            download_file(session, drive_id, dest / name)
        else:
            download_folder(session, drive_id, dest / name, (*ancestors, folder_id))
