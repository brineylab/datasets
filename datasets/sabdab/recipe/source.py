"""SAbDab2's summary and one job-backed, IMGT-numbered instance-crop archive."""
import hashlib
import json
import time
from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def digest(value):
    return hashlib.sha256(value).hexdigest()


class Source:
    def __init__(self, base):
        self.base = base.rstrip("/")
        self.session = requests.Session()
        retry = Retry(total=3, backoff_factor=1, status_forcelist=(429, 502, 503, 504),
                      allowed_methods={"GET"})
        self.session.mount("https://", HTTPAdapter(max_retries=retry))

    def get(self, path):
        response = self.session.get(self.base + path, timeout=(15, 180))
        response.raise_for_status()
        return response.content

    def archive(self, path):
        options = dict(full_structure=False, antibody_instance_crops=True, include_antigen=True)
        jobs = "/download/search-structures/jobs"
        response = self.session.post(self.base + jobs, json=options, timeout=(15, 180))
        response.raise_for_status()
        job = response.json()
        url = jobs + "/" + quote(str(job["job_id"]), safe="")
        deadline = time.monotonic() + 12 * 3600
        while job["status"] in {"queued", "running"}:
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Structure export still pending: {url}")
            time.sleep(10)
            job = json.loads(self.get(url))
        if job["status"] != "completed":
            raise ValueError(f"Structure export failed: {job.get('error', job['status'])}")
        tmp = path.with_suffix(".part")
        with self.session.get(self.base + url + "/file", stream=True, timeout=(15, 300)) as response:
            response.raise_for_status()
            with tmp.open("wb") as output:
                for block in response.iter_content(1 << 20):
                    output.write(block)
        tmp.replace(path)
