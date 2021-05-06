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
import json
import sys
import shutil
import requests
from datetime import datetime, timedelta
from netCDF4 import Dataset, num2date
import numpy as np
from nco import Nco
from nco import custom as c
import urllib.request

def get_names_and_urls(name, opt):
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

def download(config):
    days_to_keep = config['days_to_keep']
    # Download new data
    if not os.path.exists(config['download_folder']):
        os.mkdir(config['download_folder'])
    nco = Nco(debug=True)
    for name, opt in config['sources'].items():
        if name[0] == '#':
            print('Skipping ' + name[1::])
            continue
        print('='*30)
        print(name)
        print('-'*30)
        folder = os.path.join(config['download_folder'], name)
        if not os.path.exists(folder):
            os.mkdir(folder)
        agg_file = os.path.join(folder, name + '_aggregate.nc')
        try:
            if config['testing'] is True:
                opt['opt'].append(opt['subset'])
            new_download = False
            print(opt['url'])
            if opt['url'] == datetime.now().strftime(opt['url']):
                ###########################
                # Download from aggregate
                ###########################
                if 'stride' in opt:
                    stride = opt['stride']
                else:
                    stride = 1
                d = Dataset(opt['url'])
                remote_tvar = d.variables['time']
                remote_time = num2date(remote_tvar[-2:], remote_tvar.units)
                remote_time_step = remote_time[1] - remote_time[0]
                local_time_step = remote_time_step*stride
                remote_end_time = remote_time[1]
                remote_num_times = len(remote_tvar)
                if os.path.exists(agg_file):
                    l = Dataset(agg_file)
                    local_tvar = l.variables['time']
                    local_time = num2date(local_tvar[:], local_tvar.units)
                    if remote_end_time <= local_time[-1] + local_time_step:
                        print('No new data for %s, last time: %s' % (name, local_time[-1]))
                        continue
                    download_from = remote_end_time - timedelta(hours=opt['forecast_hours'])
                    if download_from > local_time[-1]:
                        download_from = local_time[-1]
                    newfile = False
                else:
                    download_from = datetime.now() - timedelta(days=1)  # Only 1 day, otherwise too large file
                    newfile = True

                # Find temporal subset to download
                last_index = remote_num_times - stride + 1
                if stride == 1:
                    last_index = last_index - 1
                first_index = np.int32(last_index - stride*np.ceil((remote_end_time - download_from).total_seconds()/local_time_step.total_seconds()) - 1)
                new_times = num2date(remote_tvar[first_index:last_index+1], remote_tvar.units)
                if newfile is False:
                    print('%s ends %s -> downloading %s -> %s' % (name, local_time[-1], new_times[0], new_times[-1]))
                else:
                    print('Downloading new file for %s: %s -> %s' % (name, new_times[0], new_times[-1]))

                ts = "-d time,%i,%i" % (first_index, last_index)
                if stride > 1:
                    ts = ts + ',%i' % stride
                fname = new_times[0].strftime(name+'_%Y%m%d%H.nc')
                fullname = os.path.join(folder, fname)
                #if newfile:
                #    fullname = agg_file
                options = opt['opt']
                options.append(ts)
                options.append("-7")  # netCDF4 CLASSIC to avoid file size limitation
                options.append("--mk_rec_dmn time")  # Make time unlimited for aggregation
                nco.ncks(input=opt['url'], output=fullname, options=options)
                if os.path.exists(fullname):
                    new_download = True
                d.close()
 
            else:
                #################################
                # Downloading from single URLS
                #################################
                fnames, urls = get_names_and_urls(name, opt)
                for fname, url in zip(fnames, urls):
                    fullname = os.path.join(folder, fname)
                    if os.path.exists(fullname):
                        print('%s exists, skipping' % fullname)
                        continue
                    print('Checking: ' + url)
                    # Check if URL is available
                    # Using requests, since .netrc file is needed
                    resp = requests.get(url + '.das', timeout=3)
                    if resp.status_code >= 400:
                        print('Requests: error code %s' % resp.status_code)
                        continue
                    # Download from URL
                    print('Downloading %s from %s...' %
                            (fullname, url))
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
                        print('STOPPING')
                        #sys.exit('stop')

            ##################
            # Postprocessing
            ##################
            if new_download is False:
                print('No download, hence no postprocessing')
                continue
            else:
                print('Postprocessing downloaded data')
            # Remove overlapping times from downloaded files
            timestep = opt['timestep']
            folder = os.path.join(config['download_folder'], name)
            catfolder = os.path.join(folder, 'concatenate')
            if not os.path.exists(folder):
                os.mkdir(folder)
            if not os.path.exists(catfolder):
                os.mkdir(catfolder)
            print(folder, catfolder)
            files = sorted(glob.glob(
                os.path.join(folder, name + '_??????????.nc')))
            print(files)
            if len(files)==0:
                continue
            times = [datetime.strptime(f[-13:-3], '%Y%m%d%H') for f in files]
            print('Making aggregate from: ', name, files)
            for i in range(len(times)-1,-1,-1):
                print(i, times[i])
                filename = files[i]
                if times[i] < datetime.now() - timedelta(hours=24*(days_to_keep+1)):
                    print('Deleting old input file:' + filename)
                    os.remove(filename)
                    continue
                if i == len(times)-1:  # Last file in list
                    print('Using whole file')
                else:
                    print(times, 'times')
                    steps = (times[i+1]-times[i]).total_seconds()/(timestep*3600)
                    print(steps, 'steps')
                    catfile = os.path.join(catfolder, name +
                                times[i].strftime('_%Y%m%d%H') +
                                times[i+1].strftime('_%Y%m%d%H.nc'))
                    print(catfile, 'catfile')
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

            ########################
            print('Maintainance')
            ########################
            catfiles = sorted(glob.glob(os.path.join(catfolder, name + '*.nc')))
            print(catfiles, 'CATFILES')
            for i, f in enumerate(catfiles):
                starttime = datetime.strptime(f[len(os.path.join(catfolder+name))+2:-14],
                                              '%Y%m%d%H')
                endtime = datetime.strptime(f[-13:-3], '%Y%m%d%H')
                if endtime < datetime.now() - timedelta(hours=24*days_to_keep):
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
            print(files, 'FILES')
            infiles = sorted(glob.glob(os.path.join(
                catfolder, name + '*.nc'))) + [files[-1]]
            if len(infiles) > 1:
                print('Concatinating: ' + str(infiles))
                nco.ncra(output=os.path.join(folder, name + '_aggregate.nc'),
                         input=infiles,
                         options=['-Y ncrcat', '-O'])  # Since Windows lack link ncrcat -> ncra
                # https://sourceforge.net/p/nco/discussion/9830/thread/e8b45a9cdb/
            elif len(infiles) == 1:
                shutil.copyfile(infiles[0], agg_file)

        except Exception as e:
            print('Downloading failed:')
            print(e)
            import traceback
            print(traceback.format_exc())

    for name, opt in config['sources'].items():
        tmpfiles = sorted(glob.glob(os.path.join(config['download_folder'], name, '*.nc*tmp')))
        for tmpfile in tmpfiles:
            print('Deleting tmp-file: ' + tmpfile)
            os.remove(tmpfile)

    # Sum up the coverage of aggregates
    print()
    print('=========================================================')
    print('Aggregate files:')
    for name, opt in config['sources'].items():
        if name[0] != '#':
            print(os.path.join(config['download_folder'],
                  name, name + '_aggregate.nc'))
    print('=========================================================')
    print('Coverage of aggregate files:')
    notify = ''
    for name, opt in config['sources'].items():
        if name[0] == '#':
            continue 
        timestep = opt['timestep']
        folder = os.path.join(config['download_folder'], name)
        aggfile = os.path.join(folder, name + '_aggregate.nc')
        try:
            d = Dataset(aggfile)
        except:
            print('Missing: ' + aggfile)
            continue
        times = d.variables['time']
        d.close()
        times = num2date(times[:], times.units)
        minushours = np.round((times[0]-datetime.now()).total_seconds()/3600)
        plushours = np.round((times[-1]-datetime.now()).total_seconds()/3600)
        expected_steps = (plushours-minushours+1)/timestep 
        if expected_steps != len(times) and name != 'ecmwf' and False:  # NB: temporarily disabled for missing times
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
    if notify != '' and config['email_notification'] is not None:
        try:
            import smtplib
            FROM = 'ThreddsHarvest@met.no'
            TO = [config['email_notification']]
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


if __name__ == '__main__':

    # Import user specific settings
    config_file = sys.argv[1]
    with open(config_file) as f:
        config = json.load(f)

    download(config)
