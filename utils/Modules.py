import yaml
import shutil
import os

def keep_patients(self, data):
        self.logger.info(f"Removing unwanted Patients in {self.collection_dir}")
        patients = data
        for dir in os.listdir(self.collection_dir):
            folder = os.path.join(self.collection_dir, dir)
            if os.path.isdir(folder) and dir not in patients:
                self.logger.debug(f"Removing folder: {folder}")
                shutil.rmtree(os.path.join(self.collection_dir, dir))