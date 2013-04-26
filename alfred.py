#!/usr/bin/python
# coding=UTF-8

import plistlib
import os.path
import uuid

preferences = plistlib.readPlist('info.plist')
bundleid = preferences['bundleid']
cache_dir = os.path.expanduser('~/Library/Caches'
                               '/com.runningwithcrayons.Alfred-2'
                               '/Workflow Data/{}'.format(bundleid))
data_dir = os.path.expanduser('~/Library/Application Support/Alfred 2'
                              '/Workflow Data/{}'.format(bundleid))


class Item(object):
    '''An item in an Alfred feedback XML message'''
    def __init__(self, title, subtitle=None, uid=None, icon=None, valid=False,
                 arg=None):
        self.title = title
        self.subtitle = subtitle
        self.icon = icon if icon is not None else 'icon.png'
        self.uid = uid
        self.valid = valid
        self.arg = arg

    def to_xml(self):
        attrs = []

        if self.uid:
            attrs.append(u'uid="{}-{}"'.format(bundleid, self.uid))
        else:
            attrs.append(u'uid="{}"'.format(uuid.uuid4()))

        if self.valid:
            attrs.append('valid="yes"')
        else:
            attrs.append('valid="no"')

        if self.arg is not None:
            attrs.append(u'arg="{}"'.format(self.arg))

        xml = [u'<item {}>'.format(u' '.join(attrs))]

        xml.append(u'<title>{}</title>'.format(self.title))

        if self.subtitle is not None:
            xml.append(u'<subtitle>{}</subtitle>'.format(self.subtitle))
        if self.icon is not None:
            xml.append(u'<icon>{}</icon>'.format(self.icon))

        xml.append(u'</item>')
        return ''.join(xml)


def fuzzy_match(test, items, key=None):
    '''Return the subset of items that fuzzy match a string [test]'''
    matches = []
    for item in items:
        if key:
            istr = key(item)
        else:
            istr = item

        match = True
        start = 0
        last_i = -1
        for c in test:
            i = istr.find(c, start)
            if i == -1:
                match = False
                break
            last_i = i
            start = i + 1

        if match:
            matches.append(item)
    return matches


def to_xml(items):
    '''Convert a list of Items to an Alfred XML feedback message'''
    msg = [u'<?xml version="1.0"?>', u'<items>']

    for item in items:
        msg.append(item.to_xml())

    msg.append(u'</items>')
    return u''.join(msg)


def get_from_user(title, prompt, hidden=False, value=None, extra_buttons=None):
    '''
    Popup a dialog to request some piece of information.

    The main use for this function is to request information that you don't
    want showing up in Alfred's command history.
    '''
    if value is None:
        value = ''

    buttons = ['Cancel', 'Ok']
    if extra_buttons:
        if isinstance(extra_buttons, (list, tuple)):
            buttons = extra_buttons + buttons
        else:
            buttons.insert(0, extra_buttons)
    buttons = '{{{}}}'.format(', '.join(['"{}"'.format(b) for b in buttons]))

    hidden = 'with hidden answer' if hidden else ''

    script = '''
        on run argv
          tell application "Alfred 2"
              activate
              set alfredPath to (path to application "Alfred 2")
              set alfredIcon to path to resource "appicon.icns" in bundle ¬
                (alfredPath as alias)

              try
                display dialog "{p}:" with title "{t}" default answer "{v}" ¬
                  buttons {b} default button "Ok" with icon alfredIcon {h}
                set answer to (button returned of result) & "|" & ¬
                  (text returned of result)
              on error number -128
                set answer to "Cancel|"
              end
          end tell
        end run'''.format(v=value, p=prompt, t=title, h=hidden, b=buttons)

    from subprocess import Popen, PIPE
    p = Popen(['osascript', '-'], stdin=PIPE, stdout=PIPE, stderr=PIPE)
    stdout, stderr = p.communicate(script)
    return stdout.decode('utf-8').rstrip('\n').split('|')


def show_message(title, message):
    '''Display a message dialog'''
    script = '''
        on run argv
          tell application "Alfred 2"
              activate
              set alfredPath to (path to application "Alfred 2")
              set alfredIcon to path to resource "appicon.icns" in bundle ¬
                (alfredPath as alias)

              display dialog "{m}" with title "{t}" buttons ¬
                {{"Ok"}} default button "Ok" with icon alfredIcon
          end tell
        end run'''.format(t=title, m=message)

    from subprocess import Popen, PIPE
    p = Popen(['osascript', '-'], stdin=PIPE, stdout=PIPE, stderr=PIPE)
    p.communicate(script)


if __name__ == '__main__':
    from sys import argv
    globals()[argv[1]](*argv[2:])
