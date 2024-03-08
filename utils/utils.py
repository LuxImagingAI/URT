import subprocess
import logging
import hashlib
import os
from checksumdir import dirhash

def run_subprocess(command, logger):

        with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as proc:
            stdout, stderr = proc.communicate()
            returncode = proc.wait()

        for line in stdout.splitlines():
                logger.debug(line.strip())

        if stderr:
            for line in stderr.splitlines():
                logger.debug(line.strip())
            
        if returncode != 0:
            raise Exception(f"Command '{' '.join(command)}' returned non-zero exit status {returncode}")
        return

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
        command = ["tar", "-I", "pigz",  "-cf", output_file, "-C", path, input_directory, "--remove-files"]
    else: 
         command = ["tar", "-I", "pigz",  "-cf", output_file, "-C", path, input_directory]
    run_subprocess(command, logger=logger)

def decompress(input_file, output_directory, logger):
    command = ["tar", "-I", "pigz",  "-xf", input_file, "-C", output_directory]
    run_subprocess(command, logger=logger)

def compute_checksum(path):
    if os.path.isfile(path):
        computed_hash = md5(path)
    else:
        computed_hash = dirhash(path, "md5")
    return computed_hash
