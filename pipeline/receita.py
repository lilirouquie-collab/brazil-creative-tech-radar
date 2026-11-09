"""Access to the Receita Federal open CNPJ files (Nextcloud / WebDAV share)."""
import csv
import io
import os
import re
import time
import zipfile
from xml.etree import ElementTree

import requests

DAV_NS = {"d": "DAV:"}
USER_AGENT = "BrazilCreativeTechRadar/1.0 (open-data research project)"


class ReceitaSource:
    def __init__(self, cfg):
        rc = cfg["receita"]
        self.token = rc["share_token"]
        self.webdav_base = rc["webdav_base"].rstrip("/")
        self.files_base = rc["files_base"]
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT

    def _propfind(self, url):
        last = None
        for attempt in range(5):
            try:
                r = self.session.request("PROPFIND", url, auth=(self.token, ""),
                                         headers={"Depth": "1"}, timeout=(20, 120))
                r.raise_for_status()
                return ElementTree.fromstring(r.content)
            except Exception as exc:  # network hiccups are frequent on release days
                last = exc
                time.sleep(15 * (attempt + 1))
        raise RuntimeError(f"Could not list {url}: {last}. If the Receita changed its "
                           "download share, update receita.share_token in config.yaml.")

    def list_months(self):
        root = self._propfind(self.webdav_base + "/")
        months = set()
        for resp in root.findall("d:response", DAV_NS):
            href = resp.find("d:href", DAV_NS).text or ""
            m = re.search(r"(\d{4}-\d{2})/?$", href)
            if m:
                months.add(m.group(1))
        return sorted(months)

    def list_files(self, month):
        root = self._propfind(f"{self.webdav_base}/{month}/")
        files = []
        for resp in root.findall("d:response", DAV_NS):
            href = resp.find("d:href", DAV_NS).text or ""
            m = re.search(r"/([^/]+\.zip)$", href, re.IGNORECASE)
            if m:
                files.append(requests.utils.unquote(m.group(1)))
        return files

    def latest_complete_month(self):
        """Most recent month whose folder already holds all the files we need."""
        for month in reversed(self.list_months()):
            files = set(self.list_files(month))
            needed = {f"Estabelecimentos{i}.zip" for i in range(10)}
            needed |= {f"Empresas{i}.zip" for i in range(10)}
            needed |= {"Simples.zip", "Cnaes.zip", "Municipios.zip", "Naturezas.zip"}
            if needed <= files:
                return month
        raise RuntimeError("No complete monthly release found on the Receita share.")

    def file_url(self, month, name):
        return self.files_base.format(token=self.token, month=month) + name

    def download(self, month, name, dest_dir):
        """Download with resume support; returns the local path."""
        url = self.file_url(month, name)
        path = os.path.join(dest_dir, name)
        for attempt in range(8):
            have = os.path.getsize(path) if os.path.exists(path) else 0
            headers = {"Range": f"bytes={have}-"} if have else {}
            try:
                with self.session.get(url, headers=headers, stream=True,
                                      timeout=(30, 300)) as r:
                    if r.status_code == 416:  # already complete
                        break
                    r.raise_for_status()
                    mode = "ab" if have and r.status_code == 206 else "wb"
                    with open(path, mode) as fh:
                        for chunk in r.iter_content(chunk_size=1 << 20):
                            fh.write(chunk)
                if zipfile.is_zipfile(path):
                    return path
                raise IOError("incomplete zip")
            except Exception as exc:
                print(f"  download {name} attempt {attempt + 1} failed: {exc}", flush=True)
                time.sleep(min(300, 20 * (attempt + 1)))
        if zipfile.is_zipfile(path):
            return path
        raise RuntimeError(f"Could not download {url}")


class LocalSource:
    """Reads zips from a local folder (tests, or files downloaded by hand)."""

    def __init__(self, folder, month):
        self.folder = folder
        self.month = month

    def latest_complete_month(self):
        return self.month

    def download(self, month, name, dest_dir):
        return os.path.join(self.folder, name)


def iter_rows(zip_path):
    """Yield CSV rows (lists of str) from every member of a Receita zip file."""
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.namelist():
            with zf.open(member) as raw:
                text = io.TextIOWrapper(raw, encoding="latin-1", newline="")
                cleaned = (line.replace("\x00", "") for line in text)
                yield from csv.reader(cleaned, delimiter=";", quotechar='"')


def load_code_table(zip_path):
    return {row[0].strip(): row[1].strip() for row in iter_rows(zip_path) if len(row) >= 2}
