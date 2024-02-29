import yaml
import shutil
import os
import pandas as pd

def add_dseg_tsv(self, data):
    self.logger.info(f"Adding dseg.tsv file to dataset")
    
    mapping = {"mapping":[], "name":[]}
    for key, value in data.items():
        mapping["mapping"].append(key)
        mapping["name"].append(value)

    df = pd.DataFrame(mapping)
    file_path = os.path.join(self.temp_collection_dir, "dseg.tsv")
    df.to_csv(file_path, sep="\t", index=False)
