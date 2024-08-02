import yaml
import subprocess
import os
from utils.utils import run_subprocess, exists_command
from downloader.Downloader import Downloader


class AwsDownloader(Downloader):
    def __init__(self, dataset, logger, temp_dir, cache_dir, datasets, credentials=None):
        super(AwsDownloader, self).__init__(dataset=dataset, logger=logger, temp_dir=temp_dir, cache_dir=cache_dir, datasets=datasets)
        try:
            self.user = credentials["user"]
            self.password = credentials["password"]
        except:
            self.user = None
            self.password = None

    
    def run(self):
        url = self.datasets[self.dataset]["url"]
        command = f"aws s3 sync --no-sign-request s3:{url} {os.path.join(self.temp_dir, self.dataset)}"
        self.logger.info(f"Downloading {self.dataset} from openneuro via AWS s3")
        
        if not exists_command("aws"):
            raise Exception("aws command not found. Please install awscli first.")
        
        try:
            run_subprocess(command, logger=self.logger)
        except Exception as e:
            # self.logger.error(f"{e}")
            raise Exception(f"Error while downloading {self.dataset} from openneuro via AWS s3.")
        self.logger.info("Done")