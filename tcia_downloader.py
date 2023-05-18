import argparse
from tcia_utils import nbia
from os import path
import subprocess, os

# parse arguments
parser = argparse.ArgumentParser(description='Download data from TCIA')
parser.add_argument('--collection', '-co', type=str, required=True, help='TCIA collection name')
parser.add_argument('--output', '-o', type=str, default='', required=False, help='Output directory')
parser.add_argument('--temp_dir', '-t', type=str, default='', required=False, help='Temporary directory for downloading')
parser.add_argument('--user', '-u', type=str, default=None, required=False, help='Username for TCIA')
parser.add_argument('--password', '-p', type=str, default=None, required=False, help='Password for TCIA')
parser.add_argument('--mode', '-m', type=str, default='nbia', required=False, help='Which downloader to use (nbia, aspera)')
args = parser.parse_args()

if args.mode != "nbia":
    raise AssertionError("Only nbia mode is supported at the moment. Future updates will include aspera as well.")

collection = args.collection 
output = args.output
output_file = path.join(output, f"{collection}.tar.xz")
temp_dir = path.join(args.temp_dir, collection)
user = args.user
password = args.password
api_url = "" if user==None else "restricted"

if not os.path.exists(output):
    os.makedirs(output)

if not os.path.exists(temp_dir):
    os.makedirs(temp_dir)

if not os.path.exists(output_file):
    if api_url == "restricted":
        nbia.getToken(user=user, password=password, api_url = api_url)

    data = nbia.getSeries(collection = collection, api_url = api_url)
    #if not path.exists(temp_dir):
    nbia.downloadSeries(data, path=temp_dir, format="csv", csv_filename=path.join(temp_dir, "metadata"), api_url = api_url)
    #else:
    #    print("Data already downloaded")

    subprocess.run(f'tar -I "xz -T0" -cf {output_file} -C {args.temp_dir} {collection} --remove-files', shell=True)
else:
    print("Output file already exists. Skipping download and compression.")