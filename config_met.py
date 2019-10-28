################################################################
# Config section
################################################################

# Where to store downloaded files
download_folder = '/vol/vvfelles/opendrift/forcing_data/'

# If testing is True, only small spatial subsets are downloaded
# If testing is False, whole domain is downloaded
# Note: if changing to False, files in download folder
#       should be manually deleted
testing = False

# Files older than this number of days are automatically deleted
days_to_keep = 7

email_notification = 'knutfd@met.no'

# Add # to start of name to disable a data source
sources = {
    # NorKyst 800m ocean model
    'norkyst': {
        'opt': [#'-d depth,0,0',  # surface only
                '-d depth,0,1',
                '-v u,v,temperature,salinity,h,projection_stere'],
        'subset': '-d X,0,10 -d Y,0,10',
        'hours': [0],
        'timestep': 1,
        'url': 'https://thredds.met.no/thredds/dodsC/fou-hi/norkyst800m-1h/NorKyst-800m_ZDEPTHS_his.fc.%Y%m%d%H.nc',
            },
    # Nordic 4km ocean model
    'nordic': {
        'opt': ['-d depth,0,0',
                '-v u,v,temperature,polar_stereographic'],
        'subset': '-d X,0,10 -d Y,0,10',
        'hours': [0],
        'timestep': 1,
        'url': 'https://thredds.met.no/thredds/dodsC/fou-hi/nordic4km-zdepths1h/roms_nordic4_ZDEPTHS_hr.fc.%Y%m%d.nc'
            },
    # MyWaveWAM 4km wave model
    'mywavewam': {
        'opt': ['-v hs,tm2,projection_3'],
        'subset': '-d rlat,0,10 -d rlon,0,10',
        'hours': [6, 18],
        'timestep': 1,
        'url': 'https://thredds.met.no/thredds/dodsC/fou-hi/mywavewam4/mywavewam4.fc.%Y%m%d%H.nc',
            },
    # MEPS atmospheric model
    'meps': {
        'opt': ['-v x_wind_10m,y_wind_10m,projection_lambert'],
        'subset': '-d x,0,10 -d y,0,10',
        'hours': [0, 6, 12, 18],
        'timestep': 1,
        'url': 'https://thredds.met.no/thredds/dodsC/meps25files/meps_det_pp_2_5km_%Y%m%dT%HZ.nc',
            },
     # Arome Arctic atmospheric model
    'aromearctic': {
        'opt': ['-v x_wind_10m,y_wind_10m,projection_lambert'],
        'subset': '-d x,0,10 -d y,0,10',
        'hours': [0, 6, 12, 18],
        'timestep': 1,
        'url': 'https://thredds.met.no/thredds/dodsC/aromearcticlatest/arome_arctic_pp_2_5km_%Y%m%dT%HZ.nc',
            },
      # ECMWF wind
    'ecmwf': {
        'opt': ['-v x_wind_10m,y_wind_10m,projection_regular_ll'],
        'subset': '-d x,0,10 -d y,0,10',
        'hours': [0],
        'timestep': 3,
        'url': 'https://thredds.met.no/thredds/dodsC/ecmwf/atmo/ec_atmo_0_1deg_%Y%m%dT000000Z_3h.nc',
            }
        }
