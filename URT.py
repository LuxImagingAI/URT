import argparse
import os
from datetime import datetime
import shutil
import logging
import yaml
from utils.utils import run_subprocess, compress, decompress, compute_checksum, exists_credentials_file, create_credentials_file
from utils import Modules
import importlib
import copy

version="2.0.4"

class URT:
    def __init__(self, credentials_file="config/credentials.yaml", root_dir="", temp_dir="", logger=None, cache_dir=None, compress=None, bids=None, dataset_name=None) -> None:
        self.logger = logger
        self.root_dir = root_dir
        self.PATH_TO_URT_FOLDER = os.path.dirname(os.path.realpath(__file__))
        self.temp_dir = temp_dir
        self.cache_dir = cache_dir
        self.compress = compress
        self.bids = bids

        self.dataset_name = dataset_name

        self.dataset_folder = dataset_name
        if bids:
            self.dataset_folder += "_BIDS"

        self.dataset_output_name = self.dataset_folder
        if compress:
            self.dataset_output_name += ".tar.gz"
        

        self.temp_collection_dir = os.path.join(temp_dir, self.dataset_folder)
        # self.temp_collection_dir_bids = os.path.join(self.temp_dir, f"{self.dataset_name_bids}")

        self.dataset_output_folder_path = os.path.join(root_dir, self.dataset_folder)
        # self.output_collection_dir_bids = os.path.join(self.root_dir, f"{self.dataset_name_bids}")

        self.dataset_output_name_path = os.path.join(self.root_dir, self.dataset_output_name)
        # self.output_file_bids = path.join(self.root_dir, f"{self.dataset_name}_BIDS.tar.gz")

        self.bidsmap_path = os.path.join("datasets", "bidsmaps", f"{self.dataset_name}.yaml")
        if not os.path.isabs(self.bidsmap_path): self.bidsmap_path = os.path.join(self.PATH_TO_URT_FOLDER, self.bidsmap_path)

        self.file_hashes_path = os.path.join(self.root_dir, ".file_hashes.yaml")
        if not os.path.isabs(self.file_hashes_path): self.file_hashes_path = os.path.join(self.PATH_TO_URT_FOLDER, self.file_hashes_path)

        self.credentials_file = credentials_file
        if not os.path.isabs(self.credentials_file): self.credentials_file = os.path.join(self.PATH_TO_URT_FOLDER, self.credentials_file)

        self.datasets_path = os.path.join("datasets", "datasets.yaml")
        if not os.path.isabs(self.datasets_path): self.datasets_path = os.path.join(self.PATH_TO_URT_FOLDER, self.datasets_path)

        self.instantiate()


    # The input is checked for errors in advance in order to minimize user confusion in cases where datasets cannot be downloaded
    def instantiate(self):
        
        # Open relevant files
        if not os.path.isfile(self.file_hashes_path):
            self.logger.debug(f"\"{self.file_hashes_path}\" does not yet exists: creating file.")
            with open(self.file_hashes_path, "w") as f:
                yaml.safe_dump({"placeholder":"placeholder"}, f)

        self.logger.info(f"Loading credentials from \"{self.credentials_file}\"")
        try:
            with open(self.credentials_file) as f:
                self.credentials = yaml.safe_load(f)
        except Exception as e:
            raise Exception(f"Could not read credentials file: {e}")
        with open(self.datasets_path, "r") as f:
            self.datasets_file = yaml.safe_load(f)
        
                
        # Check if valid bidsmaps are available for the datasets
        format = self.datasets_file[self.dataset_name]["format"]
        if self.bids and format != "bids":
            if "bids" not in self.datasets_file[self.dataset_name]:
                raise Exception("No bids conversion possible: missing data for \"bids\" in datasets.yaml")
            if not os.path.exists(self.bidsmap_path):
                raise Exception(f"No bids conversion possible: missing bidsmap for dataset \"{self.dataset_name}\"")
            
        # Get dataset information 
        if self.dataset_name in self.datasets_file and "downloader" in self.datasets_file[self.dataset_name]:
            self.downloader = self.datasets_file[self.dataset_name]["downloader"]
            self.logger.info(f"Found entry in datasets.yaml. Using \"{self.downloader}\" for the download")
        else:
            self.downloader = "TciaDownloader"
            self.logger.warning("No entry for the collection in datasets.yaml. In this case only download through TCIA (DICOM) is supported. Fallback to downloader \"TciaDownloader\".")


        # Instantiate the downloader
        module = importlib.import_module(f"downloader.{self.downloader}")

        downloader_obj = getattr(module, self.downloader)
        self.downloader_instance = downloader_obj(credentials=self.credentials, logger=self.logger, dataset=self.dataset_name, temp_dir=self.temp_dir, cache_dir=self.cache_dir, datasets=self.datasets_file)
        return
    

    def run(self):
        # Check if data already exists
        # TODO check for bugs
        if self.check_path_hash(self.dataset_output_name_path, self.dataset_output_name): 
            self.logger.info(f"Dataset {self.dataset_output_name} already existing in the output folder")
            return

        # Check if data only needs to be compressed or decompressed
        # TODO check for bugs
        self.logger.debug(f"Checking for existing compressed/uncompressed data")
        if self.check_for_existing_uncompressed_or_compressed_data(): return
        
        # TODO check rare cases, e.g. dataset downloaded but not yet converted and URT tool with the same dataset and --bids option is started
        # current behavior: re-download dataset and convert it

        # Download the data
        self.downloader_instance.run()
        
        # Converts data to the bids format (if bids argument is given and data is in dicom or unordered nifti format)
        self.convert_to_bids()

        # if "keep_patients" is defined: remove unwanted patients
        self.execute_modules()

        # compress
        
        if self.compress:
            self.logger.info("Compressing data")
            compress(output_file=self.dataset_output_name_path, path=self.temp_dir, input_directory=self.dataset_folder, logger=self.logger)
        else:
            if self.temp_dir != self.root_dir:
                self.logger.info(f"Moving data to output directory {self.root_dir}")
                temp_folder = os.path.join(self.temp_dir, self.dataset_folder)
                shutil.copytree(temp_folder, self.root_dir, dirs_exist_ok=True)
                os.remove(temp_folder)
        self.logger.info("Done")

        # Add checksum for finished dataset
        self.add_checksum(self.dataset_output_name_path, self.dataset_output_name)

        return True
    
    def add_checksum(self, path, name):
        with open(self.file_hashes_path, "r") as f:
            file_hashes = yaml.safe_load(f)

        checksum = compute_checksum(path)
        file_hashes[name] = checksum
        self.logger.debug(f"Added checksum {checksum} for dataset \"{name}\" to checksum file.")

        with open(self.file_hashes_path, "w") as f:
            yaml.safe_dump(file_hashes, f)

        return checksum
    
    def remove_checksum(self, name):
        with open(self.file_hashes_path, "r") as f:
            file_hashes = yaml.safe_load(f)

        if name in file_hashes:
            
            checksum = file_hashes.pop(name)
            self.logger.debug(f"Removed checksum {checksum} for dataset \"{self.dataset_name}\" file.")
            with open(self.file_hashes_path, "w") as f:
                yaml.safe_dump(file_hashes, f)


    # TODO commentary+logging
    def check_for_existing_uncompressed_or_compressed_data(self):
        with open(self.file_hashes_path, "r") as f:
            file_hashes = yaml.safe_load(f)

        # If target is compressed data and uncompressed data exists
        if self.compress:
            target_path = self.dataset_output_folder_path
            target_name = self.dataset_folder
            self.logger.debug(f"Checking if uncompressed dataset {target_name} is locally available")

            if target_name in file_hashes:
                if self.check_path_hash(target_path, target_name):
                    self.logger.info(f"Dataset {target_name} already existing in the output folder in uncompressed format. Compressing ...")
                    compress(output_file=self.dataset_output_name_path, path=self.root_dir, input_directory=target_name, logger=self.logger, remove_files=False)
                    self.add_checksum(self.dataset_output_name_path, self.dataset_output_name)
                    return True
        # If target is uncompressed data and compressed data exists
        else:
            target_path = self.dataset_output_name_path + ".tar.gz"
            target_name = self.dataset_output_name + ".tar.gz"
            self.logger.debug(f"Checking if compressed dataset {target_name} is locally available")

            if target_name in file_hashes:
                if self.check_path_hash(target_path, target_name):
                    self.logger.info(f"Dataset {target_name} already existing in the output folder in compressed format. Decompressing ...")
                    decompress(input_file=target_path, output_directory=self.root_dir, logger=self.logger)                
                    self.add_checksum(self.dataset_output_name_path, self.dataset_output_name)
                    return True

        return False

    
    def check_path_hash(self, path, name):
        with open(self.file_hashes_path, "r") as f:
            file_hashes = yaml.safe_load(f)

        if name in file_hashes:
            # If folder does not exists return False (means: not downloaded) and remove the checksum for this dataset from the checksum file
            if not os.path.isdir(path) and not os.path.isfile(path):
                self.logger.debug(f"Path is not a file or directory: {path}")
                self.remove_checksum(name)
                return False
        
            real_hash = file_hashes[name]
            computed_hash = compute_checksum(path)

            if computed_hash == real_hash:
                self.logger.debug(f"Checksum of local folder {path} is equivalent to checksum of {name}")
                return True
            else:
                # This case only happens when a dataset is downloaded but the hash value is not correct
                # Datasets which were only partially downloaded (downloader crashed) do not have a hash value yet
                if dir:
                    shutil.rmtree(path)
                else:
                    os.remove(path)
                self.logger.warning(f"Detected corrupted dataset. Removing {self.dataset_output_name_path}")
                return False
        
        else:
            self.logger.debug(f"No entry in  checksum file for {name}")
            return False

    def convert_to_bids(self):
        # Convert data if bids argument is given
        if self.bids:
            format = self.datasets_file[self.dataset_name]["format"]

            
            # Convert dataset
            if format == "bids":
                self.logger.info("Dataset is already in BIDS format. Nothing to do ...")
            else:
                # Get relevant data from datasets.yaml and paths
                session_prefix = self.datasets_file[self.dataset_name]["bids"]["session-prefix"]
                subject_prefix = self.datasets_file[self.dataset_name]["bids"]["subject-prefix"]
                
                dataset_temp_dir = os.path.join(self.temp_dir, self.dataset_name) 
                dataset_temp_dir_bids = os.path.join(self.temp_dir, self.dataset_name+"_BIDS") 
                plugin = "dcm2niix2bids" if format=="dicom" else "nibabel2bids"

                # Use bidsmapper
                self.logger.info("Starting bidsmapper")
                command = f"bidsmapper -f -a -n \"{subject_prefix}\" -m \"{session_prefix}\" \"{dataset_temp_dir}\" \"{dataset_temp_dir_bids}\" -t \"{self.bidsmap_path}\" -p \"{plugin}\""
                run_subprocess(command, logger=self.logger)

                # Use bidscoiner
                self.logger.info("Starting bidscoiner")
                command = f"bidscoiner -f \"{dataset_temp_dir}\" \"{dataset_temp_dir_bids}\""
                run_subprocess(command, logger=self.logger)

                shutil.rmtree(dataset_temp_dir)
                self.logger.info("Bids conversion finished")
                return
    
    def execute_modules(self):        
        if self.dataset_name in self.datasets_file and "modules" in self.datasets_file[self.dataset_name]:
            modules = self.datasets_file[self.dataset_name]["modules"]
            for module in modules:
                name = module["name"]
                try:
                    data = module["data"]
                except:
                    data = None
                function_obj = getattr(Modules, name)
                function_obj(self, data)
        return     


def get_logger(verbosity, log_dir):
    logger = logging.getLogger(__name__)
    logger.propagate = False
    level = getattr(logging, verbosity)
    logger.setLevel(logging.DEBUG)
            
    formatter = logging.Formatter(fmt ='%(asctime)s %(levelname)s: %(message)s', datefmt='%m/%d/%Y %H:%M:%S')
    
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(level)
    stream_handler.setFormatter(formatter)
    
    os.makedirs("logs", exist_ok=True)
    date = datetime.now()
    file_handler_info = logging.FileHandler(f"{log_dir}/{date}.log", mode="w")
    file_handler_info.setLevel(logging.INFO)
    file_handler_info.setFormatter(formatter)
    
    file_handler_debug = logging.FileHandler(f"{log_dir}/{date}_debug.log", mode="w")
    file_handler_debug.setLevel(logging.DEBUG)
    file_handler_debug.setFormatter(formatter)
    
    if logger.hasHandlers():
        logger.handlers.clear()

    logger.addHandler(stream_handler)
    logger.addHandler(file_handler_info)
    logger.addHandler(file_handler_debug)
    
    logger.debug(f"Level of verbosity: {verbosity}")
    return logger

def main():
    # parse arguments
    parser = argparse.ArgumentParser(description='Download data from TCIA')
    parser.add_argument('--dataset', '-co', type=str, required=True, help='Dataset name, dataset names as list or path to .yaml file')
    parser.add_argument('--output_dir', '-o', type=str, default='output', required=False, help='Output directory')
    parser.add_argument('--cache_dir', '-l', type=str, default=os.path.join(os.path.expanduser("~"), ".cache", "tcia_downloader"), required=False, help='Directory for cached files and logs. Default is ~/.cache/tcia_downloader')
    parser.add_argument('--temp_dir', '-t', type=str, default="temp", required=False, help='Temporary directory for downloading')
    parser.add_argument('--credentials', '-u', type=str, default="config/credentials.yaml", required=False, help='Username for TCIA')
    parser.add_argument('--compress', '-c', action='store_true', default=False, required=False, help='Choose whether to compress the downloaded data.')
    parser.add_argument('--bids', '-b', action='store_true', default=False, required=False, help='Choose whether to convert the downloaded data to BIDS format.')
    parser.add_argument('--verbosity', '-v', type=str, default="INFO", required=False, help="Choose the level of verbosity from [DEBUG, INFO, WARNING, ERROR, CRITICAL]. Default is 'INFO'")
    args = parser.parse_args()
        
    datasets = args.dataset
    output = os.path.normpath(args.output_dir)
    compress = args.compress
    verbosity = args.verbosity
    cache_dir = args.cache_dir
    credentials_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), args.credentials)
    log_dir = os.path.join(cache_dir, "logs") 
    os.makedirs(log_dir, exist_ok=True)
    temp_dir = args.output_dir if args.temp_dir == None else args.temp_dir
    bids = args.bids

    if temp_dir == output:
        raise Exception("Temporary directory and output directory cannot be the same")
    
    if not verbosity in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
        raise Exception("Invalid level of verbosity.")
    
    logger = get_logger(verbosity=verbosity, log_dir=log_dir)
    logger.info(f"URT downloader version {version} ")

    if not os.path.exists(output):
        os.makedirs(output)

    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)


    # If yaml file is given
    if datasets.endswith(".yaml"):
        datasets = os.path.join(os.path.dirname(os.path.realpath(__file__)), datasets)
        with open(datasets) as f:
            dataset_list = yaml.safe_load(f)
    # If (string-) list is given
    elif datasets.startswith("["):
        dataset_list = list(map(str.strip, datasets.strip('[]').split(",")))
    else:
        dataset_list = [datasets]

    with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "datasets/datasets.yaml"), "r") as f:
        datasets_file = yaml.safe_load(f)

    if not exists_credentials_file(credentials_file):
        logger.info(f"No credentials file found. Creating new one.")
        create_credentials_file(credentials_file)

    # Detect if dataset is a collection of subsets
    datasets_to_remove = []
    for d in dataset_list:
        if d in datasets_file and "subsets" in datasets_file[d]:
            datasets_to_remove.append(d)
            logger.info(f"Dataset \"{d}\" contains several subsets.")
            for s in datasets_file[d]["subsets"]:
                logger.info(f"Adding subset \"{s}\" to the list.")
                dataset_list.append(s)
    
    # Add empty strings to the remove-list
    for d in dataset_list:
        if d == "":
            logger.debug(f"Removing empty string from dataset_list: \"{d}\"")
            datasets_to_remove.append(d)

    # Remove parent-dataset
    dataset_set = set(dataset_list)
    for d in datasets_to_remove:
        if d in dataset_set:
            dataset_set.remove(d)
    dataset_list = list(dataset_set)
    logger.debug(f"Datasets to download after removal: {dataset_list}")

    i = 1
    downloader_list = []
    successful_downloads = []
    failed_downloads = []

    logger.info(f"----- Starting Initialization -----")
    for dataset in dataset_list:
        logger.info(f"Initializing dataset no. {i} of {len(dataset_list)}: {dataset}")
        i += 1
        try:
            downloader = URT(credentials_file=credentials_file, root_dir=output, temp_dir=temp_dir, logger=logger, cache_dir=cache_dir, compress=compress, bids=bids, dataset_name=dataset)
            downloader_list.append(downloader)
        except Exception as e:
            logger.exception(f"Dataset \"{dataset}\" cannot be downloaded")
            failed_downloads.append(dataset)
            # raise e # only for debugging


    logger.info(f"----- Starting Download -----")
    i = 1
    for downloader in downloader_list:
        logger.info(f"Downloading dataset no. {i} of {len(downloader_list)}: {downloader.dataset_name}")
        i += 1
        try:
            downloader.run()
        except Exception as e:
            logger.exception(f"An error occurred during download of collections {downloader.dataset_name}")
            failed_downloads.append(downloader.dataset_name)
            # raise e # only for debugging
        else:
            successful_downloads.append(downloader.dataset_name)
    
    logger.info("----------------")
    logger.info("--- finished ---")
    logger.info("----------------")

    if len(successful_downloads) > 0:
        logger.info(f"Sucessful datasets ({len(successful_downloads)}/{len(dataset_list)}):")
        for dataset in successful_downloads: logger.info(f"    {dataset}")

    if len(failed_downloads) > 0: 
        logger.info(f"Failed datasets ({len(failed_downloads)}/{len(dataset_list)}):")
        for dataset in failed_downloads: logger.info(f"    {dataset}")

main()