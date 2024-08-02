import yaml
from utils.utils import run_subprocess, exists_command
from downloader.Downloader import Downloader

class AsperaDownloader(Downloader):
    def __init__(self, dataset, logger, temp_dir, cache_dir, datasets, credentials=None) -> None:
        super(AsperaDownloader, self).__init__(dataset=dataset, logger=logger, temp_dir=temp_dir, cache_dir=cache_dir, datasets=datasets)
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

        if not exists_command("ascli"):
            raise Exception("ascli command not found. Please install aspera-cli first.")
        
        try:
            command = f"ascli faspex5 packages receive --url={url} --username={self.user} --password={self.password} --to-folder={self.temp_dir}"
            run_subprocess(command, logger=self.logger)
        except Exception as e:
            # self.logger.error(f"{e}")
            # raise e
            raise Exception("Ascli download failed: either ascli threw an error or you don't have the access permissions for this dataset.") from e
        self.logger.info("Done")
     