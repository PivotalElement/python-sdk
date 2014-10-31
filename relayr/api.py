"""
Implementation of Relayr's RESTful HTTP API as individual endpoints.

This module contains the Api class with one method for each API endpoint.
All method names start with the HTTP method followed by the resource names used
in that endpoint e.g. ``post_user_app`` for the endpoint
``POST /users/<id>/apps/<id>`` with minor modifications, usually turning plural
into singular forms.

The function ``perform_request`` performs all HTTP requests and raises an
exception for all unexpected response status codes (!= 2XX).
"""

import os
import time
import json
import platform
import urllib
import warnings
import logging

import requests

from relayr.version import __version__
from relayr.exceptions import RelayrApiException
from relayr.compat import urlencode


# read config vars from environment (restricted to Booleans)
DEBUG = True if os.environ.get('RELAYR_DEBUG', 'False') == 'True' else False
LOG = True if os.environ.get('RELAYR_LOG', 'False') == 'True' else False

_userAgent = 'Python-Relayr-Client/{version} ({plat}; {pyimpl} {pyver})'.format(
    version=__version__,
    plat=platform.platform(),
    pyimpl=platform.python_implementation(),
    pyver=platform.python_version(),
)


def create_logger(sender):
    "Create a logger for the requesting object."

    logger = logging.getLogger('Relayr API Client')
    logger.setLevel(logging.DEBUG)

    logfile = "{0}/relayr-api-{1}.log".format(os.getcwd(), id(sender))
    h = logging.FileHandler(logfile)
    # h = logging.RotatingFileHandler(logfile, 
    #     mode='a', maxBytes=2**14, backupCount=5, encoding=None, delay=0)

    # h.setLevel(logging.DEBUG)

    # create formatter and add it to the handler(s)
    fmt = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    formatter = logging.Formatter(fmt, '%Y-%m-%d %H:%M:%S.%f %Z%z')
    formatter.converter = time.gmtime
    h.setFormatter(formatter)

    # add the handler(s) to the logger
    logger.addHandler(h)

    return logger

def build_curl_call(method, url, data=None, headers=None):
    """
    Build and return a ``curl`` command for use on the command-line.

    (The data parameter is supposed to be already urlencoded...) ## FIXME
    """

    command = "curl -X {0} {1}".format(method.upper(), url)
    if headers:
        for k, v in headers.items():
            command += ' -H "{0}: {1}"'.format(k, v)
    if data:
        # Add body params (eg. --data "param1=value1&param2=value2")
        # command += ' --data "{0}"'.format(urlencode(data))
        command += ' --data "{0}"'.format(data)
    return command

class Api(object):
    """
    This class provides direct access to the Relayr API endpoints.

    Some examples:

    .. code-block:: python

        # Create an anonymous client and call simple API endpoints:
        from relayr.api import Api
        a = Api()
        assert a.get_server_status() == {'database': 'ok'}
        assert a.get_users_validate('god@in.heaven') == {'exists': False}
        assert a.get_public_device_model_meanings() > 0

    """
    def __init__(self, host=None, **kwargs):
        """
        :arg host: the base url for accessing the Relayr RESTful API, default
            is ``https://api.relayr.io``.

        :arg token: a token generated on the Relayr site for a combination of 
            a Relayr user and application.
        """

        self.host = host or 'https://api.relayr.io'
        self.useragent = _userAgent
        self.token = kwargs.get('token', '')
        self.headers = {
            'User-Agent': self.useragent,
            'Content-Type': 'application/json'
        }
        if self.token:
            self.headers['Authorization'] = 'Bearer {0}'.format(self.token)

        if LOG:
            self.logger = create_logger(self)
            self.logger.info('started')

        # check if the API is available
        try:
            self.get_server_status()
        except:
            raise 

    def __del__(self):
        """Object destruction..."""
        if LOG:
            self.logger.info('terminated')

    def perform_request(self, method, url, data=None, headers=None):
        """
        Perform an API call and return JSON result as Python datastructure.

        Query parameters are expected in the ``url`` parameter.
        For returned status codes other than 2XX a ``RelayrApiException``
        is raised that contains the API call (method and URL) plus 
        a ``curl`` command replicating the API call for debugging reuse 
        on the command-line.
        """

        if LOG:
            command = build_curl_call(method, url, data, headers)
            self.logger.info("API request: " + command)

        urlencoded_data = None
        if data is not None:
            urlencoded_data = urlencode(data)
            data = json.dumps(data)
            try:
                data = data.encode('utf-8')
            except (UnicodeDecodeError, AttributeError):
                # bytes/str - no need to re-encode
                pass

        func = getattr(requests, method.lower())
        resp = func(url, data=data or '', headers=headers or {})
        resp.connection.close()

        if LOG:
            # self.logger.info("API response header: " + resp.headers)
            self.logger.info("API response content: " + resp.content)

        status = resp.status_code
        if 200 <= status < 300:
            try:
                js = resp.json()
            except:
                js = None
                # raise ValueError('Invalid JSON code(?): %r' % resp.content)
                if DEBUG:
                    warnings.warn("Replaced suspicious API response (invalid JSON?) %r with 'null'!" % resp.content)
            return status, js
        else:
            args = (resp.json()['message'], method.upper(), url)
            msg = "{0} - {1} {2}".format(*args)
            command = build_curl_call(method, url, urlencoded_data, headers)
            msg = "%s - %s" % (msg, command)
            raise RelayrApiException(msg)

    # ..............................................................................
    # System
    # ..............................................................................

    def get_users_validate(self, userEmail):
        """
        Validate an user email address.
        
        :param userEmail: The user email address to be validated.
        :type userEmail: string
        :rtype: A dict with an ``exists`` field and a Boolean result value.
    
        Sample result::
    
            {"exists": True}
        """
        
        # https://api.relayr.io/users/validate?email=<userEmail>
        url = '{0}/users/validate?email={1}'.format(self.host, userEmail)
        _, data = self.perform_request('GET', url, headers=self.headers)
        return data

    def get_server_status(self):
        """
        Check server status.

        :rtype: A dict with certain fields describing the server status.

        Sample result::

            {"database": "ok"}
        """

        # https://api.relayr.io/server-status
        url = '{0}/server-status'.format(self.host)
        _, data = self.perform_request('GET', url, headers=self.headers)
        return data

    def post_oauth2_token(self, clientID, clientSecret, code, redirectURI):
        """
        User:token from tmp code. (?)
        """

        data = {
            "client_id": clientID,
            "client_secret": clientSecret,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirectURI
        }
    
        # https://api.relayr.io/oauth2/token
        url = '{0}/oauth2/token'.format(self.host)
        _, data = self.perform_request('POST', url, data=data, headers=self.headers)
        return data

    def get_oauth2_appdev_token(self, appID):
        """
        Get the token representing a specific Relayr application and user.
        
        :param appID: The application's UUID.
        :type appID: string
        :rtype: A dict with fields describing the token.
    
        Sample result (anonymized token value)::
    
            {
                "token": "...",
                "expiryDate": "2014-10-08T10:14:07.789Z"
            }
        """
    
        # https://api.relayr.io/oauth2/appdev-token/<appID>
        url = '{0}/oauth2/appdev-token/{1}'.format(self.host, appID)
        _, data = self.perform_request('GET', url, headers=self.headers)
        return data
    
    def post_oauth2_appdev_token(self, appID):
        """
        Generate a new token representing a developer and a Relayr Application.
        
        :param appID: The application's UUID.
        :type appID: string
        :rtype: A dict with fields describing the token.
        """
    
        # https://api.relayr.io/oauth2/appdev-token/<appID>
        url = '{0}/oauth2/appdev-token/{1}'.format(self.host, appID)
        _, data = self.perform_request('POST', url, headers=self.headers)
        return data

    def delete_oauth2_appdev_token(self, appID):
        """
        Revoke token.
        """
        
        # https://api.relayr.io/oauth2/appdev-token/<appID>
        url = '{0}/oauth2/appdev-token/{1}'.format(self.host, appID)
        _, data = self.perform_request('DELETE', url, headers=self.headers)
        return data

    # ..............................................................................
    # Users
    # ..............................................................................

    def get_oauth2_user_info(self):
        """
        Return information about the user initiating the request.
        
        :rtype: A dictionary with fields describing the user.
    
        Sample result (anonymized values)::
        
            {
                "email": "joe@foo.com", 
                "id": "...",
                "name": "joefoo"
            }
        """

        # https://api.relayr.io/oauth2/user-info
        url = '{0}/oauth2/user-info'.format(self.host)
        _, data = self.perform_request('GET', url, headers=self.headers)
        return data

    def patch_user(self, userID, name=None, email=None):
        """
        Update one or more user attributes.
        
        :param userID: the uers's UID
        :type userID: string
        :param name: the user name to be set
        :type name: string
        :param email: the user email to be set
        :type email: string
        :rtype: dict with user info fields
        """
    
        data = {}
        if name is not None:
            data.update(name=name)
        if email is not None:
            data.update(email=email)

        # https://api.relayr.io/users/%s
        url = '{0}/users/{1}'.format(self.host, userID)
        _, data = self.perform_request('PATCH', url, data=data, headers=self.headers)
        return data

    def post_user_app(self, userID, appID):
        "Install a new app under a specific user."

        # https://api.relayr.io/users/%s/apps/%s
        url = '{0}/users/{1}/apps/{2}'.format(self.host, userID, appID)
        _, data = self.perform_request('POST', url, headers=self.headers)
        return data

    def delete_user_app(self, userID):
        "Uninstall an app of a specific user."

        # https://api.relayr.io/users/%s/apps/%s
        url = '{0}/users/{1}/apps/{2}'.format(self.host, userID, appID)
        _, data = self.perform_request('DELETE', url, headers=self.headers)
        return data

    def get_user_publishers(self, userID):
        """
        Return all publishers owned by a specific user.
    
        :param userID: the uers's UID
        :type userID: string
        :rtype: list of dicts ... 
        """
        
        # https://api.relayr.io/users/%s/publishers
        url = '{0}/users/{1}/publishers'.format(self.host, userID)
        _, data = self.perform_request('GET', url, headers=self.headers)
        return data

    def get_user_apps(self, userID):
        """
        Return all apps installed for a specific user.

        :param userID: the users's UID
        :type userID: string
        :rtype: list of dicts ... with IDs and secrets
        """

        # https://api.relayr.io/users/%s/apps
        url = '{0}/users/{1}/apps'.format(self.host, userID)
        _, data = self.perform_request('GET', url, headers=self.headers)
        return data

    def get_user_transmitters(self, userID):
        """
        Return all transmitters under a specific user.
    
        :param userID: the uers's UID
        :type userID: string
        :rtype: list of dicts with IDs and secrets
        """
    
        # https://api.relayr.io/users/%s/transmitters
        url = '{0}/users/{1}/transmitters'.format(self.host, userID)
        _, data = self.perform_request('GET', url, headers=self.headers)
        return data

    def get_user_devices(self, userID):
        """
        Returns all devices registered for a specific user.
    
        :param userID: the uers's UID
        :type userID: string
        :rtype: list of dicts ...
        """
                
        # https://api.relayr.io/users/%s/devices
        url = '{0}/users/{1}/devices'.format(self.host, userID)
        _, data = self.perform_request('GET', url, headers=self.headers)
        return data

    def get_user_devices_filtered(self, userID, meaning):
        """
        Returns all devices registered for a specific user filtered by meaning.
    
        :param userID: the users's UID
        :type userID: string
        :param meaning: a meaning used for filtering results
        :type meaning: string
        :rtype: list of dicts ...
        """

        # https://api.relayr.io/users/%s/devices?meaning=%s
        url = '{0}/users/{1}/devices?meaning={}'.format(self.host, userID, meaning)
        _, data = self.perform_request('GET', url, headers=self.headers)
        return data

    def get_user_devices_bookmarked(self, userID):
        """
        Return a list of devices bookmarked by the specific user.
    
        :param userID: the uers's UID
        :type userID: string
        :rtype: list of dicts ...
        """
                
        # https://api.relayr.io/users/%s/devices/bookmarks
        url = '{0}/users/{1}/devices/bookmarks'.format(self.host, userID)
        _, data = self.perform_request('GET', url, headers=self.headers)
        return data

    def delete_user_devices_bookmarked(self, userID, deviceID):
        """
        Delete a bookmarked device. Following the deletion the device will no longer be bookmarked.
    
        :param userID: the uers's UID
        :type userID: string
        :rtype: list of dicts ...
        """
                
        # https://api.relayr.io/users/%s/devices/%s/bookmarks
        url = '{0}/users/{1}/devices/{}/bookmarks'.format(self.host, userID, deviceID)
        _, data = self.perform_request('DELETE', url, headers=self.headers)
        return data

    def post_user_wunderbar(self, userID):
        """
        Return the IDs and Secrets of the Master Module and Sensor Modules.
    
        :param userID: the users's UID
        :type userID: string
        :rtype: dict with information about master and sensor modules/devices
    
        Sample result (abbreviated, some values anonymized)::
    
            {
                "bridge": { ... }, 
                "microphone": {
                    "name": "My Wunderbar Microphone", 
                    "public": False, 
                    "secret": "......", 
                    "owner": "...", 
                    "model": {
                        "readings": [
                            {
                                "meaning": "noise_level", 
                                "unit": "dba"
                            }
                        ], 
                        "manufacturer": "Relayr GmbH", 
                        "id": "...", 
                        "name": "Wunderbar Microphone"
                    }, 
                    "id": "...", 
                    "firmwareVersion": "1.0.0"
                }, 
                "light": { ... }, 
                "masterModule": {
                    "owner": "...", 
                    "secret": "............", 
                    "id": "...", 
                    "name": "My Wunderbar Master Module"
                }, 
                "infrared": { ... }, 
                "thermometer": { ... }, 
                "gyroscope": { ... }
            }    
        """
    
        # https://api.relayr.io/users/%s/wunderbar
        url = '{0}/users/{1}/wunderbar'.format(self.host, userID)
        _, data = self.perform_request('POST', url, headers=self.headers)
        return data

    def post_users_destroy(self, userID):
        """
        Remove all Wunderbars associated with a specific user.
    
        :param userID: the users's UID
        :type userID: string
        """
    
        # https://api.relayr.io/users/%s/destroy-everything-i-love
        url = '{0}/users/{1}/destroy-everything-i-love'.format(self.host, userID)
        _, data = self.perform_request('POST', url, headers=self.headers)
        return data

    # ..............................................................................
    # Applications
    # ..............................................................................

    def get_public_apps(self):
        """
        Return list of all applications (no credentials needed).
    
        :rtype: list of dicts, each representing a relayr application
        """

        # https://api.relayr.io/apps
        url = '{0}/apps'.format(self.host)
        _, data = self.perform_request('GET', url, headers=self.headers)
        return data

    def post_app(self, appName, publisherID, redirectURI, appDescription):
        """
        Add (register) a new app to the Relayr cloud.
    
        :rtype: list of dicts, each representing a relayr application
        """

        data = {
          "name": appName,
          "publisher": publisherID,
          "redirectUri": redirectURI,
          "description": appDescription
        }
        # https://api.relayr.io/apps
        url = '{0}/apps'.format(self.host)
        _, data = self.perform_request('POST', url, data=data, headers=self.headers)
        return data

    def get_app_info(self, appID):
        """
        Returns information about the app with the given ID.
        
        Sample result (anonymized token value)::
        
            {
                "id": "...",
                "name": "My App",
                "description": "My Wunderbar app",
                ...
            }
        """
    
        # https://api.relayr.io/apps/<appID>
        url = '{0}/apps/{1}'.format(self.host, appID)
        _, data = self.perform_request('GET', url, headers=self.headers)
        return data

    def get_app_info_extended(self, appID):
        """
        Returns extended information about the app with the given ID.
        
        Sample result (some values anonymized)::
        
            {
                "id": "...",
                "name": "My App",
                "publisher": "...",
                "clientId": "...",
                "clientSecret": "...",
                "description": "My Wunderbar app",
                "redirectUri": https://relayr.io
            }
        """
    
        # https://api.relayr.io/apps/<appID>/extended
        url = '{0}/apps/{1}/extended'.format(self.host, appID)
        _, data = self.perform_request('GET', url, headers=self.headers)
        return data
    
    
    def patch_app(self, appID, description=None, name=None, redirectUri=None):
        """
        Updates one or more app attributes.
        
        :param appID: the application's UID
        :type appID: string
        :param description: the user name to be set
        :type description: string
        :param name: the user email to be set
        :type name: string
        :param redirectUri: the redirect URI to be set
        :type redirectUri: string
        
        Sample result (some values anonymized)::
        
            {
                "id": "...",
                "name": "My App",
                "publisher": "...",
                "clientId": "...",
                "clientSecret": "...",
                "description": "My Wunderbar app",
                "redirectUri": https://relayr.io
            }
        """

        data = {}
        if name is not None:
            data.update(name=name)
        if description is not None:
            data.update(description=description)
        if redirectUri is not None:
            data.update(redirectUri=redirectUri)

        # https://api.relayr.io/apps/<appID>
        url = '{0}/apps/{1}'.format(self.host, appID)
        _, data = self.perform_request('PATCH', url, data=data, headers=self.headers)
        return data

    def delete_app(self, appID):
        """
        Delete an app from the Relayr cloud.
        
        :param appID: the application's UID
        :type appID: string
        
        """

        # https://api.relayr.io/apps/<appID>
        url = '{0}/apps/{1}'.format(self.host, appID)
        _, data = self.perform_request('DELETE', url, headers=self.headers)
        return data

    def get_oauth2_app_info(self):
        """
        Return info about the app initiating the request (the one in the token).

        Sample result (anonymized token value)::
        
            {
                "id": "...",
                "name": "My App",
                "description": "My Wunderbar app"
            }
        """

        # https://api.relayr.io/oauth2/app-info
        url = '{0}/oauth2/app-info'.format(self.host)
        _, data = self.perform_request('GET', url, headers=self.headers)
        return data

    def post_app_device(appID, deviceID):
        """
        Connect an app to a device. PubNub credentials are returned as part of the response.
        """
        # {{relayrAPI}}/apps/{{appID}}/devices/{{deviceID}}
        url = '{0}/apps/{1}/devices/{2}'.format(self.host, appID, deviceID)
        _, data = self.perform_request('POST', url, headers=self.headers)
        return data

    def delete_app_device(appID, deviceID):
        """
        Disconnect an app to a device.
        """
        # {{relayrAPI}}/apps/{{appID}}/devices/{{deviceID}}
        url = '{0}/apps/{1}/devices/{2}'.format(self.host, appID, deviceID)
        _, data = self.perform_request('DELETE', url, headers=self.headers)
        return data

    # ..............................................................................
    # Publishers
    # ..............................................................................
    
    def get_public_publishers(self):
        """
        Return list of all publishers (no credentials needed).
    
        :rtype: list of dicts, each representing a relayr publisher
        """
    
        # https://api.relayr.io/publishers
        url = '{0}/publishers'.format(self.host)
        _, data = self.perform_request('GET', url, headers=self.headers)
        return data
        
    def post_publisher(self, userID, name):
        """
        Register a new publisher.
    
        :param userID: the user UID of the publisher
        :type userID: string
        :param name: the publisher name
        :type name: string
        :rtype: a dict with fields describing the new publisher
        """
    
        # https://api.relayr.io/publishers
        data = {'owner': userID, 'name': name}
        url = '{0}/publishers'.format(self.host)
        _, data = self.perform_request('POST', url, data=data, headers=self.headers)
        return data

    def delete_publisher(self, publisherID):
        """
        Delete a specific publisher from the Relayr cloud.
    
        :param publisherID: the publisher UID
        :type publisherID: string
        :rtype: an empty dict(?)
        """

        # https://api.relayr.io/publishers
        url = '{0}/publishers/{1}'.format(self.host, publisherID)
        _, data = self.perform_request('DELETE', url, headers=self.headers)
        return data

    def get_publisher_apps(self, publisherID):
        """
        Returns a list of apps published by a specific publisher.
        
        :rtype: A list of apps.
        """

        # https://api.relayr.io/publishers/<id>/apps
        url = '{0}/publishers/{1}/apps'.format(self.host, publisherID)
        _, data = self.perform_request('GET', url, headers=self.headers)
        return data

    def get_publisher_apps_extended(self, publisherID):
        """
        Returns a list of extended apps published by a specific publisher.
        
        :rtype: A list of apps.
        """

        # https://api.relayr.io/publishers/<id>/apps/extended
        url = '{0}/publishers/{1}/apps/extended'.format(self.host, publisherID)
        _, data = self.perform_request('GET', url, headers=self.headers)
        return data
    
    
    def patch_publisher(self, publisherID, name=None):
        """
        Update one or more publisher attributes.
        
        :param publisherID: the publisher's UID
        :type publisherID: string
        :param name: the publisher name to be set
        :type name: string
        :rtype: ``True``, if successful, ``False`` otherwise
        """
    
        data = {}
        if name is not None:
            data.update(name=name)
        
        # https://api.relayr.io/publishers/<id>
        url = '{0}/publishers/{1}'.format(self.host, publisherID)
        _, data = self.perform_request('PATCH', url, data=data, headers=self.headers)
        return data

    # ..............................................................................
    # Devices
    # ..............................................................................
    
    def get_device_configuration(self, deviceID):
        """
        Returns info about a device's current configuration and config. schema.

        Example result::

            {
                "version": "1.0.0", 
                "configuration": {
                    "defaultValues": {
                        "frequency": 1000
                    }, 
                    "schema": {
                        "required": [
                            "frequency"
                        ], 
                        "type": "object", 
                        "properties": {
                            "frequency": {
                                "minimum": 5, 
                                "type": "integer", 
                                "description": "Frequency of the sensor updates in milliseconds"
                            }
                        }, 
                        "title": "Relayr configuration schema"
                    }
                }
            }

        :param deviceID: the device UID
        :type deviceID: string
        """
        
        # https://api.relayr.io/devices/<deviceID>/firmware
        url = '{0}/devices/{1}/firmware'.format(self.host, deviceID)
        _, data = self.perform_request('GET', url, headers=self.headers)
        return data

    def post_device_configuration(self, deviceID, frequency):
        """
        Modify the configuration of a specific device facillitated by a schema.

        :param deviceID: the device UID
        :type deviceID: string
        :param frequency: the number of ms between two sensor transmissions
        :type frequency: integer
        """
        
        data = {'frequency': frequency, 'deviceId': deviceID}
        # https://api.relayr.io/devices/<deviceID>/configuration
        url = '{0}/devices/{1}/configuration'.format(self.host, deviceID)
        _, data = self.perform_request('POST', url, data=data, headers=self.headers)
        return data

    def get_public_devices(self, meaning=''):
        """
        Return list of all public devices (no credentials needed).
    
        :param meaning: required meaning in the device model's ``readings`` attribute
        :type meaning: string
        :rtype: list of dicts, each representing a relayr device
        """
        
        # https://api.relayr.io/devices/public
        url = '{0}/devices/public'.format(self.host)
        if meaning:
            url += '?meaning={0}'.format(meaning)
        _, data = self.perform_request('GET', url)
        return data

    def post_device(self, appName, publisherID, redirectURI, appDescription):
        """
        Add (register) a new device to the Relayr cloud.
    
        :rtype: list of dicts, each representing a relayr device
        """

        data = {
          "name": deviceName,
          "owner": userID,
          "model": modelID,
          "firmwareVersion": firmwareVersion
        }
        # https://api.relayr.io/devices
        url = '{0}/devices'.format(self.host)
        _, data = self.perform_request('POST', url, data=data, headers=self.headers)
        return data

    def get_device(self, deviceID):
        """
        Return information about a specific device with given UID.
            
        :param deviceID: the device UID
        :type deviceID: string
        :rtype: a dict with fields containing information about the device
    
        Raises ``exceptions.RelayrApiException`` for invalid UIDs or missing 
        credentials...
        """
        
        # https://api.relayr.io/devices/%s
        url = '{0}/devices/{1}'.format(self.host, deviceID)
        _, data = self.perform_request('GET', url, headers=self.headers)
        return data

    def patch_device(self, deviceID=None, deviceName=None, deviceDescription=None, deviceModel=None, isDevicePublic=None):
        """
        Updates one or more device attributes.
            
        :param deviceID: the device UID
        :type deviceID: string
        :rtype: a dict with fields containing information about the device
    
        Raises ``exceptions.RelayrApiException`` for invalid UIDs or missing 
        credentials...
        """

        data = {
          "name": deviceName,
          "description": deviceDescription,
          "model": deviceModel,
          "public": isDevicePublic
        }
        for k, v in data.items():
            if v is None:
                del data[k]
        # https://api.relayr.io/devices/%s
        url = '{0}/devices/{1}'.format(self.host, deviceID)
        _, data = self.perform_request('PATCH', url, data=data, headers=self.headers)
        return data

    def delete_device(self, deviceID):
        """
        Deletes a device from the Relayr cloud.

        :param deviceID: the device UID
        :type deviceID: string
        :rtype: a dict with fields containing information about the device
        """
        # https://api.relayr.io/devices/%s
        url = '{0}/devices/{1}'.format(self.host, deviceID)
        _, data = self.perform_request('DELETE', url, headers=self.headers)
        return data

    def get_device_apps(self, deviceID):
        """
        Return all the apps connected to a specific device.
    
        :param deviceID: the device UID
        :type deviceID: string
        :rtype: a list of dicts with information about apps
        """
    
        # https://api.relayr.io/devices/<deviceID>/apps
        url = '{0}/devices/{1}/apps'.format(self.host, deviceID)
        _, data = self.perform_request('GET', url, headers=self.headers)
        return data

    def post_devices_supscription(self, deviceID):
        """
        Post a subscription for a user to a public device.
    
        :param deviceID: the device's UID
        :type deviceID: string
        :rtype: dict with connection credentials
        
        Sample result (anonymized values)::
    
            {
                "authKey": "...", 
                "cipherKey": "...", 
                "channel": "...", 
                "subscribeKey": "sub-c-..."
            }
        """
    
        # https://api.relayr.io/devices/%s/subscription
        url = '{0}/devices/{1}/subscription'.format(self.host, deviceID)
        _, data = self.perform_request('POST', url, headers=self.headers)
        return data

    def post_device_command(self, deviceID, command, data):
        """
        Send a command to a specific device.
        """
        # https://api.relayr.io/devices/<deviceID>/cmd/<command>
        url = '{0}/devices/{1}/cmd/{2}'.format(self.host, deviceID, command)
        _, data = self.perform_request('POST', url, data=data, headers=self.headers)
        return data

    def post_device_app(deviceID, appID):
        """
        Connect a device to an app. PubNub credentials are returned as part of the response.
        """
        # {{relayrAPI}}/devices/{{deviceID}}/apps/{{appID}}
        url = '{0}/devices/{1}/apps/{2}'.format(self.host, deviceID, appID)
        _, data = self.perform_request('POST', url, headers=self.headers)
        return data

    def delete_device_app(deviceID, appID):
        """
        Disconnect a device from an app.
        """
        # {{relayrAPI}}/devices/{{deviceID}}/apps/{{appID}}
        url = '{0}/devices/{1}/apps/{2}'.format(self.host, appID, deviceID)
        _, data = self.perform_request('DELETE', url, headers=self.headers)
        return data

    # ..............................................................................
    # Device models
    # ..............................................................................
    
    def get_public_device_models(self):
        """
        Return list of all device models (no credentials needed).
    
        :rtype: list of dicts, each representing a Relayr device model
        """
    
        # https://api.relayr.io/device-models
        url = '{0}/device-models'.format(self.host)
        _, data = self.perform_request('GET', url)
        return data

    def get_device_model(self, devicemodelID):
        """
        Return information about a device model with a specific ID.
        
        :rtype: A nested dictionary structure with fields describing the DM.
        """
    
        # https://api.relayr.io/device-models/<id>
        url = '{0}/device-models/{1}'.format(self.host, devicemodelID)
        _, data = self.perform_request('GET', url, headers=self.headers)
        return data

    def get_public_device_model_meanings(self):
        """
        Return list of all device model meanings (no credentials needed).
    
        :rtype: list of dicts, each representing a Relayr device model meaning
        """

        # https://api.relayr.io/device-models/meanings
        url = '{0}/device-models/meanings'.format(self.host)
        _, data = self.perform_request('GET', url)
        return data

    # ..............................................................................
    # Transmitters
    # ..............................................................................

    def get_transmitter(self, transmitterID):
        """
        Return information about a specific transmitter with the given ID.
    
        :param transmitterID: the transmitter UID
        :type transmitterID: string
        :rtype: a dict with fields describing the transmitter
        """
    
        # https://api.relayr.io/transmitters/<id>
        url = '{0}/transmitters/{1}'.format(self.host, transmitterID)
        _, data = self.perform_request('GET', url, headers=self.headers)
        return data

    def post_transmitter(self, transmitterID, owner=None, name=None):
        """
        Register a new Transmitter to the Relayr cloud.
    
        :param transmitterID: the transmitter UID
        :type transmitterID: string
        :param owner: the transmitters owner's UID
        :type owner: string
        :param name: the transmitter name
        :type name: string
        :rtype: an empty dict(?)
        """

        data = {}
        if owner is not None:
            data.update(owner=owner)
        if name is not None:
            data.update(name=name)
        
        # https://api.relayr.io/transmitters/<id>
        url = '{0}/transmitters/{1}'.format(self.host, transmitterID)
        _, data = self.perform_request('POST', url, data=data, headers=self.headers)
        return data

    def patch_transmitter(self, transmitterID, name=None):
        """
        Update information about a specific transmitter with the given ID.
    
        :param transmitterID: the transmitter UID
        :type transmitterID: string
        :param name: the transmitter name
        :type name: string
        :rtype: an empty dict(?)
        """

        data = {}
        if name is not None:
            data.update(name=name)
                
        # https://api.relayr.io/transmitters/<id>
        url = '{0}/transmitters/{1}'.format(self.host, transmitterID)
        _, data = self.perform_request('PATCH', url, data=data, headers=self.headers)
        return data

    def delete_transmitter(self, transmitterID):
        """
        Delete a specific transmitter from the Relayr cloud.
    
        :param transmitterID: the transmitter UID
        :type transmitterID: string
        :rtype: an empty dict(?)
        """

        # https://api.relayr.io/transmitters/<id>
        url = '{0}/transmitters/{1}'.format(self.host, transmitterID)
        _, data = self.perform_request('DELETE', url, headers=self.headers)
        return data

    def post_transmitter_device(self, transmitterID, deviceID):
        """
        Connect a transmitter to a device.
    
        :param transmitterID: the transmitter UID
        :type transmitterID: string
        :param deviceID: the device UID
        :type deviceID: string
        :rtype: an empty dict(?)
        """
    
        # https://api.relayr.io/transmitters/<transmitterID>/devices/<deviceID>
        url = '{0}/transmitters/{1}/devices/{}'.format(self.host, transmitterID, deviceID)
        _, data = self.perform_request('POST', url, data=data, headers=self.headers)
        return data

    def get_transmitter_devices(self, transmitterID):
        """
        Return a list of devices connected to a specific transmitter.
    
        :param transmitterID: the transmitter UID
        :type transmitterID: string
        :rtype: a list of devices
        """
    
        # https://api.relayr.io/transmitters/<transmitterID>/devices
        url = '{0}/transmitters/{1}/devices'.format(self.host, transmitterID)
        _, data = self.perform_request('GET', url, headers=self.headers)
        return data

    def delete_transmitter_device(self, transmitterID, deviceID):
        """
        Delete a connection with a device.
    
        :param transmitterID: the transmitter UID
        :type transmitterID: string
        :param deviceID: the device UID
        :type deviceID: string
        :rtype: an empty dict(?)
        """
    
        # https://api.relayr.io/transmitters/<transmitterID>/devices/<deviceID>
        url = '{0}/transmitters/{1}/devices/{}'.format(self.host, transmitterID, deviceID)
        _, data = self.perform_request('DELETE', url, data=data, headers=self.headers)
        return data