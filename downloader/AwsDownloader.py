import yaml
import subprocess
import os
from utils.utils import run_subprocess
from downloader.Downloader import Downloader


class AwsDownloader(Downloader):
    def __init__(self, dataset, logger, temp_dir, cache_dir, credentials=None):
        super(AwsDownloader, self).__init__(dataset=dataset, logger=logger, temp_dir=temp_dir, cache_dir=cache_dir)
        try:
            self.user = credentials["user"]
            self.password = credentials["password"]
        except:
            self.user = None
            self.password = None

    
    def run(self):
        with open("datasets/datasets.yaml", "r") as file:
            datasets = yaml.safe_load(file)

        url = datasets[self.dataset]["url"]
        command = ["aws", "s3", "sync", "--no-sign-request", f"s3:{url}", os.path.join(self.temp_dir, self.dataset)]
        self.logger.info(f"Downloading {self.dataset} from openneuro via AWS s3")
        run_subprocess(command, logger=self.logger)
        self.logger.info("Done")