import sys
from datetime import datetime, timezone
from typing import Tuple

from legendmeta import LegendSlowControlDB
from pandas import DataFrame

from . import utils

scdb = LegendSlowControlDB()
scdb.connect(password="...")  # look on Confluence (or ask Sofia) for the password

# instead of dataset, retrieve 'config["dataset"]' from config json
dataset = {
    "experiment": "L200",
    "period": "p03",
    "version": "",
    "path": "/data2/public/prodenv/prod-blind/tmp/auto",
    "type": "phy",
    # "runs": 0
    # "runs": [0,1]
    "start": "2023-04-06 10:00:00",
    "end": "2023-04-08 13:00:00",
}

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# SLOW CONTROL LOADING/PLOTTING FUNCTIONS
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


def get_sc_param(param="DaqLeft-Temp2", dataset=dataset) -> DataFrame:
    """Get data from the Slow Control (SC) database for the specified parameter ```param```.

    The ```dataset```  entry is of the following type:

    dataset=
        1. dict with keys usually included when plotting other subsystems (geds, spms, ...), i.e. 'experiment', 'period', 'version', 'path', 'type' and any time selection among the following ones:
            1. 'start' : <start datetime>, 'end': <end datetime> where <datetime> input is of format 'YYYY-MM-DD hh:mm:ss'
            2. 'window'[str]: time window in the past from current time point, format: 'Xd Xh Xm' for days, hours, minutes
            2. 'timestamps': str or list of str in format 'YYYYMMDDThhmmssZ'
            3. 'runs': int or list of ints for run number(s)  e.g. 10 for r010
        2. dict with 'start' : <start datetime>, 'end': <end datetime> where <datetime> input is of format 'YYYY-MM-DD hh:mm:ss' only
    """
    # load info from settings/SC-params.json
    sc_params = utils.SC_PARAMETERS

    # check if parameter is within the one listed in settings/SC-params.json
    if param not in sc_params["SC_DB_params"].keys():
        utils.logger.error(
            f"\033[91mThe parameter {param} is not present in 'settings/SC-params.json'. Try again with another parameter or update the json file!\033[0m"
        )
        sys.exit()

    # get first/last timestamps to use when querying data from the SC database
    if set(dataset.keys()) == {"start", "end"}:
        first_tstmp = (
            datetime.strptime(dataset["start"], "%Y-%m-%d %H:%M:%S")
        ).strftime("%Y%m%dT%H%M%SZ")
        last_tstmp = (datetime.strptime(dataset["end"], "%Y-%m-%d %H:%M:%S")).strftime(
            "%Y%m%dT%H%M%SZ"
        )
    else:
        _, first_tstmp, last_tstmp = utils.get_query_times(dataset=dataset)
    utils.logger.debug(
        f"... you are going to query data from {first_tstmp} to {last_tstmp}"
    )

    # get data from the SC database
    df_param = load_table_and_apply_flags(param, sc_params, first_tstmp, last_tstmp)

    return df_param


def load_table_and_apply_flags(
    param: str, sc_params: dict, first_tstmp: str, last_tstmp: str
) -> DataFrame:
    """Load the corresponding table from SC database for the process of interest and apply already the flags for the parameter under study."""
    # getting the process and flags of interest from 'settings/SC-params.json' for the provided parameter
    table_param = sc_params["SC_DB_params"][param]["table"]
    flags_param = sc_params["SC_DB_params"][param]["flags"]

    # check if the selected table is present in the SC database. If not, arise an error and exit
    if table_param not in scdb.get_tables():
        utils.logger.error(
            "\033[91mThis is not present in the SC database! Try again.\033[0m"
        )
        sys.exit()

    # get the dataframe for the process of interest
    utils.logger.debug(
        f"... getting the dataframe for '{table_param}' in the time range of interest\n"
    )
    # SQL query to filter the dataframe based on the time range
    query = f"SELECT * FROM {table_param} WHERE tstamp >= '{first_tstmp}' AND tstamp <= '{last_tstmp}'"
    get_table_df = scdb.dataframe(query)
    # order by timestamp (not automatically done)
    get_table_df = get_table_df.sort_values(by="tstamp")

    utils.logger.debug(get_table_df)

    # let's apply the flags for keeping only the parameter of interest
    utils.logger.debug(f"... applying flags to get the parameter '{param}'")
    get_table_df = apply_flags(get_table_df, sc_params, flags_param)

    # get units and lower/upper limits for the parameter of interest
    unit, lower_lim, upper_lim = get_plotting_info(
        param, sc_params, first_tstmp, last_tstmp
    )
    # append unit, lower_lim, upper_lim to the dataframe
    get_table_df["unit"] = unit
    get_table_df["lower_lim"] = lower_lim
    get_table_df["upper_lim"] = upper_lim

    get_table_df = get_table_df.reset_index()

    utils.logger.debug(
        "... final dataframe (after flagging the events):\n%s", get_table_df
    )

    return get_table_df


def get_plotting_info(
    param: str, sc_params: dict, first_tstmp: str, last_tstmp: str
) -> Tuple[str, float, float]:
    """Return units and low/high limits of a given parameter."""
    table_param = sc_params["SC_DB_params"][param]["table"]
    flags_param = sc_params["SC_DB_params"][param]["flags"]

    # get info dataframe of the corresponding process under study (do I need to specify the param????)
    get_table_info = scdb.dataframe(table_param.replace("snap", "info"))

    # let's apply the flags for keeping only the parameter of interest
    get_table_info = apply_flags(get_table_info, sc_params, flags_param)
    utils.logger.debug(
        "... units and thresholds will be retrieved from the following object:\n%s",
        get_table_info,
    )

    # Convert first_tstmp and last_tstmp to datetime objects in the UTC timezone
    first_tstmp = datetime.strptime(first_tstmp, "%Y%m%dT%H%M%SZ").replace(
        tzinfo=timezone.utc
    )
    last_tstmp = datetime.strptime(last_tstmp, "%Y%m%dT%H%M%SZ").replace(
        tzinfo=timezone.utc
    )

    # Filter the DataFrame based on the time interval, starting to look from the latest entry ('reversed(...)')
    times = list(get_table_info["tstamp"].unique())

    for time in reversed(times):
        if first_tstmp < time < last_tstmp:
            unit = list(get_table_info["unit"].unique())[0]
            lower_lim = upper_lim = None
            utils.logger.warning(
                f"\033[93mParameter {param} has no valid range in the time period you selected. Upper and lower thresholds are set to None, while units={unit}\033[0m"
            )
            return unit, lower_lim, upper_lim

        if time < first_tstmp and time < last_tstmp:
            unit = list(
                get_table_info[get_table_info["tstamp"] == time]["unit"].unique()
            )[0]
            lower_lim = get_table_info[get_table_info["tstamp"] == time][
                "ltol"
            ].tolist()[-1]
            upper_lim = get_table_info[get_table_info["tstamp"] == time][
                "utol"
            ].tolist()[-1]
            utils.logger.debug(
                f"... parameter {param} must be within [{lower_lim};{upper_lim}] {unit}"
            )
            return unit, lower_lim, upper_lim

        if time > first_tstmp and time > last_tstmp:
            if time == times[0]:
                utils.logger.error(
                    "\033[91mYou're travelling too far in the past, there were no SC data in the time period you selected. Try again!\033[0m"
                )
                sys.exit()

    return unit, lower_lim, upper_lim


def apply_flags(df: DataFrame, sc_params: dict, flags_param: list) -> DataFrame:
    """Apply the flags read from 'settings/SC-params.json' to the input dataframe."""
    for flag in flags_param:
        column = sc_params["expressions"][flag]["column"]
        entry = sc_params["expressions"][flag]["entry"]
        df = df[df[column] == entry]

    # check if the dataframe is empty
    if df.empty:
        utils.logger.error("\033[91mThe dataframe is empty. Exiting now!\033[0m")
        exit()

    return df