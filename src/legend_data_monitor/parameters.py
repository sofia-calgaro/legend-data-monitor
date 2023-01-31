from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pygama.lgdo.lh5_store as lh5

from . import analysis

j_config, j_par, _ = analysis.read_json_files()
exp = j_config[0]["exp"]
version = j_config[0]["path"]["version"]
pulser_events = j_config[6]["pulser"]["pulser_events"]
physics_events = j_config[6]["pulser"]["physics_events"]
no_variation_pars = j_config[6]["plot_values"]["no_variation_pars"]
qc_flag = j_config[6]["quality_cuts"]
qc_version = j_config[6]["quality_cuts"]["version"]["QualityCuts_flag"][
    "apply_to_version"
]
is_qc_version = j_config[6]["quality_cuts"]["version"]["isQC_flag"]["apply_to_version"]


def load_parameter(
    data: pd.DataFrame | list[str],
    parameter: str,
    detector: str,
    det_type: str,
    time_cut: list[str],
    all_ievt: np.ndarray,
    puls_only_ievt: np.ndarray,
    not_puls_ievt: np.ndarray,
    pulser_timestamps: np.ndarry,
    start_code: str,
):
    """
    Load parameters from files.

    Parameters
    ----------
    data
                    Pandas dataframes containing dsp/hit data or list of dsp files
    parameter
                    Parameter to plot
    detector
                    Channel of the detector
    det_type
                    Type of detector (geds or spms)
    time_cut
                    List with info about time cuts
    all_ievt
                    Event number for all events
    puls_only_ievt
                    Event number for pulser events
    not_puls_ievt
                    Event number for physical events
    pulser_timestamps
                    Timestamps of pulser events
    start_code
                    Starting time of the code
    """
    no_cut_pars = ["event_rate", "K_lines"]
    qc_method = analysis.get_qc_method(version, qc_version, is_qc_version)

    if det_type == "spms":
        utime_array = lh5.load_nda(data, ["timestamp"], detector + "/dsp")[
            "timestamp"
        ]  # <- remove it when DataLoader is working for spms too!
    else:
        utime_array = data["timestamp"]

    if exp == "l60":
        # select (or remove) pulser events from timestamps array
        if all_ievt != [] and puls_only_ievt != [] and not_puls_ievt != []:
            det_only_index = np.isin(all_ievt, not_puls_ievt)
            puls_only_index = np.isin(all_ievt, puls_only_ievt)
            if parameter in pulser_events:
                utime_array = utime_array[puls_only_index]
            if parameter in physics_events:
                utime_array = utime_array[det_only_index]


    # apply quality cuts to the time array
    if qc_flag[det_type] is True:
        if parameter in pulser_events:
            keep_evt_index = puls_only_index
        elif parameter in physics_events:
            keep_evt_index = det_only_index
        else:
            keep_evt_index = []
        quality_index = analysis.get_qc_ievt(data[qc_method], keep_evt_index)
        utime_array = utime_array[quality_index]

    # cutting time array according to time selection
    utime_array_cut = utime_array
    # to handle particular cases where the timestamp array is outside the time window:
    if len(utime_array_cut) == 0:
        return [], [], []

    if parameter == "energy_in_pe" and det_type == "spms":
        hit_files = [dsp_file.replace("dsp", "hit") for dsp_file in data]
        par_array = lh5.load_nda(hit_files, ["energy_in_pe"], detector + "/hit")[
            "energy_in_pe"
        ]
        # par_array = data["energy_in_pe"] # <-- use it when DataLoader is working for spms
    elif parameter == "trigger_pos" and det_type == "spms":
        hit_files = [dsp_file.replace("dsp", "hit") for dsp_file in data]
        par_array = lh5.load_nda(hit_files, ["trigger_pos"], detector + "/hit")[
            "trigger_pos"
        ]
        # par_array = data["trigger_pos"]  # <-- use it when DataLoader is working for spms
    elif parameter == "event_rate":
        par_array, utime_array_cut = event_rate(
            data,
            utime_array,
            utime_array_cut,
            detector,
            det_type,
            all_ievt,
            puls_only_ievt,
            not_puls_ievt,
            time_cut,
            start_code,
        )
    elif parameter == "uncal_puls":
        par_array = data["trapTmax"]
    elif parameter == "cal_puls":
        par_array = data["cuspEmax_ctc_cal"]
    elif parameter == "K_lines":
        par_array = data["cuspEmax_ctc_cal"]
        # keep physical events
        if all_ievt != [] and puls_only_ievt != [] and not_puls_ievt != []:
            par_array = par_array[det_only_index]
        # temporal cut
        _, par_array = analysis.time_analysis(
            utime_array, par_array, time_cut, start_code
        )
        par_array, utime_array_cut = energy_potassium_lines(par_array, utime_array_cut)
    else:
        par_array = data[parameter]

    # select (or remove) pulser events from parameter array
    if exp == "l60":
        if all_ievt != [] and puls_only_ievt != [] and not_puls_ievt != []:
            if parameter in pulser_events:
                if parameter not in no_cut_pars:
                    par_array = par_array[puls_only_index]
            if parameter in physics_events:
                if parameter not in no_cut_pars:
                    par_array = par_array[det_only_index]


    # apply quality cuts to the parameter array
    if qc_flag[det_type] is True and parameter not in no_cut_pars:
        par_array = par_array[quality_index]

    if parameter in ["energy_in_pe", "trigger_pos"] and det_type == "spms":
        a = utime_array_cut
        b = par_array
        len_par = [len(sub_array) for sub_array in b]
        utime_array_cut = [t for i, t in enumerate(a) for _ in range(len_par[i])]
        # convert list of array to just list of values
        par_array = np.ravel(b).tolist()

    # check if there are 'nan' values in par_array; if yes, remove them
    if np.isnan(par_array).any() and parameter not in ["energy_in_pe", "trigger_pos"]:
        par_array, utime_array_cut = analysis.remove_nan(par_array, utime_array_cut)

    # convert pandas series to numpy array
    if isinstance(par_array, pd.core.series.Series):
        par_array = par_array.to_numpy()
    if isinstance(utime_array_cut, pd.core.series.Series):
        utime_array_cut = utime_array_cut.to_numpy()

    # Enable following lines to get the % variation of a parameter wrt to its mean value
    if parameter not in no_variation_pars and det_type not in [
        "spms",
        "ch000",
        "ch001",
    ]:
        # par_array_mean = np.mean(par_array[: int(0.05 * len(par_array))])
        par_array_mean = analysis.get_mean(
            par_array, utime_array_cut, parameter, detector
        )
        par_array = np.subtract(par_array, par_array_mean)
        par_array = np.divide(par_array, par_array_mean) * 100
    else:
        par_array_mean = []

    return par_array_mean, par_array, utime_array_cut


def event_rate(
    data: pd.DataFrame,
    utime_array: list,
    timestamp: list,
    detector: str,
    det_type: str,
    all_ievt: np.ndarray,
    puls_only_ievt: np.ndarray,
    not_puls_ievt: np.ndarray,
    time_cut: list[str],
    start_code: str,
):
    """
    Return the event rate (as cts/dt).

    Parameters
    ----------
    data
                Pandas dataframes containing dsp/hit data
    utime_array
                List of shifted UTC timestamps - no time cut applied
    timestamp
                List of shifted UTC timestamps - time cut applied
    detector
                Channel of the detector
    det_type
                Type of detector (geds or spms)
    all_ievt
                Event number for all events
    puls_only_ievt
                Event number for high energy pulser events
    not_puls_ievt
                Event number for physical events
    time_cut
                List with info about time cuts
    start_code
                Starting time of the code
    """
    rate = []
    times = []

    # for spms, we keep timestamp entries only if there's a non-null energy release
    if det_type == "spms":
        # energies = data["energies"] # <- use it when the DataLoader will work for spms and remove the following line
        energies = lh5.load_nda(data, ["energies"], detector + "/dsp")["energies"]

        # remove nan entries
        energies = [entry[~np.isnan(entry)] for entry in energies]
        new_energies = []  # array with True (=energy deposition) or False entries
        no_hits = []  # array with number of hits per each timestamp
        for entry in energies:
            if np.size(entry) == 0:
                new_energies.append(False)
                no_hits.append(np.size(entry))
            else:
                new_energies.append(True)
                no_hits.append(np.size(entry))
        energies = np.array(new_energies)
        no_hits = np.array(no_hits)

        # apply pulser cut
        if all_ievt != [] and puls_only_ievt != [] and not_puls_ievt != []:
            det_only_index = np.isin(all_ievt, not_puls_ievt)
            puls_only_index = np.isin(all_ievt, puls_only_ievt)
            if "event_rate" in pulser_events:
                energies = energies[puls_only_index]
                no_hits = no_hits[puls_only_index]
            if "event_rate" in physics_events:
                energies = energies[det_only_index]
                no_hits = no_hits[det_only_index]
        if len(energies) == 0:
            return np.zeros(len(timestamp)), np.array(timestamp)

        # apply quality cuts
        if qc_flag[det_type] is True:
            if "event_rate" in pulser_events:
                keep_evt_index = puls_only_index
            elif "event_rate" in physics_events:
                keep_evt_index = det_only_index
            else:
                keep_evt_index = []
            quality_index = analysis.get_qc_ievt(data["Quality_cuts"], keep_evt_index)
            energies = energies[quality_index]
            no_hits = no_hits[quality_index]
            if len(energies) == 0:
                return np.zeros(len(timestamp)), np.array(timestamp)

        # apply time cut
        timestamp, energies = analysis.time_analysis(
            utime_array, energies, time_cut, start_code
        )
        _, no_hits = analysis.time_analysis(utime_array, no_hits, time_cut, start_code)
        if len(energies) == 0:
            return np.zeros(len(timestamp)), np.array(timestamp)

        # keep timestamps that correspond to an energy deposition
        timestamp = timestamp[energies]
        no_hits = no_hits[energies]
        if len(timestamp) == 0:
            return np.array([]), np.array([])

        len_par = [no for no in no_hits]
        timestamp = [t for i, t in enumerate(timestamp) for _ in range(len_par[i])]

    # get the date+time of the first file included in the time range of interest
    if det_type != "spms":  # <- remove it when the DataLoader will work for spms!
        data = analysis.load_dsp_files(time_cut, start_code)
    date_time = (((data[0].split("/")[-1]).split("-")[4]).split("Z")[0]).split("T")
    run_start = datetime.strptime(date_time[0] + date_time[1], "%Y%m%d%H%M%S")
    run_start = datetime.strptime(str(run_start), "%Y-%m-%d %H:%M:%S")

    i = 0
    j = datetime.timestamp(run_start + timedelta(days=0, hours=2, minutes=0))
    dt = j_config[6]["par-info"]["event_rate"]["dt"]

    while j + dt <= timestamp[-1]:
        num = 0
        while timestamp[i] < (j + dt):
            num += 1
            i += 1
        if j != run_start:
            rate.append(num / dt)
            times.append(j)
        j += dt

    units = j_config[6]["par-info"]["event_rate"]["units"]
    if units == "mHz":
        fact = 1000
    if units == "Hz":
        fact = 1
    if units == "kHz":
        fact = 0.001

    return np.array(rate) * fact, np.array(times)


def energy_potassium_lines(par_array: list, timestamp: list):
    """
    Return the energy for events in around K-40 and K-42 lines.

    Parameters
    ----------
    par_array
                Energies (trapEmax) of events
    timestamp
                List of shifted UTC timestamps
    """
    par_list = []
    time_list = []

    for idx, entry in enumerate(par_array):
        if entry > 1430 and entry < 1575:
            par_list.append(entry)
            time_list.append(timestamp[idx])

    return np.array(par_list), np.array(time_list)
