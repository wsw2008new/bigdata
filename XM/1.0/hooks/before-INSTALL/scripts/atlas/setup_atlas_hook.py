#!/usr/bin/env python

__all__ = ["has_atlas_in_cluster", "setup_atlas_hook", "setup_atlas_jar_symlinks"]

# Python Imports
import os

# Local Imports
from resource_management.libraries.resources.properties_file import PropertiesFile
from resource_management.libraries.functions.format import format
from resource_management.libraries.functions.default import default
from resource_management.libraries.script import Script
from resource_management.core.resources.system import Link
from resource_management.core.logger import Logger
from ambari_commons.constants import SERVICE

'''
Only this subset of Atlas application.properties should be written out to each service that has an Atlas hook,
E.g., Hive, Storm, Sqoop, Falcon.
The reason for this is that we don't want configs to get out-of-sync between each of these services.
Assume Atlas application.properties contains props

private_prop_a
private_prop_b
private_prop_c
shared_atlas_hook_prop_d
shared_atlas_hook_prop_e

Then only shared_atlas_hook_prop_d and shared_atlas_hook_prop_e should be merged with the properties specific to
Hive, Storm, Sqoop, and Falcon.
E.g.,
Hive has,
specific_hive_atlas_hook_prop_f
specific_hive_atlas_hook_prop_g

So the atlas-application.properties.xml file that we write for Hive should contain,
shared_atlas_hook_prop_d
shared_atlas_hook_prop_e
specific_hive_atlas_hook_prop_f
specific_hive_atlas_hook_prop_g

Now, if the user wants to make a global change for Atlas hooks, they can change shared_atlas_hook_prop_d or shared_atlas_hook_prop_e
in a single place (under the Atlas Configs page).
If they want to overwrite shared_atlas_hook_prop_d just for Hive, they can add it to hive-atlas-application.properties
'''

SHARED_ATLAS_HOOK_CONFIGS = set(
    [
        "atlas.kafka.zookeeper.connect",
        "atlas.kafka.bootstrap.servers",
        "atlas.kafka.zookeeper.session.timeout.ms",
        "atlas.kafka.zookeeper.connection.timeout.ms",
        "atlas.kafka.zookeeper.sync.time.ms",
        "atlas.kafka.hook.group.id",
        "atlas.notification.create.topics",
        "atlas.notification.replicas",
        "atlas.notification.topics",
        "atlas.notification.kafka.service.principal",
        "atlas.notification.kafka.keytab.location",
        "atlas.cluster.name",
        "atlas.rest.address",

        # Security properties
        "atlas.jaas.KafkaClient.option.serviceName",
        "atlas.authentication.method.kerberos",
        "atlas.kafka.sasl.kerberos.service.name",
        "atlas.kafka.security.protocol",
        "atlas.jaas.KafkaClient.loginModuleName",
        "atlas.jaas.KafkaClient.loginModuleControlFlag"
    ]
)

SHARED_ATLAS_HOOK_SECURITY_CONFIGS_FOR_NON_CLIENT_SERVICE = set(
    [
        "atlas.jaas.KafkaClient.option.useKeyTab",
        "atlas.jaas.KafkaClient.option.storeKey"
    ]
)

NON_CLIENT_SERVICES = [SERVICE.HIVE, SERVICE.STORM, SERVICE.FALCON]


def has_atlas_in_cluster():
    """
    Determine if Atlas is installed on the cluster.
    :return: True if Atlas is installed, otherwise false.
    """
    atlas_hosts = default('/clusterHostInfo/atlas_server_hosts', [])
    return len(atlas_hosts) > 0


def setup_atlas_hook(service_name, service_props, atlas_hook_filepath, owner, group):
    """
    Generate the atlas-application.properties.xml file by merging the service_props with the Atlas application-properties.
    :param service_name: Service Name to identify if it is a client-only service, which will generate slightly different configs.
    :param service_props: Atlas configs specific to this service that must be merged.
    :param atlas_hook_filepath: Config file to write, e.g., /etc/falcon/conf/atlas-application.properties.xml
    :param owner: File owner
    :param group: File group
    """
    import params
    atlas_props = default('/configurations/application-properties', {})
    merged_props = {}
    merged_props.update(service_props)

    if has_atlas_in_cluster():
        # Take the subset
        merged_props = {}
        shared_props = SHARED_ATLAS_HOOK_CONFIGS.copy()
        if service_name in NON_CLIENT_SERVICES:
            shared_props = shared_props.union(SHARED_ATLAS_HOOK_SECURITY_CONFIGS_FOR_NON_CLIENT_SERVICE)

        for prop in shared_props:
            if prop in atlas_props:
                merged_props[prop] = atlas_props[prop]

        merged_props.update(service_props)

    Logger.info(format("Generating Atlas Hook config file {atlas_hook_filepath}"))
    PropertiesFile(atlas_hook_filepath,
                   properties=merged_props,
                   owner=owner,
                   group=group,
                   mode=0644)


from resource_management.core.resources import Execute

CONST_ATLAS_VERSION = default("/configurations/atlas-env/plugin_version", '0.8')
CONST_DOWNLOAD_URL_BASE = default("/configurations/atlas-env/plugin_base_url", 'http://yum.example.com/hadoop/') \


def install_atlas_hook(hook_name):
    if not hook_name:
        return ''
    stack_root = '/opt'
    filename = 'atlas-' + CONST_ATLAS_VERSION + '-' + hook_name + '-plugin.tar.gz'
    download_url = CONST_DOWNLOAD_URL_BASE + filename
    version_dir = stack_root + '/atlas-' + CONST_ATLAS_VERSION + '-' + hook_name + '-plugin'
    install_dir = stack_root + '/atlas-' + hook_name + '-plugin'
    if not os.path.exists(version_dir):
        Execute('rm -rf %s' % install_dir)
        Execute('wget ' + download_url + ' -O /tmp/' + filename)
        Execute('tar -zxf /tmp/' + filename + ' -C /opt')
        Execute('ln -s ' + version_dir + ' ' + install_dir)
        Execute('/bin/rm -f /tmp/' + filename)


def setup_atlas_jar_symlinks(hook_name, jar_source_dir):
    """

    @param hook_name: one of sqoop, storm, hive
    @param jar_source_dir: directory of where the symlinks need to be created from.
    """
    install_atlas_hook(hook_name)

    stack_root = '/opt'
    atlas_hook_dir = stack_root + '/atlas-' + hook_name + '-plugin'

    if os.path.exists(atlas_hook_dir):
        Logger.info("Atlas Server is present on this host, will symlink jars inside of %s to %s if not already done." %
                    (jar_source_dir, atlas_hook_dir))

        src_files = os.listdir(atlas_hook_dir)
        for file_name in src_files:
            atlas_hook_file_name = os.path.join(atlas_hook_dir, file_name)
            source_lib_file_name = os.path.join(jar_source_dir, file_name)
            if os.path.isfile(atlas_hook_file_name):
                Link(source_lib_file_name, to=atlas_hook_file_name)
    else:
        Logger.info("Atlas hook directory path {0} doesn't exist".format(atlas_hook_dir))
