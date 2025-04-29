import os
import shelve
import sys

import numpy as np
import pandas as pd
from legendmeta import LegendMetadata

# needed to know which parameters are not in DataLoader
# but need to be calculated, such as event rate
from . import utils

# -------------------------------------------------------------------------


class AnalysisData:
    """
    Object containing information for a data subselected from Subsystem data based on given criteria.

    sub_data [DataFrame]: subsystem data

    Available kwargs:
        selection=
            dict with the following contents:
                - 'parameters' [str or list of str]: parameter(s) of interest e.g. 'baseline'
                - 'event_type' [str]: event type, options: pulser/phy/all
                - 'cuts' [str or list of str]: [optional] cuts to apply to data (will be loaded but not applied immediately)
                - 'variation' [bool]: [optional] keep absolute value of parameter (False) or calculate % variation from mean (True).
                    Default: False
                - 'time_window' [str]: [optional] time window in which to calculate event rate, in case that's the parameter of interest.
                    Format: time_window='NA', where N is integer, and A is M for months, D for days, T for minutes, and S for seconds.
                    Default: None
        aux_info=
            str that has info regarding pulser operations (as difference or ratio wrt geds (spms?) data). Available options are:
                - "pulser01anaRatio"
                - "pulser01anaDiff"
        Or input kwargs directly parameters=, event_type=, cuts=, variation=, time_window=
    """

    def __init__(self, sub_data: pd.DataFrame, **kwargs):
        # if selection= was provided, take the dict
        # if kwargs were used directly, kwargs itself is already our dict
        # need to do .copy() or else modifies original config!
        analysis_info = (
            kwargs["selection"].copy() if "selection" in kwargs else kwargs.copy()
        )
        aux_info = kwargs["aux_info"] if "aux_info" in kwargs else None

        # -------------------------------------------------------------------------
        # validity checks
        # -------------------------------------------------------------------------

        # defaults
        if "time_window" not in analysis_info:
            analysis_info["time_window"] = None
        if "cuts" not in analysis_info:
            analysis_info["cuts"] = []
        if "plt_path" not in analysis_info:
            analysis_info["saving"] = analysis_info["plt_path"] = None

        # convert single parameter input to list for convenience
        for input in ["parameters", "cuts"]:
            if isinstance(analysis_info[input], str):
                analysis_info[input] = [analysis_info[input]]

        event_type_flags = {
            "pulser": ("flag_pulser", "pulser"),
            "FCbsln": ("flag_fc_bsln", "FCbsln"),
            "muon": ("flag_muon", "muon"),
        }

        event_type = analysis_info["event_type"]

        # check if the selected event type is within the available ones
        if (
            event_type not in ["all", "phy"]
            and event_type not in event_type_flags.keys()
        ):
            utils.logger.error(
                f"\033[91mThe event type '{event_type}' does not exist and cannot be flagged! Try again with one among {list(event_type_flags.keys())}.\033[0m"
            )
            sys.exit()

        if event_type not in ["all", "phy"] and event_type in event_type_flags:
            flag, subsystem_name = event_type_flags[event_type]
            if flag not in sub_data:
                utils.logger.error(
                    f"\033[91mYour subsystem data does not have a {subsystem_name} flag! We need it to subselect event type {event_type}\033[0m"
                    + f"\033[91mRun the function <subsystem>.flag_{subsystem_name}_events(<{subsystem_name}>) first, where <subsystem> is your Subsystem object, \033[0m"
                    + f"\033[91mand <{subsystem_name}> is a Subsystem object of type '{subsystem_name}', which already has its data loaded with <{subsystem_name}>.get_data(); then create an AnalysisData object.\033[0m"
                )
                sys.exit()

        # cannot do event rate and another parameter at the same time
        # since event rate is calculated in windows
        if (
            "event_rate" in analysis_info["parameters"]
            and len(analysis_info["parameters"]) > 1
        ):
            utils.logger.error(
                "\033[91mCannot get event rate and another parameter at the same time!\n \
                Event rate has to be calculated based on time windows, so the other parameter has to be thrown away.\
                Contact developers if you want, for example, to keep that parameter, but look at mean in the windows of event rate.\033[0m"
            )
            return

        # time window must be provided for event rate
        if (
            "event_rate" in analysis_info["parameters"]
            and not analysis_info["time_window"]
        ):
            utils.logger.error(
                "\033[91mProvide argument <time_window> in which to take the event rate!\033[0m"
            )
            utils.logger.error("\033[91m%s\033[0m", self.__doc__)
            return

        self.parameters = analysis_info["parameters"]
        self.evt_type = analysis_info["event_type"]
        self.time_window = analysis_info["time_window"]
        self.cuts = analysis_info["cuts"]
        self.saving = analysis_info["saving"]
        self.plt_path = analysis_info["plt_path"]
        # evaluate the variation in any case, so we can save it (later useful for dashboard;
        # when plotting, no variation will be included as specified in the config file)
        self.variation = True
        self.aux_info = aux_info

        # -------------------------------------------------------------------------
        # subselect data
        # -------------------------------------------------------------------------

        # always get basic parameters
        params_to_get = ["datetime"] + utils.COLUMNS_TO_LOAD + ["status"]

        for col in sub_data.columns:
            # pulser flag is present only if subsystem.flag_pulser_events() was called -> needed to subselect phy/pulser events
            if "flag_pulser" in col or "flag_fc_bsln" in col or "flag_muon" in col:
                params_to_get.append(col)
            # QC flag is present only if inserted as a cut in the config file -> this part is needed to apply
            if "is_" in col:
                params_to_get.append(col)

        # if special parameter, get columns needed to calculate it
        for param in self.parameters:
            # check if the parameter is within the par-settings.json file
            if param in utils.PLOT_INFO.keys():
                # check if it is a special parameter
                if param in utils.SPECIAL_PARAMETERS:
                    # ignore if none are needed
                    params_to_get += (
                        utils.SPECIAL_PARAMETERS[param]
                        if utils.SPECIAL_PARAMETERS[param]
                        else []
                    )
                else:
                    # otherwise just load it
                    params_to_get.append(param)
            # the parameter does not exist
            else:
                utils.logger.error(
                    "\033[91m'%s' either does not exist in 'par-settings.json' or you misspelled the parameter's name. "
                    + "Another possibility is that the parameter does not exists in .lh5 processed files, so if the problem "
                    + "persists check if in the production environment you are looking at the parameter is included. "
                    + "Check also that you are not trying to plot a flag (ie a quality cut), which is not a parameter by definition.\033[0m",
                    param,
                )
                sys.exit()

        # avoid repetition
        params_to_get = list(np.unique(params_to_get))

        # check if there are the corresponding columns in the dataframe; otherwise, exit
        if set(params_to_get).issubset(sub_data.columns):
            self.data = sub_data[params_to_get].copy()
        else:
            utils.logger.error(
                "\033[91mOne/more entry/entries among %s is/are not present in the dataframe. TRY AGAIN.\033[0m",
                params_to_get,
            )
            sys.exit()

        # -------------------------------------------------------------------------
        # select phy/puls/all/Klines events
        bad = self.select_events()
        if bad:
            return

        # apply cuts, if any
        self.apply_all_cuts()

        # calculate if special parameter
        self.special_parameter()

        # calculate channel mean
        self.channel_mean()

        # calculate variation if needed - only works after channel mean
        self.calculate_variation()

        # little sorting, before closing the function
        self.data = self.data.sort_values(["channel", "datetime"])

    def select_events(self):
        # do we want to keep all, phy or pulser events?
        if self.evt_type == "pulser":
            utils.logger.info("... keeping only pulser events")
            self.data = self.data[self.data["flag_pulser"]]
        elif self.evt_type == "FCbsln":
            utils.logger.info("... keeping only FC baseline events")
            self.data = self.data[self.data["flag_fc_bsln"]]
        elif self.evt_type == "muon":
            utils.logger.info("... keeping only muon events")
            self.data = self.data[self.data["flag_muon"]]
        elif self.evt_type == "phy":
            utils.logger.info(
                "... keeping only physical (non-pulser & non-FCbsln & non-muon) events"
            )
            self.data = self.data[
                (~self.data["flag_pulser"])
                | (~self.data["flag_fc_bsln"])
                | (~self.data["flag_muon"])
            ]
        elif self.evt_type == "K_events":
            utils.logger.info("... selecting K lines in physical (non-pulser) events")
            self.data = self.data[~self.data["flag_pulser"]]
            energy = utils.SPECIAL_PARAMETERS["K_events"][0]
            self.data = self.data[
                (self.data[energy] > 1430) & (self.data[energy] < 1575)
            ]
        elif self.evt_type == "all":
            utils.logger.info("... keeping all (pulser + non-pulser) events")
        else:
            utils.logger.error("\033[91mInvalid event type!\033[0m")
            utils.logger.error("\033[91m%s\033[0m", self.__doc__)
            return "bad"

    def apply_cut(self, cut: str):
        """
        Apply given boolean cut.

        Format: cut name as in lh5 files ("is_*") to apply given cut, or cut name preceded by "~" to apply a "not" cut.
        """
        if cut not in list(self.data.columns):
            utils.logger.warning(
                "\033[93mThe cut '%s' is not available "
                + "(you either misspelled the cut's name or it is not available for the data you are inspecting). "
                + "We do not apply any cut and keep everything, not to stop the flow.\033[0m",
                cut,
            )
        else:
            utils.logger.info("... applying cut: " + cut)

            cut_value = 1
            # check if the cut has "not" in it
            if cut[0] == "~":
                cut_value = 0
                cut = cut[1:]

            self.data = self.data[self.data[cut] == cut_value]

    def apply_all_cuts(self):
        for cut in self.cuts:
            self.apply_cut(cut)

    def special_parameter(self):
        for param in self.parameters:
            if param == "wf_max_rel":
                # calculate wf max relative to baseline
                self.data["wf_max_rel"] = self.data["wf_max"] - self.data["baseline"]
            elif param == "event_rate":
                # ! sorry need to jump through a lot of hoops here ! bare with me....

                # --- count number of events in given time windows
                # - count() returns count of rows for each column - redundant, same value in each (unless we have NaN)
                # just want one column 'event_rate' -> pick 'channel' since it's never NaN, so correct count; rename to event rate
                # - this is now a resampled dataframe with column event rate, and multiindex channel, datetime -> put them back as columns with reset index
                event_rate = (
                    self.data.set_index("datetime")
                    .groupby("channel")
                    .resample(self.time_window, origin="start")
                    .count()["channel"]
                    .to_frame(name="event_rate")
                    .reset_index()
                )

                # ToDo: check time_window for event rate is smaller than the time window, but bigger than the rate (otherwise plots make no sense)

                # divide event count in each time window by sampling window in seconds to get Hz
                dt_seconds = get_seconds(self.time_window)
                event_rate["event_rate"] = event_rate["event_rate"] * 1.0 / dt_seconds

                # --- get rid of last value
                # as the data range does not equally divide by the time window, the count in the last "window" will be smaller
                # as it corresponds to, in reality, smaller window
                # since we divided by the window, the rate then will appear as smaller
                # it's too complicated to fix that, so I will just get rid of the last row
                event_rate = event_rate.iloc[:-1]

                # --- shift timestamp
                # the resulting table will start with the first timestamp of the original table
                # I want to shift the time values by the half the time window, so that the event rate value corresponds to the middle of the time window
                event_rate["datetime"] = (
                    event_rate["datetime"] + pd.Timedelta(self.time_window) / 2
                )

                # --- now have to jump through hoops to put back in location position and name
                # - group original table by channel and pick first occurrence to get the channel map (ignore other columns)
                # - reindex to match event rate table index
                # - put the columns in with concat
                event_rate = event_rate.set_index("channel")
                # need to copy, otherwise next line removes "channel" from original, and crashes next time over not finding channel
                columns = utils.COLUMNS_TO_LOAD[:]
                columns.remove("channel")
                self.data = pd.concat(
                    [
                        event_rate,
                        self.data.groupby("channel")
                        .first()
                        .reindex(event_rate.index)[columns],
                    ],
                    axis=1,
                )
                # put the channel back as column
                self.data = self.data.reset_index()
            elif param == "FWHM":
                # calculate FWHM for each channel (substitute 'param' column with it)
                channel_fwhm = (
                    self.data.groupby("channel")[utils.SPECIAL_PARAMETERS[param][0]]
                    .apply(
                        lambda x: 2.355
                        * np.sqrt(np.mean((x - np.mean(x, axis=0)) ** 2, axis=0))
                    )
                    .reset_index(name="FWHM")
                )

                # join the calculated RMS values to the original dataframe
                self.data = self.data.merge(channel_fwhm, on="channel")

                # put channel back in
                self.data.reset_index()
            elif param == "exposure":
                # ------ get pulser rate for this experiment

                # retrieve first timestamp
                first_timestamp = self.data["datetime"].iloc[0]

                # ToDo: already loaded before in Subsystem => 1) load mass already then, 2) inherit channel map from Subsystem ?
                # get channel map at this timestamp
                lmeta = LegendMetadata()
                full_channel_map = lmeta.hardware.configuration.channelmaps.on(
                    timestamp=first_timestamp
                )

                # get pulser rate
                if "PULS01" in full_channel_map.keys():
                    rate = 0.05  # full_channel_map["PULS01"]["rate_in_Hz"] # L200: p02, p03
                else:
                    rate = full_channel_map["AUX00"]["rate_in_Hz"]["puls"]  # L60

                # ------ count number of pulser events

                # - subselect only pulser events (flag_pulser True)
                # - count number of rows i.e. events for each detector
                # - select arbitrary column that is definitely not NaN in each row e.g. channel to represent the count
                # - rename to "pulser_events"
                # now we have a table with number of pulser events as column with DETECTOR NAME AS INDEX
                df_livetime = (
                    self.data[self.data["flag_pulser"]]
                    .groupby("name")
                    .count()["channel"]
                    .to_frame("pulser_events")
                )

                # ------ calculate livetime for each detector and add it to original dataframe
                df_livetime["livetime_in_s"] = df_livetime["pulser_events"] / rate

                self.data = self.data.set_index("name")
                self.data = pd.concat(
                    [self.data, df_livetime.reindex(self.data.index)], axis=1
                )
                # drop the pulser events column we don't need it
                self.data = self.data.drop("pulser_events", axis=1)

                # --- calculate exposure for each detector
                # get diodes map
                dets_map = lmeta.hardware.detectors.germanium.diodes

                # add a new column "mass" to self.data containing mass values evaluated from dets_map[channel_name]["production"]["mass_in_g"], where channel_name is the value in "name" column
                for det_name in self.data.index.unique():
                    mass_in_kg = dets_map[det_name]["production"]["mass_in_g"] / 1000
                    # exposure in kg*yr
                    self.data.at[det_name, "exposure"] = (
                        mass_in_kg
                        * df_livetime.at[det_name, "livetime_in_s"]
                        / (60 * 60 * 24 * 365.25)
                    )

                self.data.reset_index()
            elif param == "AoE_Custom":
                self.data["AoE_Custom"] = self.data["A_max"] / self.data["cuspEmax"]

    def channel_mean(self):
        """
        Get mean value of each parameter of interest in each channel in the first 10% of the dataset.

        Ignore in case of SiPMs, as each entry is a list of values, not a single value.
        """
        utils.logger.info("... getting channel mean")
        # series with index channel, columns of parameters containing mean of each channel;
        # the mean is performed over the first 10% interval of the full time range specified in the config file

        # get mean (only for non-list parameters; in that case, add a new column with None values):
        # check if we are looking at SiPMs -> do not get mean because entries are usually lists
        # ToDo: need to iterate over the parameters (some of them could be lists, others not)

        # congratulations, it's a sipm!
        if self.is_spms():
            channels = (self.data["channel"]).unique()
            # !! need to update for multiple parameter case!
            channel_mean = pd.DataFrame(
                {"channel": channels, self.parameters[0]: [None] * len(channels)}
            )
            channel_mean = channel_mean.set_index("channel")
            # !! need to update for multiple parameter case!
            self.data = concat_channel_mean(self, channel_mean)
        # otherwise, it's either an aux or geds
        else:
            if self.saving is None or self.saving == "overwrite":
                # get the dataframe for timestamps below 10% of data present in the selected time window
                self_data_time_cut = cut_dataframe(self.data)
                # create a column with the mean of the cut dataframe (cut in the time window of interest)
                channel_mean = self_data_time_cut.groupby("channel").mean(
                    numeric_only=True
                )[self.parameters]
                # concatenate column with mean values
                self.data = concat_channel_mean(self, channel_mean)

            elif self.saving == "append":
                subsys = self.get_subsys() if self.aux_info is None else self.aux_info
                # the file does not exist, so we get the mean as usual
                if not os.path.exists(self.plt_path + "-" + subsys + ".dat"):
                    self_data_time_cut = cut_dataframe(self.data)
                    # create a column with the mean of the cut dataframe (cut in the time window of interest)
                    channel_mean = self_data_time_cut.groupby("channel").mean(
                        numeric_only=True
                    )[self.parameters]
                    # concatenate column with mean values
                    self.data = concat_channel_mean(self, channel_mean)

                # the file exist: we have to combine previous data with new data, and re-compute the mean over the first 10% of data (that now, are more than before)
                else:
                    # open already existing shelve file
                    with shelve.open(self.plt_path + "-" + subsys, "r") as shelf:
                        old_dict = dict(shelf)

                    if len(self.parameters) == 1:
                        param = self.parameters[0]
                        channel_mean = get_saved_df(
                            self, subsys, param, old_dict, self.evt_type
                        )
                        # concatenate column with mean values
                        self.data = concat_channel_mean(self, channel_mean)

                    if len(self.parameters) > 1:
                        for param in self.parameters:
                            parameter = (
                                param.split("_var")[0] if "_var" in param else param
                            )
                            channel_mean = get_saved_df(
                                self, subsys, parameter, old_dict, self.evt_type
                            )
                            # we need to repeat this operation for each param, otherwise only the mean of the last one survives
                            self.data = concat_channel_mean(self, channel_mean)

        if self.data.empty:
            utils.logger.error(
                f"\033[91mFor '{self.evt_type}' there are no flagged data (empty dataframe) -> no entries in the output file! Stop here the study.\033[0m"
            )

    def calculate_variation(self):
        """
        Add a new column containing the percentage variation of a given parameter.

        The new column is called '<parameter>_var'.
        There is still the <parameter> column containing absolute values.
        There is only the <parameter> column if variation is set to False.
        """
        if self.variation:
            utils.logger.info("... calculating % variation from the mean")
            for param in self.parameters:
                # % variation: subtract mean from value for each channel
                self.data[param + "_var"] = (
                    self.data[param] / self.data[param + "_mean"] - 1
                ) * 100  # %

    def is_spms(self) -> bool:
        """Return True if 'location' (=fiber) and 'position' (=top, bottom) are strings."""
        if self.data.empty:
            return False

        if isinstance(self.data.iloc[0]["location"], str) and isinstance(
            self.data.iloc[0]["position"], str
        ):
            return True
        else:
            return False

    def is_geds(self) -> bool:
        """Return True if 'location' (=string) and 'position' are NOT strings."""
        return not self.is_spms()

    def is_pulser(self) -> bool:
        """Return True if the system is the pulser channel."""
        return (
            self.is_geds()
            and self.data.iloc[0]["location"] == 0
            and self.data.iloc[0]["position"] == 0
        )

    def is_pulser01ana(self) -> bool:
        """Return True if the system is the pulser channel."""
        return (
            self.is_geds()
            and self.data.iloc[0]["location"] == -1
            and self.data.iloc[0]["position"] == -1
        )

    def is_fc_bsln(self) -> bool:
        """Return True if the system is the FC baseline channel."""
        return (
            self.is_geds()
            and self.data.iloc[0]["location"] == -2
            and self.data.iloc[0]["position"] == -2
        )

    def is_muon(self) -> bool:
        """Return True if the system is the muon channel."""
        return (
            self.is_geds()
            and self.data.iloc[0]["location"] == -3
            and self.data.iloc[0]["position"] == -3
        )

    def is_aux(self) -> bool:
        """Return True if the system is an AUX channel."""
        return (
            self.is_pulser()
            or self.is_pulser01ana()
            or self.is_fc_bsln()
            or self.is_muon()
        )

    def get_subsys(self) -> str:
        """Return 'pulser', 'pulser01ana', 'FCbsln', 'muon', 'geds' or 'spms' depending on the subsystem type."""
        if self.is_pulser():
            return "pulser"
        if self.is_pulser01ana():
            return "pulser01ana"
        if self.is_fc_bsln():
            return "FCbsln"
        if self.is_muon():
            return "muon"
        if self.is_spms():
            return "spms"
        if self.is_geds():
            return "geds"


# -------------------------------------------------------------------------
# helper function
# -------------------------------------------------------------------------


def get_seconds(time_window: str):
    """
    Convert sampling format used for DataFrame.resample() to int representing seconds.

    Needed for event rate calculation.

    >>> get_seconds('30T')
    1800
    """
    # correspondence of symbol to seconds, T = minutes
    str_to_seconds = {"S": 1, "T": 60, "H": 60 * 60, "D": 24 * 60 * 60}
    # unit of this time window
    time_unit = time_window[-1]

    return int(time_window.rstrip(time_unit)) * str_to_seconds[time_unit]


def cut_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Get mean value of the parameters under study over the first 10% of data present in the selected time range of the input dataframe."""
    min_datetime = df["datetime"].min()  # first timestamp
    max_datetime = df["datetime"].max()  # last timestamp
    duration = max_datetime - min_datetime
    ten_percent_duration = duration * 0.1
    thr_datetime = min_datetime + ten_percent_duration  # 10% timestamp
    # get only the rows for datetimes before the 10% of the specified time range
    return df.loc[df["datetime"] < thr_datetime]


def get_saved_df(
    self, subsys: str, param: str, old_dict: dict, evt_type: str
) -> pd.DataFrame:
    """Get the already saved dataframe from the already saved output shelve file, for a given parameter ```param```. In particular, it evaluates again the mean over the new 10% of data in the new larger time window."""
    # get old dataframe (we are interested only in the column with mean values)
    old_df = old_dict["monitoring"][evt_type][param]["df_" + subsys]

    # we need to re-calculate the mean value over the new bigger time window!
    # we retrieve absolute values of already saved df, we use
    old_absolute_values = old_df.copy().filter(items=["channel", "datetime", param])
    new_absolute_values = self.data.copy().filter(items=["channel", "datetime", param])

    concatenated_df = pd.concat(
        [old_absolute_values, new_absolute_values], ignore_index=True
    )
    # get the dataframe for timestamps below 10% of data present in the selected time window
    concatenated_df_time_cut = cut_dataframe(concatenated_df)
    # remove 'datetime' column (it was necessary just to evaluate again the first 10% of data that are necessary to evaluate the mean on the new dataset)
    concatenated_df_time_cut = concatenated_df_time_cut.drop(columns=["datetime"])

    # create a column with the mean of the cut dataframe (cut in the time window of interest)
    channel_mean = (
        concatenated_df_time_cut.groupby("channel")[param].mean().reset_index()
    )

    # drop potential duplicate rows
    channel_mean = channel_mean.drop_duplicates(subset=["channel"])
    # set channel to index because that's how it comes out in previous cases from df.mean()
    channel_mean = channel_mean.set_index("channel")

    return channel_mean


def get_aux_df(
    df: pd.DataFrame, parameter: list, plot_settings: dict, aux_ch: str
) -> pd.DataFrame:
    """Get dataframes containing auxiliary (PULS01ANA) data, storing absolute/diff&ratio/mean/% variations values."""
    if len(parameter) == 1:
        param = parameter[0]
        if (
            param in utils.PARAMETER_TIERS.keys()
            and utils.PARAMETER_TIERS[param] == "hit"
        ) or param in utils.SPECIAL_PARAMETERS.keys():
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

        # get abs/mean/% variation for data of aux channel --> objects to save
        utils.logger.debug(f"Getting {aux_ch} data for {param}")
        aux_data = df.copy()
        aux_data[param] = aux_data[f"{param}_{aux_ch}"]
        aux_data = aux_data.drop(
            columns=[
                f"{param}_{aux_ch}Ratio",
                f"{param}_{aux_ch}",
                f"{param}_{aux_ch}Diff",
            ]
        )
        # right now, we have the same values repeated for each ged channel
        # -> keep one and substytute with AUX channel ID
        # (only for this aux df, the others still maintain a relation with geds values)
        # keep one channel only
        first_ch = aux_data.iloc[0]["channel"]
        aux_data = aux_data[aux_data["channel"] == first_ch]
        first_timestamp = utils.unix_timestamp_to_string(
            aux_data["datetime"].dt.to_pydatetime()[0].timestamp()
        )
        if aux_ch == "pulser01ana":
            chmap = LegendMetadata().hardware.configuration.channelmaps.on(
                timestamp=first_timestamp
            )
            # PULS01ANA channel
            if "PULS01ANA" in chmap.keys():
                aux_data = get_aux_info(aux_data, chmap, "PULS01ANA")
            # PULS (=AUX00) channel (for periods below p03)
            else:
                aux_data = get_aux_info(aux_data, chmap, "PULS01")

        # get channel mean and blabla
        aux_analysis = AnalysisData(aux_data, selection=plot_settings)
        utils.logger.debug("... aux dataframe \n%s", aux_analysis.data)

        # get abs/mean/% variation for ratio values with aux channel data --> objects to save
        utils.logger.debug(f"Getting ratio wrt {aux_ch} data for {param}")
        aux_ratio_data = df.copy()
        aux_ratio_data[param] = aux_ratio_data[f"{param}_{aux_ch}Ratio"]
        aux_ratio_data = aux_ratio_data.drop(
            columns=[
                f"{param}_{aux_ch}Ratio",
                f"{param}_{aux_ch}",
                f"{param}_{aux_ch}Diff",
            ]
        )

        aux_ratio_analysis = AnalysisData(
            aux_ratio_data, selection=plot_settings, aux_info="pulser01anaRatio"
        )
        utils.logger.debug("... aux ratio dataframe \n%s", aux_ratio_analysis.data)

        # get abs/mean/% variation for difference values with aux channel data --> objects to save
        utils.logger.debug(f"Getting difference wrt {aux_ch} data for {param}")
        aux_diff_data = df.copy()
        aux_diff_data[param] = aux_diff_data[f"{param}_{aux_ch}Diff"]
        aux_diff_data = aux_diff_data.drop(
            columns=[
                f"{param}_{aux_ch}Ratio",
                f"{param}_{aux_ch}",
                f"{param}_{aux_ch}Diff",
            ]
        )
        aux_diff_analysis = AnalysisData(
            aux_diff_data, selection=plot_settings, aux_info="pulser01anaDiff"
        )
        utils.logger.debug("... aux difference dataframe \n%s", aux_diff_analysis.data)

    if len(parameter) > 1:
        utils.logger.warning(
            "\033[93mThe aux subtraction/difference is not implemented for multi parameters! We skip it and plot the normal quantities, not corrected for the aux channel.\033[0m"
        )
        if "AUX_ratio" in plot_settings.keys():
            del plot_settings["AUX_ratio"]
        if "AUX_diff" in plot_settings.keys():
            del plot_settings["AUX_diff"]
        return None, None, None

    return aux_analysis, aux_ratio_analysis, aux_diff_analysis


def get_aux_info(df: pd.DataFrame, chmap: dict, aux_ch: str) -> pd.DataFrame:
    """Return a DataFrame with correct pulser AUX info."""
    df["channel"] = LegendMetadata().channelmap().PULS01ANA.daq.rawid
    df["HV_card"] = None
    df["HV_channel"] = None
    df["cc4_channel"] = None
    df["cc4_id"] = None
    df["daq_card"] = LegendMetadata().channelmap().PULS01ANA.daq.card.id
    df["daq_crate"] = LegendMetadata().channelmap().PULS01ANA.daq.crate
    df["det_type"] = None
    df["location"] = (
        utils.SPECIAL_SYSTEMS["pulser01ana"]
        if aux_ch == "PULS01ANA"
        else utils.SPECIAL_SYSTEMS["pulser"]
    )
    df["position"] = df["location"]
    df["name"] = aux_ch

    return df


def concat_channel_mean(self, channel_mean) -> pd.DataFrame:
    """Add a new column containing the mean values of the inspected parameter."""
    # some means are meaningless -> drop the corresponding column
    if "FWHM" in self.parameters:
        channel_mean.drop("FWHM", axis=1)
    if "exposure" in self.parameters:
        channel_mean.drop("exposure", axis=1)

    # rename columns to be param_mean
    channel_mean = channel_mean.rename(
        columns={param: param + "_mean" for param in self.parameters}
    )
    # add it as column for convenience - repeating redundant information, but convenient
    self.data = self.data.set_index("channel")
    self.data = pd.concat([self.data, channel_mean.reindex(self.data.index)], axis=1)

    return self.data.reset_index()
