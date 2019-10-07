# Thredds harvest

Downloads data from thredds-servers based on user-specific configuration files.
Downloaded files/subsets are merged into aggregates with static file names.

Requirement is Nco, which can be installed with conda:
```conda install -c conda-forge nco ```

If an email address is specified in config file, a mail server must be installed to be able to receive email notfication (```smtplib```) in case of missing data.
