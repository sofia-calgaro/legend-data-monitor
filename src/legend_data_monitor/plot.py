from __future__ import annotations

import logging
import pickle as pkl
from copy import copy
from datetime import datetime

import matplotlib as mpl
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sn
from matplotlib import dates, ticker

from . import analysis, parameters

palette = sn.color_palette("hls", 15)
# sn.set_theme(style='darkgrid')

plt.rcParams.update({"figure.max_open_warning": 0})
plt.rcParams["figure.figsize"] = (14, 10)
plt.rcParams["font.size"] = 12
plt.rcParams["figure.facecolor"] = "w"
plt.rcParams["grid.color"] = "b0b0b0"
plt.rcParams["axes.facecolor"] = "w"
plt.rcParams["axes.grid"] = True
plt.rcParams["axes.grid.axis"] = "both"
plt.rcParams["axes.grid.which"] = "major"

j_config, j_par, j_plot = analysis.read_json_files()
exp = j_config[0]["exp"]
output = j_config[0]["path"]["output"]
period = j_config[1]
run = j_config[2]
filelist = j_config[3]
datatype = j_config[4]
no_variation_pars = j_config[6]["plot_values"]["no_variation_pars"]
pulser_events = j_config[6]["pulser"]["pulser_events"]
physics_events = j_config[6]["pulser"]["physics_events"]
plot_style = j_config[7]
qc_flag = j_config[6]["quality_cuts"]
verbose = j_config[12]


def plot_parameters(
    ax,
    par_array: np.ndarray,
    utime_array: np.ndarray,
    detector: str,
    det_type: str,
    parameter: str,
):
    """
    Plot the parameter VS time and check if parameters are below/above some given thresholds.

    Parameters
    ----------
    ax
                  Plot to be saved in pkl file
    par_array
                  Array with parameter values
    utime_array
                  Array with (shifted+cut) time values
    detector
                  Name of the detector
    det_type
                  Type of detector (geds or spms)
    parameter
                  Parameter to plot
    """
    # rebinning
    if (
        plot_style["par_average"] is True
        and parameter != "K_lines"
        and det_type != "ch000"
        and det_type != "ch001"
    ):
        par_array, utime_array = analysis.avg_over_entries(par_array, utime_array)

    # function to check if par values are outside some pre-defined limits
    status = analysis.check_par_values(
        utime_array, par_array, parameter, detector, det_type
    )
    times = [datetime.fromtimestamp(t) for t in utime_array]

    if det_type == "spms":
        col = j_plot[0][str(detector)]
    if det_type == "geds":
        col = j_plot[1][detector]
    if det_type == "ch000":
        col = "k"
    if det_type == "ch001":
        col = "k"

    # if we want to plot detectors that are only problematic
    status_flag = j_config[10][det_type]
    if status_flag is True and status == 1:
        if det_type == "ch000" or det_type == "ch001" or parameter == "K_lines":
            ax.plot(times, par_array, color=col, linewidth=0, marker=".", markersize=10)
            plt.plot(
                times, par_array, color=col, linewidth=0, marker=".", markersize=10
            )
        else:
            ax.plot(times, par_array, color=col, linewidth=1)
            plt.plot(times, par_array, color=col, linewidth=1)
    # plot everything independently of the detector's status
    else:
        if det_type == "ch000" or det_type == "ch001" or parameter == "K_lines":
            ax.plot(times, par_array, color=col, linewidth=0, marker=".", markersize=10)
            plt.plot(
                times, par_array, color=col, linewidth=0, marker=".", markersize=10
            )
        else:
            ax.plot(times, par_array, color=col, linewidth=2)
            plt.plot(times, par_array, color=col, linewidth=2)

    return times[0], times[-1], status, ax


def plot_parameters_200(
    ax,
    par_array: np.ndarray,
    utime_array: np.ndarray,
    detector: str,
    det_type: str,
    parameter: str,
):
    """
    Plot the parameter VS time and check if parameters are below/above some given thresholds.

    Parameters
    ----------
    ax
                  Plot to be saved in pkl file
    par_array
                  Array with parameter values
    utime_array
                  Array with (shifted+cut) time values
    detector
                  Name of the detector
    det_type
                  Type of detector (geds or spms)
    parameter
                  Parameter to plot
    """
    # rebinning
    if (
        plot_style["par_average"] is True
        and parameter != "K_lines"
        and det_type != "ch000"
        and det_type != "ch001"
    ):
        par_array, utime_array = analysis.avg_over_entries(par_array, utime_array)

    # function to check if par values are outside some pre-defined limits
    status = analysis.check_par_values(
        utime_array, par_array, parameter, detector, det_type
    )
    times = [datetime.fromtimestamp(t) for t in utime_array]

    if det_type == "spms":
        col = j_plot[0][str(detector)]
    if det_type == "geds":
        col = j_plot[1][detector]
    if det_type == "ch000":
        col = "k"
    if det_type == "ch001":
        col = "k"

    # if we want to plot detectors that are only problematic
    status_flag = j_config[10][det_type]
    if status_flag is True and status == 1:
        if det_type == "ch000" or det_type == "ch001" or parameter == "K_lines":
            ax.plot(times, par_array, color=col, linewidth=0, marker=".", markersize=10)
            plt.plot(
                times, par_array, color=col, linewidth=0, marker=".", markersize=10
            )
        else:
            ax.plot(times, par_array, color=col, linewidth=1)
            plt.plot(times, par_array, color=col, linewidth=1)
    # plot everything independently of the detector's status
    else:
        if det_type == "ch000" or det_type == "ch001" or parameter == "K_lines":
            ax.plot(times, par_array, color=col, linewidth=0, marker=".", markersize=10)
            plt.plot(
                times, par_array, color=col, linewidth=0, marker=".", markersize=10
            )
        else:
            ax.plot(times, par_array, color=col, linewidth=2)
            plt.plot(times, par_array, color=col, linewidth=2)

    return times[0], times[-1], status, ax


def plot_par_vs_time(
    data: pd.DataFrame,
    det_list: list[str],
    parameter: str,
    time_cut: list[str],
    det_type: str,
    string_number: str,
    det_dict: dict,
    all_ievt: np.ndarray,
    puls_only_ievt: np.ndarray,
    not_puls_ievt: np.ndarray,
    start_code: str,
    time_range: list[str],
    pdf=None,
) -> dict:
    """
    Plot time evolution of given parameter for geds/spms.

    Parameters
    ----------
    data
                    Pandas dataframes containing dsp/hit data
    det_list
                    List of detectors present in a string
    parameter
                    Parameter to plot
    time_cut
                    List with info about time cuts
    det_type
                    Type of detector (geds or spms)
    string_number
                    Number of the string under study
    det_dict
                    Contains info (crate, card, ch_orca) for geds/spms/other
    all_ievt
                    Event number for all events
    puls_only_ievt
                    Event number for high energy pulser events
    not_puls_ievt
                    Event number for physical events
    start_code
                    Starting time of the code
    time_range
                    First and last timestamps of the time range of interest
    """
    fig, ax = plt.subplots(1, 1)
    ax.set_facecolor("w")
    ax.grid(axis="both", which="major")
    plt.grid(axis="both", which="major")
    # plt.figure().patch.set_facecolor(j_par[0][parameter]["facecol"])
    start_times = []
    end_times = []
    handle_list = []
    map_dict = {}
    string_mean_dict = {}

    for index, detector in enumerate(det_list):
        # if detector == "ch016" or detector=="ch010": # <<-- for quick tests

        # keep entries for the selected detector
        new_data = data[data["hit_table"] == int(detector.split("ch0")[-1])]

        # skip detectors that are not geds/spms
        if det_dict[detector]["system"] == "--":
            continue

        # add entries for the legend
        # card = det_dict[detector]["daq"]["board_slot"]
        # ch_orca = det_dict[detector]["daq"]["board_ch"]
        if det_type == "geds":
            name = det_dict[detector]["det_id"]
            string_no = det_dict[detector]["string"]["number"]
            string_pos = det_dict[detector]["string"]["position"]
            lab = f"s{string_no}-p{string_pos}-{detector}-{name}"
            col = j_plot[1][detector]
        if det_type == "spms":
            name = det_dict[detector]["det_id"]
            lab = f"{name} - {detector}"
            col = j_plot[0][str(detector)]
        handle_list.append(
            mpatches.Patch(
                color=col,
                label=lab,
            )
        )

        # det parameter and time arrays for a given detector
        par_array_mean, par_array, utime_array = parameters.load_parameter(
            new_data,
            parameter,
            detector,
            det_type,
            time_cut,
            all_ievt,
            puls_only_ievt,
            not_puls_ievt,
            start_code,
        )
        if len(par_array) == 0:
            continue

        offset = 15 * (0 + index)
        par_array = np.add(par_array, offset)

        # plot detector and get its status
        start_time, end_time, status, ax = plot_parameters(
            ax, par_array, utime_array, detector, det_type, parameter
        )

        # fill the map with status flags
        if det_type == "spms":
            detector = str(detector)
        if detector not in map_dict:
            map_dict[detector] = status
        else:
            if map_dict[detector] == 0:
                map_dict[detector] = status
        # save mean over first entries
        string_mean_dict[detector] = {parameter: str(par_array_mean)}

        # skip those detectors that are not within the time window
        if start_time == 0 and end_time == 0:
            continue
        start_times.append(start_time)
        end_times.append(end_time)

    # no data were found at all
    if len(start_times) == 0 and len(end_times) == 0:
        return None, None

    locs = np.linspace(
        dates.date2num(min(start_times)), dates.date2num(max(end_times)), 10
    )
    xlab = "%d/%m"
    if j_config[11]["frmt"] == "day/month-time":
        xlab = "%d/%m\n%H:%M"
    if j_config[11]["frmt"] == "time":
        xlab = "%H:%M"
    labels = [dates.num2date(loc).strftime(xlab) for loc in locs]

    ax.set_xticks(locs)
    ax.set_xticklabels(labels)
    plt.xticks(locs, labels)
    ax.legend(
        loc=(1.04, 0.0),
        ncol=1,
        frameon=True,
        facecolor="white",
        framealpha=0,
        handles=handle_list,
    )
    plt.legend(
        loc=(1.04, 0.0),
        ncol=1,
        frameon=True,
        facecolor="white",
        framealpha=0,
        handles=handle_list,
    )
    ylab = j_par[0][parameter]["label"]
    if parameter in no_variation_pars:
        if j_par[0][parameter]["units"] != "null":
            ylab += " [" + j_par[0][parameter]["units"] + "]"
        if parameter == "event_rate":
            units = j_config[6]["par-info"]["event_rate"]["units"]
            ylab += " [" + units + "]"
    else:
        ylab += ", %"
    ax.set_ylabel(ylab)
    ax.set_xlabel(f'{j_config[11]["frmt"]} (UTC)')
    plt.ylabel(ylab)
    plt.xlabel(f'{j_config[11]["frmt"]} (UTC)')

    # set title
    if det_type == "spms":
        ax.set_title(f"spms - {string_number}")
        plt.title(f"spms - {string_number}")
    if det_type == "geds":
        ax.set_title(f"geds - string #{string_number}")
        plt.title(f"geds - string #{string_number}")

    # define horiziontal lines
    low_lim = j_par[0][parameter]["limit"][det_type][0]
    upp_lim = j_par[0][parameter]["limit"][det_type][1]
    if low_lim != "null":
        ax.axhline(y=low_lim, color="r", linestyle="--", linewidth=2)
        plt.axhline(y=low_lim, color="r", linestyle="--", linewidth=2)
    if upp_lim != "null":
        ax.axhline(y=upp_lim, color="r", linestyle="--", linewidth=2)
        plt.axhline(y=upp_lim, color="r", linestyle="--", linewidth=2)
    # plt.ylim(low_lim*(1-0.01), upp_lim*(1+0.01)) # y-axis zoom
    if parameter == "K_lines":
        ax.axhline(y=1460.8, color="r", linestyle="--", linewidth=1)
        plt.axhline(y=1460.8, color="r", linestyle="--", linewidth=1)
        ax.axhline(y=1524.6, color="r", linestyle="--", linewidth=1)
        plt.axhline(y=1524.6, color="r", linestyle="--", linewidth=1)
    ax.axhline(y=0, color="r", linestyle="--", linewidth=1)
    plt.axhline(y=0, color="r", linestyle="--", linewidth=1)

    # start_name = start_times[0].astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    # end_name = end_times[-1].astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    # define name of pkl file (with info about time cut if present)
    pkl_name = analysis.set_pkl_name(
        exp,
        period,
        datatype,
        det_type,
        string_number,
        parameter,
        time_range,
    )

    pkl.dump(ax, open(f"{output}/pkl-files/par-vs-time/{pkl_name}", "wb"))
    pdf.savefig(bbox_inches="tight")
    plt.close()

    logging.info(f"{parameter} is plotted from {start_times[0]} to {end_times[-1]}")

    return string_mean_dict, map_dict


def plot_par_vs_time_ch001(
    data: pd.DataFrame,
    parameter: str,
    time_cut: list[str],
    det_type: str,
    start_code: str,
    pulser_timestamps: np.ndarray,
    time_range: list[str],
    pdf=None,
) -> dict:
    """
    Plot time evolution of given parameter for ch000.

    Parameters
    ----------
    data
                    Pandas dataframes containing dsp/hit data
    parameter
                    Parameter to plot
    time_cut
                    List with info about time cuts
    det_type
                    Type of detector (ch001)
    start_code
                    Starting time of the code
    time_range
                    First and last timestamps of the time range of interest
    """
    fig, ax = plt.subplots(1, 1)
    ax.set_facecolor("w")
    ax.grid(axis="both", which="major")
    plt.grid(axis="both", which="major")
    start_times = []
    end_times = []
    map_dict = {}

    # keep entries for the selected detector (note: no hit table for ch000)
    # new_data = data[data["dsp_table"] == 0] # what is this line for?
    new_data = data

    all_ievt = []
    puls_only_ievt = []
    not_puls_ievt = []

    # det parameter and time arrays for a given detector
    _, par_array, utime_array = parameters.load_parameter(
        new_data,
        parameter,
        "ch001",
        det_type,
        time_cut,
        all_ievt,
        puls_only_ievt,
        not_puls_ievt,
        pulser_timestamps,
        start_code,
    )

    # plot detector and get its status
    start_time, end_time, status, ax = plot_parameters(
        ax, par_array, utime_array, "ch001", det_type, parameter
    )

    # fill the map with status flags
    if "ch001" not in map_dict:
        map_dict["ch001"] = status
    else:
        if map_dict["ch001"] == 0:
            map_dict["ch001"] = status

    start_times.append(start_time)
    end_times.append(end_time)

    # no data were found at all
    if len(start_times) == 0 and len(end_times) == 0:
        return None, None

    # 1D-plot
    locs = np.linspace(
        dates.date2num(start_times[0]), dates.date2num(end_times[-1]), 10
    )
    xlab = "%d/%m"
    if j_config[11]["frmt"] == "day/month-time":
        xlab = "%d/%m\n%H:%M"
    if j_config[11]["frmt"] == "time":
        xlab = "%H:%M"
    labels = [dates.num2date(loc).strftime(xlab) for loc in locs]
    ax.set_xticks(locs)
    ax.set_xticklabels(labels)
    plt.xticks(locs, labels)
    ax.legend(
        loc=(1.04, 0.0),
        ncol=1,
        frameon=True,
        facecolor="white",
        framealpha=0,
    )
    plt.legend(
        loc=(1.04, 0.0),
        ncol=1,
        frameon=True,
        facecolor="white",
        framealpha=0,
    )
    xlab = j_config[11]["frmt"]
    ylab = j_par[0][parameter]["label"]
    if parameter in no_variation_pars:
        if j_par[0][parameter]["units"] != "null":
            ylab += " [" + j_par[0][parameter]["units"] + "]"
        if parameter == "event_rate":
            units = j_config[6]["par-info"]["event_rate"]["units"]
            ylab += " [" + units + "]"
    else:
        ylab += ", %"
    ax.set_ylabel(ylab)
    ax.set_xlabel(f"{xlab} (UTC)")
    plt.ylabel(ylab)
    plt.xlabel(f"{xlab} (UTC)")

    # set title
    ax.set_title("ch001")
    plt.title("ch001")

    # set y-label
    low_lim = j_par[0][parameter]["limit"][det_type][0]
    upp_lim = j_par[0][parameter]["limit"][det_type][1]
    if low_lim != "null":
        ax.axhline(y=low_lim, color="r", linestyle="--", linewidth=2)
        plt.axhline(y=low_lim, color="r", linestyle="--", linewidth=2)
    if upp_lim != "null":
        ax.axhline(y=upp_lim, color="r", linestyle="--", linewidth=2)
        plt.axhline(y=upp_lim, color="r", linestyle="--", linewidth=2)

    # define name of pkl file (with info about time cut if present)
    pkl_name = analysis.set_pkl_name(
        exp,
        period,
        datatype,
        det_type,
        "",
        parameter,
        time_range,
    )

    pkl.dump(ax, open(f"{output}/pkl-files/par-vs-time/{pkl_name}", "wb"))
    pdf.savefig(bbox_inches="tight")
    plt.close()

    logging.info(f"{parameter} is plotted from {start_times[0]} to {end_times[-1]}")

    return map_dict


def plot_par_vs_time_ch000(
    data: pd.DataFrame,
    parameter: str,
    time_cut: list[str],
    det_type: str,
    start_code: str,
    time_range: list[str],
    pdf=None,
) -> dict:
    """
    Plot time evolution of given parameter for ch000.

    Parameters
    ----------
    data
                    Pandas dataframes containing dsp/hit data
    parameter
                    Parameter to plot
    time_cut
                    List with info about time cuts
    det_type
                    Type of detector (ch000)
    all_ievt
                    Event number for all events
    puls_only_ievt
                    Event number for high energy pulser events
    not_puls_ievt
                    Event number for physical events
    start_code
                    Starting time of the code
    time_range
                    First and last timestamps of the time range of interest
    """
    fig, ax = plt.subplots(1, 1)
    ax.set_facecolor("w")
    ax.grid(axis="both", which="major")
    plt.grid(axis="both", which="major")
    # plt.figure().patch.set_facecolor(j_par[0][parameter]["facecol"])
    start_times = []
    end_times = []
    map_dict = {}

    # keep entries for the selected detector (note: no hit table for ch000)
    # new_data = data[data["dsp_table"] == 0]

    new_data = data
    all_ievt = []
    puls_only_ievt = []
    not_puls_ievt = []

    # det parameter and time arrays for a given detector
    _, par_array, utime_array = parameters.load_parameter(
        new_data,
        parameter,
        "ch000",
        det_type,
        time_cut,
        all_ievt,
        puls_only_ievt,
        not_puls_ievt,
        start_code,
    )

    # plot detector and get its status
    start_time, end_time, status, ax = plot_parameters(
        ax, par_array, utime_array, "ch000", det_type, parameter
    )

    # fill the map with status flags
    if "ch000" not in map_dict:
        map_dict["ch000"] = status
    else:
        if map_dict["ch000"] == 0:
            map_dict["ch000"] = status

    start_times.append(start_time)
    end_times.append(end_time)

    # no data were found at all
    if len(start_times) == 0 and len(end_times) == 0:
        return None, None

    # 1D-plot
    locs = np.linspace(
        dates.date2num(start_times[0]), dates.date2num(end_times[-1]), 10
    )
    xlab = "%d/%m"
    if j_config[11]["frmt"] == "day/month-time":
        xlab = "%d/%m\n%H:%M"
    if j_config[11]["frmt"] == "time":
        xlab = "%H:%M"
    labels = [dates.num2date(loc).strftime(xlab) for loc in locs]
    ax.set_xticks(locs)
    ax.set_xticklabels(labels)
    plt.xticks(locs, labels)
    ax.legend(
        loc=(1.04, 0.0),
        ncol=1,
        frameon=True,
        facecolor="white",
        framealpha=0,
    )
    plt.legend(
        loc=(1.04, 0.0),
        ncol=1,
        frameon=True,
        facecolor="white",
        framealpha=0,
    )
    xlab = j_config[11]["frmt"]
    ylab = j_par[0][parameter]["label"]
    if parameter in no_variation_pars:
        if j_par[0][parameter]["units"] != "null":
            ylab += " [" + j_par[0][parameter]["units"] + "]"
        if parameter == "event_rate":
            units = j_config[6]["par-info"]["event_rate"]["units"]
            ylab += " [" + units + "]"
    else:
        ylab += ", %"
    ax.set_ylabel(ylab)
    ax.set_xlabel(f"{xlab} (UTC)")
    plt.ylabel(ylab)
    plt.xlabel(f"{xlab} (UTC)")

    # set title
    ax.set_title("ch000")
    plt.title("ch000")

    # set y-label
    low_lim = j_par[0][parameter]["limit"][det_type][0]
    upp_lim = j_par[0][parameter]["limit"][det_type][1]
    if low_lim != "null":
        ax.axhline(y=low_lim, color="r", linestyle="--", linewidth=2)
        plt.axhline(y=low_lim, color="r", linestyle="--", linewidth=2)
    if upp_lim != "null":
        ax.axhline(y=upp_lim, color="r", linestyle="--", linewidth=2)
        plt.axhline(y=upp_lim, color="r", linestyle="--", linewidth=2)

    # start_name = start_times[0].astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    # end_name = end_times[-1].astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    # define name of pkl file (with info about time cut if present)
    pkl_name = analysis.set_pkl_name(
        exp,
        period,
        datatype,
        det_type,
        "",
        parameter,
        time_range,
    )

    pkl.dump(ax, open(f"{output}/pkl-files/par-vs-time/{pkl_name}", "wb"))
    pdf.savefig(bbox_inches="tight")
    plt.close()

    logging.info(f"{parameter} is plotted from {start_times[0]} to {end_times[-1]}")

    return map_dict


def plot_par_vs_time_2d(
    data: pd.DataFrame | list[str],
    det_list: list[str],
    parameter: str,
    time_cut: list[str],
    det_type: str,
    string_number: str,
    det_dict: dict,
    all_ievt: np.ndarray,
    puls_only_ievt: np.ndarray,
    not_puls_ievt: np.ndarray,
    start_code: str,
    time_range: list[str],
    pdf=None,
) -> None:
    """
    Plot spms parameters.

    Parameters
    ----------
    data
                Pandas dataframes containing dsp/hit data or list of dsp files
    det_list
                List of detectors present in a string
    parameter
                Parameter to plot
    time_cut
                List with info about time cuts
    det_type
                Type of detector (geds or spms)
    string_number
                Number of the string under study
    det_dict
                Contains info (crate, card, ch_orca) for geds/spms/other
    all_ievt
                Event number for all events
    puls_only_ievt
                Event number for high energy pulser events
    not_puls_ievt
                Event number for physical events
    pulser_timestamps
                    Timestamps of pulser events
    start_code
                Starting time of the code
    time_range
                First and last timestamps of the time range of interest
    """
    start_times = []
    end_times = []
    plt.rcParams["font.size"] = 8

    # creation of subplots for an arbitrary number of detectors
    if "OB" in string_number:
        columns = 5
        rows = 4
    if "IB" in string_number:
        columns = 3
        rows = 3
    fig, ax_array = plt.subplots(rows, columns, squeeze=False, sharex=True, sharey=True)
    fig.suptitle(f"{det_type} - {string_number}", fontsize=12)
    ylab = j_par[0][parameter]["label"]
    if parameter in no_variation_pars:
        if j_par[0][parameter]["units"] != "null":
            ylab = ylab + " [" + j_par[0][parameter]["units"] + "]"
        if parameter == "event_rate":
            units = j_config[6]["par-info"]["event_rate"]["units"]
            ylab = ylab + " [" + units + "]"
    else:
        ylab += ", %"
    fig.supylabel(ylab, fontsize=12, x=0.005)
    xlab = j_config[11]["frmt"]
    fig.supxlabel(f"{xlab} (UTC)", fontsize=12)

    det_idx = 0
    for ax_row in ax_array:
        for axes in ax_row:
            detector = det_list[det_idx]

            # keep entries for the selected detector
            # new_data = data[data["hit_table"] == int(detector.split("ch0")[-1])] # <-- use it when DataLoader is working for spms!
            # remove the following block when DataLoader is working for spms
            if detector.split("ch0")[-1] in str(
                j_config[13][det_type]
            ) or detector.split("ch")[-1] in str(j_config[13][det_type]):
                det_idx += 1
                continue

            # skip detectors that are not geds/spms
            if det_dict[detector]["system"] == "--":
                det_idx += 1
                continue

            # add entries for the legend
            if det_type == "geds":
                name = det_dict[detector]["det_id"]
                string_no = det_dict[detector]["string"]["number"]
                string_pos = det_dict[detector]["string"]["position"]
                lbl = f"{name}\ns{string_no}-p{string_pos}-{detector}"
            else:
                name = det_dict[detector]["det_id"]
                lbl = f"{name} - {detector}"

            _, par_array, utime_array = parameters.load_parameter(
                data,  # use 'new_data' when DataLoader is working for spms
                parameter,
                detector,
                det_type,
                time_cut,
                all_ievt,
                puls_only_ievt,
                not_puls_ievt,
                pulser_timestamps,
                start_code,
            )
            if len(par_array) == 0:
                det_idx += 1
                continue
            times = [datetime.fromtimestamp(t) for t in utime_array]
            start_time = times[0]
            end_time = times[-1]

            xbin = int(((utime_array[-1] - utime_array[0]) * 1.5) / 1e3)
            if parameter == "energy_in_pe":
                col_map = "magma"
                ymin = 0
                ymax = 10
                ybin = 100
            if parameter == "trigger_pos":
                col_map = "viridis"
                ymin = -200
                ymax = 10000
                ybin = 100

            # plot
            h, xedges, yedges = np.histogram2d(
                utime_array,
                par_array,
                bins=[xbin, ybin],
                range=[[utime_array[0], utime_array[-1]], [ymin, ymax]],
            )
            to_datetime = np.vectorize(datetime.fromtimestamp)
            xedges_datetime = to_datetime(xedges)
            cmap = copy(plt.get_cmap(col_map))
            cmap.set_bad(cmap(0))

            axes.pcolor(
                xedges_datetime, yedges, h.T, norm=mpl.colors.LogNorm(), cmap=col_map
            )
            axes.set_title(f"{lbl}", fontsize=9, y=0.98)
            axes.locator_params(axis="y", nbins=5)

            det_idx += 1
            # skip those detectors that are not within the time window
            if start_time == 0 and end_time == 0:
                continue
            start_times.append(start_time)
            end_times.append(end_time)

    # no data were found at all
    if len(start_times) == 0 and len(end_times) == 0:
        if verbose is True:
            logging.error(
                f"\t...no {parameter} for spms ({string_number}) has been plotted!"
            )
        return None, None
    else:
        if verbose is True:
            logging.error(
                f"\t...{parameter} for spms ({string_number}) has been plotted!"
            )

    locs = np.linspace(
        dates.date2num(min(start_times)), dates.date2num(max(end_times)), 3
    )
    xlab = "%d/%m"
    if j_config[11]["frmt"] == "day/month-time":
        xlab = "%d/%m\n%H:%M"
    if j_config[11]["frmt"] == "time":
        xlab = "%H:%M"
    labels = [dates.num2date(loc).strftime(xlab) for loc in locs]

    [ax.set_xticks(locs) for axs in ax_array for ax in axs]
    [ax.set_xticklabels(labels) for axs in ax_array for ax in axs]
    plt.xticks(locs, labels)

    # define name of pkl file (with info about time cut if present)
    pkl_name = analysis.set_pkl_name(
        exp,
        period,
        datatype,
        det_type,
        string_number,
        parameter,
        time_range,
    )

    fig.tight_layout()
    pkl.dump(ax_array, open(f"{output}/pkl-files/par-vs-time/{pkl_name}", "wb"))
    pdf.savefig(bbox_inches="tight")
    plt.close()

    return


def plot_wtrfll(
    data: pd.DataFrame,
    det_list: list[str],
    parameter: str,
    time_cut: list[str],
    det_type: str,
    string_number: str,
    det_dict: dict,
    all_ievt: np.ndarray,
    puls_only_ievt: np.ndarray,
    not_puls_ievt: np.ndarray,
    start_code: str,
    time_range: list[str],
    pdf=None,
) -> dict:
    """
    Plot time evolution of given parameter for geds/spms as a waterfall plot.

    Parameters
    ----------
    data
                    Pandas dataframes containing dsp/hit data
    det_list
                    List of detectors present in a string
    parameter
                    Parameter to plot
    time_cut
                    List with info about time cuts
    det_type
                    Type of detector (geds or spms)
    string_number
                    Number of the string under study
    det_dict
                    Contains info (crate, card, ch_orca) for geds/spms/other
    all_ievt
                    Event number for all events
    puls_only_ievt
                    Event number for high energy pulser events
    not_puls_ievt
                    Event number for physical events
    start_code
                    Starting time of the code
    time_range
                    First and last timestamps of the time range of interest
    """
    fig = plt.figure(figsize=(12, 10))
    ax = fig.add_subplot(111, projection="3d")
    y_values = []
    start_times = []
    end_times = []
    map_dict = {}
    string_mean_dict = {}

    for index, detector in enumerate(det_list):
        if string_number == "1":

            # keep entries for the selected detector
            new_data = data[data["hit_table"] == int(detector.split("ch0")[-1])]

            # add entries for the legend
            if det_type == "geds":
                name = det_dict[detector]["det_id"]
                string_no = det_dict[detector]["string"]["number"]
                string_pos = det_dict[detector]["string"]["position"]
                new_label = f"s{string_no}-p{string_pos}-{detector}-{name}"
            else:
                name = det_dict[detector]["det_id"]
                new_label = f"{name} - {detector}"
            y_values.append(new_label)
            if det_type == "spms":
                col = j_plot[0][str(detector)]
            if det_type == "geds":
                col = j_plot[1][detector]

            # skip detectors that are not geds/spms
            if det_dict[detector]["system"] == "--":
                continue

            # det parameter and time arrays for a given detector
            par_array_mean, par_array, utime_array = parameters.load_parameter(
                new_data,
                parameter,
                detector,
                det_type,
                time_cut,
                all_ievt,
                puls_only_ievt,
                not_puls_ievt,
                start_code,
            )
            if len(par_array) == 0:
                continue

            # rebinning
            utime_list = utime_array.tolist()
            par_list = par_array.tolist()
            if plot_style["par_average"] is True and parameter != "K_lines":
                par_list, utime_list = analysis.avg_over_entries(par_array, utime_array)

            # function to check if par values are outside some pre-defined limits
            status = analysis.check_par_values(
                utime_list, par_list, parameter, detector, det_type
            )
            times = [datetime.utcfromtimestamp(t) for t in utime_list]
            utime_list = [
                (datetime.utcfromtimestamp(t)).timestamp() for t in utime_list
            ]
            start_time = times[0]
            end_time = times[-1]

            y_list = [index for i in range(0, len(utime_list))]
            ax.plot3D(utime_list, y_list, par_list, color=col, zorder=-index, alpha=0.9)
            ax.set_xlim3d(utime_list[0], utime_list[-1])

            # fill the map with status flags
            if det_type == "spms":
                detector = str(detector)
            if detector not in map_dict:
                map_dict[detector] = status
            else:
                if map_dict[detector] == 0:
                    map_dict[detector] = status
            # save mean over first entries
            string_mean_dict[detector] = {parameter: str(par_array_mean)}

            # skip those detectors that are not within the time window
            if start_time == 0 and end_time == 0:
                continue
            start_times.append(start_time)
            end_times.append(end_time)

    # no data were found at all
    if len(start_times) == 0 and len(end_times) == 0:
        return None, None

    # x-axis in dates
    locs = np.linspace(min(start_times).timestamp(), max(end_times).timestamp(), 10)
    xlab = "%d/%m"
    if j_config[11]["frmt"] == "day/month-time":
        xlab = "%d/%m\n%H:%M"
    if j_config[11]["frmt"] == "time":
        xlab = "%H:%M"
    labels = [datetime.fromtimestamp(loc).strftime(xlab) for loc in locs]

    ax.set_xticks(locs)
    ax.set_xticklabels(labels)
    plt.xticks(locs, labels)

    # plot features
    ax.set_box_aspect(aspect=(1, 1, 0.5))  # aspect ratio for axes
    xlab = j_config[11]["frmt"]
    ax.set_xlabel(f"{xlab} (UTC)", labelpad=20)
    zlab = j_par[0][parameter]["label"]
    if parameter in no_variation_pars:
        if j_par[0][parameter]["units"] != "null":
            zlab = zlab + " [" + j_par[0][parameter]["units"] + "]"
        if parameter == "event_rate":
            units = j_config[6]["par-info"]["event_rate"]["units"]
            zlab = zlab + " [" + units + "]"
    else:
        zlab += ", %"
    ax.set_zlabel(zlab, labelpad=15)

    # define new y-axis values
    yticks_loc = [i for i in range(0, len(det_list))]
    ax.set_yticks(yticks_loc)
    ax.set_yticklabels(y_values, ha="left")  # change number into name

    ax.set_ylim3d(0, len(det_list))
    fig.subplots_adjust(left=-0.21)  # to move the plot towards the left

    # define name of pkl file (with info about time cut if present)
    pkl_name = analysis.set_pkl_name(
        exp,
        period,
        datatype,
        det_type,
        string_number,
        parameter,
        time_range,
    )

    pkl.dump(ax, open(f"{output}/pkl-files/par-vs-time/{pkl_name}", "wb"))
    pdf.savefig(bbox_inches="tight")
    plt.close()

    return string_mean_dict, map_dict


def plot_ch_par_vs_time(
    data: pd.DataFrame,
    det_list: list[str],
    parameter: str,
    time_cut: list[str],
    det_type: str,
    string_number: str,
    det_dict: dict,
    all_ievt: np.ndarray,
    puls_only_ievt: np.ndarray,
    not_puls_ievt: np.ndarray,
    pulser_timestamps: np.ndarray,
    start_code: str,
    time_range: list[str],
    pdf=None,
) -> dict:
    """Plot time evolution of given parameter for each channel separately.

    Parameters
    ----------
    data
                    Pandas dataframes containing dsp/hit data
    det_list
                    List of detectors present in a string
    parameter
                    Parameter to plot
    time_cut
                    List with info about time cuts
    det_type
                    Type of detector (geds or spms)
    string_number
                    Number of the string under study
    det_dict
                    Contains info (crate, card, ch_orca) for geds/spms/other
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
    time_range
                    First and last timestamps of the time range of interest
    """
    columns = 1
    rows = len(det_list)
    plt.rcParams["figure.figsize"] = (14, (9 / 5) * rows)
    fig, ax_array = plt.subplots(
        rows, columns, squeeze=False, sharex=True, sharey=False
    )
    # fig.patch.set_facecolor(j_par[0][parameter]["facecol"])
    # to fix the title position for OB spms
    if "OB" in string_number:
        fig.suptitle(f"{det_type} - {string_number}", y=0.99)
    else:
        fig.suptitle(f"{det_type} - {string_number}")
    ylab = j_par[0][parameter]["label"]
    if parameter in no_variation_pars:
        if j_par[0][parameter]["units"] != "null":
            ylab = ylab + " [" + j_par[0][parameter]["units"] + "]"
        if parameter == "event_rate":
            units = j_config[6]["par-info"]["event_rate"]["units"]
            ylab = ylab + " [" + units + "]"
    else:
        ylab += ", %"
    fig.supylabel(ylab, x=0.005)
    xlab = j_config[11]["frmt"]
    fig.supxlabel(f"{xlab} (UTC)")
    start_times = []
    end_times = []
    map_dict = {}
    string_mean_dict = {}

    for i, ax_row in enumerate(ax_array):
        for axes in ax_row:

            detector = det_list[i]
            # keep entries for the selected detector
            if (
                det_type == "spms"
            ):  # remove the following block when DataLoader is working for spms
                new_data = data
            else:
                new_data = data[data["hit_table"] == int(detector.split("ch")[-1])]

            # skip missing detector
            if (
                det_type == "spms"
            ):  # remove the following block when DataLoader is working for spms
                if len(new_data) == 0:
                    continue
            else:
                if new_data.empty:
                    continue

            # skip detectors that are not geds/spms
            if det_dict[detector]["system"] == "--":
                continue

            if det_type == "geds":
                name = det_dict[detector]["det_id"]
                string_no = det_dict[detector]["string"]["number"]
                string_pos = det_dict[detector]["string"]["position"]
                lbl = f"{name}\ns{string_no}-p{string_pos}-{detector}"
                col = palette[int(string_pos)]
            else:
                name = det_dict[detector]["det_id"]
                lbl = f"{name} - {detector}"
            if det_type == "spms":
                col = j_plot[0][str(detector)]

            if len(time_cut) == 4:
                start_time = time_cut[0] + " " + time_cut[1]
                end_time = time_cut[2] + " " + time_cut[3]

                start_timestamp = (
                    datetime.strptime(start_time, "%d/%m/%Y %H:%M:%S")
                ).timestamp()
                end_timestamp = (
                    datetime.strptime(end_time, "%d/%m/%Y %H:%M:%S")
                ).timestamp()

                new_data = new_data[new_data["timestamp"] > start_timestamp]
                new_data = new_data[new_data["timestamp"] < end_timestamp]

            if exp == "l200":
                # select (or remove) pulser events from timestamps array
                if parameter in pulser_events:
                    new_data = new_data[new_data["timestamp"].isin(pulser_timestamps)]
                elif parameter in physics_events:
                    new_data = new_data[~new_data["timestamp"].isin(pulser_timestamps)]


            # det parameter and time arrays for a given detector
            par_array_mean, par_array, utime_array = parameters.load_parameter(
                new_data,
                parameter,
                detector,
                det_type,
                time_cut,
                all_ievt,
                puls_only_ievt,
                not_puls_ievt,
                pulser_timestamps,
                start_code,
            )
            if len(par_array) == 0:
                continue

            # function to check if par values are outside some pre-defined limits
            utime_list = utime_array.tolist()
            par_list = par_array.tolist()
            status = analysis.check_par_values(
                utime_list, par_list, parameter, detector, det_type
            )
            times = [datetime.fromtimestamp(t) for t in utime_list]
            start_time = times[0]
            end_time = times[-1]

            # if det_type == "spms":
            #     col = j_plot[0][str(detector)]
            # if det_type == "geds":
            #     col = j_plot[1][detector]
            # if det_type == "ch000":
            #     col = "r"
            # if det_type == "ch001":
            #     col = "r"

            # legend
            if parameter not in no_variation_pars:
                lbl += (
                    "\nmean = "
                    + f"{par_array_mean:.2f}"
                    + " ["
                    + j_par[0][parameter]["units"]
                    + "]"
                )

            # plot with rebinning
            if parameter != "event_rate":
                axes.plot(times, par_list, color="darkgray", linewidth=1, label=lbl)
                par_avg, utime_avg = analysis.avg_over_minutes(par_array, utime_array)
                times_avg = [datetime.fromtimestamp(t) for t in utime_avg]
                axes.plot(times_avg, par_avg, color=col, linewidth=2)
            # plot without rebinning
            else:
                axes.plot(
                    times,
                    par_list,
                    color=col,
                    linewidth=0,
                    marker=".",
                    markersize=10,
                    label=lbl,
                )

            axes.legend(
                bbox_to_anchor=(1.01, 1.0),
                loc="upper left",
                borderaxespad=0,
                handlelength=0,
                handletextpad=0,
                frameon=False,
            )

            # line at 0%
            if parameter not in no_variation_pars:
                axes.axhline(y=0, color="k", linestyle="--", linewidth=1)

            yticks = ticker.MaxNLocator(3)
            axes.yaxis.set_major_locator(yticks)

            # fill the map with status flags
            if det_type == "spms":
                detector = str(detector)
            if detector not in map_dict:
                map_dict[detector] = status
            else:
                if map_dict[detector] == 0:
                    map_dict[detector] = status
            # save mean over first entries
            string_mean_dict[detector] = {parameter: str(par_array_mean)}

            # skip those detectors that are not within the time window
            if start_time == 0 and end_time == 0:
                continue
            start_times.append(start_time)
            end_times.append(end_time)

    # no data were found at all
    if len(start_times) == 0 and len(end_times) == 0:
        return None, None

    locs = np.linspace(
        dates.date2num(min(start_times)), dates.date2num(max(end_times)), 10
    )
    xlab = "%d/%m"
    if j_config[11]["frmt"] == "day/month-time":
        xlab = "%d/%m\n%H:%M"
    if j_config[11]["frmt"] == "time":
        xlab = "%H:%M"
    labels = [dates.num2date(loc).strftime(xlab) for loc in locs]

    [ax.set_xticks(locs) for axs in ax_array for ax in axs]
    [ax.set_xticklabels(labels) for axs in ax_array for ax in axs]
    plt.xticks(locs, labels)

    low_lim = []
    high_lim = []

    # might these values become a standard for geds in future?
    if parameter == "baseline":
        low_lim = -5
        high_lim = 5
    elif parameter == "bl_std":
        low_lim = -25
        high_lim = 25
    elif parameter == "uncal_puls":
        low_lim = -0.8
        high_lim = 0.8

    # plt.ylim([low_lim, high_lim])
    # [ax.set_ylim([low_lim, high_lim]) for axs in ax_array for ax in axs]

    # no data were found at all
    if len(start_times) == 0 and len(end_times) == 0:
        return None, None

    # start_name = start_times[0].astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    # end_name = end_times[-1].astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    # define name of pkl file (with info about time cut if present)
    pkl_name = analysis.set_pkl_name(
        exp,
        period,
        datatype,
        det_type,
        string_number,
        parameter,
        time_range,
    )

    fig.tight_layout()
    pkl.dump(ax_array, open(f"{output}/pkl-files/par-vs-time/{pkl_name}", "wb"))
    pdf.savefig(bbox_inches="tight")
    plt.close()

    return string_mean_dict, map_dict
