import yaml
import subprocess
import os
from utils.utils import run_subprocess
from downloader.Downloader import Downloader


class AwsDownloader(Downloader):
    def __init__(self, collection, logger, temp_dir, cache_dir, user=None, password=None):
        super(AwsDownloader, self).__init__(collection=collection, logger=logger, temp_dir=temp_dir, cache_dir=cache_dir, user=user, password=password)

    
    def run(self):
        with open("datasets/datasets.yaml", "r") as file:
            datasets = yaml.safe_load(file)

        url = datasets[self.collection]["url"]
        command = ["aws", "s3", "sync", "--no-sign-request", f"s3:{url}", os.path.join(self.temp_dir, self.collection)]
        self.logger.info(f"Downloading {self.collection} from openneuro via AWS s3")
        run_subprocess(command, logger=self.logger)
        self.logger.info("Done")