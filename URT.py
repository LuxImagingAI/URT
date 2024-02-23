import argparse
from os import path
import os
from datetime import datetime
import shutil
import logging
import yaml
import pandas as pd
from utils.utils import run_subprocess
from utils import Modules
import importlib
import ast

version="2.0.0"

class URT:
    def __init__(self, credentials="config/credentials.yaml", root_dir="", temp_dir="", logger=None, cache_dir=None, compress=None, bids=None, dataset_name=None) -> None:
        self.logger = logger
        self.root_dir = root_dir
        self.temp_dir = temp_dir
        self.cache_dir = cache_dir
        self.compress = compress
        self.bids = bids
        self.collection_name = dataset_name
        self.collection_dir = os.path.join(temp_dir, dataset_name)
        self.datasets_file = yaml.safe_load(open("datasets/datasets.yaml", "r"))
        self.credentials = yaml.safe_load(open(credentials, "r"))
        self.bidsmap_path = os.path.join("datasets", "bidsmaps", f"{self.collection_name}.yaml")
        self.output_file = path.join(self.root_dir, f"{self.collection_name}.tar.gz")
        self.instantiate()


    # The input is checked for errors in advance in order to minimize user confusion in cases where datasets cannot be downloaded
    def instantiate(self):
        self.logger.info(f"\nInstantiating downloader {self.downloader} for datasets {self.collection_name}")

        # Check if valid bidsmaps are available for the datasets
        format = self.datasets_file[self.collection_name]["format"]
        if self.bids and format is not "bids":
            if "bids" not in self.datasets_file[self.collection_name] or not os.path.exists(self.bidsmap_path):
                raise Exception("No bids conversion possible: missing data for \"bids\" in datasets.yaml")
            
        # Check if output file already exists
        if os.path.exists(self.output_file):
            raise Exception(f"Output file ({self.output_file}) already exists. Skipping download and compression.")
        
        else:    

            # Get dataset information 
            if self.collection_name in self.datasets_file and "downloader" in self.datasets_file[self.collection_name]:
                self.downloader = self.datasets_file[self.collection_name]["downloader"]
                self.logger.info(f"Found entry in datasets.yaml. Using \"{self.downloader}\" for the download")
            else:
                self.downloader = "TciaDownloader"
                self.logger.warning("No entry for the collection in datasets.yaml. In this case only download through TCIA (DICOM) is supported. Fallback to downloader \"TciaDownloader\".")
            
            # Get user and password
            if self.downloader in self.credentials and "user" in self.credentials[self.downloader] and "password" in self.credentials[self.downloader]:
                user = self.credentials[self.downloader]["user"]
                password = self.credentials[self.downloader]["password"]

                if user == None or password == None:
                    self.logger.info(f"No credentials given (credentials.yaml contains \"None\" values for {self.downloader}): Only public datasets supported.")
            else:
                user = None
                password = None
                self.logger.info(f"No entry for {self.downloader} in credentials.yaml: Only public datasets supported.")

            # Instantiate the downloader
            module = importlib.import_module(f"downloader.{self.downloader}")

            downloader_obj = getattr(module, self.downloader)
            self.downloader_instance = downloader_obj(user=user, password=password, logger=self.logger, collection=self.collection_name, temp_dir=self.temp_dir, cache_dir=self.cache_dir)
        return
    

    def run(self):
        # Check if output file already exists

        # Download the data
        self.downloader_instance.run()
        
        # Converts data to the bids format (if bids argument is given and data is in dicom or unordered nifti format)
        self.convert_to_bids()

        # Add dseg.tsv file if applicable, now added to convert_to_bids() method
        # self.add_dseg_file()

        # if "keep_patients" is defined: remove unwanted patients
        self.execute_modules()

        # compress
        if self.compress:
            self.logger.info("Compressing data")
            
            try:
                command = ["tar", "-I", "pigz",  "-cf", self.output_file, "-C", self.temp_dir, self.collection_name, "--remove-files"]
                run_subprocess(command, logger=self.logger)
            except Exception as e:
                self.logger.error(f"An error occurred during compression: {e}")
                raise e
        else:
            if self.temp_dir != self.root_dir:
                self.logger.info(f"Moving data to output directory {self.root_dir}")
                shutil.move(os.path.join(self.temp_dir, self.collection_name), self.root_dir)
        self.logger.info("Done")

        return True
    
    def convert_to_bids(self):
        # Convert data if bids argument is given
        if self.bids:
            format = self.datasets_file[self.collection_name]["format"]

            
            # Convert dataset
            if format == "bids":
                self.logger.info("Dataset is already in BIDS format. Nothing to do ...")
            else:
                # Get relevant data from datasets.yaml and paths
                session_prefix = self.datasets_file[self.collection_name]["bids"]["session-prefix"]
                subject_prefix = self.datasets_file[self.collection_name]["bids"]["subject-prefix"]
                
                collection_dir = os.path.join(self.temp_dir, self.collection_name) 
                bids_collection_dir = os.path.join(self.temp_dir, f"{self.collection_name}_BIDS")
                plugin = "dcm2niix2bids" if format=="dicom" else "nibabel2bids"

                # Use bidsmapper
                self.logger.info("Starting bidsmapper")
                command = ["bidsmapper", "-f", "-a", "-n", subject_prefix, "-m", session_prefix, collection_dir, bids_collection_dir, "-t", bidsmap_path, "-p", plugin]
                run_subprocess(command, logger=self.logger)

                # Use bidscoiner
                self.logger.info("Starting bidscoiner")
                command = ["bidscoiner", "-f", collection_dir, bids_collection_dir]
                run_subprocess(command, logger=self.logger)

                # add dseg file if applicable
                self.execute_modules()

                shutil.rmtree(collection_dir)
                os.rename(bids_collection_dir, collection_dir)
                self.logger.info("Bids conversion finished")
                return
    
    def execute_modules(self):        
        if self.collection_name in self.datasets_file and "modules" in self.datasets_file[self.collection_name]:
            modules = self.datasets_file[self.collection_name]["modules"]
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
    parser.add_argument('--temp_dir', '-t', type=str, default=None, required=False, help='Temporary directory for downloading')
    parser.add_argument('--credentials', '-u', type=str, default="config/credentials.yaml", required=False, help='Username for TCIA')
    parser.add_argument('--compress', '-c', action='store_true', default=False, required=False, help='Choose whether to compress the downloaded data.')
    parser.add_argument('--bids', '-b', action='store_true', default=False, required=False, help='Choose whether to convert the downloaded data to BIDS format.')
    parser.add_argument('--verbosity', '-v', type=str, default="INFO", required=False, help="Choose the level of verbosity from [DEBUG, INFO, WARNING, ERROR, CRITICAL]. Default is 'INFO'")
    args = parser.parse_args()
        
    datasets = args.collection
    output = os.path.normpath(args.output_dir)
    compress = args.compress
    verbosity = args.verbosity
    cache_dir = args.cache_dir
    credentials = args.credentials
    log_dir = os.path.join(cache_dir, "logs") 
    os.makedirs(log_dir, exist_ok=True)
    temp_dir = args.output if args.temp_dir == None else args.temp_dir
    bids = args.bids
    
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
        with open(datasets) as f:
            dataset_list = yaml.safe_load(f)

    # If (string-) list is given
    elif datasets.startswith("["):
        dataset_list = ast.literal_eval(datasets)
    else:
        dataset_list = [datasets]

    i = 1
    downloader_list = []
    successful_downloads = []
    failed_downloads = []

    for d in dataset_list:
        logger.info(f"Starting with collection no. {i} from \"{datasets}\": {d}")
        dataset = d
        try:
            downloader_list.append(downloader = URT(credentials=credentials, root_dir=output, temp_dir=temp_dir, logger=logger, cache_dir=cache_dir, compress=compress, bids=bids, dataset_name=dataset))
        except Exception as e:
            logger.warning(f"Dataset \"{dataset}\" cannot be downloaded: {e}")
            failed_downloads.append(dataset)

    try:
        for downloader in downloader_list:
            downloader.run() 
    except Exception as e:
        logger.error(f"An error occurred during download of collections {dataset}: {e}")
        failed_downloads.append(dataset)
    finally:
        successful_downloads.append(dataset)
    
    logger.info("\n --- finished --- \nSuccessful datasets:")
    for dataset in successful_downloads: logger.info(f"{dataset}")

    if len(failed_downloads) > 0: 
        logger.warning("\nFailed datasets:")
        for dataset in failed_downloads: logger.warning(f"{dataset}")

main()