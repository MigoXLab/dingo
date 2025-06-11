import time

import pytest
from dingo.model.rule.utils.detect_lang import calculate_md5, download_fasttext


class TestDownloadFasttext:
    def test_download_fasttext(self):
        expected_md5 = "01810bc59c6a3d2b79c79e6336612f65"
        path = download_fasttext()
        assert calculate_md5(path) == expected_md5

    def test_not_download_fasttext(self):
        path_first = download_fasttext()
        timestamp1 = time.time()

        path_second = download_fasttext()
        timestamp2 = time.time()

        assert calculate_md5(path_first) == calculate_md5(path_second)
        assert timestamp2 - timestamp1 < 2
