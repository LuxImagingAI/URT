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

version="2.0.0"

class URT:
    def __init__(self, credentials="config/credentials.yaml", root_dir="", temp_dir="", logger=None, cache_dir=None, compress=None, bids=None, collection_name=None) -> None:
        self.logger = logger
        self.root_dir = root_dir
        self.temp_dir = temp_dir
        self.cache_dir = cache_dir
        self.compress = compress
        self.bids = bids
        self.collection_name = collection_name
        self.collection_dir = os.path.join(temp_dir, collection_name)
        self.datasets = yaml.safe_load(open("datasets/datasets.yaml", "r"))
        self.credentials = yaml.safe_load(open(credentials, "r"))

    def run(self):
        #collection_temp_dir = path.join(self.temp_dir, collection_name)
        output_file = path.join(self.root_dir, f"{self.collection_name}.tar.gz")
        output_folder = path.join(self.root_dir, f"{self.collection_name}")
        if os.path.exists(output_file):
            self.logger.warning(f"Output file ({output_file}) already exists. Skipping download and compression.")
        elif os.path.exists(output_folder):
            self.logger.warning(f"Output folder ({output_folder}) already exists. Skipping download.")
        else:    

            # Get dataset information 
            if self.collection_name in self.datasets and "downloader" in self.datasets[self.collection_name]:
                self.downloader = self.datasets[self.collection_name]["downloader"]
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
                self.logger.info(f"No entry for {self.downloader} in credentials.yaml: Only public datasets supported.")

            # Start download
            module = importlib.import_module(f"downloader.{self.downloader}")

            downloader_obj = getattr(module, self.downloader)
            downloader_instance = downloader_obj(user=user, password=password, logger=self.logger, collection=self.collection_name, temp_dir=self.temp_dir, cache_dir=self.cache_dir)            
            downloader_instance.run()
            
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
                    command = ["tar", "-I", "pigz",  "-cf", output_file, "-C", self.temp_dir, self.collection_name, "--remove-files"]
                    run_subprocess(command, logger=self.logger)
                except Exception as e:
                    self.logger.error(f"An error occurred during compression: {e}")
                    raise e
            else:
                if self.temp_dir != self.root_dir:
                    self.logger.info(f"Moving data to output directory {self.root_dir}")
                    shutil.move(os.path.join(self.temp_dir, self.collection_name), self.root_dir)
        self.logger.info("Done")
    
    def convert_to_bids(self):
        # Convert data if bids argument is given
        if self.bids:
            format = self.datasets[self.collection_name]["format"]

            bidsmap_path = os.path.join("datasets", "bidsmaps", f"{self.collection_name}.yaml")
            # Dont convert datasets which are already in bids format (or dont contain valid bidsmaps)
            if format == "bids":
                self.logger.info("Dataset is already in BIDS format. Nothing to do ...")
            elif "bids" not in self.datasets[self.collection_name] or not os.path.exists(os.path.join("datasets", "bidsmaps", f"{self.collection_name}.yaml" )):
                self.logger.warning("No bids conversion possible: missing data for \"bids\" in datasets.yaml")
            elif not os.path.exists(bidsmap_path):
                self.logger.warning("Bidsmap not found")
            # Convert dataset
            else:
                # Get relevant data from datasets.yaml and paths
                session_prefix = self.datasets[self.collection_name]["bids"]["session-prefix"]
                subject_prefix = self.datasets[self.collection_name]["bids"]["subject-prefix"]
                
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
        if self.collection_name in self.datasets and "modules" in self.datasets[self.collection_name]:
            modules = self.datasets[self.collection_name]["modules"]
            for module in modules:
                name = module["name"]
                try:
                    data = module["data"]
                except:
                    data = None
                function_obj = getattr(Modules, name)
                function_obj(self, data)
        return
    
    def add_dseg_file(self):        
        if self.collection_name in self.datasets and "bids" in self.datasets[self.collection_name] and "masks" in self.datasets[self.collection_name]["bids"]:
            self.logger.info("Adding dseg.tsv file")
            masks = self.datasets[self.collection_name]["bids"]["masks"]
            masks_pd_compatible = {
                "index": [],
                "name": [],
                "mapping": []
            }
            i=0
            for key, value in masks.items():
                masks_pd_compatible["index"].append(i)
                masks_pd_compatible["name"].append(value)
                masks_pd_compatible["mapping"].append(key)
                i+=1
            
            masks_df = pd.DataFrame(masks_pd_compatible)

            # Write the DataFrame to a .tsv file
            masks_df.to_csv(os.path.join(self.collection_dir, 'dseg.tsv'), sep='\t', index=False)
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
    parser.add_argument('--credentials', '-u', type=str, default="config/credentials.yaml", required=False, help='Username for TCIA')
    parser.add_argument('--compress', '-c', action='store_true', default=False, required=False, help='Choose whether to compress the downloaded data.')
    parser.add_argument('--bids', '-b', action='store_true', default=False, required=False, help='Choose whether to convert the downloaded data to BIDS format.')
    parser.add_argument('--verbosity', '-v', type=str, default="INFO", required=False, help="Choose the level of verbosity from [DEBUG, INFO, WARNING, ERROR, CRITICAL]. Default is 'INFO'")
    args = parser.parse_args()
        
    collection_name = args.collection
    output = os.path.normpath(args.output)
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
    logger.info(f"CoGMI downloader version {version} ")

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
                downloader = URT(credentials=credentials, root_dir=output, temp_dir=temp_dir, logger=logger, cache_dir=cache_dir, compress=compress, bids=bids, collection_name=collection_name)
                downloader.run()
        
        else:
            logger.info(f"Starting with collection: {collection_name}")
            downloader = URT(credentials=credentials, root_dir=output, temp_dir=temp_dir, logger=logger, cache_dir=cache_dir, compress=compress, bids=bids, collection_name=collection_name)
            downloader.run()
    except Exception as e:
        logger.error(f"An error occurred during download of collection {collection_name}: {e}")
        raise e


    

main()