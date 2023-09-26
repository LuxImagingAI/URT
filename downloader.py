import argparse
from utils.tcia_downloader import TciaDownloader
from utils.aspera_downloader import AsperaDownloader
from utils.openneuro_downloader import OpenneuroDownloader
from utils.utils import run_subprocess
from os import path
import subprocess, os
from datetime import datetime
import shutil
import logging
import yaml

version="1.0.0"

class CoGMIDownloader:
    def __init__(self, user=None, password=None, root_dir="", tempdir="", logger=None, cache_dir=None, compress=None, mode=None, bids=None, collection_name=None) -> None:
        self.logger = logger
        self.root_dir = root_dir
        self.temp_dir = tempdir
        self.cache_dir = cache_dir
        self.user = user
        self.password = password
        self.compress = compress
        self.mode = mode
        self.bids = bids
        self.collection_name = collection_name
    
    def run(self):
        #collection_temp_dir = path.join(self.temp_dir, collection_name)
        output_file = path.join(self.root_dir, f"{self.collection_name}.tar.gz")

        if os.path.exists(output_file):
            self.logger.warning("Output file already exists. Skipping download and compression.")
        else:    
            with open("datasets/datasets.yaml", "r") as file:
                    datasets = yaml.safe_load(file)

            if self.mode=="auto":
                if self.collection_name in datasets and "downloader" in datasets[self.collection_name]:
                    self.downloader = datasets[self.collection_name]["downloader"]
                    self.logger.info(f"Found entry in datasets.yaml. Using mode \"{self.downloader}\" for the download")
                else:
                    self.downloader = "nbia"
                    self.logger.warning("No entry for the collection in datasets.yaml. In this case only download through nbia is supported. Fallback to downloader \"nbia\".")

            if self.downloader=="nbia":
                downloader = TciaDownloader(user=self.user, password=self.password, logger=self.logger, collection_name=self.collection_name, tempdir=self.temp_dir, cache_dir=self.cache_dir)
            elif self.downloader=="aspera":
                downloader = AsperaDownloader(collection=self.collection_name, logger=self.logger, user=self.user, password=self.password, temp_dir=self.temp_dir)
            elif self.downloader=="openneuro":
                downloader = OpenneuroDownloader(logger=self.logger, collection=self.collection_name, temp_dir=self.temp_dir)
            
            if self.downloader != "none":
                downloader.run()
            
            # Converts data to the bids format (if bids argument is given and data is in dicom or unordered nifti format)
            self.convert_to_bids()

            # compress
            if self.compress:
                self.logger.info("Compressing data")
                output_file = path.join(self.root_dir, f"{self.collection_name}.tar.gz")
                
                try:
                    command = ["tar", "-I", "pigz",  "-cf", output_file, "-C", self.temp_dir, self.collection_name, "--remove-files"]
                    run_subprocess(command, logger=self.logger)
                except Exception as e:
                    self.logger.error(f"An error occurred during compression: {e}")
                    raise e
            else:
                if self.temp_dir != self.root_dir:
                    self.logger.info(f"Moving data to output directory '{self.root_dir}'")
                    shutil.move(os.path.join(self.temp_dir, self.collection_name), self.root_dir)
        self.logger.info("Done")
    
    def convert_to_bids(self):
        with open("datasets/datasets.yaml", "r") as file:
            datasets = yaml.safe_load(file)

        # Convert data if bids argument is given
        if self.bids:
            format = datasets[self.collection_name]["format"]

            # Dont convert datasets which are already in bids format (or dont contain valid bidsmaps)
            if format == "bids":
                self.logger.info("Dataset is already in BIDS format. Nothing to do ...")
            elif "bids" not in datasets[self.collection_name] or not os.path.exists(os.path.join("datasets", "bidsmaps", f"{self.collection_name}.yaml" )):
                self.logger.warning("No bids conversion possible: missing data for \"bids\" in datasets.yaml")
            
            # Convert dataset
            else:
                # Get relevant data from datasets.yaml and paths
                session_prefix = datasets[self.collection_name]["bids"]["session-prefix"]
                subject_prefix = datasets[self.collection_name]["bids"]["subject-prefix"]
                bidsmap_path = os.path.join("datasets", "bidsmaps", f"{self.collection_name}.yaml")
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

                shutil.rmtree(collection_dir)
                os.rename(bids_collection_dir, collection_dir)
                self.logger.info("Bids conversion finished")
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
    parser.add_argument('--collection', '-co', type=str, required=True, help='TCIA collection name')
    parser.add_argument('--output', '-o', type=str, default='output', required=False, help='Output directory')
    parser.add_argument('--cache_dir', '-l', type=str, default=os.path.join(os.path.expanduser("~"), ".cache", "tcia_downloader"), required=False, help='Directory for cached files and logs. Default is ~/.cache/tcia_downloader')
    parser.add_argument('--temp_dir', '-t', type=str, default=None, required=False, help='Temporary directory for downloading')
    parser.add_argument('--user', '-u', type=str, default=None, required=False, help='Username for TCIA')
    parser.add_argument('--password', '-p', type=str, default=None, required=False, help='Password for TCIA')
    parser.add_argument('--compress', '-c', action='store_true', default=False, required=False, help='Choose whether to compress the downloaded data.')
    parser.add_argument('--bids', '-b', action='store_true', default=False, required=False, help='Choose whether to convert the downloaded data to BIDS format.')
    parser.add_argument('--verbosity', '-v', type=str, default="INFO", required=False, help="Choose the level of verbosity from [DEBUG, INFO, WARNING, ERROR, CRITICAL]. Default is 'INFO'")
    args = parser.parse_args()
        
    collection_name = args.collection
    output = os.path.normpath(args.output)
    user = args.user
    password = args.password
    compress = args.compress
    verbosity = args.verbosity
    cache_dir = args.cache_dir
    log_dir = os.path.join(cache_dir, "logs") 
    os.makedirs(log_dir, exist_ok=True)
    temp_dir = args.output if args.temp_dir == None else args.temp_dir
    bids = args.bids
    mode = "auto"
    
    if not verbosity in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
        raise Exception("Invalid level of verbosity.")
    
    logger = get_logger(verbosity=verbosity, log_dir=log_dir)
    logger.info(f"CoGMI downloader version {version} ")
    
    if mode not in ["nbia", "aspera", "openneuro", "auto"]:
        raise AssertionError("Mode not supported. Check the documentation again")

    if user == None or args.password == None:
        logger.info("No username or password provided. Downloading public data only.")

    if not os.path.exists(output):
        os.makedirs(output)

    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)

    

    try:

        # If list is given convert all datasets
        if collection_name.endswith(".yaml"):
            with open(collection_name) as f:
                dataset_list = yaml.safe_load(f)
            i = 1
            for d in dataset_list:
                logger.info(f"Starting with collection no. {i} from \"{collection_name}\": {d}")
                collection_name = d
                downloader = CoGMIDownloader(user=user, password=password, root_dir=output, tempdir=temp_dir, logger=logger, cache_dir=cache_dir, compress=compress, mode=mode, bids=bids, collection_name=collection_name)
                downloader.run()
        
        else:
            downloader = CoGMIDownloader(user=user, password=password, root_dir=output, tempdir=temp_dir, logger=logger, cache_dir=cache_dir, compress=compress, mode=mode, bids=bids, collection_name=collection_name)
            downloader.run()
    except Exception as e:
        logger.error(f"An error occurred during download of collection {collection_name}: {e}")
        raise e


    

main()