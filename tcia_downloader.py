import argparse
from tcia_utils import nbia
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

def get_token(user, pw):
    token_url = "https://keycloak.dbmi.cloud/auth/realms/TCIA/protocol/openid-connect/token"
    params = {'client_id': 'nbia',
                    'scope': 'openid',
                    'grant_type': 'password',
                    'username': user,
                    'password': pw
                    }
    
    data = requests.post(token_url, data=params)  
    data.raise_for_status()
    access_token = data.json()["access_token"]
    expires_in = data.json()["expires_in"]
    id_token = data.json()["id_token"]
    
    return access_token

    
def rename_patients(folder, series):
    print("Renaming folders to patient id")
    meta_data_df = pd.DataFrame.from_dict(series)
    
    for root, dirs, files in os.walk(folder):
        for dir in dirs:
            entry_df = meta_data_df[meta_data_df["SeriesInstanceUID"] == dir]
            
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
                
                dicom_tag = nbia.getDicomTags(seriesUid=dir, format="df")
                study_desription = dicom_tag[dicom_tag["name"]=="Study Description"]["data"].values[0]

                old_path = os.path.join(root, dir)
                new_path = os.path.join(root, patient_id, f"{date}-{study_desription}-{StudyInstanceUID}", f"{SeriesNumber}-{SeriesDescription}-{SeriesInstanceUID}")
                
                # to avoid recreation of the folder due to multiple runs
                if not patient_id in old_path:
                    os.makedirs(new_path, exist_ok=True)
                    os.rename(old_path, new_path)
                

def check_collection(series, collection_name, api_url):
    if series==None:
        available_collections = nbia.getCollections(api_url = api_url)
        print(f"Collection \"{collection_name}\" not found. Available collections are:")
        for i in available_collections:
            print(i)
        raise AssertionError("Collection not found.")

def getSOPInstanceUIDs(SeriesInstanceUID, token, session):

    if token == None:
        sop_url = "https://services.cancerimagingarchive.net/nbia-api/services/v1/getSOPInstanceUIDs?SeriesInstanceUID="
        sop_url = sop_url + SeriesInstanceUID
        data = session.get(url = sop_url, timeout=10)
    else:
        sop_url = "https://services.cancerimagingarchive.net/nbia-api/services/v2/getSOPInstanceUIDs?SeriesInstanceUID="
        sop_url = sop_url + SeriesInstanceUID
        api_call_headers = {'Authorization': 'Bearer ' + token}
        data = session.get(url = sop_url, headers=api_call_headers, timeout=10)
    SOPInstanceUID_list = data.json() # list of dictionaries with {"SOPInstanceUID": SOPInstanceUID}
    return SOPInstanceUID_list

def query_md5(SOPInstanceUID, token, session):
    
    if token==None:
        base_url = "https://services.cancerimagingarchive.net/nbia-api/services/v1/getM5HashForImage?SOPInstanceUid="
        url = base_url + SOPInstanceUID
        data = session.get(url = url, timeout=10)
    else:
        base_url = "https://services.cancerimagingarchive.net/nbia-api/services/v2/getM5HashForImage?SOPInstanceUid="
        url = base_url + SOPInstanceUID
        api_call_headers = {'Authorization': 'Bearer ' + token}
        data = session.get(url = url, headers = api_call_headers, timeout=10)
        
    return data.text

def md5(fname):
    hash_md5 = hashlib.md5()
    with open(fname, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def query_md5_series(series_df, token, session):
    SeriesInstanceUID = series_df["SeriesInstanceUID"].values
    assert(len(SeriesInstanceUID) == 1)
    SeriesInstanceUID = SeriesInstanceUID[0]
    
    SOPInstanceUIDS = getSOPInstanceUIDs(SeriesInstanceUID, token, session)
    
    md5_list = []
    for SOPInstanceUID in SOPInstanceUIDS:
        md5 = query_md5(SOPInstanceUID["SOPInstanceUID"], token, session)
        md5_list.append(md5)
    
    return md5_list
    
def compute_md5_folder(folder):
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
                hash_dict[SeriesInstanceUID]["md5"].append(md5(file_path))
                
    return hash_dict

def remove_corrupted_series(root_dir, series, token, session):
    print("Checking for corrupted files")
    
    series = pd.DataFrame.from_dict(series)
    hash_dict = compute_md5_folder(root_dir)
    counter = 0
    
    for key, value in hash_dict.items():
        md5_list = query_md5_series(series[series["SeriesInstanceUID"]==key], token, session)
        if not set(md5_list) == set(value["md5"]):
            print(f"Corrupted files found in series {key}. Removing...")
            shutil.rmtree(value["path"])
            counter += 1
    
    print(f"Removed {counter} corrupted series.")
    return


def remove_downloaded_instances(series, temp_dir):
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
            #print(f"Skipping instance {pruned_entry}: already downloaded")
                
    return meta_data_df_pruned.to_dict(orient='records')


def download_series(series, temp_dir, collection_name, api_url, token, exceptions, counter):
    try:
        series_to_download = series
        session = requests_cache.CachedSession()
        
        # Remove already downloaded instances
        for i in range(counter.value, 10):
            # counter ensures that the number of attempts is limited, otherwise killing the process would reset the counter
            counter.value = i
            
            remove_corrupted_series(temp_dir, series, token, session)
            series_to_download = remove_downloaded_instances(series_to_download, temp_dir)
            
            if len(series_to_download) == 0:
                # rename folders to patient id if all dowloads were successful
                rename_patients(temp_dir, series)
                return
            else:
                if i>1:
                    message = f"Retrying download of instances that failed previously (attempt no. {i})"
                    warnings.warn(message)
                    time.sleep(60)
                nbia.downloadSeries(series_to_download, path=temp_dir, format="csv", csv_filename=path.join(temp_dir, "metadata"), api_url = api_url)
            
        raise Exception("Download failed. Please check your internet connection and try again.")
    
    except Exception as e:
        exceptions.put(str(e))
    
def create_signal_handler(processes):
    def signal_handler(signal_number, frame):
        print("Stopping subprocesses...")
        for process in processes:
            process.terminate()
        sys.exit(0)
    return signal_handler
    
def generate_tokens(api_url, user, password):
    if api_url == "restricted":
        nbia.getToken(user=user, pw=password)
        token = get_token(user, password)
        token_expires = datetime.now() + timedelta(hours=1, minutes=50)
    else:
        token = None
        token_expires = datetime.now() + timedelta(weeks=100)
    return token, token_expires

def main():
    # parse arguments
    parser = argparse.ArgumentParser(description='Download data from TCIA')
    parser.add_argument('--collection', '-co', type=str, required=True, help='TCIA collection name')
    parser.add_argument('--output', '-o', type=str, default='', required=False, help='Output directory')
    parser.add_argument('--temp_dir', '-t', type=str, default='', required=False, help='Temporary directory for downloading')
    parser.add_argument('--user', '-u', type=str, default=None, required=False, help='Username for TCIA')
    parser.add_argument('--password', '-p', type=str, default=None, required=False, help='Password for TCIA')
    parser.add_argument('--mode', '-m', type=str, default='nbia', required=False, help='Which downloader to use (nbia, aspera)')
    parser.add_argument('--compress', '-c', type=bool, default=True, required=False, help='Choose whether to compress the downloaded data. If False, the data will be downloaded only to the temporary directory')
    parser.add_argument('--bids_format', '-b', type=bool, default=False, required=False, help='Choose whether to convert the downloaded data to BIDS format. If False, the data will be downloaded only to the temporary directory')
    args = parser.parse_args()

    if args.mode != "nbia":
        raise AssertionError("Only nbia mode is supported at the moment. Future updates will include aspera as well.")

    if args.user == None or args.password == None:
        print("Warning: No username or password provided. Downloading public data only.")
        
    collection_name = args.collection
    output = args.output
    output_file = path.join(output, f"{collection_name}.tar.gz")
    temp_dir = path.join(args.temp_dir, collection_name)
    user = args.user
    password = args.password
    api_url = "" if user==None else "restricted"
    compress = args.compress

    if not os.path.exists(output):
        os.makedirs(output)

    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)

    if os.path.exists(output_file):
        print("Output file already exists. Skipping download and compression.")

    else:    
        token, token_expires = generate_tokens(api_url, user, password)

        series = nbia.getSeries(collection = collection_name, api_url = api_url)
        # check if collection exists
        check_collection(series, collection_name, api_url)
        
        # Queues for multiprocessing
        exceptions = mp.Queue()
        counter = mp.Value("i", 1)
        
        # download series
        finished = False
        while True:
            
            try:
                download_process.terminate()
                download_process.wait()
            except:
                pass
            
            
            download_process = mp.Process(target=download_series, args=(series, temp_dir, collection_name, api_url, token, exceptions, counter))
            signal.signal(signal.SIGINT, create_signal_handler([download_process]))
            download_process.start()
            
            while datetime.now() < token_expires:
                if not exceptions.empty():
                    raise Exception("Exception from subprocess: ", exceptions.get()) # TODO: print exception
                elif not download_process.is_alive():
                    finished = True
                    break
                time.sleep(10)
                
            if finished:
                break
            
            print("Token expired. Refreshing token...")
            token, token_expires = generate_tokens(api_url, user, password)
            
            
        # compress
        if compress:
            try:
                print("Compressing data")
                command = ["tar", "-I", "pigz",  "-cf", output_file, "-C", args.temp_dir, collection_name, "--remove-files"]
                subprocess.run(command)
            except Exception as e:
                print(f"An error occurred during compression: {e}")

main()