How to inspect plots
====================

Output files
------------

After the code has run, hdf object files containing the data and plots generated for the inspected parameters/subsystems
are produced, together with a pdf file containing all the generated plots and a log file containing running information. In particular,
the last two files are created for each inspected subsystem (pulser, geds, spms).

.. warning::

  Shelve files are produced as an output as well, this was the first format chosen for the output.
  The code still has to be fixed to remove these files from routines.
  At the moment, they are important when using the ``"saving": "append"`` option, so do not remove them if you are going to use it!

Files are usually collected in the output folder specified in the ``output`` config entry:

.. code-block:: json

  {
  "output": "<output_path>",
  // ...

Then, depending on the chosen dataset (``experiment``, ``period``, ``version``, ``type``, time selection),
different output folders can be created. In general, the output folder is structured as it follows:

.. code-block::

  <output_path>
    └── prod-ref
      └── <version>
        └── generated
          └── plt
            └── <type>
              └── <period>
                └── <time_selection>
                  ├── <experiment>-<period>-<time_selection>-<type>-<subsystem>.pdf
                  ├── <experiment>-<period>-<time_selection>-<type>-<subsystem>.log
                  └── <experiment>-<period>-<time_selection>-<type>.{dat,bak,dir}
                  �~T~T�~T~@�~T~@ <experiment>-<period>-<time_selection>-<hdf


Files are usually saved using the following format ``exp-period-datatype-time_interval``:

- ``experiment`` identifies the experiment (e.g. *l200*);
- ``period`` identifies a certain period of data taking (e.g. *p01*);
- ``time_selection`` can differ depending on the selected time range (see below for more details);
- ``type`` denotes the run type (e.g. *phy*, *cal*, or *cal_phy* if multiple types are selected in a row).

.. note::

  ``time_selection`` can assume one of the following formats, depending on what we put as a time range into ``dataset``:

  - if ``{'start': '20220928T080000Z', 'end': '20220928T093000Z'}`` (start + end), then <time_selection> = ``20220928T080000Z_20220928T093000Z``;
  - if ``{'timestamps': ['20230207T103123Z']}`` (one key), then <time_selection> = ``20230207T103123Z``;
  - if ``{'timestamps': ['20230207T103123Z', '20230207T141123Z', '20230207T083323Z']}`` (multiple keys), then <time_selection> = ``20230207T083323Z_20230207T141123Z`` (min/max timestamp interval)
  - if ``{'runs': 1}`` (one run), then <time_selection> = ``r001``;
  - if ``{'runs': [1, 2, 3]}`` (multiple runs), then <time_selection> = ``r001_r002_r003``.


Output .hdf files
-------------

Output hdf files for ``geds`` have the following dictionary structure, where ``<param>`` is the name of one of the inspected parameters, ``<flag>`` is the event type, e.g. *IsPulser* or *IsBsln*:

- ``<flag>_<param>_info`` = some useful info
- ``<flag>_<param>`` = absolute values
- ``<flag>_<param>_mean`` = average over the first 10% of data (within the selected time window) of ``<flag>_<param>``
- ``<flag>_<param>_var`` = % variations of ``<param>`` wrt ``<flag>_<param>_mean``
- ``<flag>_<param>_pulser01anaRatio`` = ratio of absolute values ``<flag>_<param>`` with PULS01ANA absolute values
- ``<flag>_<param>_pulser01anaRatio_mean`` = average over the first 10% of data (within the selected time window) of ``<flag>_<param>_pulser01anaRatio``
- ``<flag>_<param>_pulser01anaRatio_var`` = % variations of ``<flag>_<param>_pulser01anaRatio`` wrt ``<flag>_<param>_pulser01anaRatio_mean``
- ``<flag>_<param>_pulser01anaDiff`` = difference of absolute values ``<flag>_<param>`` with PULS01ANA absolute values
- ``<flag>_<param>_pulser01anaDiff_mean`` = average over the first 10% of data (within the selected time window) of ``<flag>_<param>_pulser01anaDiff``
- ``<flag>_<param>_pulser01anaDiff_var`` = % variations of ``<flag>_<param>_pulser01anaDiff`` wrt ``<flag>_<param>_pulser01anaDiff_mean``




Inspect plots
-------------

- Some standard plots to monitor detectors' response can be found online on the `Dashboard <https://legend-exp.atlassian.net/wiki/spaces/LEGEND/pages/637861889/Monitoring+Dashboard+Manual>`_
- Some notebooks to interactively inspect plots can be found under the ``notebook`` folder
