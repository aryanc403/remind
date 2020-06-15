import os

DATA_DIR = 'data'
LOGS_DIR = 'logs'
CONTESTS_DB_FILE_PATH = os.path.join(DATA_DIR, 'contests.json')
LOG_FILE_PATH = os.path.join(LOGS_DIR, 'remind.log')
GUILD_SETTINGS_MAP_PATH = os.path.join(DATA_DIR, 'guild_settings_map')
ALL_DIRS = (attrib_value for attrib_name, attrib_value in list(
    globals().items()) if attrib_name.endswith('DIR'))
