import yaml
from utils.utils import run_subprocess
from downloader.Downloader import Downloader

class AsperaDownloader(Downloader):
    def __init__(self, dataset, logger, temp_dir, cache_dir, credentials=None) -> None:
        super(AsperaDownloader, self).__init__(dataset=dataset, logger=logger, temp_dir=temp_dir, cache_dir=cache_dir)
        try:
            self.user = credentials["TCIA"]["user"]
            self.password = credentials["TCIA"]["password"]
        except:
            self.user = None
            self.password = None
    
    def run(self):
        with open("datasets/datasets.yaml", "r") as file:
                    datasets = yaml.safe_load(file)

        url = datasets[self.dataset]["url"]
        if self.password == None:
            self.logger.info(f"No credentials given to AsperaDownloader: only download of public datasets possible")

        self.logger.info(f"Downloading {self.dataset} from TCIA with aspera")

        try:
            command = ["ascli", "faspex5", "packages", "receive", f"--url={url}", f"--username={self.user}", f"--password={self.password}", f"--to-folder={self.temp_dir}"]
            run_subprocess(command, logger=self.logger)
        except Exception as e:
            # self.logger.error(f"You might need to check your permissions to download this dataset. Error: {e}")
            # raise e
            raise Exception("Ascli download failed: either ascli threw an error or you don't have the access permissions for this dataset.") from e
        self.logger.info("Done")
     