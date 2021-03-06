import os
from resource_management.core.resources import Execute
from resource_management.libraries.functions.default import default

CONST_RANGER_VERSION = default("/configurations/ranger-env/plugin_version", '0.7.0')
CONST_DOWNLOAD_URL_BASE = default("/configurations/ranger-env/plugin_base_url", 'http://yum.example.com/hadoop/')
stack_root = '/opt'


def install_ranger_plugin(service_name):
    if not service_name:
        return ''
    filename = 'ranger-' + CONST_RANGER_VERSION + '-' + service_name + '-plugin.tar.gz'
    download_url = CONST_DOWNLOAD_URL_BASE + filename
    version_dir = stack_root + '/ranger-' + CONST_RANGER_VERSION + '-' + service_name + '-plugin'
    install_dir = stack_root + '/ranger-' + service_name + '-plugin'
    if not os.path.exists(version_dir):
        Execute('rm -rf %s' % install_dir)
        Execute('wget ' + download_url + ' -O /tmp/' + filename)
        Execute('tar -zxf /tmp/' + filename + ' -C /opt')
        Execute('ln -s ' + version_dir + ' ' + install_dir)
        Execute('/bin/rm -f /tmp/' + filename)
