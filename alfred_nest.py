#!/usr/bin/env python
# coding=UTF-8

from sys import stdout
import nest as nestlib
import alfred
import os.path
import os


def _out(msg):
    '''Output a string'''
    stdout.write(msg.encode('utf-8'))


def _get_nest():
    '''Get an authenticated Nest object'''
    if not os.path.isdir(alfred.cache_dir):
        os.mkdir(alfred.cache_dir)
        if not os.access(alfred.cache_dir, os.W_OK):
            raise IOError('No write access to dir: %s' % alfred.cache_dir)
    nest = nestlib.Nest(cache_dir=alfred.cache_dir)

    if not nest.has_session:
        alfred.show_message('First things first...', 'Before you can use this '
                            'workflow you need to supply your Nest account '
                            "email and password. This information isn't "
                            'stored anywhere (only a session cookie is '
                            "saved), so you'll periodically have to login "
                            'again.')

        while True:
            email = alfred.get_from_user('Email', 'Nest account email address')
            if len(email) == 0:
                nest = None
                break
            password = alfred.get_from_user('Password',
                                            'Nest account password',
                                            hidden=True)
            if len(password) == 0:
                nest = None
                break

            if nest.login(email, password):
                alfred.show_message('Success!',
                                    "You're logged in an ready to go!")
                break
            else:
                alfred.show_message('Login failed',
                                    'Either the Nest service is temporarily '
                                    'down or your email and password were '
                                    'incorrect. Click OK to try again.')

    return nest


def tell_target(nest, temp):
    '''Tell the target temperature'''
    if len(temp) == 1 or len(temp) > 2:
        return [alfred.Item('target', 'Waiting for valid input...')]

    target = nest.target_temperature
    units = nest.scale.upper()
    item = alfred.Item('target', u'Target temperature: {:.1f}°{}'.format(
                       target, units))

    if len(temp) == 2:
        item.valid = True
        item.arg = temp

    if len(temp) == 2:
        item.subtitle = u'Press Enter to update'
    else:
        item.subtitle = u'Enter a temperature in °{} to update'.format(units)

    return [item]


def do_target(nest, temp):
    '''Set the target temperature'''
    temp = float(temp)
    nest.target_temperature = temp
    _out(u'Target temperature set to {:.1f}°{}'.format(
         temp, nest.scale.upper()))


def tell_status(nest, ignore):
    '''Tell the Nest's overall status'''
    temp = nest.temperature
    target = nest.target_temperature
    humidity = nest.humidity
    away = 'yes' if nest.away else 'no'
    fan = nest.fan
    mode = nest.mode.lower()
    units = nest.scale.upper()
    item = alfred.Item('status', u'Temperature: {:.1f}°{}'.format(temp,
                       units))

    item.subtitle = u'Target: {:.1f}°{}    Humidity: {:.1f}%    ' \
                    'Mode: {}    Fan: {}    Away: {}'.format(target, units,
                                                             humidity,
                                                             mode, fan, away)
    return [item]


def tell_fan(nest, ignore):
    '''Tell the Nest's fan mode'''

    subtitle = 'Press enter to switch '

    if nest.fan == 'auto':
        msg = 'Fan is in auto mode'
        subtitle += 'on'
        arg = 'on'
    else:
        msg = 'Fan is on'
        subtitle += 'to auto mode'
        arg = 'auto'

    item = alfred.Item('fan', msg, valid=True, arg=arg, subtitle=subtitle)
    return [item]


def do_fan(nest, mode):
    '''Set the Nest's fan mode'''
    if mode not in ('on', 'auto'):
        raise Exception('Invalid input')

    nest.fan = mode

    if nest.fan == 'auto':
        print 'Fan is in auto mode'
    else:
        print 'Fan is on'


def tell_away(nest, ignore):
    '''Tell the Nest's "away" status'''

    if nest.away:
        msg = "Nest thinks you're away"
        arg = 'off'
    else:
        msg = "Nest thinks you're at home"
        arg = 'on'

    item = alfred.Item('away', msg, valid=True, arg=arg,
                       subtitle='Press enter to toggle')
    return [item]


def do_away(nest, val):
    '''Set the Nest's "away" status'''
    away = None

    if val:
        val = val.lower()
        if val in ('on', 'yes', 'true', '1'):
            val = True
        elif val in ('off', 'no', 'false', '0'):
            val = False
        else:
            raise Exception('Invalid input')

        nest.away = val
        away = val
    else:
        away = nest.away

    if away:
        print 'Away mode is enabled'
    else:
        print 'Away mode is disabled'


def tell_weather(nest, ignored):
    '''Tell the current weather and a short forecast'''
    def to_deg_f(temp):
        return (temp / 1.8) + 32

    def new_forecast(title, info):
        tcond = info['conditions']
        thi = info['high_temperature']
        tlo = info['low_temperature']
        item = alfred.Item('weather{}'.format(info['date']), title)
        item.subtitle = u'{}, High: {:.1f}°F, Low: {:.1f}°F'.format(
            tcond, thi, tlo)
        return item

    data = nest.weather
    conditions = data['now']['conditions']
    temp = to_deg_f(data['now']['current_temperature'])
    humidity = data['now']['current_humidity']

    items = []

    item = alfred.Item('weather0', 'Now')
    item.subtitle = u'{}, {:.1f}°F, {:.1f}% humidity'.format(
        conditions, temp, humidity)
    items.append(item)

    items.append(new_forecast('Today', data['forecast']['daily'][0]))
    items.append(new_forecast('Tomorrow', data['forecast']['daily'][1]))

    return items


def tell(name, query=''):
    '''Tell something'''
    try:
        cmd = 'tell_{}'.format(name)
        if cmd in globals():
            nest = _get_nest()
            if nest is None:
                return
            items = globals()[cmd](nest, query)
        else:
            items = [alfred.Item('tell', 'Invalid action "{}"'.format(name))]
    except nestlib.FailedRequest, e:
        items = [alfred.Item(None, 'Request failed: {}'.format(e.response))]
    except Exception, e:
        items = [alfred.Item(None, 'Error: {}'.format(e))]

    _out(alfred.to_xml(items))


def do(name, query=''):
    '''Do something'''
    try:
        cmd = 'do_{}'.format(name)
        if cmd in globals():
            nest = _get_nest()
            if nest is None:
                return
            globals()[cmd](nest, query)
        else:
            _out('Invalid command "{}"'.format(name))
    except nestlib.FailedRequest, e:
        _out('Request failed: {}'.format(e.response))
    except Exception, e:
        _out('Error: {}'.format(e))


if __name__ == '__main__':
    tell('fan')
