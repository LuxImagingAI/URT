import yaml
import subprocess
import os
from utils.utils import run_subprocess

class OpenneuroDownloader:
    def __init__(self, collection, logger, temp_dir) -> None:
        self.collection = collection
        self.logger = logger
        self.temp_dir = temp_dir
    
    def run(self):
        with open("datasets/datasets.yaml", "r") as file:
            datasets = yaml.safe_load(file)

        url = datasets[self.collection]["url"]
        command = ["aws", "s3", "sync", "--no-sign-request", f"s3:{url}", os.path.join(self.temp_dir, self.collection)]
        self.logger.info(f"Downloading {self.collection} from openneuro via aws s3")
        run_subprocess(command, logger=self.logger)
        self.logger.info("Done")