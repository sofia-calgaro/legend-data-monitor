from __future__ import annotations

import importlib.resources
import json
import logging
import os
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pygama.lgdo.lh5_store as lh5
from pygama.flow import DataLoader, FileDB

from . import timecut

pkg = importlib.resources.files("legend_data_monitor")


def read_json_files():
    """Read json files of 'settings/' folder and return three lists."""
    with open(pkg / ".." / ".." / "config.json") as f:
        data_config = json.load(f)
    with open(pkg / "settings" / "par-settings.json") as g:
        data_par = json.load(g)
    with open(pkg / "settings" / "plot-settings.json") as h:
        data_plot = json.load(h)
    j_config = []
    j_par = []
    j_plot = []

    j_config.append(data_config["run_info"])    # 0
    j_config.append(data_config["period"])      # 1
    j_config.append(data_config["run"])         # 2
    j_config.append(data_config["file_list"])   # 3
    j_config.append(data_config["datatype"])    # 4
    j_config.append(data_config["det_type"])    # 5
    j_config.append(data_config["par_to_plot"]) # 6
    j_config.append(data_config["plot_style"])  # 7
    j_config.append(data_config["time_window"]) # 8
    j_config.append(data_config["last_hours"])  # 9
    j_config.append(data_config["status"])      # 10
    j_config.append(data_config["time-format"]) # 11
    j_config.append(data_config["verbose"])     # 12

    j_par.append(data_par["par_to_plot"])  # 0

    j_plot.append(data_plot["spms_name_dict"])  # 0
    j_plot.append(data_plot["geds_name_dict"])  # 1
    j_plot.append(data_plot["spms_col_dict"])   # 2
    j_plot.append(data_plot["geds_col_dict"])   # 3

    return j_config, j_par, j_plot


j_config, j_par, j_plot = read_json_files()
files_path = j_config[0]["path"]["lh5-files"]
version = j_config[0]["path"]["version"]
period = j_config[1]
run = j_config[2]
filelist = j_config[3]
datatype = j_config[4]
keep_puls_pars = j_config[6]["pulser"]["keep_puls_pars"]
keep_phys_pars = j_config[6]["pulser"]["keep_phys_pars"]


def write_config(files_path: str, version: str, det_map: list[list[str]], parameters: list[str], det_type: str):

    if '0' in det_type: 
        det_list = [0]
        dict_dbconfig = {
            "data_dir" : files_path + version + "/generated/tier",
            "tier_dirs": {
                "dsp": "/dsp"
            },
            "file_format": {
                "dsp": "/phy/{period}/{run}/{exp}-{period}-{run}-phy-{timestamp}-tier_dsp.lh5"
            },
            "table_format": {
                "dsp": "ch{ch:03d}/dsp"
            },
            "tables": {
                "dsp": det_list
            },
            "columns": {
            "dsp": parameters
            }
        }
        dict_dlconfig = {
            "levels": {
                "dsp":{
                    "tiers": ["dsp"]    
                }
            },
            "channel_map": {}
        }
    else:
        # flattening list[list[str]] to list[str]
        flat_list = [subl for l in det_map for subl in l]

        # converting channel number to int to give array as input to FileDB
        det_list = [int(l.split("ch0")[-1]) for l in flat_list]
    
        dsp_list = det_list.copy()
        hit_list = det_list.copy()
        
        # removing channels having no hit data
        for ch in [24, 10, 41]:
            hit_list.remove(ch)

        dict_dbconfig = {
            "data_dir" : files_path + version + "/generated/tier",
            "tier_dirs": {
                "dsp": "/dsp",
                "hit": "/hit"
            },
            "file_format": {
                "dsp": "/phy/{period}/{run}/{exp}-{period}-{run}-phy-{timestamp}-tier_dsp.lh5",
                "hit": "/phy/{period}/{run}/{exp}-{period}-{run}-phy-{timestamp}-tier_hit.lh5"
            },
            "table_format": {
                "dsp": "ch{ch:03d}/dsp",
                "hit": "ch{ch:03d}/hit"
            },
            "tables": {
                "dsp": dsp_list,
                "hit": hit_list
            },
            "columns": {
            "dsp": parameters,
            "hit": parameters
            }
        }
        dict_dlconfig = {
            "levels": {
                "hit":{
                    "tiers": ["dsp","hit"]    
                }
            },
            "channel_map": {}
        }

    # Serializing json
    json_dbconfig = json.dumps(dict_dbconfig, indent=4)
    json_dlconfig = json.dumps(dict_dlconfig, indent=4)

    # Writing to sample.json
    dbconfig_filename = "dbconfig_" + det_type + ".json"
    dlconfig_filename = "dlconfig_" + det_type + ".json"

    # Writing FileDB config file 
    with open(dbconfig_filename, "w") as outfile:
        outfile.write(json_dbconfig)

    # Writing DataLoader config file
    with open(dlconfig_filename, "w") as outfile:
        outfile.write(json_dlconfig)

    return dbconfig_filename, dlconfig_filename


def read_from_dataloader(
    dbconfig: str,
    dlconfig: str,
    query: str | list[str],
    parameters: list[str]
    ):

    dl = DataLoader(dlconfig, dbconfig)
    dl.set_files(query)
    dl.set_output(fmt="pd.DataFrame", columns = parameters)
    
    return dl.load()


def set_query(time_cut: list, start_code: str, run: str|list[str]):
    
    query = ""

    # Reading from file
    if filelist:
        with open(filelist) as f:
            lines = f.readlines()
        lines = [line.strip('\n') for line in lines]
        query = lines

    # Applying time cut
    if len(time_cut) > 0:
        start, stop = timecut.time_dates(time_cut, start_code)
        start_datetime = datetime.strptime(start, "%Y%m%dT%H%M%SZ")
        start_datetime = start_datetime - timedelta(minutes = 120)
        start = start_datetime.strftime("%Y%m%dT%H%M%SZ")
        query = query + f"timestamp > '{start}' and timestamp < '{stop}'"

    # Applying run cut
    if run:
        query = query + " and "
        if isinstance(run, str):
            query = query + f"run == '{run}'"
        elif isinstance(run, list):
            for r in run:
                query = query + f"run == '{r}' or "     
            # Just the remove the final 'or'
            query = query[:-4]

    if query == "" :
        logging.error(
        'Empty query.\nProvide at least a run name, a time interval of a list of files to open.'
    )
    return query


def load_geds():
    """Load channel map for geds."""
    config_path = j_config[0]["path"]["geds-config"]
    with open(config_path) as d:
        channel_map = json.load(d)
    geds_dict = channel_map["hardware_configuration"]["channel_map"]

    return geds_dict


def load_spms(raw_files: list[str]):
    """Load channel map for spms."""
    config_path = j_config[0]["path"]["spms-config"]
    with open(config_path) as d:
        channel_map = json.load(d)
    spms_dict = channel_map

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
    min_str = int(min(str_no))
    max_str = int(max(str_no))
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
            pos, string = (list(t) for t in zip(*sorted(zip(pos, string))))
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


def add_offset_to_timestamp(tmp_array: np.ndarray, dsp_file: list[str]):
    """
    Add a time shift to the filename given by the time shown in 'runtime'.

    Parameters
    ----------
    tmp_array
                Time since beginning of file
    dsp_file
                lh5 dsp file
    """
    date_time = (((dsp_file.split("/")[-1]).split("-")[4]).split("Z")[0]).split("T")
    date = date_time[0]
    time = date_time[1]
    run_start = datetime.strptime(date + time, "%Y%m%d%H%M%S")
    utime_array = tmp_array + np.full(tmp_array.size, run_start.timestamp())

    return utime_array


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
            utime_array = timecut.cut_array_in_min_max(utime_array, start_index, end_index)
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


def get_puls_ievt(query: str):
    """
    Select pulser events.

    Parameters
    ----------
    dsp_files
               lh5 dsp file
    """
    
    parameters = ["wf_max", "baseline"]
    dbconfig_filename, dlconfig_filename = write_config(files_path, version,[["ch00"]], parameters, "ch00")
    ch0_data = read_from_dataloader(dbconfig_filename, dlconfig_filename, query, parameters)
    
    wf_max = ch0_data["wf_max"]
    baseline = ch0_data["baseline"]

    wf_max = np.subtract(wf_max, baseline)
    puls_ievt = []
    pulser_entry = []
    not_pulser_entry = []
    high_thr = 12500

    for idx, entry in enumerate(wf_max):
        puls_ievt.append(idx)
        if entry > high_thr:
            pulser_entry.append(idx)
        else:
            not_pulser_entry.append(idx)

    # pulser+physical events
    puls_ievt = np.array(puls_ievt)
    # HW pulser+FC entries
    puls_only_ievt = puls_ievt[np.isin(puls_ievt, pulser_entry)]
    # physical entries
    not_puls_ievt = puls_ievt[np.isin(puls_ievt, not_pulser_entry)]

    return puls_ievt, puls_only_ievt, not_puls_ievt


def get_qc_ievt(
    hit_files: list,
    detector: str,
    keep_evt_index: np.array,
):
    """
    Apply quality cuts to parameter/time arrays.

    Parameters
    ----------
    hit_files
                lh5 hit files
    detector
                Name of the detector
    keep_evt_index
                Event number for either high energy pulser or physical events
    """
    quality_index = lh5.load_nda(hit_files, ["Quality_cuts"], detector + "/hit")[
        "Quality_cuts"
    ]

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
    print("Inizio: ", type(par_array))
    par_array_no_nan = par_array[~np.isnan(par_array)]
    time_array_no_nan = time_array[~np.isnan(par_array)]
    print("Fine: ", type(par_array))
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


def get_mean(parameter: str, detector: str):
    """
    Evaluate the average over first files/hours. It is used when we want to show the percentage variation of a parameter with respect to its average value.

    Parameters
    ----------
    parameter
                Parameter to plot
    detector
                Name of the detector
    """
    input_dsp = files_path + version + "/inputs/config/tier_dsp/"
    input_hit = files_path + version + "/inputs/config/tier_hit/"
    config_dsp = os.listdir(input_dsp)
    config_hit = os.listdir(input_hit)
    config_dsp = [input_dsp + f for f in config_dsp if "ICPC" in f][0]
    config_hit = [input_hit + f for f in config_hit if "ICPC" in f][0]
    with open(config_dsp) as d:
        outputs_dsp = json.load(d)
    dsp_pars = outputs_dsp["outputs"]
    with open(config_hit) as h:
        outputs_hit = json.load(h)
    hit_pars = outputs_hit["outputs"]
    # get the parameter's tier
    if parameter in dsp_pars:
        file_type = "dsp"
    if parameter in hit_pars:
        file_type = "hit"

    # get the path of files for a given parameter, depending if it belongs to the dsp or hit tier
    file_path = (
        files_path
        + version
        + "/generated/tier/"
        + file_type
        + "/"
        + datatype
        + "/"
        + period
        + "/"
        + run
        + "/"
    )

    # get list of lh5 files in chronological order
    lh5_files = os.listdir(file_path)
    lh5_files = sorted(
        lh5_files,
        key=lambda file: int(
            ((file.split("-")[4]).split("Z")[0]).split("T")[0]
            + ((file.split("-")[4]).split("Z")[0]).split("T")[1]
        ),
    )
    lh5_files = [file_path + f for f in lh5_files]

    par_array = lh5.load_nda(lh5_files, [parameter], detector + "/" + file_type)[
        parameter
    ]
    # apply selection of pulser/physical events
    all_ievt, puls_only_ievt, not_puls_ievt = get_puls_ievt()
    if all_ievt != [] and puls_only_ievt != [] and not_puls_ievt != []:
        det_only_index = np.isin(all_ievt, not_puls_ievt)
        puls_only_index = np.isin(all_ievt, puls_only_ievt)
        if parameter in keep_puls_pars:
            par_array = par_array[puls_only_index]
        if parameter in keep_phys_pars:
            par_array = par_array[det_only_index]

    # use the first file (about 1h long) to compute the mean of a parameter
    len_first = len(
        lh5.load_nda(lh5_files[0], [parameter], detector + "/" + file_type)[parameter]
    )
    par_array_mean = np.mean(par_array[:len_first])

    return par_array_mean


def set_pkl_name(
    exp, period, run, datatype, det_type, string_number, parameter, time_cut, start_code, start_name, end_name
):
    """
    Set the pkl filename.

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
            Type of detector (geds or spms)
    string_number
            Number of the string under study
    parameter
            Parameter to plot
    time_cut
            List with info about time cuts
    start_code
            Starting time of the code
    start_name
            String with timestamp of first event
    end_name
            String with timestamp of last event        
    """
    run_name = ""
    if isinstance(run, str):
        run_name = run
    elif isinstance(run, list):
        for r in run:
            run_name = run_name + r + "-"
    run_name = run_name[:-1]

    if run:
    # define name of pkl file (with info about time cut if present)
        if len(time_cut) != 0:
            start, end = timecut.time_dates(time_cut, start_code)
            pkl_name = exp + "-" + period + "-" + run + "-" + datatype + "-" + start + "_" + end + "-" + parameter
        else:
            pkl_name = exp + "-" + period + "-" + run_name + "-" + start_name + "-" + end_name + "-" + datatype + "-" + parameter
        if det_type == "geds":
            pkl_name += "-string" + string_number + ".pkl"
        if det_type == "spms":
            pkl_name += "-" + string_number + ".pkl"
    else:
        if len(time_cut) != 0:
            start, end = timecut.time_dates(time_cut, start_code)
            pkl_name = exp + "-" + period + "-" + datatype + "-" + start + "_" + end + "-" + parameter
        else:
            pkl_name = exp + "-" + period + "-" + datatype + "-" + start_name + "-" + end_name + "-" + parameter
        if det_type == "geds":
            pkl_name += "-string" + string_number + ".pkl"
        if det_type == "spms":
            pkl_name += "-" + string_number + ".pkl"

    return pkl_name
