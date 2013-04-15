from __future__ import unicode_literals

import logging
import pkg_resources

from mopidy import exceptions
from mopidy import config as config_lib


logger = logging.getLogger('mopidy.ext')


class Extension(object):
    """Base class for Mopidy extensions"""

    dist_name = None
    """The extension's distribution name, as registered on PyPI

    Example: ``Mopidy-Soundspot``
    """

    ext_name = None
    """The extension's short name, as used in setup.py and as config section
    name

    Example: ``soundspot``
    """

    version = None
    """The extension's version

    Should match the :attr:`__version__` attribute on the extension's main
    Python module and the version registered on PyPI.
    """

    def get_default_config(self):
        """The extension's default config as a bytestring

        :returns: bytes
        """
        raise NotImplementedError(
            'Add at least a config section with "enabled = true"')

    def get_config_schema(self):
        """The extension's config validation schema

        :returns: :class:`~mopidy.config.schema.ExtensionConfigSchema`
        """
        return config_lib.ExtensionConfigSchema(self.ext_name)

    def validate_environment(self):
        """Checks if the extension can run in the current environment

        For example, this method can be used to check if all dependencies that
        are needed are installed.

        :raises: :class:`~mopidy.exceptions.ExtensionError`
        :returns: :class:`None`
        """
        pass

    def get_frontend_classes(self):
        """List of frontend actor classes to start

        :returns: list of :class:`pykka.Actor` subclasses
        """
        return []

    def get_backend_classes(self):
        """List of backend actor classes to start

        :returns: list of :class:`~mopidy.backends.base.Backend` subclasses
        """
        return []

    def register_gstreamer_elements(self):
        """Hook for registering custom GStreamer elements

        Register custom GStreamer elements by implementing this method.
        Example::

            def register_gstreamer_elements(self):
                from .mixer import SoundspotMixer
                gobject.type_register(SoundspotMixer)
                gst.element_register(
                    SoundspotMixer, 'soundspotmixer', gst.RANK_MARGINAL)

        :returns: :class:`None`
        """
        pass


def load_extensions():
    """Find all installed extensions.

    :returns: list of installed extensions
    """

    installed_extensions = []

    for entry_point in pkg_resources.iter_entry_points('mopidy.ext'):
        logger.debug('Loading entry point: %s', entry_point)
        extension_class = entry_point.load(require=False)
        extension = extension_class()
        extension.entry_point = entry_point
        installed_extensions.append(extension)
        logger.debug(
            'Loaded extension: %s %s', extension.dist_name, extension.version)

    names = (e.ext_name for e in installed_extensions)
    logging.debug('Discovered extensions: %s', ', '.join(names))
    return installed_extensions


def validate_extensions(installed_extensions):
    """Verify extension's dependencies and environment.

    :param installed_extensions: list of installed extensions
    :returns: list of valid extensions
    """

    valid_extensions = []

    for extension in installed_extensions:
        logger.debug('Validating extension: %s', extension.ext_name)

        if extension.ext_name != extension.entry_point.name:
            logger.warning(
                'Disabled extension %(ep)s: entry point name (%(ep)s) '
                'does not match extension name (%(ext)s)',
                {'ep': extension.entry_point.name, 'ext': extension.ext_name})
            continue

        try:
            extension.entry_point.require()
        except pkg_resources.DistributionNotFound as ex:
            logger.info(
                'Disabled extension %s: Dependency %s not found',
                extension.ext_name, ex)
            continue

        try:
            extension.validate_environment()
        except exceptions.ExtensionError as ex:
            logger.info(
                'Disabled extension %s: %s', extension.ext_name, ex.message)
            continue

        valid_extensions.append(extension)

    names = (e.ext_name for e in valid_extensions)
    logger.debug('Valid extensions: %s', ', '.join(names))
    return valid_extensions


def filter_enabled_extensions(raw_config, extensions):
    boolean = config_lib.Boolean()
    enabled_extensions = []
    enabled_names = []
    disabled_names = []

    for extension in extensions:
        # TODO: handle key and value errors.
        enabled = raw_config[extension.ext_name]['enabled']
        if boolean.deserialize(enabled):
            enabled_extensions.append(extension)
            enabled_names.append(extension.ext_name)
        else:
            disabled_names.append(extension.ext_name)

    logging.info(
        'Enabled extensions: %s', ', '.join(enabled_names) or 'none')
    logging.info(
        'Disabled extensions: %s', ', '.join(disabled_names) or 'none')
    return enabled_extensions
