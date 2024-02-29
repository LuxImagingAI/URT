import yaml
from utils.utils import run_subprocess, OutputLogger, compute_checksum
from downloader.Downloader import Downloader
import synapseclient
import contextlib
import synapseutils
import zipfile
import os, shutil

class SynapseDownloader(Downloader):
    def __init__(self, dataset, logger, temp_dir, cache_dir, credentials=None) -> None:
        super(SynapseDownloader, self).__init__(dataset=dataset, logger=logger, temp_dir=temp_dir, cache_dir=cache_dir)
        
        self.syn = synapseclient.Synapse(silent=True, cache_root_dir=self.cache_dir)
        self.synapse_file_hashes_path = os.path.join(temp_dir, ".synapse_file_hashes.yaml")
        self.dataset_path = os.path.join(self.temp_dir, self.dataset)

        try:
            self.token = credentials["Synapse"]["token"]
        except:
            self.token = None

        with contextlib.redirect_stderr(OutputLogger(self.logger)):
            self.syn.login(authToken=self.token, silent=True)
        
        # Create file for storing checksums of completed downloads in the temporary directory. Otherwise problems might occur when bids conversion fails and URT is restarted
        if not os.path.isfile(self.synapse_file_hashes_path):
            self.logger.debug(f"\"{self.synapse_file_hashes_path}\" does not yet exists: creating file.")
            with open(self.synapse_file_hashes_path, "w") as f:
                yaml.safe_dump({"placeholder":"placeholder"}, f)

    
    def run(self):
        if self.check_for_downloaded_data(): return

        with open("datasets/datasets.yaml", "r") as file:
            datasets = yaml.safe_load(file)

        if not "id" in datasets[self.dataset]:
            raise Exception(f"The dataset {self.dataset} is missing an id in the datasets.yaml file")
        
        id = datasets[self.dataset]["id"]
        self.logger.info(f"Downloading {self.dataset} from Synapse")

        # Download the data via synapse API
        with contextlib.redirect_stdout(OutputLogger(self.logger)):
            files = synapseutils.syncFromSynapse(self.syn, id, path=self.temp_dir) 
        
        # Unpack the data
        file_path = files[0].path
        self.logger.debug("Unpacking dataset from .zip archive")
        output_folder = os.path.join(self.temp_dir, self.dataset)
        output_folder_temp = os.path.join(self.temp_dir, ".tmp", self.dataset)
        with zipfile.ZipFile(file_path, "r") as zip_ref:
            zip_ref.extractall(output_folder_temp)

        # Adjust path
        directory = os.listdir(output_folder_temp)[0]
        dataset_dir = os.path.join(output_folder_temp, directory)
        self.logger.debug(f"Moving dataset from {dataset_dir} to {output_folder}")
        shutil.move(dataset_dir, output_folder)
        shutil.rmtree(output_folder_temp)
        os.remove(file_path)
        self.add_checksum()
        # No sophisticated error handling needed for corrupted datasets: synapseutils will remove any partially downloaded dataset when interrupted
        # TODO but error handling when dataset is downloaded but BIDS conversion fails is needed
    
    def check_for_downloaded_data(self):
        with open(self.synapse_file_hashes_path, "r") as f:
            synapse_checksums = yaml.safe_load(f)
        
        if self.dataset in synapse_checksums:
            # If checksum exists but not the folder of the dataset remove checksum and return False
            if not os.path.isdir(self.dataset_path) and not os.path.isfile(self.dataset_path):
                self.logger.debug(f"Path is not a file or directory: {self.dataset_path}")
                self.remove_checksum()
                return False
            
            path = self.dataset_path
            computed_checksum = compute_checksum(path)
            if synapse_checksums[self.dataset] == computed_checksum:
                self.logger.info(f"Found partially processed dataset in temporary directory: skipping download")
                return True
            else:
                self.logger.info(f"Found partially processed dataset in temporary directory with wrong checksum: deleting corrupted dataset.")
                shutil.rmtree(path)
                os.remove(path)
                return False
        
        return False
    
    def add_checksum(self):
        with open(self.synapse_file_hashes_path, "r") as f:
            synapse_checksums = yaml.safe_load(f)
        
        checksum = compute_checksum(self.dataset_path)
        synapse_checksums[self.dataset] = checksum

        with open(self.synapse_file_hashes_path, "w") as f:
                yaml.safe_dump(synapse_checksums, f)
    
    def remove_checksum(self):
        with open(self.synapse_file_hashes_path, "r") as f:
            synapse_checksums = yaml.safe_load(f)
        
        synapse_checksums.pop(self.dataset)

        with open(self.synapse_file_hashes_path, "w") as f:
                yaml.safe_dump(synapse_checksums, f)