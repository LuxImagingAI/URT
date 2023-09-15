import argparse
from utils.tcia import Tcia_api
from os import path
import subprocess, os
import pandas as pd
import time
import warnings
from datetime import datetime, timedelta
import multiprocessing as mp
import requests
import hashlib
import shutil
import sys
import signal
import requests_cache
import logging
from copy import deepcopy


class Downloader:
    def __init__(self, user=None, password=None, root_dir="", tempdir="", collection_name=None, logger=None, cache_dir=None) -> None:
        self.logger = logger
        self.tcia_api = Tcia_api(user=user, pw=password, logger=logger, cache_dir=cache_dir)
        self.root_dir = root_dir
        self.temp_dir = tempdir
        self.collection_name = collection_name
        self.series_metadata_df = None
        self.seriesDF = None
    
    
    def convert_StudyInstance_path(self, root_path, SeriesUID):  
        # Get entries from series dataframe and metadata dataframe
        entry_df = self.seriesDF[self.seriesDF["SeriesInstanceUID"] == SeriesUID]
        entry_metadata_df = self.series_metadata_df[self.series_metadata_df["Series UID"] == SeriesUID]

        if entry_df.empty:
            return None
        else:
        # Get metadata
            patient_id = entry_df["PatientID"].values[0]
            
            SeriesDate = entry_df["SeriesDate"]
            
            # Check if SeriesDate is NaN: In some cases image metadata does not contain the SeriesData which leads to NaN in the dataframe
            if SeriesDate.isnull().any():
                self.logger.debug("SeriesDate is NaN. Using 'unkown_date' as SeriesDate instead.")
                date = "unknown_date"
            else:
                date = str(datetime.strptime(SeriesDate.values[0], "%Y-%m-%d %H:%M:%S.%f").date().strftime("%d-%m-%Y"))

            SeriesInstanceUID = entry_df["SeriesInstanceUID"]
            StudyInstanceUID = entry_df["StudyInstanceUID"]
            SeriesDescription = entry_df["SeriesDescription"]
            SeriesNumber = entry_df["SeriesNumber"]
            StudyDescription = entry_metadata_df["Study Description"]
            self.logger.debug(f"One of the entries in the metadata is NaN. SeriesInstanceUID: {SeriesInstanceUID.values[0]}, StudyInstanceUID: {StudyInstanceUID.values[0]}, SeriesDescription: {SeriesDescription.values[0]}, Seriesnumber: {SeriesNumber.values[0]}, StudyDescription: {StudyDescription.values[0]}") if SeriesInstanceUID.isnull().any() or StudyInstanceUID.isnull().any() or SeriesDescription.isnull().any() or SeriesNumber.isnull().any() or StudyDescription.isnull().any() else None
            
            SeriesNumber = SeriesNumber.values[0]
            SeriesDescription = SeriesDescription.values[0]
            StudyInstanceUID = StudyInstanceUID.values[0][-5:] # last 5 digits are used as identifier (as in the original nbia downloader)
            SeriesInstanceUID = SeriesInstanceUID.values[0][-5:] # last 5 digits are used as identifier (as in the original nbia downloader)
            StudyDescription = StudyDescription.values[0]

            # Construct new path
            path = os.path.join(root_path, patient_id, f"{date}-{StudyDescription}-{StudyInstanceUID}", f"{SeriesNumber}-{SeriesDescription}-{SeriesInstanceUID}")
            
            return path
    
    
    def rename_patients(self, folder):
        self.logger.info("Renaming folders")
        #meta_data_df = pd.DataFrame.from_dict(series)
        
        for root, dirs, files in os.walk(folder):
            for dir in dirs:
                new_path = self.convert_StudyInstance_path(root, dir)
                
                if not new_path==None:
                    old_path = os.path.join(root, dir)                    
                    
                    # Rename instance
                    os.makedirs(new_path, exist_ok=True)
                    os.rename(old_path, new_path)
                    



    def md5(self, fname):
        hash_md5 = hashlib.md5()
        with open(fname, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def query_md5_series(self, series_df):
        SeriesInstanceUID = series_df["SeriesInstanceUID"].values
        assert(len(SeriesInstanceUID) == 1)
        SeriesInstanceUID = SeriesInstanceUID[0]
        
        SOPInstanceUIDS = self.tcia_api.getSOPInstanceUIDs(SeriesInstanceUID)
        
        md5_list = []
        for SOPInstanceUID in SOPInstanceUIDS:
            md5 = self.tcia_api.query_md5(SOPInstanceUID["SOPInstanceUID"])
            md5_list.append(md5)
        
        return md5_list
        
    def compute_md5_folder(self, folder):
        '''
        Returns the computed md5 hashes and the md5 hashes from the md5hashes.csv file for all files it can find in the folder.
        '''
        
        md5_dict = {
            "SeriesInstanceUID": [],
            "md5": [],
            "path": [],
        }
        
        real_md5_dict = {
            "SeriesInstanceUID": [],
            "md5": [],
            "path": [],
        }
        
        for root, dirs, files in os.walk(folder):
            for file in files:
                SeriesInstanceUID = root.split("/")[-1]
                if file.endswith(".dcm"):
                    md5_dict["path"].append(root)
                    md5_dict["SeriesInstanceUID"].append(SeriesInstanceUID)
                        
                    file_path = os.path.join(root, file)
                    md5_dict["md5"].append(self.md5(file_path))
                    
                if file.endswith("md5hashes.csv"):
                    real_md5_df = pd.read_csv(os.path.join(root, file))
                    for index, row in real_md5_df.iterrows():
                        real_md5_dict["path"].append(root)
                        real_md5_dict["SeriesInstanceUID"].append(SeriesInstanceUID)
                        real_md5_dict["md5"].append(row["MD5Hash"])
        md5_df = pd.DataFrame(md5_dict)
        real_md5_df = pd.DataFrame(real_md5_dict)
                    
        return md5_df, real_md5_df
    
    def get_corrupted_series_df(self, dir):
        md5_df, real_md5_df = self.compute_md5_folder(dir)
        corrupted_series_df = pd.concat([md5_df, real_md5_df]).drop_duplicates(keep=False).reset_index(drop=True)
        for path in set(corrupted_series_df["path"]):
            self.logger.warning(f"Corrupted series found: {path}.")           
        return corrupted_series_df
    
    
    def remove_corrupted_series(self, dir):
        if len(os.listdir(dir))==0:
            return
        else:
            self.logger.info("Checking for corrupted files")
            corrupted_series_df = self.get_corrupted_series_df(dir)
            counter = 0
            for path in set(corrupted_series_df["path"]):
                shutil.rmtree(path)
                counter += 1
            if counter==0:
                self.logger.info("No corrupted series found.")
            else:
                self.logger.info(f"Removed {counter} corrupted series.")
            return
    

    def remove_downloaded_instances(self, series, temp_dir):
        self.logger.info("Checking for downloaded instances")
        meta_data_df = pd.DataFrame.from_dict(series)
        meta_data_df_pruned = meta_data_df
        
        for root, dirs, files in os.walk(temp_dir):
            for dir in dirs:
                meta_data_df_pruned = meta_data_df_pruned[meta_data_df_pruned["SeriesInstanceUID"] != dir]
        
        
        for index, row in self.seriesDF.iterrows():
            path = self.convert_StudyInstance_path(temp_dir, row["SeriesInstanceUID"])
            if os.path.exists(path):
                meta_data_df_pruned = meta_data_df_pruned[meta_data_df_pruned["SeriesInstanceUID"] != row["SeriesInstanceUID"]]
        
        difference_df = pd.concat([meta_data_df, meta_data_df_pruned]).drop_duplicates(keep=False)
        if not difference_df.empty:
            for index, row in difference_df.iterrows():
                pruned_entry = row["SeriesInstanceUID"]
                self.logger.debug(f"Skipping instance {pruned_entry}: downloaded")
        
        self.logger.info(f"Found {len(difference_df)} downloaded instances in '{temp_dir}'")

        return meta_data_df_pruned


    def download_series_metadata(self, csv_filename):
        self.logger.debug("Downloading metadata")
        series_metadata_df = self.tcia_api.getSeriesMetadataDF(self.seriesDF)
        self.series_metadata_df = series_metadata_df
        series_metadata_df.to_csv(csv_filename, index=False)
        return
        
    def download_series(self):        
        # Remove already downloaded instances
        for i in range(1, 10):
            timeout = (i**2)+5
            series_to_download = self.remove_downloaded_instances(self.seriesDF, self.temp_dir)
            
            # rename folders to patient id if all dowloads were successful
            if len(series_to_download) == 0:
                return
            else:
                if i>1:
                    self.logger.warning(f"Download failed. Retrying in {timeout} seconds...")
                    time.sleep(timeout)
                self.tcia_api.downloadSeries(series_to_download, path=self.temp_dir)
                self.remove_corrupted_series(self.temp_dir)
            
        raise Exception("Download failed. Please check your internet connection and try again.")
        
    def add_paths_to_series(self):
        for index, values in self.seriesDF.iterrows():
            path = self.convert_StudyInstance_path(self.temp_dir, values["SeriesInstanceUID"])
            self.seriesDF.at[index, "path"] = path
        
    def remove_unkown_instances(self):
        for root, dirs, files in os.walk(self.temp_dir):
            if True in [file.endswith(".dcm") for file in files]:
                valid_UID = True if root.split("/")[-1] in self.seriesDF["SeriesInstanceUID"].values else False
                valid_path = True if root in self.seriesDF["path"].values else False
                if not valid_UID and not valid_path:
                    shutil.rmtree(root)
                    self.logger.warning(f"Removed unknown instance {root}")
        return

    def run(self):
        
        # check if collection exists
        self.tcia_api.check_collection(self.collection_name)
        
        # Get series from tcia api as dataframe
        self.seriesDF = self.tcia_api.getSeriesDF(self.collection_name)
        
        # Download metadata
        self.download_series_metadata(csv_filename=path.join(self.temp_dir, "metadata.csv"))
        
        # Add paths to series
        self.add_paths_to_series()
        
        # Remove unknown instances
        self.remove_unkown_instances()
        
        # Download series
        self.download_series()
        
        # Rename patients
        self.rename_patients(self.temp_dir)

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
    parser.add_argument('--temp_dir', '-t', type=str, default=None, required=False, help='Temporary directory for downloading')
    parser.add_argument('--user', '-u', type=str, default=None, required=False, help='Username for TCIA')
    parser.add_argument('--password', '-p', type=str, default=None, required=False, help='Password for TCIA')
    parser.add_argument('--mode', '-m', type=str, default='nbia', required=False, help='Which downloader to use (nbia, aspera)')
    parser.add_argument('--compress', '-c', action='store_true', default=False, required=False, help='Choose whether to compress the downloaded data. If False, the data will be downloaded only to the temporary directory')
    parser.add_argument('--bids', '-b', type=bool, default=False, required=False, help='Choose whether to convert the downloaded data to BIDS format. If False, the data will be downloaded only to the temporary directory')
    parser.add_argument('--verbosity', '-v', type=str, default="INFO", required=False, help="Choose the level of verbosity from [DEBUG, INFO, WARNING, ERROR, CRITICAL]. Default is 'INFO'")
    parser.add_argument('--cache_dir', '-l', type=str, default=os.path.join(os.path.expanduser("~"), ".cache", "tcia_downloader"), required=False, help='Directory for cached files and logs. Default is ~/.cache/tcia_downloader')
    args = parser.parse_args()
        
    collection_name = args.collection
    output = os.path.normpath(args.output)
    output_file = path.join(output, f"{collection_name}.tar.gz")
    user = args.user
    password = args.password
    compress = args.compress
    verbosity = args.verbosity
    cache_dir = args.cache_dir
    log_dir = os.path.join(cache_dir, "logs") 
    os.makedirs(log_dir, exist_ok=True)
    temp_dir = os.path.join(args.output, collection_name) if args.temp_dir == None else path.join(args.temp_dir, collection_name)
    
    if not verbosity in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
        raise Exception("Invalid level of verbosity.")
    
    logger = get_logger(verbosity=verbosity, log_dir=log_dir)
        
    
    if args.mode != "nbia":
        raise AssertionError("Only nbia mode is supported at the moment. Future updates will include aspera as well.")

    if user == None or args.password == None:
        logger.info("No username or password provided. Downloading public data only.")

    if not os.path.exists(output):
        os.makedirs(output)

    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)

    if os.path.exists(output_file):
        logger.warning("Output file already exists. Skipping download and compression.")

    else:    
        
        downloader = Downloader(user=user, password=password, logger=logger, collection_name=collection_name, root_dir=output, tempdir=temp_dir, cache_dir=cache_dir)
        try:
            downloader.run()
        except Exception as e:
            logger.error(f"An error occurred during download: {e}")
            raise e
            
        # compress
        if compress:
            try:
                logger.info("Compressing data")
                command = ["tar", "-I", "pigz",  "-cf", output_file, "-C", args.temp_dir, collection_name, "--remove-files"]
                subprocess.run(command)
            except Exception as e:
                raise e
                # logger.error(f"An error occurred during compression: {e}")
        else:
            if path.dirname(temp_dir) != output:
                logger.info(f"Moving data to output directory '{output}'")
                shutil.move(temp_dir, output)

main()