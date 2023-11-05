import subprocess
import yaml
from utils.utils import run_subprocess
from downloader.Downloader import Downloader

class AsperaDownloader(Downloader):
    def __init__(self, collection, logger, temp_dir, cache_dir, user=None, password=None) -> None:
        super(AsperaDownloader, self).__init__(collection=collection, logger=logger, temp_dir=temp_dir, cache_dir=cache_dir, user=user, password=password)
        self.user = user
        self.password = password
    
    def run(self):
        with open("datasets/datasets.yaml", "r") as file:
                    datasets = yaml.safe_load(file)

        url = datasets[self.collection]["url"]
        command = ["ascli", "faspex", "package", "recv", f"--username={self.user}", f"--password={self.password}", f"--url=https://faspex.cancerimagingarchive.net/aspera/faspex", f"--to-folder={self.temp_dir}", f"{url}"]
        self.logger.info(f"Downloading {self.collection} from tcia with aspera")
        run_subprocess(command, logger=self.logger)
        self.logger.info("Done")
        