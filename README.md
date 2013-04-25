[Alfred 2][alfred] Workflow for controlling a [Nest][nest]
==========================================================

<p align="center">
<img alt="Screenshot" src="http://dl.dropbox.com/s/znojcyqezs3amcq/jc-nest_screenshot.png" />
</p>

<p align="center">
  <a href="http://dl.dropbox.com/s/qmu1iyora9h6pr9/jc-nest.alfredworkflow"><img
    src="http://dl.dropbox.com/s/m823ene4il9cnac/dl_button.png" alt="Download"></a>
</p>

This workflow lets you control the basic features of a Nest thermostat. It
provides several commands, accessible via `nest [command]`:

  * `away` - show and toggle away mode
  * `fan` - show and toggle the fan mode
  * `mode` - show and toggle the heat/cool mode (heat, cool, or heat/cool)
  * `status` - show general Nest status
  * `target` - get and set the target temperature or temperature range
  * `weather` - show local weather (according to the Nest servers)

Your location (for weather) and your temperature scale preference are read from
your Nest account.

The first time you run any of the commands you'll be asked for your Nest
account information. This information is only used to authenticate with Nest
and get a session cookie. It isn't stored anywhere permanent, which means
you'll have to re-login once a month. At some point I should probably look into
using the Keychain for longer term storage.

Installation
------------

The easiest way to install the workflow is to download the
[prepackaged workflow][package].  Double-click on the downloaded file, or drag
it into the Alfred Workflows window, and Alfred should install it.

Requirements
------------

The only requirements are:

  * Python 2.7+
  * `requests`

If you have Lion or Mountain Lion, the [prepackaged workflow][package] includes
everything you need.

Credits
-------

I borrowed the idea for using AppleScript dialogs to get login information from 
[gharlan's GitHub workflow][gharlan]. I wasn't terribly happy with my first
implementation, which just had you enter your information in the Alfred command
pane, because there doesn't seem to be a way to keep things out of Alfred's
command history.

[Nokipore's alfred-python][nokipore] package showed me a cleaner way to
structure my Alfred interface code.

[package]: http://dl.dropbox.com/s/qmu1iyora9h6pr9/jc-nest.alfredworkflow
[nest]: http://www.nest.com
[alfred]: http://www.alfredapp.com
[gharlan]: http://github.com/gharlan/alfred-github-workflow
[nokipore]: http://github.com/nikipore/alfred-python
