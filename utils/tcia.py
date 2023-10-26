import os
import pandas as pd
import time
from datetime import datetime, timedelta
import requests
import sys
import requests_cache
import zipfile, io

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
            raise Exception("Collection not found.")
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