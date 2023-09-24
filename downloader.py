import argparse
from utils.tcia import TciaAPI
from utils.tcia_downloader import TciaDownloader
from utils.aspera_downloader import AsperaDownloader
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
import tarfile


class Downloader:
    def __init__(self, user=None, password=None, root_dir="", tempdir="", logger=None, cache_dir=None, compress=None, mode=None) -> None:
        self.logger = logger
        self.root_dir = root_dir
        self.temp_dir = tempdir
        self.cache_dir = cache_dir
        self.user = user
        self.password = password
        self.compress = compress
        self.mode = mode
    
    def run(self, collection_name):
        #collection_temp_dir = path.join(self.temp_dir, collection_name)
        output_file = path.join(self.root_dir, f"{collection_name}.tar.gz")

        if os.path.exists(output_file):
            self.logger.warning("Output file already exists. Skipping download and compression.")
        else:    
            
            if self.mode=="nbia":
                downloader = TciaDownloader(user=self.user, password=self.password, logger=self.logger, collection_name=collection_name, tempdir=self.temp_dir, cache_dir=self.cache_dir)
            elif self.mode=="aspera":
                downloader = AsperaDownloader(collection=collection_name, logger=self.logger, user=self.user, password=self.password, temp_dir=self.temp_dir)
            
            downloader.run()
                        
            # compress
            if self.compress:
                self.logger.info("Compressing data")
                output_file = path.join(self.root_dir, f"{collection_name}.tar.gz")
                
                try:
                    command = ["tar", "-I", "pigz",  "-cf", output_file, "-C", self.temp_dir, collection_name, "--remove-files"]
                    subprocess.run(command)
                except Exception as e:
                    self.logger.error(f"An error occurred during compression: {e}")
                    raise e
            else:
                if path.dirname(self.temp_dir) != self.root_dir:
                    self.logger.info(f"Moving data to output directory '{self.root_dir}'")
                    shutil.move(self.temp_dir, self.root_dir)
        self.logger.info("Done")
    
    
    

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
    user = args.user
    password = args.password
    compress = args.compress
    verbosity = args.verbosity
    cache_dir = args.cache_dir
    log_dir = os.path.join(cache_dir, "logs") 
    os.makedirs(log_dir, exist_ok=True)
    temp_dir = args.output if args.temp_dir == None else args.temp_dir
    mode = args.mode
    
    if not verbosity in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
        raise Exception("Invalid level of verbosity.")
    
    logger = get_logger(verbosity=verbosity, log_dir=log_dir)
        
    
    if mode not in ["nbia", "aspera"]:
        raise AssertionError("Only nbia mode is supported at the moment. Future updates will include aspera as well.")

    if user == None or args.password == None:
        logger.info("No username or password provided. Downloading public data only.")

    if not os.path.exists(output):
        os.makedirs(output)

    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)

    

    try:
        downloader = Downloader(user=user, password=password, root_dir=output, tempdir=temp_dir, logger=logger, cache_dir=cache_dir, compress=compress, mode=mode)
        downloader.run(collection_name=collection_name)
    except Exception as e:
        logger.error(f"An error occurred during download of collection {collection_name}: {e}")
        raise e


    

main()