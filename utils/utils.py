import subprocess
import logging
import hashlib
import os
from checksumdir import dirhash
import signal
import sys
from threading import Thread
import re
import yaml
import shutil

def strip_ansi_escape_codes(text):
    # Regular expression to remove ANSI escape codes
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

def log_subprocess_output(pipe, logger):
    for line in iter(pipe.readline, ''):
        line = line.strip()
        line = strip_ansi_escape_codes(line)
        logger(line)

def run_subprocess(command, logger):
    command_log = command.split(" ")
    for i, arg in enumerate(command_log):
        if "--password" in arg:
            command_log[i] = "--password=********"
        if "--user" in arg:
            command_log[i] = "--user=********"

    logger.debug(f"Running subprocess: {' '.join(command_log)}")

    process = subprocess.Popen(command, text=True, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, executable="/bin/bash")
    stdout_thread = Thread(target=log_subprocess_output, args=(process.stdout, logger.debug))
    stderr_thread = Thread(target=log_subprocess_output, args=(process.stderr, logger.debug))

    # Start the threads
    stdout_thread.start()
    stderr_thread.start()

    exitcode = process.wait() # 0 means success

    if exitcode != 0:
        raise Exception(f"Command '{command}' returned non-zero exit status {exitcode}")


class OutputLogger:
    def __init__(self, logger, level="DEBUG") -> None:
          self.logger = logger
          self.level = getattr(logging, level)
    
    def write(self, msg):
        if msg and not msg.isspace():
            self.logger.log(self.level, msg)
    
    def flush(self): pass

def md5(fname):
        hash_md5 = hashlib.md5()
        with open(fname, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

def compress(output_file, path, input_directory, logger, remove_files = True):
    if remove_files:
        command = f"tar -I pigz -cf {output_file} -C {path} {input_directory} --remove-files"
    else: 
         command = f"tar -I pigz -cf {output_file} -C {path} {input_directory}"
    run_subprocess(command, logger=logger)

def decompress(input_file, output_directory, logger):
    command = f"tar -I pigz -xf {input_file} -C {output_directory}"
    run_subprocess(command, logger=logger)

def compute_checksum(path):
    if os.path.isfile(path):
        computed_hash = md5(path)
    else:
        computed_hash = dirhash(path, "md5")
    return computed_hash


def exists_credentials_file(credentials_path):
    print(credentials_path)
    try:
        credentials_path.endswith(".yaml")
    except:
        try:
            credentials_path.endswith(".yml")
        except:
            raise Exception("Credentials file must be a .yml or .yaml file")
    return os.path.isfile(credentials_path)

def create_credentials_file(path):

    credentials = {
        "TCIA": {
            "user": "",
            "password": "",
        },
        "Synapse": {
            "token": "",
        }
    }

    # Create credentials file
    if not os.path.exists(os.path.dirname(path)):
        os.mkdir(os.path.dirname(path))

    with open(path, "w") as f:
        yaml.safe_dump(credentials, f)

def exists_command(command):
    return shutil.which(command) != None