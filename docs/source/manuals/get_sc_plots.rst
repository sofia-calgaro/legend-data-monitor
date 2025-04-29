How to load and plot Slow Control data
======================================

How to load SC data
-------------------

A number of parameters related to the LEGEND hardware configuration and status are recorded in the Slow Control (SC) database.
The latter, PostgreSQL database resides on the ``legend-sc.lngs.infn.it`` host, part of the LNGS network.
To access the SC database, follow the `Confluence (Python Software Stack) <https://legend-exp.atlassian.net/wiki/spaces/LEGEND/pages/494764033/Python+Software+Stack>`_ instructions.
Data are loaded following the `pylegendmeta <https://github.com/legend-exp/pylegendmeta>`_ tutorial, which shows how to retrieve info from the SC database.


Available SC parameters
-----------------------

Available parameters at the moment include:

* ``PT114``, ``PT115``, ``PT118`` (cryostat pressures)
* ``PT202``, ``PT205``, ``PT208`` (cryostat vacuum)
* ``LT01`` (water loop fine fill level)
* ``RREiT`` (injected air temperature clean room), ``RRNTe`` (clean room temperature north), ``RRSTe`` (clean room temperature south), ``ZUL_T_RR`` (supply air temperature clean room)
* ``DaqLeft-Temp1``, ``DaqLeft-Temp2``, ``DaqRight-Temp1``, ``DaqRight-Temp2`` (rack present temperatures)
* if you want more, contact us!

These can be easily access for any time range of interest by giving a my_config.json file as input to the command line in the following way:

.. code-block::

  legend-data-monitor user_scdb --config my_config --port N --pswd ThePassword

.. note::

  - ``N`` is whatever number in the range 1024-65535. Setting a personal port different from the default one (5432) is a safer option, otherwise if a port is already in use by another user, you'll receive an error indicating that the port is already taken and you will not be able to access the SC database;
  - ``ThePassword`` can be found on Confluence at `this page <https://legend-exp.atlassian.net/wiki/spaces/LEGEND/pages/494764033/Python+Software+Stack#Metadata-access>`_.

An example of a config.json file is the following:

.. code-block:: json

  {
  "output": "/data1/users/<your_username>/prod-ref-v2",
  "dataset": {
    "experiment": "L200",
    "period": "p09",
    "version": "tmp-auto",
    "path": "/data2/public/prodenv/prod-blind/",
    "type": "phy",
    "time_selection": ...
    },
  "saving": "overwrite",
  "slow_control": {
    "parameters": ["DaqLeft-Temp1", "ZUL_T_RR"]
    }
  }

The meaning of each entry is explained below:

* ``output``: foldeer where to store output files;
* ``dataset``:

    * ``experiment``: either *L60* (to be checked) or *L200*
    * ``period``: period to inspect
    * ``version``: prodenv version (eg *tmp-auto* or *ref-v1.0.0*)
    * ``path``: global path to prod-blind prodenv folder
    * ``type``: type of data to inspect (either *cal* or *phy*)
    *  ``time selection``: list of either ``runs`` or ``timestamps`` (use the format *YMDTHMSZ*), or add entries ``start`` and ``end`` with format *Y-M-D H:M:S* (see below for more detailed info)

* ``saving``: either *overwrite* (overwrites any already present file) or *append* (takes the previous file and append new data, eg for a new inspected time range)
* ``slow_control``: filed for specifying SC parameters

    * ``parameters``: list of parameters to inspect (see among the available ones what you can choose)


In principle, for plotting the SC data you would need just the start and the end of a time interval of interest. This means that SC data does not depend on any dataset info (i.e. on entries ``experiment``, ``period``, ``version``, ``type``).
However, these entries are important to retrieve any channel map of interest for the given time range of interest.

We store SC data in the following way:

.. code-block::

  <output>
    └── generated
      └── plt
        └── <type>
          └── <period>
              └── <time_selection>
                ├── SC-<time_selection>.hdf
                └── SC-<time_selection>.{dat,bak,dir}


.. note::

  ``time_selection`` can assume one of the following formats, depending on what we put as a time range into ``dataset``:

  - if ``{'start': '20220928T080000Z', 'end': '20220928T093000Z'}`` (start + end), then <time_selection> = ``20220928T080000Z_20220928T093000Z``;
  - if ``{'timestamps': ['20230207T103123Z']}`` (one key), then <time_selection> = ``20230207T103123Z``;
  - if ``{'timestamps': ['20230207T103123Z', '20230207T141123Z', '20230207T083323Z']}`` (multiple keys), then <time_selection> = ``20230207T083323Z_20230207T141123Z`` (min/max timestamp interval)
  - if ``{'runs': 1}`` (one run), then <time_selection> = ``r001``;
  - if ``{'runs': [1, 2, 3]}`` (multiple runs), then <time_selection> = ``r001_r002_r003``.
