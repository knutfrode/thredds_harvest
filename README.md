# Thredds harvest

Downloads data from thredds-servers based on user-specific configuration files.
Downloaded files/subsets are merged into aggregates with static file names.

A conda environment with necessary requirements can be installed with the command:
```conda env create -f environment.yml ```

If an email address is specified in config file, a mail server must be installed to be able to receive email notfication (```smtplib```) in case of missing data.

Usage:

```$ harvest_from_thredds.py <config_file.json>```
