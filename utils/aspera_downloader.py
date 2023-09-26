import subprocess
import yaml
from utils.utils import run_subprocess

class AsperaDownloader:
    def __init__(self, collection, logger, user, password, temp_dir) -> None:
        self.collection = collection
        self.logger = logger
        self.user = user
        self.password = password
        self.temp_dir = temp_dir
    
    def run(self):
        with open("datasets/datasets.yaml", "r") as file:
                    datasets = yaml.safe_load(file)

        url = datasets[self.collection]["url"]
        command = ["ascli", "faspex", "package", "recv", f"--username={self.user}", f"--password={self.password}", f"--url=https://faspex.cancerimagingarchive.net/aspera/faspex", f"--to-folder={self.temp_dir}", f"{url}"]
        self.logger.info(f"Downloading {self.collection} from tcia with aspera")
        run_subprocess(command, logger=self.logger)
        self.logger.info("Done")
        