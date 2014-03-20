#!/usr/bin/env python

import json
import requests
import logging
import ssl
from datetime import datetime
from os.path import exists, expanduser, dirname
from os import makedirs, remove
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.poolmanager import PoolManager


LOG = logging.getLogger(__name__)


default_cache_dir = expanduser('~/.nest')
login_url = 'https://home.nest.com/user/login'
user_agent = 'Nest/2.1.3 CFNetwork/548.0.4'


class TlsAdapter(HTTPAdapter):
    def init_poolmanager(self, connections, maxsize, block=False):
        self.poolmanager = PoolManager(num_pools=connections,
                                       maxsize=maxsize,
                                       block=block,
                                       ssl_version=ssl.PROTOCOL_TLSv1)


class FailedRequest(Exception):
    def __init__(self, message, response):
        super(FailedRequest, self).__init__(message)
        self.response = response


class NotAuthenticated(Exception):
    def __init__(self, message):
        super(NotAuthenticated, self).__init__(message)


class Nest(object):
    def __init__(self, id, structure):
        '''Initialize this Nest.'''
        self._id = str(id)
        self._structure = structure
        self._account = structure.account

    @property
    def account(self):
        return self._account

    @property
    def structure(self):
        return self._structure

    @property
    def name(self):
        return self.account.status['shared'][self.id]['name']

    @property
    def id(self):
        return self._id

    @property
    def scale(self):
        return self.account.status['device'][self.id]['temperature_scale']

    @property
    def ip(self):
        return self.account.status['metadata'][self.id]['last_ip']

    @property
    def humidity(self):
        return self.account.status['device'][self.id]['current_humidity']

    @property
    def temperature(self):
        temp = self.account.status['shared'][self.id]['current_temperature']
        if self.scale == 'F':
            temp = (temp * 1.8) + 32
        return temp

    @property
    def leaf(self):
        return self.account.status['device'][self.id]['leaf']

    @property
    def mode(self):
        mode = self.account.status['device'][self.id][
            'current_schedule_mode']
        return mode.lower()

    @mode.setter
    def mode(self, mode):
        mode = mode.upper()
        data = {'device': {self.id: {'current_schedule_mode': mode}}}
        self.account.request('POST', 'put', data=data)
        self.account.status['device'][self.id]['current_schedule_mode'] = mode

    @property
    def fan(self):
        return self.account.status['device'][self.id]['fan_mode']

    @fan.setter
    def fan(self, mode):
        if mode not in ('auto', 'on'):
            raise Exception('Invalid fan mode "{}". Must be "auto" or '
                            '"on"'.format(mode))
        data = {'device': {self.id: {'fan_mode': mode}}}
        self.account.request('POST', 'put', data=data)
        self.account.status['device'][self.id]['fan_mode'] = mode

    @property
    def target_temperature(self):
        shared = self.account.status['shared'][self.id]
        if self.mode == 'range':
            temp = [shared['target_temperature_low'],
                    shared['target_temperature_high']]
            if self.scale == 'F':
                temp = [(t * 1.8) + 32 for t in temp]
        else:
            temp = shared['target_temperature']
            if self.scale == 'F':
                temp = (temp * 1.8) + 32
        return temp

    @target_temperature.setter
    def target_temperature(self, temp):
        if isinstance(temp, (list, tuple)):
            # temp is (low, high)
            lo_and_hi = [float(t) for t in temp]
            if lo_and_hi[1] - lo_and_hi[0] < 3.0:
                raise Exception('High and low temperatures are too close')
            if self.scale == 'F':
                lo_and_hi = [(t - 32) / 1.8 for t in lo_and_hi]
            data = {
                'target_temperature_low': lo_and_hi[0],
                'target_temperature_high': lo_and_hi[1],
            }
        else:
            temp = float(temp)
            if self.scale == 'F':
                temp = (temp - 32) / 1.8
            data = {
                'target_change_pending': True,
                'target_temperature': temp
            }

        self.account.request('POST', 'put/shared.{}'.format(self.id),
                             data=data)

        shared = self.account.status['shared'][self.id]
        if isinstance(temp, (list, tuple)):
            shared['target_temperature_low'] = lo_and_hi[0]
            shared['target_temperature_high'] = lo_and_hi[1]
        else:
            shared['target_temperature'] = temp


class Structure(object):
    def __init__(self, structure_id, account):
        '''Initialize this structure.'''
        self._account = account
        self._id = structure_id
        self._nests = None

    @property
    def account(self):
        return self._account

    @property
    def id(self):
        return self._id

    @property
    def name(self):
        return self.account.status['structure'][self.id]['name']

    @property
    def nests(self):
        if self._nests is None:
            nests = {}
            for dev in self.account.status['structure'][self.id]['devices']:
                id = dev.split('.')[1]
                nests[id] = Nest(id, self)
            self._nests = nests
        return self._nests

    @property
    def location(self):
        return self.account.status['structure'][self.id]['postal_code']

    @property
    def weather(self):
        url = '{}{}'.format(self.account.session['urls']['weather_url'],
                            self.location)
        return requests.get(url).json()[self.location]

    # away ###############################

    @property
    def away(self):
        return self.account.status['structure'][self.id]['away']

    @away.setter
    def away(self, value):
        from time import time
        value = bool(value)
        data = {
            'away_timestamp': int(time()),
            'away': value,
            'away_setter': 0
        }
        self.account.request('POST', 'put/structure.{}'.format(self.id),
                             data=data)
        self.account.status['structure'][self.id]['away'] = value


class Account(object):
    def __init__(self, cache_dir=None):
        '''Initialize this nest interface.'''

        if cache_dir is None:
            cache_dir = default_cache_dir

        self._session_file = '{}/session.json'.format(cache_dir)
        self._status = None
        self._structures = None
        self._nests = None
        self._session = None

    @property
    def status(self):
        if self._status is None:
            r = self.request('GET', 'mobile/user.{}'.format(self.user_id))
            self._status = r.json()
        return self._status

    @property
    def structures(self):
        if self._structures is None:
            structures = {}
            user_structs = self.status['user'][self.user_id]['structures']
            LOG.debug('structs: %s', user_structs)
            for struct in user_structs:
                id = struct.split('.')[1]
                structures[id] = Structure(id, self)
            self._structures = structures
        return self._structures

    @property
    def nests(self):
        if self._nests is None:
            nests = {}
            for struct in self.structures.values():
                for id, nest in struct.nests.items():
                    nests[id] = nest
            self._nests = nests
        return self._nests

    @property
    def user_id(self):
        return self.session['userid']

    @property
    def session(self):
        return self._session

    @property
    def has_session(self):
        try:
            with open(self._session_file, 'rt') as sfile:
                self._session = json.load(sfile)
                expiry = datetime.strptime(self.session['expires_in'],
                                           '%a, %d-%b-%Y %H:%M:%S GMT')
                if datetime.utcnow() <= expiry:
                    return True
        except Exception:
            LOG.exception('missing or corrupt session file')

        return False

    def clear_session(self):
        '''Delete the session file'''
        remove(self._session_file)

    def login(self, email, password):
        '''Login to the user's Nest account.'''

        # make the cache dir if it doesn't exist
        cache_dir = dirname(self._session_file)
        if not exists(cache_dir):
            makedirs(cache_dir)

        # authenticate with Nest and save the returned session data
        res = requests.post(login_url, {'username': email,
                                        'password': password})
        if res.status_code != 200:
            return False

        session = res.json()
        with open(self._session_file, 'wt') as sfile:
            json.dump(session, sfile, indent=2)
        self._session = session

        return True

    def request(self, method='GET', path='', data=None):
        '''GET from or POST to a user's Nest account.

        This function requires a valid session to exist.
        '''
        # check that we have a valid session
        if not self.has_session:
            raise NotAuthenticated('No session -- login first')

        #from requests.utils import cookiejar_from_dict
        self._requestor = requests.Session()
        self._requestor.mount('https://', TlsAdapter())
        self._requestor.headers.update({
            'User-Agent': user_agent,
            'Authorization': 'Basic ' + self.session['access_token'],
            'X-nl-user-id': self.session['userid'],
            'X-nl-protocol-version': '1',
            'Accept-Language': 'en-us',
            'Connection': 'keep-alive',
            'Accept': '*/*'
        })

        base_url = '{}/v2'.format(self.session['urls']['transport_url'])
        url = '{}/{}'.format(base_url, path)

        if method == 'GET':
            LOG.info('GETting %s', url)
            # don't put headers it a status request
            if not url.endswith('.json'):
                r = self._requestor.get(url)
            else:
                r = requests.get(url)
        elif method == 'POST':
            if not isinstance(data, (str, unicode)):
                # convert data dicts to JSON strings
                data = json.dumps(data)
            r = self._requestor.post(url, data=data)
        else:
            raise Exception('Invalid method "{}"'.format(method))

        if r.status_code != 200:
            raise FailedRequest('Request failed', r)

        return r


if __name__ == '__main__':
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument('property', help='Property to get or set',
                        choices=('ip', 'status', 'temperature', 'humidity',
                                 'target_temperature', 'away', 'leaf',
                                 'weather'))
    parser.add_argument('value', nargs='?', help='Value to set')
    args = parser.parse_args()

    nest = Nest()

    from pprint import pprint
    if hasattr(nest, args.property):
        pprint(getattr(nest, args.property))
    elif args.property in globals():
        globals()[args.property]()

    if args.value:
        print 'Setting {} to {}'.format(args.property, args.value)
        setattr(nest, args.property, args.value)
