#!/usr/bin/env python
# coding=UTF-8

from sys import stdout
import nest as nestlib
import alfred
import os.path
import os


MODES = {
    'heat': {'label': 'Heat', 'desc': 'Heat to a certain temperature'},
    'cool': {'label': 'Cool', 'desc': 'Cool to a certain temperature'},
    'range': {'label': 'Heat/cool', 'desc': 'Heat to a minimum temperature '
              'and cool to a maximum temperature'}
}

show_exceptions = False


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
            btn, email = alfred.get_from_user('Email',
                                              'Nest account email address')
            if btn == 'Cancel':
                nest = None
                break
            btn, password = alfred.get_from_user('Password',
                                                 'Nest account password',
                                                 hidden=True)
            if btn == 'Cancel':
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
    target = nest.target_temperature
    temp = temp.strip()
    temp = temp.strip('"')
    temp = temp.strip("'")

    if nest.mode == 'range' and len(temp) > 0:
        temps = temp.split()
        if len(temps) != 2:
            return [alfred.Item('Waiting for valid input...')]
        for t in temps:
            if len(t) == 1 or len(t) > 2:
                return [alfred.Item('Waiting for valid input...')]

    units = nest.scale.upper()

    if nest.mode == 'range':
        item = alfred.Item(u'Target temperature range is {lo:.1f}°{units} - '
                           u'{hi:.1f}°{units}'.format(lo=target[0],
                                                      hi=target[1],
                                                      units=units))
    else:
        item = alfred.Item(u'Target temperature: {:.1f}°{}'.format(target, units))

    if len(temp) > 0:
        # only need to check for empty temp here since we already validated it
        # above
        item.valid = True
        item.arg = temp

    if nest.mode == 'range':
        item.subtitle = u'Enter a temperature range in °{} to update; ' \
                        u'use format "low high"'.format(units)
    else:
        item.subtitle = u'Enter a temperature in °{} to update'.format(units)

    return [item]


def do_target(nest, temp):
    '''Set the target temperature'''
    temp = temp.strip()
    if ' ' in temp:
        temp = temp.split()
    nest.target_temperature = temp

    if isinstance(temp, list):
        _out(u'Target temperature range is now {lo}°{units} - '
             u'{hi}°{units}'.format(lo=temp[0], hi=temp[1],
                                    units=nest.scale.upper()))
    else:
        _out(u'Target temperature set to {}°{}'.format(temp,
             nest.scale.upper()))


def tell_status(nest, ignore):
    '''Tell the Nest's overall status'''
    temp = nest.temperature
    target = nest.target_temperature
    humidity = nest.humidity
    away = 'yes' if nest.away else 'no'
    fan = nest.fan
    units = nest.scale.upper()
    item = alfred.Item(u'Temperature: {:.1f}°{}'.format(temp, units))

    if nest.mode == 'range':
        target = u'Heat/cool to {l:.1f}°{u} - {h:.1f}°{u}'.format(l=target[0],
                                                                  h=target[1],
                                                                  u=units)
    elif nest.mode == 'heat':
        target = u'Heating to {:.1f}°{}'.format(target, units)
    else:
        target = u'Cooling to {:.1f}°{}'.format(target, units)

    item.subtitle = u'{}    Humidity: {:.1f}%    Fan: {}    Away: {}'.format(
        target, humidity, fan, away)
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

    item = alfred.Item(msg, valid=True, arg=arg, subtitle=subtitle)
    return [item]


def do_fan(nest, mode):
    '''Set the Nest's fan mode'''
    if mode not in ('on', 'auto'):
        raise Exception('Invalid input')

    nest.fan = mode

    if nest.fan == 'auto':
        _out('Fan is in auto mode')
    else:
        _out('Fan is on')


def tell_away(nest, ignore):
    '''Tell the Nest's "away" status'''

    if nest.away:
        msg = "Nest thinks you're away"
        arg = 'off'
    else:
        msg = "Nest thinks you're at home"
        arg = 'on'

    item = alfred.Item(msg, valid=True, arg=arg,
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
        _out('Away mode is enabled')
    else:
        _out('Away mode is disabled')


def tell_weather(nest, ignored):
    '''Tell the current weather and a short forecast'''
    def to_deg_f(temp):
        return (temp / 1.8) + 32

    def new_forecast(title, info):
        tcond = info['conditions'].capitalize()
        thi = info['high_temperature']
        tlo = info['low_temperature']
        item = alfred.Item(u'{}: {}'.format(title, tcond),
                           subtitle=u'High: {:.1f}°F,  Low: {:.1f}°F'.format(
                           thi, tlo))
        return item

    data = nest.weather
    conditions = data['now']['conditions'].capitalize()
    temp = to_deg_f(data['now']['current_temperature'])
    humidity = data['now']['current_humidity']

    items = []

    item = alfred.Item(u'Now: {}'.format(conditions))
    item.subtitle = u'{:.1f}°F,  {:.1f}% humidity'.format(temp, humidity)
    items.append(item)

    items.append(new_forecast('Today', data['forecast']['daily'][0]))
    items.append(new_forecast('Tomorrow', data['forecast']['daily'][1]))

    return items


def tell_mode(nest, query):
    items = []

    for mode in sorted(MODES.keys()):
        title = MODES[mode]['label']
        if mode == nest.mode:
            title += ' (active)'
        items.append(alfred.Item(title, subtitle=MODES[mode]['desc'], arg=mode,
                                 valid=True))

    if len(query.strip()) > 0:
        q = query.strip().lower()
        items = alfred.fuzzy_match(q, items, key=lambda i: i.title.lower())

    return items


def do_mode(nest, mode):
    nest.mode = mode
    label = MODES[mode]['label'].lower()
    _out('Temperature mode set to {}'.format(label))


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
            items = [alfred.Item('Invalid action "{}"'.format(name))]
    except nestlib.FailedRequest, e:
        if show_exceptions:
            import traceback
            traceback.print_exc()
        items = [alfred.Item('Request failed: {}'.format(e.response))]
    except Exception, e:
        if show_exceptions:
            import traceback
            traceback.print_exc()
        items = [alfred.Item('Error: {}'.format(e))]

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
        if show_exceptions:
            import traceback
            traceback.print_exc()
        _out('Request failed: {}'.format(e.response))
    except Exception, e:
        if show_exceptions:
            import traceback
            traceback.print_exc()
        _out('Error: {}'.format(e))


if __name__ == '__main__':
    show_exceptions = True
    from sys import argv
    globals()[argv[1]](*argv[2:])
