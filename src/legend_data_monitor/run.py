from __future__ import annotations

import json
import logging
import os
from datetime import datetime

from matplotlib.backends.backend_pdf import PdfPages

from . import analysis, map, plot, timecut

log = logging.getLogger(__name__)

# config JSON info
j_config, j_par, _ = analysis.read_json_files()
exp = j_config[0]["exp"]
files_path = j_config[0]["path"]["lh5-files"]
version = j_config[0]["path"]["version"]
output = j_config[0]["path"]["output"]
period = j_config[1]
run = j_config[2]
filelist = j_config[3]
datatype = j_config[4]
det_type = j_config[5]
par_to_plot = j_config[6]
qc_flag = par_to_plot["quality_cuts"]
qc_version = par_to_plot["quality_cuts"]["version"]["QualityCuts_flag"][
    "apply_to_version"
]
is_qc_version = par_to_plot["quality_cuts"]["version"]["isQC_flag"]["apply_to_version"]
three_dim_pars = j_config[7]["three_dim_pars"]
time_window = j_config[8]
last_hours = j_config[9]
verbose = j_config[12]


def main():
    start_code = (datetime.now()).strftime("%d/%m/%Y %H:%M:%S")  # common starting time
    path = files_path + version + "/generated/tier"
    out_path = output

    # output folders
    if os.path.isdir(out_path) is False:
        os.mkdir(out_path)
    pdf_path = os.path.join(out_path, "pdf-files")
    log_path = os.path.join(out_path, "log-files")
    json_path = os.path.join(out_path, "json-files")
    for out_dir in ["log-files", "pdf-files", "pkl-files", "json-files"]:
        if out_dir not in os.listdir(out_path):
            os.mkdir(os.path.join(out_path, out_dir))
        if out_dir in ["pdf-files", "pkl-files"]:
            for out_subdir in ["par-vs-time", "heatmaps"]:
                if os.path.isdir(f"{out_path}/{out_dir}/{out_subdir}") is False:
                    os.mkdir(f"{out_path}/{out_dir}/{out_subdir}")
    plot_path = pdf_path + "/par-vs-time"
    map_path = pdf_path + "/heatmaps"

    # time selection info
    time_cut = timecut.build_timecut_list(time_window, last_hours)

    # get start and stop for the time range of interest
    time_range = analysis.get_files_timestamps(time_cut, start_code)
    # output log-filenames
    log_name = (
        f"{log_path}/{exp}-{period}-{datatype}-{time_range[0]}_{time_range[1]}.log"
    )

    # set up logging to file
    logging.basicConfig(
        filename=log_name,
        level=logging.INFO,
        filemode="w",
        format="%(levelname)s: %(message)s",
    )
    # set up logging to console
    console = logging.StreamHandler()
    console.setLevel(logging.ERROR)
    formatter = logging.Formatter("%(asctime)s:  %(message)s")
    console.setFormatter(formatter)
    logging.getLogger("").addHandler(console)

    logging.error(
        f'Started compiling at {(datetime.now()).strftime("%d/%m/%Y %H:%M:%S")}'
    )

    # start analysis
    select_and_plot_run(
        path, json_path, plot_path, map_path, start_code, time_cut, time_range
    )

    logging.error(
        f'Finished compiling at {(datetime.now()).strftime("%d/%m/%Y %H:%M:%S")}'
    )


def select_and_plot_run(
    path: str,
    json_path: str,
    plot_path: str,
    map_path: str,
    start_code: str,
    time_cut: list[str],
    time_range: list[str],
) -> None:
    """
    Select run and call dump_all_plots_together().

    Parameters
    ----------
    path
                Path to lh5 folders
    json_path
                Path where to save mean of perentage variations plots
    plot_path
                Path where to save output plots
    map_path
                Path where to save output heatmaps
    start_code
                Starting time of the code
    time_cut
                List with info about time cuts
    time_range
                First and last timestamps of the time range of interest
    """
    # define output paths
    path = os.path.join(
        plot_path, f"{exp}-{period}-{datatype}-{time_range[0]}_{time_range[1]}.pdf"
    )
    map_path = os.path.join(
        map_path, f"{exp}-{period}-{datatype}-{time_range[0]}_{time_range[1]}.pdf"
    )

    # detector dictionaries
    geds_dict = analysis.load_geds()
    spms_dict = analysis.load_spms()
    mean_dict = {}

    query = analysis.set_query(time_cut, start_code, run)

    """
    # get pulser-events indices (will be put here in common for geds&spms once DataLoader works for spms too)
    all_ievt, puls_only_ievt, not_puls_ievt = analysis.get_puls_ievt(query)
    """
    # all_ievt, puls_only_ievt, not_puls_ievt = analysis.get_puls_ievt(query)

    with PdfPages(path) as pdf:
        with PdfPages(map_path) as pdf_map:
            if (
                det_type["geds"] is False
                and det_type["spms"] is False
                and det_type["ch000"] is False
                and det_type["ch001"] is False
            ):
                logging.error(
                    "NO detectors have been selected! Enable geds and/or spms and/or ch000 in config.json"
                )
                return

            if exp == "l60":
                    # get pulser-events indices (L60)
                    all_ievt, puls_only_ievt, not_puls_ievt = analysis.get_puls_ievt(
                        query
                    )
                    pulser_timestamps = []
            elif exp == "l200":
                # get pulser-events indices (L200)
                pulser_timestamps = analysis.get_pulser_timestamps(query)
                all_ievt = []
                puls_only_ievt = []
                not_puls_ievt = []

            # geds plots
            if det_type["geds"] is True:

                string_geds, string_geds_name = analysis.read_geds(geds_dict)
                geds_par = par_to_plot["geds"]
                if len(geds_par) == 0:
                    logging.error("Geds: NO parameters have been enabled!")
                else:
                    db_parameters = analysis.load_df_cols(geds_par, "geds")
                    dbconfig_filename, dlconfig_filename = analysis.write_config(
                        files_path, version, string_geds, db_parameters, "geds"
                    )
                    data = analysis.read_from_dataloader(
                        dbconfig_filename, dlconfig_filename, query, db_parameters
                    )
                    logging.error("Geds will be plotted...")

                    qc_method = analysis.get_qc_method(
                        version, qc_version, is_qc_version
                    )
                    for entry in ["timestamp", qc_method]:
                        if entry in geds_par:
                            geds_par.remove(entry)

                    for par in geds_par:
                        det_status_dict = {}
                        if par != "timestamp":
                            for (det_list, string) in zip(
                                string_geds, string_geds_name
                            ):

                                if len(det_list) == 0:
                                    continue

                                if par in three_dim_pars:
                                    string_mean_dict, map_dict = plot.plot_wtrfll(
                                        data,
                                        det_list,
                                        par,
                                        time_cut,
                                        "geds",
                                        string,
                                        geds_dict,
                                        all_ievt,
                                        puls_only_ievt,
                                        not_puls_ievt,
                                        start_code,
                                        time_range,
                                        pdf,
                                    )
                                else:
                                    if par == "K_lines":
                                        (
                                            string_mean_dict,
                                            map_dict,
                                        ) = plot.plot_par_vs_time(
                                            data,
                                            det_list,
                                            par,
                                            time_cut,
                                            "geds",
                                            string,
                                            geds_dict,
                                            all_ievt,
                                            puls_only_ievt,
                                            not_puls_ievt,
                                            start_code,
                                            time_range,
                                            pdf,
                                        )
                                    else:
                                        (
                                            string_mean_dict,
                                            map_dict,
                                        ) = plot.plot_ch_par_vs_time(
                                            data,
                                            det_list,
                                            par,
                                            time_cut,
                                            "geds",
                                            string,
                                            geds_dict,
                                            all_ievt,
                                            puls_only_ievt,
                                            not_puls_ievt,
                                            pulser_timestamps,
                                            start_code,
                                            time_range,
                                            pdf,
                                        )
                                if map_dict is not None:
                                    for det, status in map_dict.items():
                                        det_status_dict[det] = status

                                if string_mean_dict is not None:
                                    for k in string_mean_dict:
                                        if k in mean_dict:
                                            mean_dict[k].update(string_mean_dict[k])
                                        else:
                                            mean_dict[k] = string_mean_dict[k]

                                if verbose is True:
                                    if map_dict is not None:
                                        logging.error(
                                            f"\t...{par} for geds (string #{string}) has been plotted!"
                                        )
                                    else:
                                        logging.error(
                                            f"\t...no {par} plots for geds - string #{string}!"
                                        )
                            if det_status_dict != []:
                                map.geds_map(
                                    par,
                                    geds_dict,
                                    string_geds,
                                    string_geds_name,
                                    det_status_dict,
                                    time_cut,
                                    map_path,
                                    start_code,
                                    time_range,
                                    pdf_map,
                                )

            # spms plots
            if det_type["spms"] is True:
                if datatype == "cal":
                    logging.error("No SiPMs for calibration data!")
                else:
                    (
                        spms_merged,
                        spms_name_merged,
                        string_spms,
                        string_spms_name,
                    ) = analysis.read_spms(spms_dict)
                    spms_par = par_to_plot["spms"]
                    if len(spms_par) == 0:
                        logging.error("Spms: NO parameters have been enabled!")
                    else:
                        logging.error("Spms will be plotted...")

                        data = analysis.load_dsp_files(time_cut, start_code)
                        # get pulser-events indices
                        (
                            all_ievt,
                            puls_only_ievt,
                            not_puls_ievt,
                        ) = analysis.get_puls_ievt_spms(data)
                        for par in spms_par:
                            if par in ["energy_in_pe", "trigger_pos"]:
                                for (det_list, string) in zip(
                                    spms_merged, spms_name_merged
                                ):
                                    # if string == "top_IB": # <- for quick checks
                                    plot.plot_par_vs_time_2d(
                                        data,
                                        det_list,
                                        par,
                                        time_cut,
                                        "spms",
                                        string,
                                        spms_dict,
                                        all_ievt,
                                        puls_only_ievt,
                                        not_puls_ievt,
                                        pulser_timestamps,
                                        start_code,
                                        time_range,
                                        pdf,
                                    )
                            else:
                                for (det_list, string) in zip(
                                    spms_merged, spms_name_merged
                                ):
                                    # if string == "top_IB": # <- for quick checks
                                    (_, map_dict,) = plot.plot_ch_par_vs_time(
                                        data,
                                        det_list,
                                        par,
                                        time_cut,
                                        "spms",
                                        string,
                                        spms_dict,
                                        all_ievt,
                                        puls_only_ievt,
                                        not_puls_ievt,
                                        start_code,
                                        time_range,
                                        pdf,
                                    )
                                    if verbose is True:
                                        logging.error(
                                            f"\t...{par} for spms ({string}) has been plotted!"
                                        )
            """
            # enable the following block when the DataLoader works for spms too...
            if det_type["spms"] is True:
                if datatype == "cal":
                    logging.error("No SiPMs for calibration data!")
                else:
                    (
                        spms_merged,
                        spms_name_merged,
                        string_spms,
                        string_spms_name,
                    ) = analysis.read_spms(spms_dict)

                    spms_par = par_to_plot["spms"]
                    if len(spms_par) == 0:
                        logging.error("Spms: NO parameters have been enabled!")
                    else:
                        db_parameters = analysis.load_df_cols(spms_par, "spms")
                        dbconfig_filename, dlconfig_filename = analysis.write_config(
                            files_path, version, string_spms, db_parameters, "spms"
                        )
                        data = analysis.read_from_dataloader(
                            dbconfig_filename, dlconfig_filename, query, db_parameters
                        )

                        logging.error("Spms will be plotted...")
                        if "timestamp" in spms_par:
                            spms_par.remove("timestamp")
                        for par in spms_par:
                            if par in ["energy_in_pe", "trigger_pos"]:
                                for (det_list, string) in zip(
                                    spms_merged, spms_name_merged
                                ):
                                    # if string=="top_IB":
                                    plot.plot_par_vs_time_2d(
                                        data,
                                        det_list,
                                        par,
                                        time_cut,
                                        "spms",
                                        string,
                                        spms_dict,
                                        all_ievt,
                                        puls_only_ievt,
                                        not_puls_ievt,
                                        start_code,
                                        time_range,
                                        pdf,
                                    )
                                    if verbose is True:
                                        logging.error(
                                            f"\t...{par} for spms ({string}) has been plotted!"
                                        )
                            else:
                                det_status_dict = {}
                                for (det_list, string) in zip(
                                    string_spms, string_spms_name
                                ):
                                    if len(det_list) == 0:
                                        continue
                                    if len(string) != 0:
                                        (
                                            _,
                                            map_dict,
                                        ) = plot.plot_ch_par_vs_time(
                                            data,
                                            det_list,
                                            par,
                                            time_cut,
                                            "spms",
                                            string,
                                            spms_dict,
                                            all_ievt,
                                            puls_only_ievt,
                                            not_puls_ievt,
                                            start_code,
                                            time_range,
                                            pdf,
                                        )
                                    if map_dict is not None:
                                        for det, status in map_dict.items():
                                            det_status_dict[det] = status

                                    if verbose is True:
                                        if map_dict is not None:
                                            logging.error(
                                                f"\t...{par} for spms ({string}) has been plotted!"
                                            )
                                        else:
                                            logging.error(
                                                f"\t...no {par} plots for spms - {string}!"
                                            )
                                #if det_status_dict != []:
                                #    map.spms_map(
                                #        par,
                                #        spms_dict,
                                #        spms_merged,
                                #        spms_name_merged,
                                #        det_status_dict,
                                #        time_cut,
                                #        map_path,
                                #        start_code,
                                #        time_ramge,
                                #        pdf_map,
                                #    )
            """

            # ch000 plots
            if det_type["ch000"] is True:
                ch000_par = par_to_plot["ch000"]
                if len(ch000_par) == 0:
                    logging.error("ch000: NO parameters have been enabled!")
                else:
                    db_parameters = analysis.load_df_cols(ch000_par, "ch000")
                    dbconfig_filename, dlconfig_filename = analysis.write_config(
                        files_path, version, [["ch000"]], db_parameters, "ch000"
                    )
                    data = analysis.read_from_dataloader(
                        dbconfig_filename, dlconfig_filename, query, db_parameters
                    )
                    print(data)
                    logging.error("ch000 will be plotted...")
                    if "timestamp" in ch000_par:
                        ch000_par.remove("timestamp")
                    for par in ch000_par:
                        map_dict = plot.plot_par_vs_time_ch000(
                            data,
                            par,
                            time_cut,
                            "ch000",
                            start_code,
                            time_range,
                            pdf,
                        )
                        if verbose is True:
                            if map_dict is not None:
                                logging.error(f"\t...{par} for ch000 has been plotted!")
                            else:
                                logging.error(f"\t...no {par} plots for ch000!")

            # ch001 plots
            if det_type["ch001"] is True:
                ch001_par = par_to_plot["ch001"]
                if len(ch001_par) == 0:
                    logging.error("ch001: NO parameters have been enabled!")
                else:
                    db_parameters = analysis.load_df_cols(ch001_par, "ch001")
                    dbconfig_filename, dlconfig_filename = analysis.write_config(
                        files_path, version, [["ch001"]], db_parameters, "ch001"
                    )
                    data = analysis.read_from_dataloader(
                        dbconfig_filename, dlconfig_filename, query, db_parameters
                    )

                    print(data)
                    logging.error("ch001 will be plotted...")
                    if "timestamp" in ch001_par:
                        ch001_par.remove("timestamp")
                    for par in ch001_par:
                        map_dict = plot.plot_par_vs_time_ch001(
                            data,
                            par,
                            time_cut,
                            "ch001",
                            start_code,
                            pulser_timestamps,
                            time_range,
                            pdf,
                        )
                        if verbose is True:
                            if map_dict is not None:
                                logging.error(f"\t...{par} for ch001 has been plotted!")
                            else:
                                logging.error(f"\t...no {par} plots for ch001!")

    # defining json file name (not for spms; there, we do not have parameters for which we evaluate averages)
    if (
        det_type["geds"] is True
        or det_type["ch000"] is True
        or det_type["ch001"] is True
    ):
        jsonfile_name = (
            f"{exp}-{period}-{datatype}-{time_range[0]}_{time_range[1]}.json"
        )

        # list with all the files already saved in out/json_files directory
        file_list = os.listdir(output + "json-files")
        # if there is no mean_dict.json for this run, create a new one
        if jsonfile_name not in file_list:
            jsonfile_name = str(output + "json-files/" + jsonfile_name)
            json_mean_dict = json.dumps(mean_dict, indent=4)
            with open(jsonfile_name, "w") as f:
                f.write(json_mean_dict)
        if verbose is True:
            logging.error(f"Means are saved in {json_path}")

    if verbose is True:
        logging.error(f"Plots are saved in {path}")
        logging.error(f"Heatmaps are saved in {map_path}")
