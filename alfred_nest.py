#!/usr/bin/env python
# coding=UTF-8

import nest as nestlib
import logging
from jcalfred import Workflow, Item, Keychain


LOG = logging.getLogger(__name__)

MODES = {
    'heat': {'label': 'Heat', 'desc': 'Heat to a certain temperature'},
    'cool': {'label': 'Cool', 'desc': 'Cool to a certain temperature'},
    'range': {'label': 'Heat/cool', 'desc': 'Heat to a minimum temperature '
              'and cool to a maximum temperature'}
}


class NestWorkflow(Workflow):
    def __init__(self, *args, **kw):
        super(NestWorkflow, self).__init__(*args, **kw)
        self.keychain = Keychain('jc-nest')
        self.account = self._get_account()
        self.nest = None

        LOG.warn('nests: %s', self.account.nests)

        if 'nest' in self.config:
            LOG.debug('using saved nest id %s', self.config['nest'])
            self.nest = self.account.nests[self.config['nest']]
        else:
            LOG.debug('using first nest id')
            self.nest = self.account.nests.values()[0]
            self.config['nest'] = self.nest.id

    def _get_account(self):
        '''Get an authenticated Nest object'''
        LOG.debug('getting Nest')

        account = nestlib.Account(cache_dir=self.cache_dir)

        if not account.has_session:
            entry = self.keychain.get_password('nest')

            if not entry:
                self.show_message(
                    'First things first...',
                    'Before you can use this workflow you need to supply your '
                    "Nest account email and password. This information will "
                    'be stored in your login keychain.')

            while True:
                if entry:
                    email = entry['comment']
                    password = entry['password']
                else:
                    btn, email = self.get_from_user(
                        'Email', 'Nest account email address')
                    if btn == 'Cancel':
                        account = None
                        break
                    btn, password = self.get_from_user(
                        'Password', 'Nest account password', hidden=True)
                    if btn == 'Cancel':
                        account = None
                        break

                if account.login(email, password):
                    if not entry:
                        self.show_message('Success!',
                                          "You're logged in an ready to go!")
                        self.keychain.set_password('nest', password,
                                                   comment=email)
                    break
                else:
                    entry = None
                    self.show_message('Error logging in',
                                      'Either the Nest service is temporarily '
                                      'down or your email and password were '
                                      'incorrect. Click OK to re-enter your '
                                      'login information.')

        return account

    def do_debug(self, ignored):
        '''Opent the debug log file'''
        LOG.debug('opening log file %s', self.log_file)
        import os
        os.system('open "{0}"'.format(self.log_file))

    def tell_nest(self, query):
        '''Display the available Nests'''
        LOG.debug('listing Nests')

        items = []
        for nest in self.account.nests.values():
            title = unicode(nest.name)
            if nest.id == self.nest.id:
                title += u' (active)'
            subtitle = u'ID: {0}    Location: {1}'.format(nest.id,
                                                          nest.structure.name)
            items.append(Item(title, subtitle=subtitle, arg=nest.id,
                              valid=True))

        if len(query.strip()) > 0:
            q = query.strip().lower()
            items = self.fuzzy_match(q, items, key=lambda i: i.title.lower())

        return items

    def do_nest(self, nest_id):
        '''Select the active Nest'''
        LOG.debug('selecting Nest')
        self.nest = self.account.nests[nest_id]
        self.config['nest'] = nest_id
        self.puts(u'Set active Nest to "{0}" ({1})'.format(self.nest.name,
                                                           nest_id))

    def tell_target(self, temp):
        '''Tell the target temperature'''
        LOG.debug('telling target temperature')

        target = self.nest.target_temperature
        temp = temp.strip()
        temp = temp.strip('"')
        temp = temp.strip("'")
        units = self.nest.scale.upper()

        if temp:
            if self.nest.mode == 'range':
                temps = temp.split()
                if len(temps) != 2:
                    return [Item('Waiting for valid input...')]
                for t in temps:
                    if len(t) == 1 or len(t) > 2:
                        return [Item('Waiting for valid input...')]
                return [Item(u'Set temperature range to %.1f°%s - %.1f°%s' % (
                             float(temps[0]), units, float(temps[1]), units),
                             arg=temp, valid=True)]
            else:
                return [Item(u'Set temperature to %.1f°%s' % (float(temp),
                        units), arg=temp, valid=True)]
        else:
            if self.nest.mode == 'range':
                item = Item(
                    u'Target temperature range is %.1f°%s - '
                    u'%.1f°%s' % (target[0], units, target[1], units))
            else:
                item = Item(
                    u'Target temperature: %.1f°%s' % (target, units))

        if self.nest.mode == 'range':
            item.subtitle = (u'Enter a temperature range in °%s to update; '
                             u'use format "low high"' % units)
        else:
            item.subtitle = u'Enter a temperature in °%s to update' % units

        return [item]

    def do_target(self, temp):
        '''Set the target temperature'''
        LOG.debug('doing target temperature')

        temp = temp.strip()
        if ' ' in temp:
            temp = temp.split()
        self.nest.target_temperature = temp
        units = self.nest.scale.upper()

        if isinstance(temp, list):
            self.puts(u'Target temperature range is now %s°%s - '
                      u'%s°%s' % (temp[0], units, temp[1], units))
        else:
            self.puts(u'Target temperature set to %s°%s' % (temp, units))

    def tell_status(self, ignore):
        '''Tell the Nest's overall status'''
        LOG.debug('telling status')

        temp = self.nest.temperature
        target = self.nest.target_temperature
        humidity = self.nest.humidity
        away = 'yes' if self.nest.structure.away else 'no'
        fan = self.nest.fan
        units = self.nest.scale.upper()
        item = Item(u'Temperature: %.1f°%s' % (temp, units))

        if self.nest.mode == 'range':
            target = u'Heat/cool to %.1f°%s - %.1f°%s' % (
                target[0], units, target[1], units)
        elif self.nest.mode == 'heat':
            target = u'Heating to %.1f°%s' % (target, units)
        else:
            target = u'Cooling to %.1f°%s' % (target, units)

        item.subtitle = u'%s    Humidity: %.1f%%    Fan: %s    Away: %s' % (
            target, humidity, fan, away)
        return [item]

    def tell_fan(self, ignore):
        '''Tell the Nest's fan mode'''
        LOG.debug('telling fan')

        subtitle = 'Press enter to switch '

        if self.nest.fan == 'auto':
            msg = 'Fan is in auto mode'
            subtitle += 'on'
            arg = 'on'
        else:
            msg = 'Fan is on'
            subtitle += 'to auto mode'
            arg = 'auto'

        item = Item(msg, valid=True, arg=arg, subtitle=subtitle)
        return [item]

    def do_fan(self, mode):
        '''Set the Nest's fan mode'''
        LOG.debug('doing fan')

        if mode not in ('on', 'auto'):
            raise Exception('Invalid input')

        self.nest.fan = mode

        if self.nest.fan == 'auto':
            self.puts('Fan is in auto mode')
        else:
            self.puts('Fan is on')

    def tell_away(self, ignore):
        '''Tell the Nest's "away" status'''
        LOG.debug('telling away')

        if self.nest.structure.away:
            msg = "Nest thinks you're away"
            arg = 'off'
        else:
            msg = "Nest thinks you're at home"
            arg = 'on'

        item = Item(msg, valid=True, arg=arg,
                    subtitle='Press enter to toggle')
        return [item]

    def do_away(self, val):
        '''Set the Nest's "away" status'''
        LOG.debug('doing away')

        away = None

        if val:
            val = val.lower()
            if val in ('on', 'yes', 'true', '1'):
                val = True
            elif val in ('off', 'no', 'false', '0'):
                val = False
            else:
                raise Exception('Invalid input')

            self.nest.structure.away = val
            away = val
        else:
            away = self.nest.structure.away

        if away:
            self.puts('Away mode is enabled')
        else:
            self.puts('Away mode is disabled')

    def tell_weather(self, ignored):
        '''Tell the current weather and a short forecast'''
        LOG.debug('telling weather')

        def to_deg_f(temp):
            return (temp / 1.8) + 32

        def new_forecast(title, info):
            tcond = info['conditions'].capitalize()
            thi = info['high_temperature']
            tlo = info['low_temperature']
            item = Item(u'%s: %s' % (title, tcond),
                        subtitle=u'High: %.1f°F,  Low: %.1f°F' % (
                        thi, tlo))
            return item

        data = self.nest.structure.weather
        conditions = data['now']['conditions'].capitalize()
        temp = to_deg_f(data['now']['current_temperature'])
        humidity = data['now']['current_humidity']

        items = []

        item = Item(u'Now: %s' % conditions)
        item.subtitle = u'%.1f°F,  %.1f%% humidity' % (temp, humidity)
        items.append(item)

        items.append(new_forecast('Today', data['forecast']['daily'][0]))
        items.append(new_forecast('Tomorrow', data['forecast']['daily'][1]))

        return items

    def tell_mode(self, query):
        LOG.debug('telling mode')
        items = []

        for mode in sorted(MODES.keys()):
            title = MODES[mode]['label']
            if mode == self.nest.mode:
                title += ' (active)'
            items.append(Item(title, subtitle=MODES[mode]['desc'],
                         arg=mode, valid=True))

        if len(query.strip()) > 0:
            q = query.strip().lower()
            items = self.fuzzy_match(q, items, key=lambda i: i.title.lower())

        return items

    def do_mode(self, mode):
        LOG.debug('getting mode')
        self.nest.mode = mode
        label = MODES[mode]['label'].lower()
        self.puts('Temperature mode set to %s' % label)


if __name__ == '__main__':
    from sys import argv
    getattr(NestWorkflow(), argv[1])(*argv[2:])
