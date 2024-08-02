import yaml
import subprocess
import os
from downloader.Downloader import Downloader
from utils.utils import run_subprocess


class Manual(Downloader):
    def __init__(self, collection, logger, temp_dir, cache_dir, datasets, credentials=None):
        super(Manual, self).__init__(dataset=collection, logger=logger, temp_dir=temp_dir, cache_dir=cache_dir, datasets=datasets)

    
    def run(self):
        self.logger.info(f"Nothing to download for collection {self.collection}")
        return