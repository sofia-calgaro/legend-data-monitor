import logging
import pickle as pkl
from copy import copy
from datetime import datetime, timezone

import analysis
import matplotlib as mpl
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import parameters
import pygama.lgdo.lh5_store as lh5
import timecut
from matplotlib import dates

# plt.rcParams['figure.figsize'] = (12, 8)
plt.rcParams["figure.figsize"] = (10, 5)
plt.rcParams["font.size"] = 12
j_config, j_par, j_plot = analysis.read_json_files()
exp = j_config[0]["exp"]
period = j_config[1]
run = j_config[2]
datatype = j_config[3]


def plot_parameters(ax, par_array, utime_array, detector, det_type, parameter):
    """
    Description
    -----------
    Plots the parameter VS time and check if parameters are
    below/above soome given thresholds.

    Parameters
    ----------
    par_array   : array
                  Array with parameter values
    utime_array : array
                  Array with (shifted+cut) time values
    detector    : string
                  Name of the detector
    det_type    : string
                  Type of detector (geds or spms)
    parameter   : string
                  Parameter to plot
    """

    # evaluate (x,y) points
    time_slice = j_config[4][det_type]
    if parameter != "event_rate":
        times_average, par_average = analysis.par_time_average(
            utime_array, par_array, time_slice
        )
    else:
        times_average = utime_array
        par_average = par_array

    # function to check if par values are outside some pre-defined limits
    status = analysis.check_par_values(
        times_average, par_average, parameter, detector, det_type
    )
    times = [datetime.fromtimestamp(t) for t in times_average]

    status_flag = j_config[9][det_type]

    if status_flag == True:
        if status == 1:
            if det_type == "spms":
                ax.plot(times, par_average, color=j_plot[2][str(detector)], linewidth=1)
                plt.plot(
                    times, par_average, color=j_plot[2][str(detector)], linewidth=1
                )
            if det_type == "geds":
                ax.plot(times, par_average, color=j_plot[3][detector], linewidth=1)
                plt.plot(times, par_average, color=j_plot[3][detector], linewidth=1)
    else:
        if det_type == "spms":
            ax.plot(times, par_average, color=j_plot[2][str(detector)], linewidth=1)
            plt.plot(times, par_average, color=j_plot[2][str(detector)], linewidth=1)
        if det_type == "geds":
            ax.plot(times, par_average, color=j_plot[3][detector], linewidth=1)
            plt.plot(times, par_average, color=j_plot[3][detector], linewidth=1)

    return times[0], times[-1], status, ax


def plot_par_vs_time(
    raw_files,
    det_list,
    parameter,
    time_cut,
    det_type,
    string_number,
    det_dict,
    pdf=None,
):
    """
    Parameters
    ----------
    raw_files     : list
                    Strings of lh5 raw files
    parameter     : string
                    Paramter to plot
    time_cut      : list
                    List with info about time cuts
    det_type      : string
                    Type of detector (geds or spms)
    string_number : string
                    Number of the string under study
    det_dict      : dictionary
                    Contains info (crate, card, ch_orca) for geds/spms/other
    """

    fig, ax = plt.subplots(1, 1)
    plt.figure().patch.set_facecolor(j_par[0][parameter]["facecol"])
    start_times = []
    end_times = []
    handle_list = []
    map_dict = {}

    for raw_file in raw_files:
        dsp_file = raw_file.replace("raw", "dsp")
        # if os.path.exists(dsp_file) == False:          # too verbose (but could be useful..add it in the log file maybe?)
        #    print(f'File {dsp_file} does not exist')

        for detector in det_list:
            if det_type == "geds":
                if detector not in lh5.ls(raw_file, ""):
                    logging.warning(f'No "{detector}" branch in file {raw_file}')
                    continue
            if det_type == "spms":
                if detector not in lh5.ls(raw_file, ""):
                    logging.warning(f'No "{detector}" branch in file {raw_file}')
                    continue

            # add entries for the legend
            card = det_dict[detector]["card"]
            ch_orca = det_dict[detector]["ch_orca"]
            crate = det_dict[detector]["crate"]
            if raw_file == raw_files[0]:
                if det_type == "spms":
                    handle_list.append(
                        mpatches.Patch(
                            color=j_plot[2][str(detector)],
                            label=f"{detector} - FC: {card},{ch_orca} ({crate})",
                        )
                    )
                if det_type == "geds":
                    handle_list.append(
                        mpatches.Patch(
                            color=j_plot[3][detector],
                            label=f"{detector} - FC: {card},{ch_orca} ({crate})",
                        )
                    )

            # plot detectors of the same string
            par_np_array, utime_array = parameters.load_parameter(
                parameter, raw_file, dsp_file, detector, det_type, time_cut
            )

            # to handle particular cases where the timestamp array is outside the time window:
            if len(par_np_array) == 0 and len(utime_array) == 0:
                continue

            start_time, end_time, status, ax = plot_parameters(
                ax, par_np_array, utime_array, detector, det_type, parameter
            )

            # fill the map with status flags
            if det_type == "spms":
                detector = str(detector)
            if detector not in map_dict:
                map_dict[detector] = status
            else:
                if map_dict[detector] == 0:
                    map_dict[detector] = status

            # skip those events that are not within the time window
            if start_time == 0 and end_time == 0:
                if raw_file != raw_files[-1]:
                    continue
                else:
                    break
            start_times.append(start_time)
            end_times.append(end_time)

    if len(start_times) == 0 and len(end_times) == 0:
        logging.warning(f'No "{det_type}" plot')
        return

    # 1D-plot
    local_timezone = datetime.now(timezone.utc).astimezone().tzinfo
    locs = np.linspace(
        dates.date2num(start_times[0]), dates.date2num(end_times[-1]), 10
    )
    xlab = "%d/%m"
    if j_config[10]["frmt"] == "day/month-time":
        xlab = "%d/%m\n%H:%M"
    if j_config[10]["frmt"] == "time":
        xlab = "%H:%M"
    labels = [dates.num2date(loc, tz=local_timezone).strftime(xlab) for loc in locs]
    ax.set_xticks(locs)
    ax.set_xticklabels(labels)
    plt.xticks(locs, labels)
    plt.xticks(rotation=45, ha="center")
    ax.legend(
        loc=(1.04, 0.0),
        ncol=1,
        frameon=True,
        facecolor="white",
        framealpha=0,
        handles=handle_list,
    )
    ax.grid(axis="both")
    plt.legend(
        loc=(1.04, 0.0),
        ncol=1,
        frameon=True,
        facecolor="white",
        framealpha=0,
        handles=handle_list,
    )
    plt.xticks(rotation=45, ha="center")
    plt.grid(axis="both")
    ylab = j_par[0][parameter]["label"]
    if j_par[0][parameter]["units"] != "null":
        ylab = ylab + " [" + j_par[0][parameter]["units"] + "]"
    if parameter == "event_rate":
        units = j_config[5]["Available-par"]["Other-par"]["event_rate"]["units"][
            det_type
        ]
        ylab = ylab + " [" + units + "]"
    ax.set_ylabel(ylab)
    ax.set_xlabel(f'{j_config[10]["frmt"]} (UTC)')
    plt.ylabel(ylab)
    plt.xlabel(f'{j_config[10]["frmt"]} (UTC)')

    # set title
    if det_type == "spms":
        ax.set_title(f"spms - {string_number}")
        plt.title(f"spms - {string_number}")
    if det_type == "geds":
        ax.set_title(f"geds - string #{string_number}")
        plt.title(f"geds - string #{string_number}")

    # set y-label
    low_lim = j_par[0][parameter]["limit"][det_type][0]
    upp_lim = j_par[0][parameter]["limit"][det_type][1]
    if low_lim != "null":
        ax.axhline(y=low_lim, color="r", linestyle="--", linewidth=2)
        plt.axhline(y=low_lim, color="r", linestyle="--", linewidth=2)
    if upp_lim != "null":
        ax.axhline(y=upp_lim, color="r", linestyle="--", linewidth=2)
        plt.axhline(y=upp_lim, color="r", linestyle="--", linewidth=2)
    # plt.ylim(low_lim*(1-0.01), upp_lim*(1+0.01)) # y-axis zoom
    # if det_type == 'geds': plt.ylim(0,40)
    # if det_type == 'spms': plt.ylim(0,4)

    # define name of pkl file (with info about time cut if present)
    if len(time_cut) != 0:
        start, end = timecut.time_dates(time_cut)
        if det_type == "geds":
            pkl_name = (
                exp
                + "-"
                + period
                + "-"
                + run
                + "-"
                + datatype
                + "-"
                + start
                + "_"
                + end
                + "-"
                + parameter
                + "-string"
                + string_number
                + ".pkl"
            )
        if det_type == "spms":
            pkl_name = (
                exp
                + "-"
                + period
                + "-"
                + run
                + "-"
                + datatype
                + "-"
                + start
                + "_"
                + end
                + "-"
                + parameter
                + "-"
                + string_number
                + ".pkl"
            )
    else:
        if det_type == "geds":
            pkl_name = (
                exp
                + "-"
                + period
                + "-"
                + run
                + "-"
                + datatype
                + "-"
                + parameter
                + "-string"
                + string_number
                + ".pkl"
            )
        if det_type == "spms":
            pkl_name = (
                exp
                + "-"
                + period
                + "-"
                + run
                + "-"
                + datatype
                + "-"
                + parameter
                + "-"
                + string_number
                + ".pkl"
            )

    pkl.dump(ax, open(f"pkl-files/par-vs-time/{pkl_name}", "wb"))
    pdf.savefig(bbox_inches="tight")
    plt.close()

    logging.info(f'"{parameter}" is plotted from {start_times[0]} to {end_times[-1]}')

    return map_dict


def plot_par_vs_time_2d(
    raw_files, det_list, time_cut, det_type, string_number, det_dict, pdf=None
):
    """
    Description:
    No map is provided as an output.

    Parameters
    ----------
    raw_files     : list
                    Strings of lh5 raw files
    det_list      : list
                    Detector channel numbers
    time_cut      : list
                    List with info about time cuts
    string_number : string
                    Number of the string under study
    det_type      : string
                    Type of detector (geds or spms)
    det_dict      : dictionary
                    Contains info (crate, card, ch_orca) for geds/spms/other
    """

    parameter = "gain"
    handle_list = []
    plt.rcParams["font.size"] = 6
    if "OB" in string_number:
        fig, (
            (ax1, ax2, ax3, ax4, ax5),
            (ax6, ax7, ax8, ax9, ax10),
            (ax11, ax12, ax13, ax14, ax15),
            (ax16, ax17, ax18, ax19, ax20),
        ) = plt.subplots(4, 5, sharex=True, sharey=True)
        ax_list = [
            ax1,
            ax2,
            ax3,
            ax4,
            ax5,
            ax6,
            ax7,
            ax8,
            ax9,
            ax10,
            ax11,
            ax12,
            ax13,
            ax14,
            ax15,
            ax16,
            ax17,
            ax18,
            ax19,
            ax20,
        ]
    if "IB" in string_number:
        fig, ((ax1, ax2, ax3), (ax4, ax5, ax6), (ax7, ax8, ax9)) = plt.subplots(
            3, 3, sharex=True, sharey=True
        )
        ax_list = [ax1, ax2, ax3, ax4, ax5, ax6, ax7, ax8, ax9]

    ax_idx = 0
    fig.patch.set_facecolor(j_par[0][parameter]["facecol"])
    fig.suptitle(f"spms - {string_number}", fontsize=8)

    for detector in det_list:
        wf_array = lh5.load_nda(
            raw_files, ["values"], detector + "/raw/waveform", verbose=False
        )["values"]

        # add entries for the legend
        card = det_dict[detector]["card"]
        ch_orca = det_dict[detector]["ch_orca"]
        crate = det_dict[detector]["crate"]
        if det_type == "spms":
            handle_list.append(
                mpatches.Patch(
                    color=j_plot[2][str(detector)],
                    label=f"{detector} - FC: {card},{ch_orca} ({crate})",
                )
            )
        if det_type == "geds":
            handle_list.append(
                mpatches.Patch(
                    color=j_plot[3][detector],
                    label=f"{detector} - FC: {card},{ch_orca} ({crate})",
                )
            )

        # select the channel
        utime_array = analysis.build_utime_array(
            raw_files, detector, "spms"
        )  # shifted timestamps (puls events are not removed)
        utime_array, wf_array = analysis.time_analysis(utime_array, wf_array, time_cut)

        # calculate the gain
        if parameter == "gain":
            par_array = parameters.spms_gain(wf_array)
        if len(par_array) == 0 and len(utime_array) == 0:
            continue

        # define x-axis
        start_time = datetime.fromtimestamp(utime_array[0])
        end_time = datetime.fromtimestamp(utime_array[-1])
        local_timezone = datetime.now(timezone.utc).astimezone().tzinfo
        locs = np.linspace(dates.date2num(start_time), dates.date2num(end_time), 3)
        xlab = "%d/%m"
        if j_config[10]["frmt"] == "day/month-time":
            xlab = "%d/%m\n%H:%M"
        if j_config[10]["frmt"] == "time":
            xlab = "%H:%M"
        labels = [dates.num2date(loc, tz=local_timezone).strftime(xlab) for loc in locs]

        # 2D-plot
        H, xedges, yedges = np.histogram2d(
            utime_array,
            par_array,
            bins=[200, 200],
            range=[[utime_array[0], utime_array[-1]], [0, 300]],
        )
        to_datetime = np.vectorize(datetime.fromtimestamp)
        xedges_datetime = to_datetime(xedges)
        cmap = copy(plt.get_cmap("hot"))
        cmap.set_bad(cmap(0))

        ylab = j_par[0][parameter]["label"]
        if j_par[0][parameter]["units"] != "null":
            ylab = ylab + " [" + j_par[0][parameter]["units"] + "]"

        ax_list[ax_idx].pcolor(
            xedges_datetime, yedges, H.T, norm=mpl.colors.LogNorm(), cmap="magma"
        )
        if "OB" in string_number:
            ax_list[ax_idx].set_title(
                f"{detector} - FC: {card},{ch_orca} ({crate})", fontsize=7, y=0.93
            )
            if ax_idx == 0 or ax_idx == 5 or ax_idx == 10 or ax_idx == 15:
                ax_list[ax_idx].set(ylabel="Gain [ADC]")
            if (
                ax_idx == 15
                or ax_idx == 16
                or ax_idx == 17
                or ax_idx == 18
                or ax_idx == 19
            ):
                ax_list[ax_idx].set(xlabel=f'{j_config[10]["frmt"]} (UTC)')
        if "IB" in string_number:
            ax_list[ax_idx].set_title(
                f"{detector} - FC: {card},{ch_orca} ({crate})", fontsize=7, y=0.95
            )
            if ax_idx == 0 or ax_idx == 3 or ax_idx == 6:
                ax_list[ax_idx].set(ylabel="Gain [ADC]")
            if ax_idx == 6 or ax_idx == 7 or ax_idx == 8:
                ax_list[ax_idx].set(xlabel=f'{j_config[10]["frmt"]} (UTC)')
        ax_list[ax_idx].set_xticks(locs)
        ax_list[ax_idx].set_xticklabels(labels)
        plt.setp(ax_list[ax_idx].get_xticklabels(), rotation=0, ha="center")

        ax_idx += 1
        handle_list = []
        start_time = end_time = 0

    # define name of pkl file (with info about time cut if present)
    if len(time_cut) != 0:
        start, end = timecut.time_dates(time_cut)
        if det_type == "geds":
            pkl_name = (
                exp
                + "-"
                + period
                + "-"
                + run
                + "-"
                + datatype
                + "-"
                + start
                + "_"
                + end
                + "-"
                + parameter
                + "-string"
                + string_number
                + ".pkl"
            )
        if det_type == "spms":
            pkl_name = (
                exp
                + "-"
                + period
                + "-"
                + run
                + "-"
                + datatype
                + "-"
                + start
                + "_"
                + end
                + "-"
                + parameter
                + "-"
                + string_number
                + ".pkl"
            )
    else:
        if det_type == "geds":
            pkl_name = (
                exp
                + "-"
                + period
                + "-"
                + run
                + "-"
                + datatype
                + "-"
                + parameter
                + "-string"
                + string_number
                + ".pkl"
            )
        if det_type == "spms":
            pkl_name = (
                exp
                + "-"
                + period
                + "-"
                + run
                + "-"
                + datatype
                + "-"
                + parameter
                + "-"
                + string_number
                + ".pkl"
            )

    pkl.dump(ax_list, open(f"pkl-files/par-vs-time/{pkl_name}", "wb"))
    pdf.savefig(bbox_inches="tight")
    plt.close()

    return
