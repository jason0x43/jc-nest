#!/usr/bin/env python

from datetime import datetime
from os.path import exists, expanduser, dirname
from os import makedirs
import json
import requests


default_cache_dir = expanduser('~/.nest')
login_url = 'https://home.nest.com/user/login'
user_agent = 'Nest/1.1.0.10 CFNetwork/548.0.4'


class NotAuthenticated(Exception):
    def __init__(self, message):
        super(NotAuthenticated, self).__init__(message)


class Nest(object):
    def __init__(self, cache_dir=None):
        '''Initialize this nest interface'''

        if cache_dir is None:
            cache_dir = default_cache_dir

        self._session_file = '{}/session.json'.format(cache_dir)
        self._cookie_file = '{}/cookies.json'.format(cache_dir)
        self._status = None
        self._nest_session = None

    @property
    def status(self):
        if self._status is None:
            self._status = self._request('GET',
                                         'mobile/user.{}'.format(self.user_id))
        return self._status

    @property
    def structure_id(self):
        return self.status['user'][self.user_id]['structures'][0].split('.')[1]

    @property
    def device_id(self):
        return self.status['structure'][self.structure_id]['devices'][
            0].split('.')[1]

    @property
    def location(self):
        return self.status['structure'][self.structure_id]['postal_code']

    @property
    def scale(self):
        return self.status['device'][self.device_id]['temperature_scale']

    @property
    def user_id(self):
        return self.nest_session['userid']

    @property
    def ip(self):
        return self.status['metadata'][self.device_id]['last_ip']

    @property
    def humidity(self):
        return self.status['device'][self.device_id]['current_humidity']

    @property
    def mode(self):
        return self.status['device'][self.device_id]['current_schedule_mode']

    @property
    def temperature(self):
        temp = self.status['shared'][self.device_id]['current_temperature']
        if self.scale == 'F':
            temp = (temp * 1.8) + 32
        return temp

    @property
    def leaf(self):
        return self.status['device'][self.device_id]['leaf']

    @property
    def weather(self):
        r = requests.get('https://home.nest.com/api/0.1/weather/forecast/'
                         '{}'.format(self.location))
        return r.json()

    # away ###############################

    def _get_away(self):
        return self.status['structure'][self.structure_id]['away']

    def _set_away(self, value):
        from time import time
        value = bool(value)
        data = {
            'away_timestamp': int(time()),
            'away': value,
            'away_setter': 0
        }
        self._request('POST', 'put/structure.{}'.format(self.structure_id),
                      data=data, expect_response=False)

    away = property(_get_away, _set_away)

    # target temp ########################

    def _get_target_temperature(self):
        temp = self.status['shared'][self.device_id]['target_temperature']
        if self.scale == 'F':
            temp = (temp * 1.8) + 32
        return temp

    def _set_target_temperature(self, temp):
        temp = float(temp)
        if self.scale == 'F':
            temp = (temp - 32) / 1.8
        data = {
            'target_change_pending': True,
            'target_temperature': temp
        }
        self._request('POST', 'put/shared.{}'.format(self.device_id),
                      data=data, expect_response=False)

    target_temperature = property(_get_target_temperature,
                                  _set_target_temperature)

    ######################################

    @property
    def nest_session(self):
        if self._nest_session is None:
            raise NotAuthenticated('No session available -- login first')
        return self._nest_session

    @property
    def has_session(self):
        if not exists(self._session_file) or not exists(self._cookie_file):
            return False

        try:
            with open(self._session_file, 'rt') as sfile:
                self._nest_session = json.load(sfile)
                expiry = datetime.strptime(self.nest_session['expires_in'],
                                           '%a, %d-%b-%Y %H:%M:%S GMT')
                if datetime.utcnow() <= expiry:
                    with open(self._cookie_file, 'rt') as cfile:
                        cookies = json.load(cfile)
                        if len(cookies) > 0:
                            return True
        except Exception:
            pass

        return False

    def login(self, email, password):
        '''Login to the user's Nest account'''

        # make the cache dir if it doesn't exist
        cache_dir = dirname(self._session_file)
        if not exists(cache_dir):
            makedirs(cache_dir)

        # authenticate with Nest and save the returned session data
        from requests.utils import dict_from_cookiejar
        res = requests.post(login_url, {'username': email,
                                        'password': password})
        if res.status_code != 200:
            return False

        session = res.json()
        cookies = dict_from_cookiejar(res.cookies)
        with open(self._session_file, 'wt') as sfile:
            json.dump(session, sfile)
        with open(self._cookie_file, 'wt') as cfile:
            json.dump(cookies, cfile)
        self._nest_session = res.json()

        return True

    def _request(self, method='GET', path='', data=None, expect_response=True):
        '''
        GET from or POST to a user's Nest account

        This function requires a valid session to exist.
        '''
        # check that we have a valid session
        if not self.has_session:
            raise NotAuthenticated('No session -- login first')

        from requests.utils import cookiejar_from_dict
        self._session = requests.Session()
        self._session.headers.update({
            'User-Agent': user_agent,
            'Authorization': 'Basic ' + self.nest_session['access_token'],
            'X-nl-user-id': self.nest_session['userid'],
            'X-nl-protocol-version': '1',
            'Accept-Language': 'en-us',
            'Connection': 'keep-alive',
            'Accept': '*/*'
        })

        with open(self._cookie_file, 'rt') as cfile:
            cookies = json.load(cfile)
            self._session.cookies = cookiejar_from_dict(cookies)

        base_url = '{}/v2'.format(self.nest_session['urls']['transport_url'])
        url = '{}/{}'.format(base_url, path)

        if method == 'GET':
            # don't put headers it a status request
            if not url.endswith('.json'):
                r = self._session.get(url)
            else:
                r = requests.get(url)
        elif method == 'POST':
            if not isinstance(data, (str, unicode)):
                data = json.dumps(data)
            r = self._session.post(url, data=data)
        elif method == 'DELETE':
            r = self._session.delete(url)
        else:
            raise Exception('Invalid method "{}"'.format(method))

        if expect_response:
            return r.json()


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
