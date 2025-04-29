How to produce plots
====================

How to run legend-data-monitor
------------------------------
After the installation, a executable is available at ``~/.local/bin``.
To automatically generate plots, two different methods are available.
All methods rely on the existence of a config file containing the output folder (``output``)
where to store results, the ``dataset`` you want to inspect, and the ``subsystems`` (pulser, geds, spms)
you want to study and for which you want to load data. See next section for more details.

You can either run the code by importing the ``legend-data-monitor`` module:

.. code-block:: python

  import legend-data-monitor as ldm
  user_config = path_to_config.json
  ldm.control_plots(user_config)

Or run it by parsing to the executable the path to the config file:

.. code-block:: bash

  $ legend-data-monitor user_prod --config path_to_config.json

If you want to inspect bunches of data (useful to avoid the process to get killed
when loading lots of heavy files), you can use

.. code-block:: bash

  $ legend-data-monitor user_bunch --config path_to_config.json --n_files N

where ``N`` specifies how many files you want to inspect together at each iteration e.g. ``N=40``
(one run is usually made up of ca. 160 files).


.. warning::

  Use the ``user_prod`` command line interface for generating your own plots.
  ``auto_prod`` and ``user_rsync_prod`` were designed to be used during automatic data production, for generating monitoring plots on the fly for new processed data. For the moment, no documentation will be provided.


Configuration file
------------------
In the following, we describe the structure of the configuration file in detail.


Example config
~~~~~~~~~~~~~~
.. code-block:: json

 {
  "output": "<output_path>", // output folder
  "dataset": {
    "experiment": "L200",
    "period": "p09",
    "version": "tmp-auto",
    "path": "/data2/public/prodenv/prod-blind/",
    "type": "phy",// data type (either cal, phy, or ["cal", "phy"])
    "start": "2023-02-07 02:00:00",  // time cut (here based on start+end)
    "end": "2023-02-07 03:30:00"
  },
  "subsystems": {
    "geds": { // type of subsystem to plot (geds, spms, pulser)
      "Baselines in pulser events": {
        "parameters": "baseline",
        "event_type": "pulser",
        "plot_structure": "per channel",
        "plot_style": "vs time",
        "variation": true,
        "resampled": "also",
        "time_window": "1H",
        "status": true
        }
      }
    }
  }

The argument ``output`` is the path to where plots and inspected data will be saved. Will create subfolders in given path for different outputs. Will be created if does not exist.

In particular, ``dataset`` settings are:

- ``experiment``: experiment, in uppercase (``L60`` or ``L200``);
- ``period``: format ``pXX``. Note: not needed for ``DataLoader`` as it finds period by itself based on provided selection (see below), only used in output filename;
- ``version``: version of production cycle, format ``vXX.YY``. Note: needed for ``DataLoader`` to look in the desired path;
- ``path``: path to ``prod-ref`` folder;
- ``type``: type of data, physics (``phy``) or calibration (``cal``). Possible to use one or both to make one dataset (``["phy", "cal"]``);
- ``selection``: time window to select data;

.. note::

  Time selection is based on:

  - ``'start': '2023-02-07 02:00:00', 'end': '2023-02-07 03:30:00'`` (start + end) in format ``YYYY-MM-DD hh:mm:ss``;
  - ``'timestamps': ['20230207T103123Z', '20230207T141123Z', ...]`` (list of keys) in format ``YYYYMMDDThhmmssZ``;
  - ``'window': '1d 2h 0m'`` ( time window in the past from current time point) in format ``Xd Xh Xm`` for days, hours, minutes;
  - ``'runs': 1`` (one run) or ``'runs': [1, 2, 3]`` (list of runs) in integer format.


Then, ``subsystems`` can either be ``pulser``, ``geds`` or ``spms`` (note: spms plots are not implemented yet, but DataLoader can load the respective data if needed).

For each subsystem to be plotted, specify

- ``"<some title>"``: the title of the plot you want to generate. eg. "Baselines in pulser events"
- ``parameters``: one or multiple parameters of interest to be plotted for this subsystem. In addition to any parameter present in ``lh5``, the following special parameters are implemented (see provided examples below for more details on how to select these parameters):
    - ``"K_lines"``: events whose energy is contained within 1430 and 1575 keV (40K and 42K regions)
    - ``"FWHM"``: FWHM values for each channel
    - ``"wf_max_rel"``: relative difference between ``wf_max`` and baseline
    - ``"event_rate"``: event rate calculated in windows specified in the field ``"sampling"`` under ``plotting.parameters``.
- ``"event_type"``: which events to plot. Choose among ``pulser``  (events flagged as pulser based on AUX channel), ``phy`` (physical, i.e. non-pulser events), or ``all``.
- ``"plot_structure"``: plot arrangement. Choose among
    - ``per channel`` (pulser, geds): group plots by channel (ie each channel has its own AxesSubplot)
    - ``per cc4`` (geds): group plots by CC4 (ie all channels belonging to the same CC4 are in the same AxesSubplot)
    - ``per string`` (geds): group plots by string (ie all channels belonging to the same string are in the same AxesSubplot)
    - ``array`` (geds): group all channels in the same AxesSubplot
    - ``per fiber`` (spms): group channels separating them into IB and OB, and put top/bottom channels of a given fiber together to look for correlations within the fiber and among neighbouring fibers
    - ``per barrel`` (spms): group channels separating them into top/bottom IB/OB
- ``"plot_style"``: plot style. Choose among
    - ``vs time``: plot parameter VS time, as well as resampled values in window given in plot settings (see ``time_window``)
    - ``vs ch``: plot parameter VS channel ID
    - ``histogram``: plot distribution of given parameter
    - ``scatter``: plot all entries of a parameter with points
    - ``heatmap``: plot 2d histos, with time on x axis
- ``"variation"``: set it to ``True`` if you want % variation instead of absolute values for your parameter. Percentage variations are evaluated as: ``(param/mean - 1)*100``, where ``mean`` is the mean of the parameter under study evaluated over the first 10% of the time interval you specified in the ``dataset`` entry
- ``"resampled"``: set it to ``"also"`` if you want to plot resampled values for the parameter under study. Resampling is done using the ``"time_window"`` you specify. Possible values are:
    - ``"none"``: do not plot resampled values, i.e. events for each saved timestamps
    - ``"only"``: plot resampled values, i.e. averaged events over each saved timestamps (average window equal to ``"time_window"``)
    - ``"also"``: plot both resampled and not resampled values
- ``"time_window"``: resampling time (``T``=minutes, ``H``=hours, ``D``=days) used to print resampled values (useful to spot trends over time)
- ``"status"``: set it to ``True`` if you want to generate a status map for the subsystem and parameter under study (note, 2023-03-07: this works only for geds). In order to work, you first need to specify the limits you want to set as a either low or high threshold (or both) for the parameter under study by adding the % or absolute threshoold for the subsystem of interest in ``settings/par-setting.json``.

.. warning::

  There is no event type selection ready for calibration data.
  This means you always have to use ``"event_type": "all"`` as long as the different event selections are not properly implemented for calibration data too.

..
    "variation": Only implemented for ``"per_channel"`` plot style. Currently required even if the plot style is not ``"per_channel"``, will be fixed in the future.

More that one subsystem can be entered, for instance:

.. code-block:: json

  "subsystems": {
    "pulser": {
      "Pulser event rate": {
        "parameters": "event_rate",
        "event_type": "pulser",
        "plot_structure": "per channel",
        "plot_style": "vs time",
        "variation": false,
        "time_window": "1H"
      },
      "AUX channel waveform maximum": {
        "parameters": "wf_max",
        "event_type": "all",
        "plot_structure": "per channel",
        "plot_style": "histogram",
        "variation": false
      }
    },
    "geds": {
      "Baselines in pulser events": {
        "parameters": "baseline",
        "event_type": "pulser",
        "plot_structure": "per channel",
        "plot_style": "vs time",
        "variation": true,
        "time_window": "1H"
      }
    }

..
  More examples can be found under ``examples/`` folder present in the Github repository.



Special parameters
------------------
More attention must be paid to the following special parameters, for which a particular ``subsystem`` entry is required.

K lines
~~~~~~~
To plot events having energies within 1430 and 1575 keV (ie, around the 40K and 42K area), grouping channels by string and selecting phy (=not-pulser) events, use

.. code-block:: json

    "subsystems": {
      "geds": {
          "K events":{
              "parameters": "K_events",
              "event_type": "K_lines",
              "plot_structure": "per string",
              "plot_style" : "scatter"
        }
      }
    }

FWHM
~~~~
To plot FWHM values for each channel, grouping them by strings, selecting only pulser events, use

.. code-block:: json

    "subsystems": {
        "geds": {
          "FWHM in pulser events":{
              "parameters": "FWHM",
              "event_type": "pulser",
              "plot_structure": "array",
              "plot_style" : "vs ch"
          }
        }
    }

Relative maximum of the waveform
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
To plot the relative difference between ``wf_max`` and ``baseline``, use

.. code-block:: json

    "subsystems": {
        "pulser": {
            "Relative wf_max": {
                "parameters": "wf_max_rel",
                "event_type": "pulser", // or phy, all, ...
                "plot_structure": "per channel",
                "plot_style": "vs time",
                "variation": true, // optional
                "time_window": "5T"
            }
        }
    }

Event rate
~~~~~~~~~~
To plot the event rate, by sampling over a period of time equal to ``<time_window>`` (T=minutes, H=hours, D=days), use:

.. code-block:: json

    "subsystems": {
        "geds": {
            "Event rate": {
                "parameters": "event_rate",
                "event_type": "pulser",
                "plot_structure": "per channel",
                "plot_style": "vs time",
                "resampled": "no",
                "variation": false,
                "time_window": "5T"
            }
        }
    }
