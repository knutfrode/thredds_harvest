#!/usr/bin/env python

# This script performs the following actions:
# - subsets of Thredds datasets (see config) are downloaded to local file
# - accumulated precipitation is converted to hourly precipitation
# - downloaded files are finally merged into aggregates:
#       <model>_aggrecate.nc
# This script should be run routinely e.g. every 1 hour
# In case of delay/problems, it might help to delete 
# everything in download folder
#
# Knut-Frode Dagestad
# MET Norway, Dec 2018

import os
import glob
import sys
from datetime import datetime, timedelta
from nco import Nco
from nco import custom as c
if sys.version_info>= (3,0):
    pv=3  # Python3
    import urllib.request
else:
    pv=2  # Python2
    import urllib2

# User specific settings are stored in this config file
config_file = 'config_met'

config = __import__(config_file)


def get_names_and_urls(name, url):
    fnames = []
    urls = []
    for days in [-1, 0]:  # yesterday and today
        for hour in opt['hours']:
            time = (datetime.now()+timedelta(days=days))
            time = time.replace(hour=hour, minute=0,
                                second=0, microsecond=0)
            if time > datetime.now():
                continue
            if name == 'norkyst':
                # For NorKyst, URLs do not mach beginning of data
                time = time + timedelta(hours=24)
            fnames.append(time.strftime(name+'_%Y%m%d%H.nc'))
            urls.append(time.strftime(opt['url']))
    # Remove duplicates
    fnames_unique = []
    urls_unique = []
    for i in range(len(urls)):
        if urls[i] not in urls_unique:
            urls_unique.append(urls[i])
            fnames_unique.append(fnames[i])
    return fnames_unique, urls_unique


# Download new data
if not os.path.exists(config.download_folder):
    os.mkdir(config.download_folder)
nco = Nco(debug=True)
for name, opt in config.sources.items():
    if config.testing is True:
        opt['opt'].append(opt['subset'])
    new_download = False
    if name[0] == '#':
        print('Skipping ' + name[1::])
        continue
    fnames, urls = get_names_and_urls(name, opt['url'])
    print(fnames, urls)
    for fname, url in zip(fnames, urls):
        print('Checking:' + fname)
        folder = config.download_folder + '/' + name + '/'
        fullname = folder + fname
        if os.path.exists(fullname):
            print('%s exists, skipping' % fullname)
            continue
        # Check if URL is available
        try:
            timeout = 3  # Timeout in seconds
            try:
                print('Trying with requests library')
                import requests
                resp = requests.get(url + '.das', timeout=timeout)
                if resp.status_code >= 400:
                    raise Exception('Open error - requests')
            except Exception as e:
                print('Requests did not work, trying with urlopen')
                if pv == 2:  # Python2
                    ret = urllib2.urlopen(url + '.das',
                                          timeout=timeout)
                elif pv == 3:
                    ret = urllib.request.urlopen(url + '.das',
                                                 timeout=timeout)
                if ret.code != 200:
                    raise Exception('Open error - urllib')
        except Exception as e:
            print('Not available: ' + url)
            continue
        print(url)
        # Download from URL
        print('Downloading %s from %s...' %
                (fullname, url))
        if not os.path.exists(folder):
            os.mkdir(folder)
        try:
            nco.ncks(input=url, output=fullname,
                     options=opt['opt'])
            if os.path.exists(fullname):
                new_download = True
                if name in ['meps', 'aromearctic'] and 'acc' in opt['opt']:
                    print('Converting accumulated precipitation to hourly')
                    nco.ncap2(input=fullname, output=fullname,
                              options=['-O'],
                              spt='\'precipitation_amount=precipitation_amount_acc(1:$time.size-1,0,:,:)-precipitation_amount_acc(0:$time.size-2,0,:,:)\'')
        except Exception as e:
            print('DOWNLOAD NOT SUCCESSFUL!')
            print(e)
            sys.exit('stop')

    if new_download is False:
        continue
    # Remove overlapping times from downloaded files
    timestep = opt['timestep']
    folder = config.download_folder + '/' + name + '/'
    catfolder = folder + 'concatenate/'
    if not os.path.exists(folder):
        os.mkdir(folder)
    if not os.path.exists(catfolder):
        os.mkdir(catfolder)
    files = sorted(glob.glob(folder + name + '_??????????.nc'))
    if len(files)==0:
        continue
    times = [datetime.strptime(f[-13:-3], '%Y%m%d%H') for f in files]
    print('Making aggregate from: ', name, files)
    for i in range(len(times)-1,-1,-1):
        print(i, times[i])
        filename = files[i]
        if times[i] < datetime.now() - timedelta(hours=24*config.days_to_keep):
            print('Deleting old input file:' + f)
            os.remove(filename)
            continue
        if i == len(times)-1:
            print('Using whole file')
        else:
            steps = (times[i+1]-times[i]).total_seconds()/(timestep*3600)
            catfile = catfolder + name + \
                        times[i].strftime('_%Y%m%d%H') + \
                        times[i+1].strftime('_%Y%m%d%H.nc')
            if not os.path.exists(catfile):
                print('Cutting...')
                try:
                    # Cut part of file for later concatenation
                    nco.ncks(input=filename, output=catfile,
                             options=['-d time,0,%i' % (steps-1)])
                    # Delete the contents of original file to save space
                    os.remove(filename)
                    # Create empty file, to prevent new download
                    open(filename, 'a').close()
                except:
                    print('Cutting failed, hence removing input file: ' + filename)
                    os.remove(filename)
                    try:
                        os.remove(catfile)
                    except:
                        pass

    print('Maintainance')
    catfiles = sorted(glob.glob(catfolder + name + '*.nc'))
    for i, f in enumerate(catfiles):
        starttime = datetime.strptime(f[len(catfolder+name)+1:-14],
                                      '%Y%m%d%H')
        endtime = datetime.strptime(f[-13:-3], '%Y%m%d%H')
        if endtime < datetime.now() - timedelta(hours=24*config.days_to_keep):
            print('Deleting old catfile:' + f)
            os.remove(f)
            previous_endtime = endtime
            previous_starttime = starttime
            continue
        if i>0 and starttime < previous_endtime:
            print('Overlapping catfiles, cutting the first: (%s, %s)' %
                  (catfiles[i-1], catfiles[i]))
            steps = (previous_endtime-starttime).total_seconds()/(timestep*3600)
            totalsteps = (previous_endtime-previous_starttime).total_seconds()/(timestep*3600)
            stepstocut = totalsteps - steps
            newname = catfiles[i-1][0:-14] + starttime.strftime('_%Y%m%d%H.nc')
            nco.ncks(input=catfiles[i-1], output=newname,
                     options=['-d time,0,%i' % (stepstocut-1)])
            os.remove(catfiles[i-1])
        previous_endtime = endtime
        previous_starttime = starttime

    # Finally, concatenate all files in catfolder + latest-file
    infiles = sorted(glob.glob(catfolder + name + '*.nc')) + [files[-1]]
    print(infiles)
    nco.ncrcat(output=folder + name + '_aggregate.nc',
               input=infiles)

# Sum up the coverage of aggregates
print('=========================================================')
print('Aggregate files:')
for name, opt in config.sources.items():
    if name[0] != '#':
        print(config.download_folder + name + '/'
              + name + '_aggregate.nc')
print('=========================================================')
print('Coverage of aggregate files:')
try:
    notify = ''
    from netCDF4 import Dataset, num2date
    import numpy as np
    for name, opt in config.sources.items():
        if name[0] == '#':
            continue 
        timestep = opt['timestep']
        folder = config.download_folder + '/' + name + '/'
        aggfile = folder + name + '_aggregate.nc'
        try:
            d = Dataset(aggfile)
        except:
            print('Missing: ' + aggfile)
            continue
        times = d.variables['time']
        times = num2date(times[:], times.units)
        minushours = np.round((times[0]-datetime.now()).total_seconds()/3600)
        plushours = np.round((times[-1]-datetime.now()).total_seconds()/3600)
        expected_steps = (plushours-minushours+1)/timestep 
        if expected_steps != len(times) and name != 'ecmwf':
            warn = 'Expected %d steps, files has %d steps' % (
                        expected_steps, len(times))
        else:
            warn = ''
        if plushours < 24:
            warn += ', short forecast'
        else:
            warn += ''
        if minushours > -24:
            warn += ', short history'
        else:
            warn += ''
        summary = ('%12s%11sUTC - %9sUTC  (%+d, %+d) %s' %
            (name, times[0].strftime('%d %b %H'),
             times[-1].strftime('%d %b %H'),
             minushours, plushours, warn))
        print(summary)
        if warn != '':
            notify = notify + '\n' + summary
    print('=========================================================')
    if notify != '' and config.email_notification is not None:
        try:
            import smtplib
            FROM = 'ThreddsHarvest@met.no'
            TO = [config.email_notification]
            message = """From: %s\nTo: %s\nSubject: %s\n\n%s""" % (
                FROM, ', '.join(TO),
                'Thredds Harvest - short timeseries', notify)
            server = smtplib.SMTP('localhost')
            server.sendmail(FROM, TO, message)
            server.quit()
            print('Email sent to ' + TO[0])
            print(message)
        except Exception as ex:
            print('Could not send mail report on missing data')
            print(ex)
except Exception as e:
    print(e)
    print('Install netCDF4 to report summary of downloaded data')
