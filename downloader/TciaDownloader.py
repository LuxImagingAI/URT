import os
import pandas as pd
import time
from datetime import datetime, timedelta
import requests
import sys
import requests_cache
import zipfile, io
from os import path
import hashlib
import shutil
from downloader.Downloader import Downloader

class TciaAPI:
    def __init__(self, user=None, pw=None, logger=None, cache_dir=None):
        self.cached_session = requests_cache.CachedSession(os.path.join(cache_dir, "http_cache.sqlite"), backend="sqlite", expire_after=timedelta(days=2))
        self.session = requests.Session()
        self.base_url = "https://services.cancerimagingarchive.net/nbia-api/services/v1/" if pw==None else "https://services.cancerimagingarchive.net/nbia-api/services/v2/"
        self.advanced_url = "https://services.cancerimagingarchive.net/nbia-api/services/"
        self.logger = logger
        self.token, self.token_expires = None, None
        self.user = user
        self.password = pw
        self.generate_tokens()
    
    def dict_to_dataframe(func):
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            #assert(isinstance(result, dict))
            return pd.DataFrame.from_dict(result)
        return wrapper

    def get_token(self, user, pw):
        token_url = "https://keycloak.dbmi.cloud/auth/realms/TCIA/protocol/openid-connect/token"
        params = {'client_id': 'nbia',
                        'scope': 'openid',
                        'grant_type': 'password',
                        'username': user,
                        'password': pw
                        }
        
        data = self.post_request(url=token_url, params=params)
        access_token = data.json()["access_token"]
        # expires_in = data.json()["expires_in"]
        # id_token = data.json()["id_token"]
    
        return access_token
    
    def generate_tokens(self):
        if not self.password==None:
            self.logger.info("Requesting token")
            token = self.get_token(self.user, self.password)
            token_expires = datetime.now() + timedelta(hours=1, minutes=50)
            self.logger.info(f"Token expires at {token_expires}")
        else:
            token = None
            token_expires = datetime.now() + timedelta(weeks=100)
        self.token_expires = token_expires
        self.token = token
        return
    
    def renew_tokens(self):
        if datetime.now() > self.token_expires:
            self.logger.info("Renewing token")
            self.generate_tokens()
        return

    def get_call_headers(self):
        if self.token == None:
            api_call_headers = None
        else:
            api_call_headers = {'Authorization': 'Bearer ' + self.token}
        return api_call_headers
    
    def post_request(self, url, params):
        '''
        Only used for requesting tokens
        '''
        data = None
        self.logger.debug(f"Requesting {url}")
        
        
        for i in range(0, 5):
            timeout = ((i+5)**2)+20
            try:
                data = self.session.post(url, data=params, timeout=timeout)  
            except Exception as e:
                if isinstance(e, KeyboardInterrupt):
                    sys.exit()
                self.logger.warning(f"POST request failed for {url} after timeout of {timeout} seconds. Retrying...")
                continue
            else:
                if data.status_code != 200:
                    self.logger.warning(f"POST request failed for {url} with status code {data.status_code}. Waiting for {timeout} seconds and retrying...")
                    time.sleep(timeout)
                    continue
                else:
                    return data
                

        raise Exception(f"Request failed {10} times for {url}.")
    
    def get_request(self, url, params={}, use_cache=True, advanced_api=False):
        data = None
        #self.logger.debug(f"Requesting {url} with params {params}")
        self.renew_tokens()
        
        for i in range(0, 10):
            timeout = ((i+5)**2)+20
            try:
                if use_cache:
                    data = self.cached_session.get(url = url, headers=self.get_call_headers(), params=params, timeout=timeout)
                else:
                    data = self.session.get(url = url, headers=self.get_call_headers(), params=params, timeout=timeout)
            except Exception as e:
                if isinstance(e, KeyboardInterrupt):
                    sys.exit()
                self.logger.warning(f"GET request failed for {url} with params {params} after timeout of {timeout} seconds. Retrying...")
                continue
            else:
                if data.status_code != 200:
                    self.logger.warning(f"GET request failed for {url} with params {params} and status code {data.status_code}. Waiting for {timeout} seconds and retrying...")
                    time.sleep(timeout)
                else:   
                    #self.logger.debug(f"GET request successful for {url} with status code {data.status_code}. Answer took {data.elapsed.total_seconds()} seconds.")
                    return data
                
        raise Exception(f"Request failed {10} times for {url}.")
            
    def getCollection(self):
        self.logger.debug(f"Requesting available collections")
        url = self.base_url + "getCollectionValues"
        data = self.get_request(url=url, use_cache=False)
        collections = data.json() # list of dictionaries with {"Collection": collection_name}
        return collections
    
    def check_collection(self, collection_name):
        available_collections = self.getCollection()
        available_collections_list = [i["Collection"] for i in available_collections]
        if not collection_name in available_collections_list:
            available_collections_string = "\n".join(available_collections_list)
            self.logger.error(f"Collection \"{collection_name}\" not found. Available collections are: \n{available_collections_string}")
            raise Exception("Collection not found. Either the dataset does not exist or your need to provide credentials to access restricted data on TCIA")
        else:
            self.logger.info(f"Collection \"{collection_name}\" found.")
        
    def getSOPInstanceUIDs(self, SeriesInstanceUID):
        SOPInstanceURL = "getSOPInstanceUIDs"
        url = self.base_url + SOPInstanceURL
        params = {"SeriesInstanceUID": SeriesInstanceUID}
        data = self.get_request(url=url, params=params)
        SOPInstanceUID_list = data.json() # list of dictionaries with {"SOPInstanceUID": SOPInstanceUID}
        return SOPInstanceUID_list
    
    def query_md5(self, SOPInstanceUID):
        md5_url = "getM5HashForImage"
        url = self.base_url + md5_url
        params = {"SOPInstanceUid": SOPInstanceUID}
        data = self.get_request(url=url, params=params)
        md5 = data.text
        return md5
    
    def getDicomTags(self, SeriesUID):
        DicomtagsURL = "getDicomTags"
        url = self.advanced_url + DicomtagsURL
        params = {"SeriesUID": SeriesUID}
        data = self.get_request(url=url, params=params)
        tags = data.json()
        return tags
    
    @dict_to_dataframe
    def getDicomTagsDF(self, SeriesUID):
        return self.getDicomTags(SeriesUID=SeriesUID)
    
    
    def downloadSeriesInstance(self, SeriesInstanceUID, directory, md5=True):
        self.logger.debug(f"Downloading {SeriesInstanceUID} to {directory}")
        if md5:
            SeriesInstanceUIDURL = "getImageWithMD5Hash"
        else:
            SeriesInstanceUIDURL = "getImage"
        url = self.base_url + SeriesInstanceUIDURL
        params = {"SeriesInstanceUID": SeriesInstanceUID}
        data = self.get_request(url=url, params=params, use_cache=False)
        
        path = directory + "/" + SeriesInstanceUID
        with zipfile.ZipFile(io.BytesIO(data.content)) as zip_file:
            zip_file.extractall(path=path)
        return

    
    def downloadSeries(self, series, path):
        assert(isinstance(series, pd.DataFrame))
        self.logger.info(f"Downloading {len(series)} series to {path}")
        for i, row in series.iterrows():
            self.downloadSeriesInstance(row["SeriesInstanceUID"], path)
        return
    
    def getSeriesInstanceMetadata(self, SeriesInstanceUID):
        self.logger.debug(f"Requesting metadata for SeriesInstanceUID {SeriesInstanceUID}")
        SeriesMetaDataURL = "getSeriesMetaData"
        url = self.base_url + SeriesMetaDataURL
        params = {"SeriesInstanceUID": SeriesInstanceUID}
        data = self.get_request(url=url, params=params)
        metadata = data.json()
        return metadata
    
    def getSeriesMetadataDF(self, SeriesUID):
        self.logger.info("Downloading metadata")
        '''
        Returns more metadata than just "getSeries"
        '''
        assert(isinstance(SeriesUID, pd.DataFrame))
        meta_data_df = pd.DataFrame()
        
        for i, row in SeriesUID.iterrows():
            SeriesInstanceUID = row["SeriesInstanceUID"]
            SeriesInstanceMetadata = self.getSeriesInstanceMetadata(SeriesInstanceUID)
            meta_data_df = pd.concat([meta_data_df, pd.DataFrame(SeriesInstanceMetadata)], ignore_index=True)
        return meta_data_df
            
    
    def getSeries(self, collection_name):
        '''
        Returns less metadata than "getSeriesInstanceMetadata", but is more flexible with respect to the parameters
        '''
        SeriesURL = "getSeries"
        url = self.base_url + SeriesURL
        params = {"Collection": collection_name}
        data = self.get_request(url=url, params=params)
        series = data.json()
        return series
    
    @dict_to_dataframe
    def getSeriesDF(self, collection_name):
        return self.getSeries(collection_name=collection_name)
    

class TciaDownloader(Downloader):
    def __init__(self, user=None, password=None, temp_dir="", collection=None, logger=None, cache_dir=None) -> None:
        super(TciaDownloader, self).__init__(collection=collection, logger=logger, temp_dir=os.path.join(temp_dir, collection), cache_dir=cache_dir, user=user, password=password)
        self.user = user
        self.password = password
        self.tcia_api = TciaAPI(user=user, pw=password, logger=logger, cache_dir=cache_dir)
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
            
            
            try:
                SeriesDate = entry_df["SeriesDate"]
            except:
                date = "unkown_date"
            else:
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
        
        os.makedirs(self.temp_dir, exist_ok=True)

        # check if collection exists
        self.tcia_api.check_collection(self.collection)
        
        # Get series from tcia api as dataframe
        self.seriesDF = self.tcia_api.getSeriesDF(self.collection)
        
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
                
