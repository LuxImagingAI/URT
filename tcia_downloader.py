import argparse
from tcia_utils import nbia
from os import path
import subprocess, os
import pandas as pd
import time
import warnings


def rename_patients(folder, series):
    print("Renaming folders to patient id")
    meta_data_df = pd.DataFrame.from_dict(series)
    
    for root, dirs, files in os.walk(folder):
        for dir in dirs:
            entry_df = meta_data_df[meta_data_df["SeriesInstanceUID"] == dir]
            
            # if the directory is a SeriesInstanceUID: move it to the patient folder
            if not entry_df.empty:
                patient_id = entry_df["PatientID"].values[0]
                old_path = os.path.join(root, dir)
                new_path = os.path.join(root, patient_id, dir)
                
                # to avoid recreation of the folder due to multiple runs
                if not patient_id in old_path:
                    os.makedirs(os.path.join(root, patient_id), exist_ok=True)
                    os.rename(old_path, new_path)
                

def check_collection(series, collection_name, api_url):
    if series==None:
        available_collections = nbia.getCollections(api_url = api_url)
        print(f"Collection \"{collection_name}\" not found. Available collections are:")
        for i in available_collections:
            print(i)
        raise AssertionError("Collection not found.")

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
            print(f"Skipping instance {pruned_entry}: already downloaded")
                
    return meta_data_df_pruned.to_dict(orient='records')

def download_series(series, temp_dir, collection_name, api_url):
    # check if collection exists
    check_collection(series, collection_name, api_url)
    series_to_download = series
    
    # Remove already downloaded instances
    for i in range(1,6):
        series_to_download = remove_downloaded_instances(series_to_download, temp_dir)
        
        if len(series_to_download) == 0:
            # rename folders to patient id if all dowloads were successful
            rename_patients(temp_dir, series)
            return
        else:
            if i>1:
                message = f"Retrying download of instances that failed previously (attempt no. {i})"
                warnings.warn(message)
                time.sleep(5)
            nbia.downloadSeries(series_to_download, path=temp_dir, format="csv", csv_filename=path.join(temp_dir, "metadata"), api_url = api_url)
    raise Exception("Download failed. Please check your internet connection and try again.")
    

def main():
    # parse arguments
    parser = argparse.ArgumentParser(description='Download data from TCIA')
    parser.add_argument('--collection', '-co', type=str, required=True, help='TCIA collection name')
    parser.add_argument('--output', '-o', type=str, default='', required=False, help='Output directory')
    parser.add_argument('--temp_dir', '-t', type=str, default='', required=False, help='Temporary directory for downloading')
    parser.add_argument('--user', '-u', type=str, default=None, required=False, help='Username for TCIA')
    parser.add_argument('--password', '-p', type=str, default=None, required=False, help='Password for TCIA')
    parser.add_argument('--mode', '-m', type=str, default='nbia', required=False, help='Which downloader to use (nbia, aspera)')
    parser.add_argument('--compress', '-c', type=str, default=True, required=False, help='Choose whether to compress the downloaded data. If False, the data will be downloaded only to the temporary directory')
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
        if api_url == "restricted":
            nbia.getToken(user=user, pw=password)


        series = nbia.getSeries(collection = collection_name, api_url = api_url)
        
        # download
        download_series(series, temp_dir, collection_name, api_url)
            
        
        # compress
        if compress:
            try:
                print("Compressing data")
                command = ["tar", "-I", "pigz",  "-cf", output_file, "-C", args.temp_dir, collection_name, "--remove-files"]
                subprocess.run(command)
                #subprocess.run(f'tar -I pigz -cf {output_file} -C {args.temp_dir} {collection_name} --remove-files', shell=True)
            except Exception as e:
                print(f"An error occurred during compression: {e}")

main()