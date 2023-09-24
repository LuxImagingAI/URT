import subprocess

class AsperaDownloader:
    def __init__(self, collection, logger, user, password, temp_dir) -> None:
        self.collection = collection
        self.logger = logger
        self.user = user
        self.password = password
        self.temp_dir = temp_dir
    
    def run(self):
        urls = {"UCSF-PDGM": "https://faspex.cancerimagingarchive.net/aspera/faspex/external_deliveries/357?passcode=e722861fdd0278611166a64f0b66e46d9e6ae17c"}
        url = urls[self.collection]
        command = ["ascli", "faspex", "package", "recv", f"--username={self.user}", f"--password={self.password}", f"--url=https://faspex.cancerimagingarchive.net/aspera/faspex", f"--to-folder={self.temp_dir}", f"{url}"]
        self.logger.info(f"Downloading {self.collection} from tcia with aspera")
        subprocess.run(command)
        self.logger.info("Done")
        