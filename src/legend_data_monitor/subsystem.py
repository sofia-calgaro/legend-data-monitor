import os
import typing
from datetime import datetime

import numpy as np
import pandas as pd
from legendmeta import LegendMetadata
from pygama.flow import DataLoader

from . import utils

LEGEND_META = LegendMetadata()

list_of_str = list[str]
tuple_of_str = tuple[str]


class Subsystem:
    """
    Object containing information for a given subsystem such as channel map, channels status etc.

    sub_type [str]: geds | spms | pulser

    Options for kwargs

    dataset=
        dict with the following keys:
            - 'experiment' [str]: 'L60' or 'L200'
            - 'path' [str]: < move description here from get_data() >
            - 'version' [str]: < move description here from get_data() >
            - 'type' [str]: 'phy' or 'cal'
            - the following key(s) depending in time selection
                1) 'start' : <start datetime>, 'end': <end datetime> where <datetime> input is of format 'YYYY-MM-DD hh:mm:ss'
                2) 'window'[str]: time window in the past from current time point, format: 'Xd Xh Xm' for days, hours, minutes
                2) 'timestamps': str or list of str in format 'YYYYMMDDThhmmssZ'
                3) 'runs': int or list of ints for run number(s)  e.g. 10 for r010
    Or input kwargs separately path=, version=, type=; start=&end=, or window=, or timestamps=, or runs=

    Experiment is needed to know which channel belongs to the pulser Subsystem, AUX0 (L60) or AUX1 (L200)
    Selection range is needed for the channel map and status information at that time point, and should be the only information needed,
        however, pylegendmeta only allows query .on(timestamp=...) but not .on(run=...);
        therefore, to be able to get info in case of `runs` selection, we need to know
        path, version, and run type to look up first timestamp of the run

    Might set default "latest" for version, but gotta be careful.
    """

    def __init__(self, sub_type: str, **kwargs):
        utils.logger.info(r"\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/")
        utils.logger.info(r"\/\ Setting up " + sub_type)
        utils.logger.info(r"\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/")

        self.type = sub_type

        # -------------------------------------------------------------------------
        # input check
        # -------------------------------------------------------------------------

        # if setup= kwarg was provided, get dict provided
        # otherwise kwargs is itself already the dict we need with experiment= and period=
        data_info = kwargs["dataset"] if "dataset" in kwargs else kwargs

        # -------------------------------------------------------------------------
        # check validity
        # -------------------------------------------------------------------------

        if "experiment" not in data_info:
            utils.logger.error("Provide experiment name!")
            utils.logger.error(self.__doc__)
            return

        if "type" not in data_info:
            utils.logger.error("Provide data type!")
            utils.logger.error(self.__doc__)
            return

        # convert to list for convenience
        # ! currently not possible with channel status
        # if isinstance(data_info["type"], str):
        #     data_info["type"] = [data_info["type"]]

        data_types = ["phy", "cal"]
        # ! currently not possible with channel status
        # for datatype in data_info["type"]:
        # if datatype not in data_types:
        if not data_info["type"] in data_types:
            utils.logger.error("Invalid data type provided!")
            utils.logger.error(self.__doc__)
            return

        if "path" not in data_info:
            utils.logger.error("Provide path to data!")
            utils.logger.error(self.__doc__)
            return
        if not os.path.exists(data_info["path"]):
            utils.logger.error("The data path you provided does not exist!")
            return

        if "version" not in data_info:
            utils.logger.error("Provide pygama version!")
            utils.logger.error(self.__doc__)
            return

        if not os.path.exists(os.path.join(data_info["path"], data_info["version"])):
            utils.logger.error("Provide valid pygama version!")
            utils.logger.error(self.__doc__)
            return

        # validity of time selection will be checked in utils

        # ? create a checking function taking dict in

        # -------------------------------------------------------------------------
        # get channel info for this subsystem
        # -------------------------------------------------------------------------

        # needed to know which AUX channel is pulser
        self.experiment = data_info["experiment"]
        # need to remember for channel status query
        # ! now needs to be single !
        self.datatype = data_info["type"]
        # need to remember for DataLoader config
        self.path = data_info["path"]
        self.version = data_info["version"]

        self.timerange, self.first_timestamp = utils.get_query_times(**kwargs)

        # None will be returned if something went wrong
        if not self.timerange:
            utils.logger.error(self.get_data.__doc__)
            return

        self.channel_map = self.get_channel_map()  # pd.DataFrame

        # add column status to channel map stating On/Off
        self.get_channel_status()

        # -------------------------------------------------------------------------
        # K lines
        # -------------------------------------------------------------------------

        # # a bit cumbersome, but we need to know if K_lines was requested to select specified energy parameter
        # self.k_lines = False
        # for plot in self.plots:
        #     # if K lines is asked, set to true
        #     self.k_lines = self.k_lines or (self.plots[plot]['events'] == 'K_lines')

        # -------------------------------------------------------------------------
        # have something before get_data() is called just in case
        self.data = pd.DataFrame()

    def get_data(self, parameters: typing.Union[str, list_of_str, tuple_of_str] = ()):
        """
        Get data for requested parameters from DataLoader and "prime" it to be ready for analysis.

        parameters: single parameter or list of parameters to load.
            If empty, only default parameters will be loaded (channel, timestamp; baseline and wfmax for pulser)
        """
        utils.logger.info("... getting data")

        # -------------------------------------------------------------------------
        # Set up DataLoader config
        # -------------------------------------------------------------------------
        utils.logger.info("...... setting up DataLoader")

        # --- construct list of parameters for the data loader
        # depending on special parameters, k lines etc.
        params_for_dataloader = self.get_parameters_for_dataloader(parameters)

        # --- set up DataLoader config
        # needs to know path and version from data_info
        dlconfig, dbconfig = self.construct_dataloader_configs(params_for_dataloader)

        # --- set up DataLoader
        dl = DataLoader(dlconfig, dbconfig)

        # -------------------------------------------------------------------------
        # Set up query
        # -------------------------------------------------------------------------

        # if querying by run, time word is 'run'; otherwise 'timestamp'; is the key of the timerange dict
        time_word = list(self.timerange.keys())[0]

        if "start" in self.timerange[time_word]:
            # query by (run/timestamp >= ) and (run/timestamp <=) if format {start: end:}
            query = f"({time_word} >= '{self.timerange[time_word]['start']}') and ({time_word} <= '{self.timerange[time_word]['end']}')"
        else:
            # query by (run/timestamp == ) or (run/timestamp == ) if format [list of runs/timestamps]
            query = " or ".join(
                f"({time_word} == '" + run_or_timestamp + "')"
                for run_or_timestamp in self.timerange[time_word]
            )

        # --- cal or phy data or both
        # ! not possible to load both phy and cal for now, based on how channel status works
        # query += (
        #     " and ("
        #     + " or ".join("(type == '" + x + "')" for x in self.type)
        #     + ")"
        # )
        query += f" and (type == '{self.datatype}')"

        # !!!! QUICKFIX FOR R010
        query += " and (timestamp != '20230125T222013Z')"
        query += " and (timestamp != '20230126T015308Z')"

        utils.logger.info(
            "...... querying DataLoader (includes quickfix-removed faulty files for r010)"
        )
        utils.logger.info(query)

        # -------------------------------------------------------------------------
        # Query DataLoader & load data
        # -------------------------------------------------------------------------

        # --- query data loader
        dl.set_files(query)
        dl.set_output(fmt="pd.DataFrame", columns=params_for_dataloader)

        now = datetime.now()
        self.data = dl.load()
        utils.logger.info(f"Total time to load data: {(datetime.now() - now)}")

        # -------------------------------------------------------------------------
        # polish things up
        # -------------------------------------------------------------------------

        tier = "hit" if "hit" in dbconfig["columns"] else "dsp"
        # remove columns we don't need
        self.data = self.data.drop([f"{tier}_idx", "file"], axis=1)
        # rename channel to channel
        self.data = self.data.rename(columns={f"{tier}_table": "channel"})

        # -------------------------------------------------------------------------
        # create datetime column based on initial key and timestamp
        # -------------------------------------------------------------------------

        # convert UTC timestamp to datetime (unix epoch time)
        self.data["datetime"] = pd.to_datetime(
            self.data["timestamp"], origin="unix", utc=True, unit="s"
        )
        # drop timestamp
        self.data = self.data.drop("timestamp", axis=1)

        # -------------------------------------------------------------------------
        # add detector name, location and position from map
        # -------------------------------------------------------------------------

        utils.logger.info("... mapping to name and string/fiber position")
        self.data = self.data.set_index("channel")
        # expand channel map index to match that of data with repeating channels
        ch_map_reindexed = self.channel_map.set_index("channel").reindex(
            self.data.index
        )
        # append the channel map columns to the data
        self.data = pd.concat([self.data, ch_map_reindexed], axis=1)
        self.data = self.data.reset_index()
        # stupid dataframe, why float
        for col in ["location", "position"]:
            # ignore string values for fibers ('I/OB-XXX-XXX') and positions ('top/bottom') for SiPMs
            if isinstance(self.data[col].iloc[0], float):
                self.data[col] = self.data[col].astype(int)

        # -------------------------------------------------------------------------
        # if this subsystem is pulser, flag pulser timestamps
        # -------------------------------------------------------------------------

        if self.type == "pulser":
            self.flag_pulser_events()

    def flag_pulser_events(self, pulser=None):
        utils.logger.info("... flagging pulser events")

        # --- if a pulser object was provided, flag pulser events in data based on its flag
        if pulser:
            try:
                pulser_timestamps = pulser.data[pulser.data["flag_pulser"]][
                    "datetime"
                ]  # .set_index('datetime').index
                self.data["flag_pulser"] = False
                self.data = self.data.set_index("datetime")
                self.data.loc[pulser_timestamps, "flag_pulser"] = True
            except KeyError:
                utils.logger.warning(
                    "Warning: cannot flag pulser events, timestamps don't match!\n \
                    If you are you looking at calibration data, it's not possible to flag pulser events in it this way.\n \
                    Contact the developers if you would like them to focus on advanced flagging methods."
                )
                utils.logger.warning("! Proceeding without pulser flag !")

        else:
            # --- if no object was provided, it's understood that this itself is a pulser
            # find timestamps over threshold
            high_thr = 12500
            self.data = self.data.set_index("datetime")
            wf_max_rel = self.data["wf_max"] - self.data["baseline"]
            pulser_timestamps = self.data[wf_max_rel > high_thr].index
            # flag them
            self.data["flag_pulser"] = False
            self.data.loc[pulser_timestamps, "flag_pulser"] = True

        self.data = self.data.reset_index()

    def get_channel_map(self):
        """
        Build channel map for given subsystem.

        setup_info: dict with the keys 'experiment' and 'period'

        Later will probably be changed to get channel map by timestamp (or hopefully run, if possible)
        Planning to add:
            - CC4 name
            - barrel column for SiPMs special case
        """
        utils.logger.info("... getting channel map")

        # -------------------------------------------------------------------------
        # load full channel map of this exp and period
        # -------------------------------------------------------------------------

        full_channel_map = LEGEND_META.hardware.configuration.channelmaps.on(
            timestamp=self.first_timestamp
        )

        df_map = pd.DataFrame(
            columns=["name", "location", "channel", "position", "cc4_id", "cc4_channel"]
        )
        df_map = df_map.set_index("channel")

        # -------------------------------------------------------------------------
        # helper function to determine which channel map entry belongs to this subsystem
        # -------------------------------------------------------------------------

        # dct_key is the subdict corresponding to one chmap entry
        def is_subsystem(entry):
            # special case for pulser
            if self.type == "pulser":
                pulser_ch = 0 if self.experiment == "L60" else 1
                return entry["system"] == "auxs" and entry["daq"]["fcid"] == pulser_ch
            # for geds or spms
            return entry["system"] == self.type

        # name of location in the channel map
        loc_code = {"geds": "string", "spms": "fiber"}

        # -------------------------------------------------------------------------
        # loop over entries and find out subsystem
        # -------------------------------------------------------------------------

        # config.channel_map is already a dict read from the channel map json
        for entry in full_channel_map:
            # skip 'BF' don't even know what it is
            if "BF" in entry:
                continue

            entry_info = full_channel_map[entry]
            # skip if this is not our system
            if not is_subsystem(entry_info):
                continue

            # --- add info for this channel
            # FlashCam channel, unique for geds/spms/pulser
            ch = entry_info["daq"]["fcid"]
            df_map.at[ch, "name"] = entry_info["name"]
            # number/name of string/fiber for geds/spms, dummy for pulser
            df_map.at[ch, "location"] = (
                0
                if self.type == "pulser"
                else entry_info["location"][loc_code[self.type]]
            )
            # position in string/fiber for geds/spms, dummy for pulser (works if there is only one pulser channel)
            df_map.at[ch, "position"] = (
                0 if self.type == "pulser" else entry_info["location"]["position"]
            )
            # CC4 information - will be None for L60 or spms -> put an if condition to avoid?
            df_map.at[ch, "cc4_id"] = (
                entry_info["electronics"]["cc4"]["id"] if self.type == "geds" else None
            )
            df_map.at[ch, "cc4_channel"] = (
                entry_info["electronics"]["cc4"]["channel"]
                if self.type == "geds"
                else None
            )

        df_map = df_map.reset_index()

        # -------------------------------------------------------------------------

        # stupid dataframe, can use dtype somehow to fix it?
        for col in ["channel", "location", "position", "cc4_channel"]:
            if isinstance(df_map[col].loc[0], float):
                df_map[col] = df_map[col].astype(int)

        # sort by channel -> do we really need to?
        df_map = df_map.sort_values("channel")
        return df_map

    def get_channel_status(self):
        """
        Add status column to channel map with On/Off for software status.

        setup_info: dict with the keys 'experiment' and 'period'

        Later will probably be changed to get channel status by timestamp (or hopefully run, if possible)
        """
        utils.logger.info("... getting channel status")

        # -------------------------------------------------------------------------
        # load full status map of this time selection
        # -------------------------------------------------------------------------

        full_status_map = LEGEND_META.dataprod.config.on(
            timestamp=self.first_timestamp, system=self.datatype
        )["hardware_configuration"]["channel_map"]

        # AUX channels are not in status map, so at least for pulser need default On
        self.channel_map["status"] = "On"
        self.channel_map = self.channel_map.set_index("channel")
        for channel in full_status_map:
            # convert string channel ('ch005') to integer (5)
            ch = int(channel[2:])
            # status map contains all channels, check if this channel is in our subsystem
            if ch in self.channel_map.index:
                self.channel_map.at[ch, "status"] = full_status_map[channel][
                    "software_status"
                ]

        self.channel_map = self.channel_map.reset_index()

    def get_parameters_for_dataloader(self, parameters: typing.Union[str, list_of_str]):
        """
        Construct list of parameters to query from the DataLoader.

        - parameters that are always loaded (+ pulser special case)
        - parameters that are already in lh5
        - parameters needed for calculation, if special parameter(s) asked (e.g. wf_max_rel)
        """
        # --- always read timestamp
        params = ["timestamp"]
        # --- always get wf_max & baseline for pulser for flagging
        if self.type == "pulser":
            params += ["wf_max", "baseline"]

        # --- add user requested parameters
        # change to list for convenience, if input was single
        if isinstance(parameters, str):
            parameters = [parameters]

        global USER_TO_PYGAMA
        for param in parameters:
            if param in utils.SPECIAL_PARAMETERS:
                # for special parameters, look up which parameters are needed to be loaded for their calculation
                # if none, ignore
                params += (
                    utils.SPECIAL_PARAMETERS[param]
                    if utils.SPECIAL_PARAMETERS[param]
                    else []
                )
            else:
                # otherwise just add the parameter directly
                params.append(param)

        # add K_lines energy if needed
        # if 'K_lines' in parameters:
        #     params.append(SPECIAL_PARAMETERS['K_lines'][0])

        # some parameters might be repeated twice - remove
        return list(np.unique(params))

    def construct_dataloader_configs(self, params: list_of_str):
        """
        Construct DL and DB configs for DataLoader based on parameters and which tiers they belong to.

        params: list of parameters to load
        data_info: dict of containing type:, path:, version:
        """
        # -------------------------------------------------------------------------
        # which parameters belong to which tiers
        # -------------------------------------------------------------------------

        # --- convert info in json to DataFrame for convenience
        # parameter tier
        # baseline  dsp
        # ...
        param_tiers = pd.DataFrame.from_dict(utils.PARAMETER_TIERS.items())
        param_tiers.columns = ["param", "tier"]

        # which of these are requested by user
        param_tiers = param_tiers[param_tiers["param"].isin(params)]
        utils.logger.info("...... loading parameters from the following tiers:")
        utils.logger.debug(param_tiers)

        # -------------------------------------------------------------------------
        # set up config templates
        # -------------------------------------------------------------------------

        dict_dbconfig = {
            "data_dir": os.path.join(self.path, self.version, "generated", "tier"),
            "tier_dirs": {},
            "file_format": {},
            "table_format": {},
            "tables": {},
            "columns": {},
        }
        dict_dlconfig = {"channel_map": {}, "levels": {}}

        # -------------------------------------------------------------------------
        # set up tiers depending on what parameters we need

        # ronly load channels that are On (Off channels will crash DataLoader)
        chlist = list(self.channel_map[self.channel_map["status"] == "On"]["channel"])
        removed_chs = list(
            self.channel_map[self.channel_map["status"] == "Off"]["channel"]
        )
        utils.logger.info(f"...... not loading channels with status Off: {removed_chs}")

        # --- settings for each tier
        for tier, tier_params in param_tiers.groupby("tier"):
            dict_dbconfig["tier_dirs"][tier] = f"/{tier}"
            # type not fixed and instead specified in the query
            dict_dbconfig["file_format"][tier] = (
                "/{type}/{period}/{run}/{exp}-{period}-{run}-{type}-{timestamp}-tier_"
                + tier
                + ".lh5"
            )
            dict_dbconfig["table_format"][tier] = "ch{ch:03d}/" + tier

            dict_dbconfig["tables"][tier] = chlist

            dict_dbconfig["columns"][tier] = list(tier_params["param"])

            # dict_dlconfig['levels'][tier] = {'tiers': [tier]}

        # --- settings based on tier hierarchy
        order = {"hit": 3, "dsp": 2, "raw": 1}
        param_tiers["order"] = param_tiers["tier"].apply(lambda x: order[x])
        # find highest tier
        max_tier = param_tiers[param_tiers["order"] == param_tiers["order"].max()][
            "tier"
        ].iloc[0]
        # format {"hit": {"tiers": ["dsp", "hit"]}}
        dict_dlconfig["levels"][max_tier] = {
            "tiers": list(param_tiers["tier"].unique())
        }

        return dict_dlconfig, dict_dbconfig
