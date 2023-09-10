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


class Downloader:
    def __init__(self, user=None, password=None, root_dir="", tempdir="", collection_name=None, logger=None) -> None:
        self.logger = logger
        self.tcia_api = Tcia_api(user=user, pw=password, logger=logger)
        self.root_dir = root_dir
        self.temp_dir = tempdir
        self.collection_name = collection_name
        self.series_metadata_df = None
        self.seriesDF = None
    
    def rename_patients(self, folder):
        self.logger.info("Renaming folders")
        #meta_data_df = pd.DataFrame.from_dict(series)
        
        for root, dirs, files in os.walk(folder):
            for dir in dirs:
                entry_df = self.seriesDF[self.seriesDF["SeriesInstanceUID"] == dir]
                entry_metadata_df = self.series_metadata_df[self.series_metadata_df["Series UID"] == dir]
                
                # if the directory is a SeriesInstanceUID: move it to the patient folder
                if not entry_df.empty:
                    patient_id = entry_df["PatientID"].values[0]
                    date = str(datetime.strptime(entry_df["SeriesDate"].values[0], "%Y-%m-%d %H:%M:%S.%f").date().strftime("%d-%m-%Y"))

                    SeriesInstanceUID = entry_df["SeriesInstanceUID"].values[0]
                    SeriesInstanceUID = SeriesInstanceUID[-5:]
                    StudyInstanceUID = entry_df["StudyInstanceUID"].values[0]
                    StudyInstanceUID = StudyInstanceUID[-5:]
                    SeriesDescription = entry_df["SeriesDescription"].values[0]
                    SeriesNumber = entry_df["SeriesNumber"].values[0]
                    
                    # dicom_tag = self.tcia_api.getDicomTagsDF(SeriesUID=dir)
                    # study_desription = dicom_tag[dicom_tag["name"]=="Study Description"]["data"].values[0]
                    study_desription = entry_metadata_df["Study Description"].values[0]
                    old_path = os.path.join(root, dir)
                    new_path = os.path.join(root, patient_id, f"{date}-{study_desription}-{StudyInstanceUID}", f"{SeriesNumber}-{SeriesDescription}-{SeriesInstanceUID}")
                    
                    # to avoid recreation of the folder due to multiple runs
                    if not patient_id in old_path:
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
        Format:
        
        hash_dict = {
            SeriesInstanceUID: {
                path: path,
                hash: [md5, ..., md5]
                },
        }
        
        '''
        
        hash_dict = {}
        
        for root, dirs, files in os.walk(folder):
            for file in files:
                if file.endswith(".dcm"):
                    SeriesInstanceUID = root.split("/")[-1]
                    if not SeriesInstanceUID in hash_dict:
                        hash_dict[SeriesInstanceUID] = {}
                        hash_dict[SeriesInstanceUID]["path"] = root
                        hash_dict[SeriesInstanceUID]["md5"] = []
                        
                    file_path = os.path.join(root, file)
                    hash_dict[SeriesInstanceUID]["md5"].append(self.md5(file_path))
                    
        return hash_dict

    def remove_corrupted_series(self, dir, series):
        if len(os.listdir(dir))==0:
            return
        else:
            self.logger.info("Checking for corrupted files")
            
            series = pd.DataFrame.from_dict(series)
            hash_dict = self.compute_md5_folder(dir)
            counter = 0
            
            for key, value in hash_dict.items():
                md5_list = self.query_md5_series(series[series["SeriesInstanceUID"]==key])
                if not set(md5_list) == set(value["md5"]):
                    self.logger.warning(f"Corrupted files found in series {key}. Removing...")
                    shutil.rmtree(value["path"])
                    counter += 1
                else:
                    self.logger.debug(f"Series {key} is ok.")
            
            self.logger.info(f"Removed {counter} corrupted series.")
            return


    def remove_downloaded_instances(self, series, temp_dir):
        self.logger.info("Checking for already downloaded instances")
        meta_data_df = pd.DataFrame.from_dict(series)
        meta_data_df_pruned = meta_data_df
        
        for root, dirs, files in os.walk(temp_dir):
            for dir in dirs:
                mask = meta_data_df_pruned["SeriesInstanceUID"] != dir
                meta_data_df_pruned = meta_data_df_pruned[mask]
        
        difference_df = pd.concat([meta_data_df, meta_data_df_pruned]).drop_duplicates(keep=False)
        if not difference_df.empty:
            for index, row in difference_df.iterrows():
                pruned_entry = row["SeriesInstanceUID"]
                self.logger.debug(f"Skipping instance {pruned_entry}: already downloaded")
        
        self.logger.info(f"Found {len(difference_df)} already downloaded instances")

        return meta_data_df_pruned


    def download_series_metadata(self, csv_filename):
        self.logger.debug("Downloading metadata")
        series_metadata_df = self.tcia_api.getSeriesMetadataDF(self.seriesDF)
        self.series_metadata_df = series_metadata_df
        series_metadata_df.to_csv(csv_filename, index=False)
        return
        
    def download_series(self):
        series_to_download = self.seriesDF
        
        # Remove already downloaded instances
        for i in range(1, 10):
            timeout = (i**2)+5
            
            self.remove_corrupted_series(self.temp_dir, self.seriesDF)
            series_to_download = self.remove_downloaded_instances(series_to_download, self.temp_dir)
            
            # rename folders to patient id if all dowloads were successful
            if len(series_to_download) == 0:
                return
            else:
                if i>1:
                    self.logger.warning(f"Download failed. Retrying in {timeout} seconds...")
                    time.sleep(timeout)
                self.tcia_api.downloadSeries(series_to_download, path=self.temp_dir)
            
        raise Exception("Download failed. Please check your internet connection and try again.")


    def run(self):

        # check if collection exists
        self.tcia_api.check_collection(self.collection_name)
        
        # Get series from tcia api as dataframe
        self.seriesDF = self.tcia_api.getSeriesDF(self.collection_name)
        
        # Download series
        self.download_series()
        
        # Download metadata
        self.download_series_metadata(csv_filename=path.join(self.temp_dir, "metadata.csv"))
        
        # Rename patients
        self.rename_patients(self.temp_dir)

def get_logger(verbosity):
    logger = logging.getLogger(__name__)
    logger.propagate = False
    level = getattr(logging, verbosity)
    logger.setLevel(logging.DEBUG)
            
    formatter = logging.Formatter(fmt ='%(asctime)s %(levelname)s: %(message)s', datefmt='%m/%d/%Y %H:%M:%S')
    
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(level)
    stream_handler.setFormatter(formatter)
    
    os.makedirs("logs", exist_ok=True)
    file_handler_info = logging.FileHandler("logs/downloader.log", mode="w")
    file_handler_info.setLevel(logging.INFO)
    file_handler_info.setFormatter(formatter)
    
    file_handler_debug = logging.FileHandler("logs/downloader_debug.log", mode="w")
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
    parser.add_argument('--output', '-o', type=str, default='', required=False, help='Output directory')
    parser.add_argument('--temp_dir', '-t', type=str, default='', required=False, help='Temporary directory for downloading')
    parser.add_argument('--user', '-u', type=str, default=None, required=False, help='Username for TCIA')
    parser.add_argument('--password', '-p', type=str, default=None, required=False, help='Password for TCIA')
    parser.add_argument('--mode', '-m', type=str, default='nbia', required=False, help='Which downloader to use (nbia, aspera)')
    parser.add_argument('--compress', '-c', action='store_true', default=False, required=False, help='Choose whether to compress the downloaded data. If False, the data will be downloaded only to the temporary directory')
    parser.add_argument('--bids_format', '-b', type=bool, default=False, required=False, help='Choose whether to convert the downloaded data to BIDS format. If False, the data will be downloaded only to the temporary directory')
    parser.add_argument('--verbosity', '-v', type=str, default="INFO", required=False, help="Choose the level of verbosity from [DEBUG, INFO, WARNING, ERROR, CRITICAL]. Default is 'INFO'")
    args = parser.parse_args()
        
    collection_name = args.collection
    output = args.output
    output_file = path.join(output, f"{collection_name}.tar.gz")
    temp_dir = path.join(args.temp_dir, collection_name)
    user = args.user
    password = args.password
    compress = args.compress
    verbosity = args.verbosity
    
    if not verbosity in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
        raise Exception("Invalid level of verbosity.")
    
    logger = get_logger(verbosity=verbosity)
        
    
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
        
        downloader = Downloader(user=user, password=password, logger=logger, collection_name=collection_name, root_dir=output, tempdir=temp_dir)
        downloader.run()
            
        # compress
        if compress:
            try:
                logger.info("Compressing data")
                command = ["tar", "-I", "pigz",  "-cf", output_file, "-C", args.temp_dir, collection_name, "--remove-files"]
                subprocess.run(command)
            except Exception as e:
                raise e
                # logger.error(f"An error occurred during compression: {e}")

main()