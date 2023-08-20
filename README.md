# tcia_downloader
Python script with matching slurm bash file for downloading datatasets from the TCIA (The Cancer Imaging Archive). The datasets are directly converted to a compressed archive (tar.xz). Currently suppports the nbia datasets (datasets with limited access not tested yet). Will support the aspera downloader in the future as well.

## The tcia_downloader.py file
The script takes up to 5 arguments as input:

--collection: 
the name of the collection which should be downloaded

--output:
the output directory for the archive

--temp_dir:
the directory where the data is stored temporarily, e.g. for downloading (before compression). Can be useful in the HPC use case (inode limit)

--user:
The username of a TCIA acount. Needed when restricted collections are accessed.


--password:
The password of a TCIA acount. Needed when restricted collections are accessed.

--mode:
The mode of the downloader. Can be either 'nbia' or 'aspera'. Default is 'nbia'. (not implemented yet)

## The tcia_downloader_hpc.sh file
This is just a template containing slurm directives. It can therefore be used locally as well as in an HPC environment. Adjust this file according to your application. It can be used as follows:

```
using slurm:
sbatch tcia_downloader_hpc.sh

using locally:
./tcia_downloader_hpc.sh
```


