# -*- coding: utf-8 -*-

"""
This module contains abstractions for Relayr API resources.

Resources right now can be users, publishers, applications, devices, device
models and transmitters.
"""


from relayr import exceptions
from relayr.dataconnection import PubnubDataConnection


class User(object):
    "A Relayr user."

    def __init__(self, userID=None, client=None):
        self.userID = userID
        self.client = client

    def __repr__(self):
        return "%s(userID=%r)" % (self.__class__.__name__, self.userID)

    def get_publishers(self):
        "Return a generator of the publishers of the user."

        for pub_json in self.client.api.get_user_publishers(self.userID):
            p = Publisher(pub_json['id'], client=self.client)
            for k in pub_json:
                setattr(p, k, pub_json[k])
            yield p

    def get_apps(self):
        "Return a generator of the apps of the user."

        for app_json in self.client.api.get_user_apps(self.userID):
            ## TODO: change 'app' field to 'id' in API?
            app = App(app_json['app'], client=self.client)
            app.get_info()
            yield app

    def get_transmitters(self):
        "Return a generator of the transmitters of the user."

        for trans_json in self.client.api.get_user_transmitters(self.userID):
            trans = Transmitter(trans_json['id'], client=self.client)
            trans.get_info()
            yield trans

    def get_devices(self):
        "Return a generator of the devices of the user."

        for dev_json in self.client.api.get_user_devices(self.userID):
            dev = Device(dev_json['id'], client=self.client)
            dev.get_info()
            yield dev

    def connect_device(self, device, callback):
        "Open and return a connection to the data provider."

        creds = self.client.api.post_devices_supscription(device.id)
        return PubnubDataConnection(callback, creds)

    def disconnect_device(self, deviceID):
        # There is no disconnect in the API...
        raise NotImplementedError

    def update(self, name=None, email=None):
        res = self.client.api.patch_user(self.userID, name=name, email=email)
        for k in res:
            setattr(self, k, res[k])
        return self

    ## TODO: rename to 'registered_wunderbar_devices'?
    def register_wunderbar(self):
        """
        Return registered Wunderbar devices (master and sensor modules).
    
        :rtype: A generator over the registered devices and one transmitter.
        """    
        res = self.client.api.post_user_wunderbar(self.userID)
        for k, v in res.items():
            if 'model' in v:
                item = Device(res[k]['id'], client=self.client)
                item.get_info()
            else:
                item = Transmitter(res[k]['id'], client=self.client)
                item.get_info()
            yield item

    def remove_wunderbar(self):
        """
        Remove all Wunderbars associated with this user.
    
        :param userID: the users's UID
        :type userID: string
        """    
        res = self.client.api.post_users_destroy(self.userID)
        return res


class Publisher(object):
    """
    A Relayr publisher.

    A publisher has a few attributes, which can be chaged. It can be
    registered to and deleted from the Relayr cloud. And it list all 
    applications it has published in the Relayr cloud.
    """

    def __init__(self, publisherID=None, client=None):
        self.publisherID = publisherID
        self.client = client

    def __repr__(self):
        return "%s(publisherID=%r)" % (self.__class__.__name__, self.publisherID)

    def get_apps(self, extended=False):
        """
        Get list of apps for this publisher.

        If the optional parameter ``extended`` is ``False`` (default) the 
        resulting apps will contain only the fields ``id``, ``name`` and 
        ``description``. If it is ``True`` there will be these additional 
        fields: ``publisher``, ``clientId``, ``clientSecret`` and
        ``redirectUri``.

        :param extended: flag indicating if the info should be extended
        :type extended: booloean
        :rtype: A list of dicts representing apps.
        """

        func = self.client.api.get_publisher_apps
        if extended:
            func = self.client.api.get_publisher_apps_extended
        return func(self.publisherID)

    def update(self, name=None):
        """
        Update certain information fields of the publishers.
        
        :param name: the user email to be set
        :type name: string
        """
        res = self.api.patch_publisher(self.userID, name=name)
        for k in res:
            setattr(self, k, res[k])
        return self

    def register(self, name, userID, publisher):
        """
        Add this publisher to the relayr repository.

        :param name: the publisher name to be set
        :type name: string
        :param userID: the publisher UID to be set
        :type userID: string(?)
        """
        raise NotImplementedError

    def delete(self):
        """
        Delete this publisher from the Relayr Cloud.
        """
        res = self.api.delete_publisher(self.publisherID)


class App(object):
    """
    A Relayr application.
    
    An application has a few attributes, which can be changed. It can be
    registered to and deleted from the Relayr cloud. And it can be connected 
    to and disconnected from devices.
    """
    
    def __init__(self, appID=None, client=None):
        self.appID = appID
        self.client = client

    def __repr__(self):
        return "%s(appID=%r)" % (self.__class__.__name__, self.appID)

    def get_info(self, extended=False):
        """
        Get application info.
        
        If the optional parameter ``extended`` is ``False`` (default) the 
        result will contain only the fields ``id``, ``name`` and 
        ``description``. If it is ``True`` there will be these additional 
        fields: ``publisher``, ``clientId``, ``clientSecret`` and
        ``redirectUri``.
        
        :param extended: flag indicating if the info should be extended
        :type extended: booloean
        :rtype: A dict with certain fields.
        """

        func = self.client.api.get_app_info
        if extended:
            func = self.client.api.get_app_info_extended
        res = func(self.appID)
        for k in res:
            setattr(self, k, res[k])
        return self

    def update(self, description=None, name=None, redirectUri=None):
        """
        Update certain fields in the application description.
        
        :param description: the user name to be set
        :type description: string
        :param name: the user email to be set
        :type name: string
        :param redirectUri: the redirect URI to be set
        :type redirectUri: string
        """
        res = self.client.api.patch_app(self.appID, description=description,
            name=name, redirectUri=redirectUri)
        for k in res:
            setattr(self, k, res[k])
        return self

    def delete(self):
        """
        Delete this app from the Relayr Cloud.
        """
        res = self.api.delete_publisher(self.appID)

    def register(self, name, publisher):
        """
        Add this app to the relayr repository.

        :param name: the app name to be set
        :type name: string
        :param publisher: the publisher to be set
        :type publisher: string(?)
        """
        raise NotImplementedError

    def connect_to_device(self, device):
        """
        Connects this app to a device.
        
        PubNub credentials are returned as part of the response.

        There is also an Device.connect_to_device() method...

        :param device: the device (name) to be connected
        :type device: string(?)
        """
        raise NotImplementedError

    def disconnect_from_device(self, device):
        """
        Disonnect this app from a device.

        There is also an Device.disconnect_from_app() method...

        :param device: the device (name) to be disconnected from
        :type device: string(?)
        """
        raise NotImplementedError


class Device(object):
    """
    A Relayr device.
    """

    def __init__(self, deviceID=None, client=None):
        self.deviceID = deviceID
        self.client = client

    def __repr__(self):
        return "%s(deviceID=%r)" % (self.__class__.__name__, self.deviceID)

    def get_info(self):
        """
        Get device info and store as instance attributes.

        :rtype: self.
        """

        res = self.client.api.get_device(self.deviceID)
        for k in res:
            if k == 'model':
                self.model = DeviceModel(res[k]['id'], client=self.client)
                self.model.get_info()
            else:
                setattr(self, k, res[k])
        return self

    def update(self, description=None, name=None, model=None, public=None):
        """
        Update certain fields in the device description.
        
        :param description: the description to be set
        :type description: string
        :param name: the user name to be set
        :type name: string
        :param model: the device model to be set
        :type name: string?
        :param public: a flag for making the device public
        :type redirectUri: boolean
        """
        res = self.client.api.patch_device(self.deviceID, deviceDescription=description,
            deviceName=name, deviceModel=model, isDevicePublic=public)
        for k in res:
            setattr(self, k, res[k])
        return self

    def get_connected_apps(self):
        """
        Get all apps connected to this device.
        
        :rtype: A list of apps.
        """

        res = self.client.api.get_device_apps(self.deviceID)
        return res

    def connect_to_app(self, app):
        """
        Connect this device to an app.
        
        PubNub credentials are returned as part of the response.

        There is also an App.connect_to_device() method...

        :param app: the app (name) to be connected
        :type app: string(?)
        """
        raise NotImplementedError

    def disconnect_from_app(self, app):
        """
        Disconnect this device from an app.

        There is also an App.disconnect_from_device() method...

        :param app: the app (name) to be disconnected from
        :type app: string(?)
        """
        raise NotImplementedError

    def connect_to_public_device(self, deviceID, callback):
        """
        Subscribe a user to a public device.

        :param deviceID: the device's UID
        :type deviceID: string

        """
        creds = self.client.api.post_devices_supscription(self.deviceID)
        return PubnubDataConnection(callback, creds)

    def send_command(self, command, data):
        """
        Send a command to this device.

        :param command: the command to be sent
        :type command: string
        :param data: the command data to be sent
        :type command: dict
        """
        
        res = self.client.api.post_device_command(self.deviceID, command, data)
        return res

    def delete(self):
        """
        Delete this device from the Relayr cloud.

        :type command: self
        """
        
        res = self.client.api.delete_device(self.deviceID)
        return self

    def switch_led_on(self, bool=True):
        """
        Switch on device's LED for ca. 10 seconds or switch it off now.

        :param bool: the desired state, on if True (default), off if False
        :type bool: boolean
        :type command: self
        """
        self.send_command('led', {'cmd': int(bool)})
        return self

class DeviceModel(object):
    """
    Relayr device model.
    """
    
    def __init__(self, uuid=None, client=None):
        self.uuid = uuid
        self.client = client

    def __repr__(self):
        return "%s(uuid=%r)" % (self.__class__.__name__, self.uuid)

    def get_info(self):
        """
        Get device model info and store as instance attributes.
        
        :rtype: self.
        """
        res = self.client.api.get_device_model(self.uuid)
        for k, v in res.items():
            setattr(self, k, v)
        return self


class Transmitter(object):
    "A Relayr transmitter, like a Wunderbar."
    
    def __init__(self, transmitterID=None, client=None):
        self.transmitterID = transmitterID
        self.client = client

    def __repr__(self):
        args = (self.__class__.__name__, self.transmitterID)
        return "%s(transmitterID=%r)" % args

    def get_info(self):
        """
        Get transmitter info.
        """
        res = self.client.api.get_transmitter(self.transmitterID)
        for k, v in res.items():
            setattr(self, k, v)
        return self

    def delete(self):
        """
        Delete this transmitter from the Relayr cloud.

        :type command: self
        """
        
        res = self.client.api.delete_transmitter(self.transmitterID)
        return self

    def update(self, name=None):
        """
        Set transmitter info.
        """
        res = self.client.api.patch_transmitter(self.transmitterID, name=name)
        for k, v in res.items():
            setattr(self, k, v)
        return self

    def get_connected_devices(self):
        """
        Return a list of devices connected to this specific transmitter.
        
        :rtype: A list of devices.
        """
        res = self.client.api.get_transmitter_devices(self.transmitterID)
        for d in res:
            dev = Device(d['id'], client=self.client)
            dev.get_info()
            yield dev