import importlib.resources
import os
import json
import logging
from datetime import datetime

import numpy as np
import pygama.lgdo.lh5_store as lh5
from pygama.lgdo import LH5Store
from pygama.raw.orca import orca_streamer

from . import timecut

pkg = importlib.resources.files("legend_data_monitor")


def read_json_files():
    """Read json files of 'settings/' folder and return three lists."""
    with open("config.json") as f:
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
    j_config.append(data_config["datatype"])  # 3
    j_config.append(data_config["det_type"])  # 4
    j_config.append(data_config["par_to_plot"])  # 5
    j_config.append(data_config["time_slice"])  # 6
    j_config.append(data_config["time_window"])  # 7
    j_config.append(data_config["last_hours"])  # 8
    j_config.append(data_config["status"])  # 9
    j_config.append(data_config["time-format"])  # 10
    j_config.append(data_config["verbose"])  # 11

    j_par.append(data_par["par_to_plot"])  # 0

    j_plot.append(data_plot["spms_name_dict"])  # 0
    j_plot.append(data_plot["geds_name_dict"])  # 1
    j_plot.append(data_plot["spms_col_dict"])  # 2
    j_plot.append(data_plot["geds_col_dict"])  # 3

    return j_config, j_par, j_plot


j_config, j_par, j_plot = read_json_files()


def load_channels(raw_files):
    """
    Load channel map.

    Description
    -----------
    Return 3 dictionaries for geds/spms/other (pulser, aux)
    containing info about the crate, card, and orca channel.

    Parameters
    ----------
    raw_files : list
                Strings of lh5 raw files
    """
    channels = lh5.ls(raw_files[0], '')
    filename = os.path.basename(raw_files[0])
    fn_split = filename.split("-")
    orca_name = f'{fn_split[0]}-{fn_split[1]}-{fn_split[2]}-{fn_split[3]}-{fn_split[4]}.orca'
    data_type = fn_split[3]
    orca_path = j_config[0]['path']['orca-files']
    period = j_config[1]
    run = j_config[2]
    orca_file = f'{orca_path}{data_type}/{period}/{run}/{orca_name}'
    orstr = orca_streamer.OrcaStreamer();
    orstr.open_stream(orca_file)
    channel_map = json.loads(orstr.header["ObjectInfo"]["ORL200Model"]["DetectorMap"])
    store = LH5Store()

    geds_dict  = {}
    spms_dict  = {}
    other_dict = {}
    ch_dict = {}

    for ch in channels:
        crate   = store.read_object(f'{ch}/raw/crate', raw_files[0])[0].nda[0]
        card    = store.read_object(f'{ch}/raw/card', raw_files[0])[0].nda[0]
        ch_orca = store.read_object(f'{ch}/raw/ch_orca', raw_files[0])[0].nda[0]
        daq_dict = {}
        daq_dict['crate']   = crate
        daq_dict['card']    = card
        daq_dict['ch_orca'] = ch_orca

        if crate==0:
            for det, entry in channel_map.items():
                if entry['daq']['crate']==f'{crate}' and entry['daq']['board_slot']==f'{card}' and entry['daq']['board_ch']==f'{ch_orca}':
                    string_dict = {}
                    string_dict['number']   = entry['string']['number']
                    string_dict['position'] = entry['string']['position']

                    geds_dict[ch] = { "system": "ged", "det": det, "string": string_dict, "daq": daq_dict }

        if crate==1: other_dict[ch] = { "system": "--" , "daq": daq_dict }
        if crate==2: spms_dict[ch]  = { "system": "spm", "daq": daq_dict }

    return geds_dict, spms_dict, other_dict


def read_geds(geds_dict):
    """
    Build an array of germanium strings.

    Parameters
    ----------
    geds_dict: dictionary
               Contains info (crate, card, ch_orca) for geds
    """
    geds_list = list(geds_dict.keys())
    string_tot  = []
    string_name = []

    # no of strings
    str_no = [v['string']['number'] for k,v in geds_dict.items() if v['string']['number']!='--']
    min_str = int(min(str_no))
    max_str = int(max(str_no))
    idx = min_str

    # fill lists with strings of channels ('while' loop over no of string)
    while idx<=max_str:
        string = [k for k,v in geds_dict.items() if v['string']['number'] == str(idx)]
        pos = []
        for k1,v1 in geds_dict.items():
          for k2,v2 in v1.items():
            if k2=='string':
              for k3,v3 in v2.items():
                  if k3=='position' and v1['string']['number'] == str(idx):
                     pos.append(v3)

        if len(string)==0:
           idx += 1
        else:
           # order channels within a string
           pos, string = (list(t) for t in zip(*sorted(zip(pos, string))))
           string_tot.append(string)
           string_name.append(f'{idx}')
           idx += 1

    return string_tot, string_name


def read_spms(spms_dict):
    """
    Build two lists for IN and OUT spms.

    Parameters
    ----------
    spms_dict: dictionary
               Contains info (crate, card, ch_orca) for spms
    """
    spms_map = json.load(open(pkg / "settings" / "spms_map.json"))
    top_OB = []
    bot_OB = []
    top_IB = []
    bot_IB = []

    # loop over spms channels (i.e. channels w/ crate=2)
    for ch in list(spms_dict.keys()):
        card    = spms_dict[ch]['daq']['card']
        ch_orca = spms_dict[ch]['daq']['ch_orca']
    
        idx = '0'
        for serial in list(spms_map.keys()):
            if spms_map[serial]['card']==card and spms_map[serial]['ch_orca']==ch_orca: 
                idx = str(serial)
        if idx=='0': continue

        spms_type = spms_map[idx]['type']
        spms_pos  = spms_map[idx]['pos']
        if spms_type=='OB' and spms_pos=='top': top_OB.append(ch)
        if spms_type=='OB' and spms_pos=='bot': bot_OB.append(ch)
        if spms_type=='IB' and spms_pos=='top': top_IB.append(ch)
        if spms_type=='IB' and spms_pos=='bot': bot_IB.append(ch)

    
    half_len_topOB = int(len(top_OB)/2)
    half_len_botOB = int(len(bot_OB)/2)
    top_OB_1 = top_OB[half_len_topOB:]
    top_OB_2 = top_OB[:half_len_topOB]
    bot_OB_1 = bot_OB[half_len_botOB:]
    bot_OB_2 = bot_OB[:half_len_botOB]
    string_tot_div = [top_OB_1, top_OB_2, bot_OB_1, bot_OB_2, top_IB, bot_IB]
    string_name_div = ["top_OB (1)", "top_OB (2)", "bot_OB (1)", "bot_OB (2)", "top_IB", "bot_IB"]
    
    string_tot = [top_OB, bot_OB, top_IB, bot_IB]
    string_name = ["top_OB", "bot_OB", "top_IB", "bot_IB"]

    return string_tot, string_name, string_tot_div, string_name_div


def check_par_values(times_average, par_average, parameter, detector, det_type):
    """
    Check parameter values.

    Description
    -----------
    Check if a given parameter is above or below a given threshold. If this
    happens, the corresponding UTC interval time at which this happens is recorded
    in the .log file as a WARNING together with the parameter and detector names.


    Parameters
    ----------
    times_average: array
                   Array with x-axis time average values
    par_average  : array
                   Array with y-axis parameter average values
    parameter    : string
                   Name of the parameter to plot
    detector     : string
                   Channel of the detector
    det_type     : string
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
                    logging.warning(
                        f' "{parameter}"<{low_lim} {units} (at {time1}) for ch={detector}'
                    )
                else:
                    logging.warning(
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
                    logging.warning(
                        f' "{parameter}">{upp_lim} {units} (at {time1}) for ch={detector}'
                    )
                else:
                    logging.warning(
                        f' "{parameter}">{upp_lim} {units} ({time1} -> {time2}) for ch={detector}'
                    )
            idx = idx + 1
        # value within the limits
        else:
            idx = idx + 1

    return thr_flag


def build_utime_array(raw_files, detector, det_type):
    """
    Return an array with shifted time arrays for geds detectors.

    Parameters
    ----------
    raw_files : list
                Strings of lh5 raw files
    detector  : string
                Channel of the detector
    det_type  : string
                Type of detector (geds or spms)
    """
    if det_type == "spms":
        utime_array = load_shifted_times(raw_files, "spms", detector)
    if det_type == "geds":
        utime_array = load_shifted_times(raw_files, "geds", detector)

    return utime_array


def load_shifted_times(raw_files, det_type, detector):
    """
    Return an array with shifted time arrays for spms detectors.

    Parameters
    ----------
    raw_files    : list/string
                   Strings of lh5 raw files
    det_type      : string
                   Type of detector (geds or spms)
    detector     : string
                   Name of the detector
    """
    utime_array = np.empty((0, 0))
    tmp_array = np.empty((0, 0))

    if isinstance(raw_files, list):
        for raw_file in raw_files:
            tmp_array = lh5.load_nda(raw_file, ["runtime"], detector + "/raw")[
                "runtime"
            ]
            utime_array = np.append(
                utime_array, add_offset_to_timestamp(tmp_array, raw_file)
            )
    else:
        tmp_array = lh5.load_nda(raw_files, ["runtime"], detector + "/raw")["runtime"]
        utime_array = np.append(
            utime_array, add_offset_to_timestamp(tmp_array, raw_files)
        )

    return utime_array


def add_offset_to_timestamp(tmp_array, raw_file):
    """
    Add a time shift to the filename given by the time shown in 'runtime'.

    Parameters
    ----------
    tmp_array : array
                Time since beginning of file
    raw_file  : string
                String of lh5 raw file
    """
    date_time = (((raw_file.split("/")[-1]).split("-")[4]).split("Z")[0]).split("T")
    date = date_time[0]
    time = date_time[1]
    run_start = datetime.strptime(date + time, "%Y%m%d%H%M%S")
    utime_array = tmp_array + np.full(tmp_array.size, run_start.timestamp())

    return utime_array


def build_par_array(raw_files, dsp_files, parameter, detector, det_type):
    """
    Build an array with parameter values.

    Parameters
    ----------
    raw_files   : list
                  Strings of lh5 raw files
    dsp_files   : list
                  Strings of lh5 dsp files
    parameter   : string
                  Name of the parameter
    detector    : string
                  Channel of the detector
    det_type    : string
                  Type of detector (geds or spms)
    """
    utime_array = build_utime_array(raw_files, detector, det_type)
    if j_par[0][parameter]["tier"] == 1:
        par_array = lh5.load_nda(raw_files, [parameter], detector + "/raw/")[parameter]
    else:
        par_array = lh5.load_nda(dsp_files, [parameter], detector + "/dsp/")[parameter]
        if len(par_array) == 2 * len(utime_array):
            par_array = par_array[: len(utime_array)]

    return par_array


def time_analysis(utime_array, par_array, time_cut):
    """
    Return the timestamp & parameter lists after the time cuts.

    Parameters
    ----------
    utime_array : array
                  Array of (already shifted) timestamps
    par_array   : array
                  Array with parameter values
    time_cut    : list
                  List with info about time cuts
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
        start_index = timecut.min_timestamp_thr(utime_array.tolist(), time_cut)
        if len(utime_array) != 0:
            utime_array = timecut.cut_array_below_min(utime_array, start_index)
        if len(par_array) != 0:
            par_array = timecut.cut_array_below_min(par_array, start_index)

    return utime_array, par_array


def par_time_average(utime_array, par_array, time_slice):
    """
    Compute time average using time slice.

    Description
    -----------
    Redifines the time/parameter arrays by selecting only
    values that differ by a quantity equal to 'time_slice'.

    Parameters
    ----------
    utime_array : array
                  Array of (already shifted) timestamps
    par_array   : array
                  Array with parameter values
    time_slice  : int
                  Step value to separate parameter values in plot
    """
    bins = np.arange(
        (np.amin(utime_array) // time_slice) * time_slice,
        ((np.amax(utime_array) // time_slice) + 2) * time_slice,
        time_slice,
    )
    binned = np.digitize(utime_array, bins)
    bin_nos = np.unique(binned)

    par_average = np.zeros(len(bins) - 1)
    par_average[:] = np.nan
    par_std = np.zeros(len(bins) - 1)
    par_std[:] = np.nan
    for i in bin_nos:
        par_average[i - 1] = np.mean(par_array[np.where(binned == i)[0]])
        par_std[i - 1] = np.std(par_array[np.where(binned == i)[0]])
    times_average = (bins[:-1] + bins[1:]) / 2

    return times_average, par_average


def puls_analysis(raw_file, detector, det_type):
    """
    Select pulser events.

    Description
    -----------
    Returns an array with pulser only entries, an array with detector and
    pulser entries, an array with detector only entries.


    Parameters
    ----------
    raw_file : string
               lh5 raw file
    detector : string
               Channel of the detector
    det_type : string
               Type of detector (geds or spms)
    """
    wfs = lh5.load_nda(raw_file, ["values"], "ch000/raw/waveform")["values"]
    det_and_puls_ievt = lh5.load_nda(raw_file, ["eventnumber"], detector + "/raw")[
        "eventnumber"
    ]  # detector+pulser events
    puls_ievt = lh5.load_nda(raw_file, ["eventnumber"], "ch000/raw")[
        "eventnumber"
    ]  # not all events are pulser events
    pulser_entry = []
    not_pulser_entry = []

    """
    for idx,_wf in enumerate(wfs):
        # if len([*filter(lambda x: x >= 17000, wf)]):
        # if any(y > 17000 for y in wf):
        if sum(wf) / len(wf) > 15000:
            pulser_entry.append(idx)
        else:
            not_pulser_entry.append(idx)
    """
    for idx in range(0, len(wfs)):
        not_pulser_entry.append(idx)

    # pulser entries
    puls_only_ievt = puls_ievt[np.isin(puls_ievt, pulser_entry)]
    # not pulser entries
    not_puls_ievt = puls_ievt[np.isin(puls_ievt, not_pulser_entry)]
    # detector entries
    det_only_ievt = det_and_puls_ievt[np.isin(det_and_puls_ievt, not_puls_ievt)]

    return puls_only_ievt, det_and_puls_ievt, det_only_ievt


def remove_nan_values(par_array, time_array):
    """
    Remove NaN values from arrays.

    Description
    -----------
    Removes the 'nan' values that appear in
    the array with the parameters values (and,
    consequently, the corresponding entries in the
    time array).

    Parameters
    ----------
    par_array  : array
                 Array with parameter values
    time_array : array
                 Array with time values
    """
    par_array_no_nan = []
    time_array_no_nan = []

    if np.isnan(par_array).any():
        par_array_no_nan = par_array[~np.isnan(par_array)]
        time_array_no_nan = time_array[~np.isnan(par_array)]
    else:
        par_array_no_nan = par_array
        time_array_no_nan = time_array

    return np.asarray(par_array_no_nan), np.asarray(time_array_no_nan)
