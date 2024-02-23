import yaml
import shutil
import os
import pandas as pd

def keep_patients(self, data):
        self.logger.info(f"Removing unwanted Patients in {self.collection_dir}")
        patients = data
        for dir in os.listdir(self.collection_dir):
            folder = os.path.join(self.collection_dir, dir)
            if os.path.isdir(folder) and dir not in patients:
                self.logger.debug(f"Removing folder: {folder}")
                shutil.rmtree(os.path.join(self.collection_dir, dir))

def add_dseg_tsv(self, data):
    self.logger.info(f"Adding dseg.tsv file to dataset")
    
    mapping = {"mapping":[], "name":[]}
    for key, value in data.items():
        mapping["mapping"].append(key)
        mapping["name"].append(value)

    df = pd.DataFrame(mapping)
    file_path = os.path.join(self.collection_dir, "dseg.tsv")
    df.to_csv(file_path, sep="\t", index=False)
