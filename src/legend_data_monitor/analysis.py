from __future__ import annotations

import importlib.resources
import json
import logging
import operator
import os
import sys
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pygama.lgdo.lh5_store as lh5
from legendmeta import LegendMetadata
from pygama.flow import DataLoader

from . import timecut

pkg = importlib.resources.files("legend_data_monitor")
ops = {"<=": operator.le, "<": operator.lt, ">=": operator.ge, ">": operator.gt}
lmeta = LegendMetadata()


def read_json_files():
    """Read json files of 'settings/' folder and return three lists."""
    with open(pkg / "settings" / "lngs-config.json") as f:
        data_config = json.load(f)
    with open(pkg / "settings" / "par-settings.json") as g:
        data_par = json.load(g)
    with open(pkg / "settings" / "plot-settings.json") as h:
        data_plot = json.load(h)
    j_config = []
    j_par = []
    j_plot = []

    j_config.append(data_config["run_info"])  # 0
    j_config.append(data_config["period"])  # 1
    j_config.append(data_config["run"])  # 2
    j_config.append(data_config["file_keys"])  # 3
    j_config.append(data_config["datatype"])  # 4
    j_config.append(data_config["det_type"])  # 5
    j_config.append(data_config["par_to_plot"])  # 6
    j_config.append(data_config["plot_style"])  # 7
    j_config.append(data_config["time_window"])  # 8
    j_config.append(data_config["last_hours"])  # 9
    j_config.append(data_config["status"])  # 10
    j_config.append(data_config["time-format"])  # 11
    j_config.append(data_config["verbose"])  # 12
    j_config.append(data_config["no_avail_chs"])  # 13

    j_par.append(data_par["par_to_plot"])  # 0

    j_plot.append(data_plot["spms_col_dict"])  # 0
    j_plot.append(data_plot["geds_col_dict"])  # 1

    return j_config, j_par, j_plot


j_config, j_par, j_plot = read_json_files()
exp = j_config[0]["exp"]
files_path = j_config[0]["path"]["lh5-files"]
version = j_config[0]["path"]["version"]
output = j_config[0]["path"]["output"]
period = j_config[1]
run = j_config[2]
file_keys = j_config[3]
datatype = j_config[4]
pulser_events = j_config[6]["pulser"]["pulser_events"]
physics_events = j_config[6]["pulser"]["physics_events"]
qc_flag = j_config[6]["quality_cuts"]
qc_version = j_config[6]["quality_cuts"]["version"]["QualityCuts_flag"][
    "apply_to_version"
]
is_qc_version = j_config[6]["quality_cuts"]["version"]["isQC_flag"]["apply_to_version"]
time_window = j_config[8]
last_hours = j_config[9]
verbose = j_config[12]


def write_config(
    files_path: str,
    version: str,
    det_map: list[list[str]],
    parameters: list[str],
    det_type: str,
):
    """
    Write DataLoader config file.

    Parameters
    ----------
    files_path
                Path previous to generated files path
    version
                Version of processed data
    det_map
                Map of detectors
    parameters
                Parameters to plot
    det_type
                Type of detector (geds, spms or ch000)
    """
    if det_type == "ch001":
        if det_type == "ch001":
            det_type = "evts"
        det_list = [1]
        dict_dbconfig = {
            "data_dir": files_path + version + "/generated/tier",
            "tier_dirs": {"dsp": "/dsp"},
            "file_format": {
                "dsp": "/phy/{period}/{run}/{exp}-{period}-{run}-phy-{timestamp}-tier_dsp.lh5"
            },
            "table_format": {"dsp": "ch{ch:03d}/dsp"},
            "tables": {"dsp": det_list},
            "columns": {"dsp": parameters},
        }
        dict_dlconfig = {"levels": {"dsp": {"tiers": ["dsp"]}}, "channel_map": {}}

    if det_type == "ch000":
        if det_type == "ch000":
            det_type = "evts"
        det_list = [0]
        dict_dbconfig = {
            "data_dir": files_path + version + "/generated/tier",
            "tier_dirs": {"dsp": "/dsp"},
            "file_format": {
                "dsp": "/phy/{period}/{run}/{exp}-{period}-{run}-phy-{timestamp}-tier_dsp.lh5"
            },
            "table_format": {"dsp": "ch{ch:03d}/dsp"},
            "tables": {"dsp": det_list},
            "columns": {"dsp": parameters},
        }
        dict_dlconfig = {"levels": {"dsp": {"tiers": ["dsp"]}}, "channel_map": {}}
    if det_type == "geds" or det_type == "spms":
        # flattening list[list[str]] to list[str]
        flat_list = [ch for det in det_map for ch in det]

        # converting channel number to int to give array as input to FileDB
        det_list = [int(elem.split("ch")[-1]) for elem in flat_list]

        dsp_list = det_list.copy()
        hit_list = det_list.copy()

        # removing channels having no hit data
        removed_chs = j_config[13][det_type]

        for ch in removed_chs:
            if ch in hit_list:
                hit_list.remove(ch)

        dict_dbconfig = {
            "data_dir": files_path + version + "/generated/tier",
            "tier_dirs": {"dsp": "/dsp", "hit": "/hit"},
            "file_format": {
                "dsp": "/phy/{period}/{run}/{exp}-{period}-{run}-phy-{timestamp}-tier_dsp.lh5",
                "hit": "/phy/{period}/{run}/{exp}-{period}-{run}-phy-{timestamp}-tier_hit.lh5",
            },
            "table_format": {"dsp": "ch{ch:03d}/dsp", "hit": "ch{ch:03d}/hit"},
            "tables": {"dsp": dsp_list, "hit": hit_list},
            "columns": {"dsp": parameters, "hit": parameters},
        }
        dict_dlconfig = {
            "levels": {"hit": {"tiers": ["dsp", "hit"]}},
            "channel_map": {},
        }

    # Serializing json
    json_dbconfig = json.dumps(dict_dbconfig, indent=4)
    json_dlconfig = json.dumps(dict_dlconfig, indent=4)

    # Writing to _.json
    dbconfig_filename = str(pkg / "settings" / f"dbconfig_{det_type}.json")
    dlconfig_filename = str(pkg / "settings" / f"dlconfig_{det_type}.json")

    # Writing FileDB config file
    with open(dbconfig_filename, "w") as outfile:
        outfile.write(json_dbconfig)

    # Writing DataLoader config file
    with open(dlconfig_filename, "w") as outfile:
        outfile.write(json_dlconfig)

    return dbconfig_filename, dlconfig_filename


def read_from_dataloader(
    dbconfig: str, dlconfig: str, query: str | list[str], parameters: list[str]
):
    """
    Return the loaded data as a pandas DataFrame.

    Parameters
    ----------
    dbconfig
                Database filename
    dlconfig
                Configuration filename
    query
                Cut over files
    parameters
                Parameters to load
    """
    dl = DataLoader(dlconfig, dbconfig)
    dl.set_files(query)
    dl.set_output(fmt="pd.DataFrame", columns=parameters)

    return dl.load()


def set_query(time_cut: list, start_code: str, run: str | list[str]):
    """
    Load specific runs and/or files.

    Parameters
    ----------
    time_cut
                List with info about time cuts
    start_code
                Starting time of the code
    run
                Run(s) to load
    """
    query = ""

    # Reading from file or list of keys
    if file_keys != "":
        if isinstance(file_keys, list):
            query = file_keys
        else:
            with open(file_keys) as f:
                lines = f.readlines()
            keys = [(line.strip("\n")).split("-")[-1] for line in lines]
            query = keys

    # Applying time cut
    if len(time_cut) > 0:
        start, stop = timecut.time_dates(time_cut, start_code)
        start_datetime = datetime.strptime(start, "%Y%m%dT%H%M%SZ")
        start_datetime = start_datetime - timedelta(minutes=120)
        start = start_datetime.strftime("%Y%m%dT%H%M%SZ")
        if query != "":
            query += " and "
        query += f"timestamp > '{start}' and timestamp < '{stop}'"

    # Applying run cut
    if run:
        if query != "":
            query += " and "
        if isinstance(run, str):
            query += f"run == '{run}'"
        elif isinstance(run, list):
            for r in run:
                query += f"run == '{r}' or "
            # Just the remove the final 'or'
            query = query[:-4]

    if query == "":
        logging.error(
            "Empty query: provide at least a run, a time interval or a list of files to open, try again!"
        )
        sys.exit(1)

    return query


def get_qc_method(version: str, qc_version: str, is_qc_version: str):
    """
    Define the quality cut method to use, depending on the version of processed files under inspection.

    Parameters
    ----------
    version
                Version of processed files under inspection
    qc_version
                Version condition for Quality_Cuts flag (eg. "<=v06.00")
    is_qc_version
                Version condition for isQC flag (eg. ">v06.00")
    """
    # if True, we use 'Quality_cuts' as quality cuts
    if ops[qc_version[:-6]](version, qc_version[-6:]):
        qc_method = "Quality_cuts"

    # if True, we use 'is_valid_0vbb' as quality cuts
    elif ops[is_qc_version[:-6]](version, is_qc_version[-6:]):
        # get available parameters in hit files
        config_hit_file_path = files_path + version + "/inputs/config/tier_hit/"
        config_hit_file = [
            config_hit_file_path + f
            for f in os.listdir(config_hit_file_path)
            if "ICPC" in f
        ][0]
        with open(config_hit_file) as d:
            hit_dict = json.load(d)
        avail_hit_pars = hit_dict["outputs"]

        # check if the wanted selection has been implemented in the version of interest or not
        config_selection = j_config[6]["quality_cuts"]["version"]["isQC_flag"]["which"]
        if config_selection in avail_hit_pars:
            qc_method = j_config[6]["quality_cuts"]["version"]["isQC_flag"]["which"]
        else:
            logging.error(
                f"'{config_selection}' has not been implemented in version {version}, try again with another flag, another version in {files_path}!\n(...or check quality cut versions in config file...)"
            )
            sys.exit(1)

    else:
        logging.error(
            "There is a conflict among files' version and quality cuts versions, check it!"
        )
        sys.exit(1)

    return qc_method


def load_df_cols(par_to_plot: list[str], det_type: str):
    """
    Load parameters to plot starting from config file input.

    Parameters
    ----------
    par_to_plot
                Parameters to load for a given type of detector.
    det_type
                Type of detector (geds or spms)
    """
    db_parameters = par_to_plot

    if "uncal_puls" in db_parameters:
        db_parameters = [db.replace("uncal_puls", "trapTmax") for db in db_parameters]
    if "cal_puls" in db_parameters:
        db_parameters = [
            db.replace("cal_puls", "cuspEmax_ctc_cal") for db in db_parameters
        ]
    if "K_lines" in db_parameters:
        db_parameters = [
            db.replace("K_lines", "cuspEmax_ctc_cal") for db in db_parameters
        ]
    if "event_rate" in db_parameters:
        if det_type == "spms":
            db_parameters = [
                db.replace("event_rate", "energies") for db in db_parameters
            ]

    # load quality cuts, if enabled
    if qc_flag[det_type] is True:
        qc_method = get_qc_method(version, qc_version, is_qc_version)
        db_parameters.append(qc_method)

    # load always timestamps
    db_parameters.append("timestamp")

    return db_parameters


def load_geds():
    """Load channel map for geds."""
    # json_file = f"{exp.upper()}-{period}-r%-T%-all-config"
    json_file = "L200-p01-r%-T%-all-config"
    map_lmeta = lmeta["hardware"]["configuration"]["channelmaps"]
    channel_map = map_lmeta[json_file]

    if exp == "l60" or exp == "l200":
        geds_dict = {}
        for k1, v1 in channel_map.items():
            if "S0" not in k1:  # keep only geds
                info_dict = {}
                info_dict["system"] = "ged"
                info_dict["det_type"] = "icpc"
                info_dict["hardware_status"] = "--"
                info_dict["software_status"] = "--"
                info_dict["electronics"] = "--"
                for k2, v2 in v1.items():
                    if k2 == "detname":
                        info_dict["det_id"] = v2
                    if k2 == "location":
                        info_dict["string"] = {
                            "number": str(v2["string"]),
                            "position": str(v2["position"]),
                        }
                    if k2 == "daq":
                        info_dict[k2] = {
                            "board_ch": str(v1[k2]["channel"]),  # check if it's ok
                            "board_slot": str(v2["card"]["id"]),  # check if it's ok
                            "board_id": str(v2["card"]["address"]),
                            "crate": str(v1[k2]["crate"]),
                        }
                    if k2 == "voltage":
                        info_dict["high_voltage"] = {
                            "board_chan": str(v1[k2]["channel"]),
                            "cable": "--",
                            "flange_id": "?",  # check it
                            "flange_pos": "--",
                            "crate": "0",  # check if it's ok
                        }
                    if k2 == "electronics":
                        info_dict[k2] = {
                            "fanout_card": "?",  # check it
                            "lmfe_id": str(v2["cc4"]["id"]),  # check if it's ok
                            "raspberrypi": "?",  # check it
                            "cc4_ch": str(v2["cc4"]["channel"]),
                            "head_card_ana": "?",  # check it
                            "head_card_dig": "?",  # check it
                        }
                # get the FC channel
                channel = v1["daq"]["fc_channel"]
                if channel < 10:
                    channel = f"ch00{channel}"
                elif channel > 9 and channel < 100:
                    channel = f"ch0{channel}"
                else:
                    channel = f"ch{channel}"
                # final dictionary
                geds_dict[channel] = info_dict

        # sorting channels in dict
        geds_keys = list(geds_dict.keys())
        geds_keys.sort()
        geds_dict = {i: geds_dict[i] for i in geds_keys}

    return geds_dict


def load_spms():
    """Load channel map for spms."""
    map_path = j_config[0]["path"]["channel-map"]

    if exp == "l60":
        map_file = map_path + f"{exp.upper()}-{period}-r%-T%-SiPM-config.json"
        with open(map_file) as f:
            spms_dict = json.load(f)

    if exp == "l200":
        # we keep using L60 map because L200 map has no info about spms positions
        # map_file = map_path + f"L60-{period}-r%-T%-SiPM-config.json"
        map_file = map_path + "L60-p01-r%-T%-SiPM-config.json"
        with open(map_file) as f:
            spms_dict = json.load(f)


        # # a future possible dictionary for L200
        # json_file = f"{exp.upper()}-{period}-r%-T%-all-config"
        # map_lmeta = lmeta["hardware"]["configuration"]["channelmaps"]
        # channel_map = map_lmeta[json_file]

        # spms_dict = {}
        # for k1,v1 in channel_map.items():
        #     if 'S0' in k1: # keep only spms
        #         info_dict = {}
        #         info_dict["system"] = "spm"
        #         info_dict["det_id"] = v1["detname"]
        #         info_dict["barrel"] = str(v1["location"]["fiber"])[2:]

        #         for k2,v2 in v1.items():
        #             if k2 == "detname":
        #                 info_dict["det_id"] = v2
        #             if k2 == "daq":
        #                 info_dict[k2] = {
        #                     "board_ch": str(v1[k2]["channel"]), # check if it's ok
        #                     "board_slot": str(v2["card"]["id"]), # check if it's ok
        #                     "board_id": str(v2["card"]["address"]),
        #                     "crate": str(v1[k2]["crate"])
        #                 }
        #         # get the FC channel
        #         channel = v1["daq"]["fc_channel"]
        #         if channel < 10:
        #             channel = f"ch00{channel}"
        #         elif channel > 9 and channel < 100:
        #             channel = f"ch0{channel}"
        #         else:
        #             channel = f"ch{channel}"
        #         # final dictionary
        #         spms_dict[channel] = info_dict

        # # sorting channels in dict
        # spms_keys = list(spms_dict.keys())
        # spms_keys.sort()
        # spms_dict = {i: spms_dict[i] for i in spms_keys}

    return spms_dict


def read_geds(geds_dict: dict):
    """
    Build an array of germanium strings.

    Parameters
    ----------
    geds_dict
               Contains info (crate, card, ch_orca) for geds
    """
    string_tot = []
    string_name = []

    # no of strings
    str_no = [
        v["string"]["number"]
        for k, v in geds_dict.items()
        if v["string"]["number"] != "--"
    ]

    unique_list = list(int(a) for a in set(str_no))
    min_str = min(unique_list)
    max_str = max(unique_list)
    idx = min_str

    # fill lists with strings of channels ('while' loop over no of string)
    while idx <= max_str:
        string = [k for k, v in geds_dict.items() if v["string"]["number"] == str(idx)]
        pos = []
        for v1 in geds_dict.values():
            for k2, v2 in v1.items():
                if k2 == "string":
                    for k3, v3 in v2.items():
                        if k3 == "position" and v1["string"]["number"] == str(idx):
                            pos.append(v3)

        if len(string) == 0:
            idx += 1
        else:
            # order channels within a string
            # print(pos, string)
            # pos, string = (list(t) for t in zip(*sorted(zip(pos, string))))
            string_tot.append(string)
            string_name.append(f"{idx}")
            idx += 1

    return string_tot, string_name


def read_spms_old(spms_dict: dict):
    """
    Build two lists for IN and OUT spms.

    Parameters
    ----------
    spms_dict
               Contains info (crate, card, ch_orca) for spms
    """
    spms_map = json.load(open(pkg / "settings" / "spms_map.json"))
    top_ob = []
    bot_ob = []
    top_ib = []
    bot_ib = []

    # loop over spms channels (i.e. channels w/ crate=2)
    for ch in list(spms_dict.keys()):
        card = spms_dict[ch]["daq"]["card"]
        ch_orca = spms_dict[ch]["daq"]["ch_orca"]

        idx = "0"
        for serial in list(spms_map.keys()):
            if (
                spms_map[serial]["card"] == card
                and spms_map[serial]["ch_orca"] == ch_orca
            ):
                idx = str(serial)
        if idx == "0":
            continue

        spms_type = spms_map[idx]["type"]
        spms_pos = spms_map[idx]["pos"]
        if spms_type == "OB" and spms_pos == "top":
            top_ob.append(ch)
        if spms_type == "OB" and spms_pos == "bot":
            bot_ob.append(ch)
        if spms_type == "IB" and spms_pos == "top":
            top_ib.append(ch)
        if spms_type == "IB" and spms_pos == "bot":
            bot_ib.append(ch)

    half_len_top_ob = int(len(top_ob) / 2)
    half_len_bot_ob = int(len(bot_ob) / 2)
    top_ob_1 = top_ob[half_len_top_ob:]
    top_ob_2 = top_ob[:half_len_top_ob]
    bot_ob_1 = bot_ob[half_len_bot_ob:]
    bot_ob_2 = bot_ob[:half_len_bot_ob]

    string_tot_div = [top_ob_1, top_ob_2, bot_ob_1, bot_ob_2, top_ib, bot_ib]
    string_name_div = [
        "top_OB-1",
        "top_OB-2",
        "bot_OB-1",
        "bot_OB-2",
        "top_IB",
        "bot_IB",
    ]

    string_tot = [top_ob, bot_ob, top_ib, bot_ib]
    string_name = ["top_OB", "bot_OB", "top_IB", "bot_IB"]

    return string_tot, string_name, string_tot_div, string_name_div


def read_spms(spms_dict: dict):
    """
    Build two lists for IN and OUT spms.

    Parameters
    ----------
    spms_dict
               Contains info (crate, card, ch_orca, barrel, det_name) for spms
    """
    top_ob = []
    bot_ob = []
    top_ib = []
    bot_ib = []

    # loop over spms channels (i.e. channels w/ crate=2)
    for ch in list(spms_dict.keys()):
        # card = spms_dict[ch]["daq"]["card"]
        # ch_orca = spms_dict[ch]["daq"]["ch_orca"]
        spms_type = spms_dict[ch]["barrel"]
        det_name_int = int(spms_dict[ch]["det_id"].split("S")[1])

        if spms_type == "OB" and det_name_int % 2 != 0:
            top_ob.append(ch)
        if spms_type == "OB" and det_name_int % 2 == 0:
            bot_ob.append(ch)
        if spms_type == "IB" and det_name_int % 2 != 0:
            top_ib.append(ch)
        if spms_type == "IB" and det_name_int % 2 == 0:
            bot_ib.append(ch)

    string_tot = [top_ob, bot_ob, top_ib, bot_ib]
    string_name = ["top_OB", "bot_OB", "top_IB", "bot_IB"]

    return string_tot, string_name, string_tot, string_name


def load_dsp_files(time_cut: list[str], start_code: str):
    """
    Load dsp files applying the time cut over filenames.

    Parameters
    ----------
    time_cut
                List with info about time cuts
    start_code
                Starting time of the code
    """
    path = files_path + version + "/generated/tier"
    avail_runs = os.listdir(path + "/dsp/" + datatype + "/" + period)

    full_paths = []
    # load files of all runs (there is no enabled run(s) selection)
    if run == "":
        for avail_run in avail_runs:
            full_paths.append(os.path.join(path, "dsp", datatype, period, avail_run))
    # run(s) selection is enabled
    else:
        if isinstance(run, str):
            full_paths.append(os.path.join(path, "dsp", datatype, period, run))
        if isinstance(run, list):
            for r in run:
                full_paths.append(os.path.join(path, "dsp", datatype, period, r))

    # get list of lh5 files in chronological order
    lh5_files = []
    for full_path in full_paths:
        for lh5_file in os.listdir(full_path):
            lh5_files.append(lh5_file)

    lh5_files = sorted(
        lh5_files,
        key=lambda file: int(
            ((file.split("-")[4]).split("Z")[0]).split("T")[0]
            + ((file.split("-")[4]).split("Z")[0]).split("T")[1]
        ),
    )

    # keep 'cal' or 'phy' data
    loaded_files = [f for f in lh5_files if datatype in f]

    # get time cuts info
    time_cut = timecut.build_timecut_list(time_window, last_hours)

    # keep some keys (if specified)
    if len(time_cut) == 0 and file_keys != "":
        # it's a file of keys; let's convert it into a list
        if isinstance(file_keys, list):
            list_keys = file_keys
        else:
            with open(file_keys) as f:
                lines = f.readlines()
            list_keys = [line.strip("\n") for line in lines]
        loaded_files = [f for f in loaded_files for k in list_keys if k in f]

    # apply time cut to lh5 filenames
    if len(time_cut) == 3:
        loaded_files = timecut.cut_below_threshold_filelist(
            full_path, loaded_files, time_cut, start_code
        )
    if len(time_cut) == 4:
        loaded_files = timecut.cut_min_max_filelist(full_path, loaded_files, time_cut)

    # get full file paths
    lh5_files = []
    for lh5_file in loaded_files:
        run_no = lh5_file.split("-")[-4]
        lh5_files.append(os.path.join(path, "dsp", datatype, period, run_no, lh5_file))

    dsp_files = []
    for lh5_file in lh5_files:
        if os.path.isfile(lh5_file.replace("dsp", "hit")):
            dsp_files.append(lh5_file)

    if len(dsp_files) == 0:
        if verbose is True:
            logging.error("There are no files to inspect!")
            sys.exit(1)

    return dsp_files


def get_files_timestamps(time_cut: list[str], start_code: str):
    """
    Get the first and last timestamps of the time range of interest.

    Parameters
    ----------
    time_cut
                List with info about time cuts
    start_code
                Starting time of the code
    """
    if time_window["enabled"] is True or last_hours["enabled"] is True:
        if run == "" and file_keys == "":
            first_timestamp, last_timestamp = timecut.time_dates(time_cut, start_code)
        else:
            logging.error("Too many time selections are enabled, pick one!")
            sys.exit(1)

    if time_window["enabled"] is False and last_hours["enabled"] is False:
        if run != "" and file_keys != "":
            logging.error("Too many time selections are enabled, pick one!")
            sys.exit(1)

        # (run(s) selection OR everything ) || (keys selection)
        if ((run != "" and file_keys == "") or (run == "" and file_keys == "")) or (
            run == "" and file_keys != ""
        ):
            files = load_dsp_files(time_cut, start_code)
            first_file = files[0]
            last_file = files[-1]
            first_timestamp = ((first_file.split("/")[-1]).split("-"))[4]
            last_timestamp = (
                lh5.load_nda(last_file, ["timestamp"], "ch000/dsp")["timestamp"]
            )[
                -1
            ] - 2 * 60 * 60  # in seconds (2h shift)
            last_timestamp = datetime.fromtimestamp(last_timestamp).strftime(
                "%Y%m%dT%H%M%SZ"
            )

    return [first_timestamp, last_timestamp]


def check_par_values(
    times_average: np.ndarray,
    par_average: np.ndarray,
    parameter: str,
    detector: str,
    det_type: str,
):
    """
    Check parameter values.

    Parameters
    ----------
    times_average
                   Array with x-axis time average values
    par_average
                   Array with y-axis parameter average values
    parameter
                   Name of the parameter to plot
    detector
                   Channel of the detector
    det_type
                   Type of detector (geds or spms)
    """
    low_lim = j_par[0][parameter]["limit"][det_type][0]
    upp_lim = j_par[0][parameter]["limit"][det_type][1]
    units = j_par[0][parameter]["units"]
    thr_flag = 0

    idx = 0
    while idx + 1 < len(par_average):
        # value below the threshold
        if low_lim != "null":
            if par_average[idx] < low_lim:
                thr_flag = 1  # problems!
                j = 0
                time1 = datetime.fromtimestamp(times_average[idx]).strftime(
                    "%d/%m %H:%M:%S"
                )
                while par_average[idx + j] < low_lim and idx + j + 1 < len(par_average):
                    j = j + 1
                idx = idx + j - 1
                time2 = datetime.fromtimestamp(times_average[idx]).strftime(
                    "%d/%m %H:%M:%S"
                )
                if time1 == time2:
                    logging.debug(
                        f' "{parameter}"<{low_lim} {units} (at {time1}) for ch={detector}'
                    )
                else:
                    logging.debug(
                        f' "{parameter}"<{low_lim} {units} ({time1} -> {time2}) for ch={detector}'
                    )
            idx = idx + 1
        # value above the threshold
        if upp_lim != "null":
            if par_average[idx] > upp_lim:
                thr_flag = 1  # problems!
                j = 0
                time1 = datetime.fromtimestamp(times_average[idx]).strftime(
                    "%d/%m %H:%M:%S"
                )
                while par_average[idx + j] > upp_lim and idx + j + 1 < len(par_average):
                    j = j + 1
                idx = idx + j - 1
                time2 = datetime.fromtimestamp(times_average[idx]).strftime(
                    "%d/%m %H:%M:%S"
                )
                if time1 == time2:
                    logging.debug(
                        f' "{parameter}">{upp_lim} {units} (at {time1}) for ch={detector}'
                    )
                else:
                    logging.debug(
                        f' "{parameter}">{upp_lim} {units} ({time1} -> {time2}) for ch={detector}'
                    )
            idx = idx + 1
        # value within the limits
        else:
            idx = idx + 1

    return thr_flag


def time_analysis(
    utime_array: np.ndarray, par_array: np.ndarray, time_cut: list[str], start_code: str
):
    """
    Return the timestamp & parameter lists after the time cuts.

    Parameters
    ----------
    utime_array
                Array of (already shifted) timestamps
    par_array
                Array with parameter values
    time_cut
                List with info about time cuts
    start_code
                Starting time of the code
    """
    # time window analysis
    if len(time_cut) == 4:
        start_index, end_index = timecut.min_max_timestamp_thr(
            utime_array.tolist(),
            time_cut[0] + " " + time_cut[1],
            time_cut[2] + " " + time_cut[3],
        )
        # to handle particular cases where the timestamp array is outside the time window:
        if end_index != end_index or start_index != start_index:
            return [], []
        if len(utime_array) != 0:
            utime_array = timecut.cut_array_in_min_max(
                utime_array, start_index, end_index
            )
        if len(par_array) != 0:
            par_array = timecut.cut_array_in_min_max(par_array, start_index, end_index)
    # last X hours analysis
    if len(time_cut) == 3:
        start_index = timecut.min_timestamp_thr(
            utime_array.tolist(), time_cut, start_code
        )
        end_index = timecut.max_timestamp_thr(
            utime_array.tolist(), time_cut, start_code
        )
        if len(utime_array) != 0:
            utime_array = utime_array[start_index:end_index]
        if len(par_array) != 0:
            par_array = par_array[start_index:end_index]

    return utime_array, par_array


def get_pulser_timestamps(query: str):

    parameters = ["wf_max", "baseline", "timestamp"]

    dbconfig_filename, dlconfig_filename = write_config(
        files_path, version, [["ch001"]], parameters, "ch001"
    )

    ch1_data = read_from_dataloader(
        dbconfig_filename, dlconfig_filename, query, parameters
    )

    wf_max = ch1_data["wf_max"]
    baseline = ch1_data["baseline"]
    timestamps = ch1_data["timestamp"]

    wf_max = np.subtract(wf_max, baseline)

    high_thr = 12500

    above_threshold_ts = timestamps[wf_max > high_thr]

    return above_threshold_ts


def get_puls_ievt(query: str):
    """
    Select pulser events.

    Parameters
    ----------
    query
            Cut over files
    """
    parameters = ["wf_max", "baseline"]
    # dbconfig_filename, dlconfig_filename = write_config(
    #     files_path, version, [["ch000"]], parameters, "ch000"
    # )
    dbconfig_filename, dlconfig_filename = write_config(
        files_path, version, [["ch001"]], parameters, "ch001"
    )
    ch0_data = read_from_dataloader(
        dbconfig_filename, dlconfig_filename, query, parameters
    )

    wf_max = ch0_data["wf_max"]
    baseline = ch0_data["baseline"]

    wf_max = np.subtract(wf_max, baseline)
    puls_ievt = []
    pulser_entry = []
    not_pulser_entry = []
    high_thr = 12500
    # high_thr = 20000

    for idx, entry in enumerate(wf_max):
        puls_ievt.append(idx)
        if entry > high_thr:
            pulser_entry.append(idx)
        if entry < high_thr:
            not_pulser_entry.append(idx)

    # pulser+physical events
    puls_ievt = np.array(puls_ievt)
    # HW pulser+FC entries
    puls_only_ievt = puls_ievt[np.isin(puls_ievt, pulser_entry)]
    # physical entries
    not_puls_ievt = puls_ievt[np.isin(puls_ievt, not_pulser_entry)]

    return puls_ievt, puls_only_ievt, not_puls_ievt


def get_puls_ievt_spms(dsp_files: list[str]):
    """
    Select pulser events for spms only.

    Parameters
    ----------
    dsp_files
            List of dsp files
    """
    wf_max = lh5.load_nda(dsp_files, ["wf_max"], "ch000/dsp/")["wf_max"]
    baseline = lh5.load_nda(dsp_files, ["baseline"], "ch000/dsp")["baseline"]
    wf_max = np.subtract(wf_max, baseline)
    puls_ievt = []
    pulser_entry = []
    not_pulser_entry = []
    high_thr = 12500

    for idx, entry in enumerate(wf_max):
        puls_ievt.append(idx)
        if entry > high_thr:
            pulser_entry.append(idx)
        if entry < high_thr:
            not_pulser_entry.append(idx)

    # pulser+physical events
    puls_ievt = np.array(puls_ievt)
    # HW pulser+FC entries
    puls_only_ievt = puls_ievt[np.isin(puls_ievt, pulser_entry)]
    # physical entries
    not_puls_ievt = puls_ievt[np.isin(puls_ievt, not_pulser_entry)]

    return puls_ievt, puls_only_ievt, not_puls_ievt


def get_qc_ievt(
    quality_index: np.array,
    keep_evt_index: np.array,
):
    """
    Apply quality cuts to parameter/time arrays.

    Parameters
    ----------
    quality_index
                    Quality cuts, event by event
    keep_evt_index
                    Event number for either high energy pulser or physical events
    """
    if keep_evt_index != []:
        quality_index = quality_index[keep_evt_index]

    return quality_index


def remove_nan(par_array: np.ndarray, time_array: np.ndarray):
    """
    Remove NaN values from arrays.

    Parameters
    ----------
    par_array
                 Array with parameter values
    time_array
                 Array with time values
    """
    par_array_no_nan = par_array[~np.isnan(par_array)]
    time_array_no_nan = time_array[~np.isnan(par_array)]
    return par_array_no_nan, time_array_no_nan
    # return np.asarray(par_array_no_nan), np.asarray(time_array_no_nan)


def avg_over_entries(par_array: np.ndarray, time_array: np.ndarray):
    """
    Evaluate the average over N entries in arrays.

    Parameters
    ----------
    par_array
                 Array with parameter values
    time_array
                 Array with time values
    """
    par_avg = []
    time_avg = []

    step = round(((time_array[-1] - time_array[0]) * 6) / (4 * 60 * 60))
    i = 0

    while (i + 1) * step < len(par_array):
        total = 0
        tot_time = 0
        for entry in range(i * step, (i + 1) * step):
            total += par_array[entry]
            tot_time += time_array[entry]
        par_avg.append(total / step)
        if i == 0:
            time_avg.append(time_array[0])
        else:
            time_avg.append(tot_time / step)
        i += 1
    time_avg[-1] = time_array[-1]

    return par_avg, time_avg


def avg_over_minutes(par_array: np.ndarray, time_array: np.ndarray):
    """
    Evaluate the average over N minutes. It is used in plots, together with all entries for spotting potential trends in data.

    Parameters
    ----------
    par_array
                 Array with parameter values
    time_array
                 Array with time values
    """
    par_avg = []
    time_avg = []

    dt = j_config[7]["avg_interval"] * 60  # minutes in seconds
    start = time_array[0]
    end = time_array[-1]

    t = start
    while t <= end:
        time_avg.append(t)
        tot = 0
        j = 0
        for idx, entry in enumerate(par_array):
            if time_array[idx] >= t and time_array[idx] < t + dt:
                tot += entry
                j += 1
        if j != 0:
            par_avg.append(tot / j)
        else:
            par_avg.append(np.nan)
        t += dt

    iniz = 0
    i = 0
    while i < len(time_array) - 1:
        if t - dt >= time_array[i] and t - dt <= time_array[i + 1]:
            iniz = i
        i += 1

    # add last point at the end of the selected time window
    time_avg.append(end)
    par_avg.append(np.mean(par_array[iniz:-1]))

    return par_avg, time_avg


def get_mean(
    par_array: np.ndarray | pd.core.series.Series,
    time_array: np.ndarray | pd.core.series.Series,
    parameter: str,
    detector: str,
):
    """
    Evaluate the average over first files/hours. It is used when we want to show the percentage variation of a parameter with respect to its average value.

    Parameters
    ----------
    parameter
                Parameter to plot
    detector
                Name of the detector
    """
    # output path with json files
    out_path = output
    json_path = os.path.join(out_path, "json-files")

    # defining json file name for this run
    run_name = ""
    if isinstance(run, str):
        run_name = run
    elif isinstance(run, list):
        for r in run:
            run_name = run_name + r + "-"
        run_name = run_name[:-1]

    jsonfile_name = f"{exp}-{period}-{run_name}-{datatype}.json"

    # list with all the files already saved in out/json_files directory
    file_list = os.listdir(json_path)

    # if file already exists, open it and get mean for detector/parameter
    if jsonfile_name in file_list:
        with open(json_path + "/" + jsonfile_name) as file:
            mydict = json.load(file)
            mean = mydict[detector][parameter]
            mean = float(mean)
    else:
        # whatever the time length, compute mean over 1h of data
        first_hour_indices = np.where(time_array < time_array[0] + 3600)
        par_array = par_array[first_hour_indices]
        mean = np.mean(par_array)

    return mean


def set_pkl_name(
    exp: str,
    period: str,
    datatype: str,
    det_type: str,
    string_number: str,
    parameter: str,
    time_range: list[str],
):
    """
    Set the pkl file's name.

    Parameters
    ----------
    exp
            Experiment info (eg. l60)
    period
            Period info (eg. p01)
    run
            Run number
    datatype
            Either 'cal' or 'phy'
    det_type
            Type of detector (geds, spms or ch000)
    string_number
            Number of the string under study
    parameter
            Parameter to plot
    time_range
            First and last timestamps of the time range of interest
    """
    pkl_name = (
        exp
        + "-"
        + period
        + "-"
        + datatype
        + "-"
        + time_range[0]
        + "_"
        + time_range[1]
        + "-"
        + parameter
    )

    if det_type == "geds":
        pkl_name += "-S" + string_number + ".pkl"
    if det_type == "spms":
        pkl_name += "-" + string_number + ".pkl"
    if det_type == "ch000":
        pkl_name += "-ch000.pkl"

    return pkl_name
