import json
import os
import re
import sys
import subprocess

from . import slow_control, plotting, subsystem, utils


def retrieve_scdb(user_config_path: str):
    """Set the configuration file and the output paths when a user config file is provided. The function to retrieve Slow Control data from database is then automatically called."""
    # -------------------------------------------------------------------------
    # SSH tunnel to the Slow Control database
    # -------------------------------------------------------------------------
    # for the settings, see instructions on Confluence
    try:
        subprocess.run("ssh -T -N -f ugnet-proxy", shell=True, check=True)
        print("SSH tunnel to Slow Control database established successfully.")
    except subprocess.CalledProcessError as e:
        print("Error running SSH tunnel to Slow Control database command:", e)
        sys.exit()

    # -------------------------------------------------------------------------
    # Read user settings
    # -------------------------------------------------------------------------
    with open(user_config_path) as f:
        config = json.load(f)

    # check validity of scdb settings
    valid = utils.check_scdb_settings(config)
    if not valid:
        return

    # -------------------------------------------------------------------------
    # Define PDF file basename
    # -------------------------------------------------------------------------

    # Format: l200-p02-{run}-{data_type}; One pdf/log/shelve file for each subsystem
    out_path = utils.get_output_path(config) + "-slow_control.hdf"

    # -------------------------------------------------------------------------
    # Load and save data
    # -------------------------------------------------------------------------
    for idx, param in enumerate(config["slow_control"]["parameters"]):
        utils.logger.info(
            "\33[34m~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~\33[0m"
        )
        utils.logger.info(f"\33[34m~~~ R E T R I E V I N G : {param}\33[0m")
        utils.logger.info(
            "\33[34m~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~\33[0m"
        )

        # build a SlowControl object
        # - select parameter of interest from a list of available parameters
        # - apply time interval cuts
        # - get values from SC database (available from LNGS only)
        # - get limits/units/... from SC databasee (available from LNGS only)
        sc_analysis = slow_control.SlowControl(param, dataset=config["dataset"])

        # check if the dataframe is empty or not (no data)
        if utils.check_empty_df(sc_analysis):
            utils.logger.warning(
                "\033[93m'%s' is not inspected, we continue with the next parameter (if present).\033[0m",
                param,
            )
            continue

        # remove the slow control hdf file if
        #   1) it already exists
        #   2) we specified "overwrite" as saving option
        #   3) it is the first parameter we want to save (idx==0)
        if os.path.exists(out_path) and config["saving"] == "overwrite" and idx == 0:
            os.remove(out_path)

        # save data to hdf file
        sc_analysis.data.copy().to_hdf(
            out_path,
            key=param.replace("-", "_"),
            mode="a",
        )


def control_plots(user_config_path: str, n_files=None):
    """Set the configuration file and the output paths when a user config file is provided. The function to generate plots is then automatically called."""
    # -------------------------------------------------------------------------
    # Read user settings
    # -------------------------------------------------------------------------
    with open(user_config_path) as f:
        config = json.load(f)

    # check validity of plot settings
    valid = utils.check_plot_settings(config)
    if not valid:
        return

    # -------------------------------------------------------------------------
    # Define PDF file basename
    # -------------------------------------------------------------------------

    # Format: l200-p02-{run}-{data_type}; One pdf/log/shelve file for each subsystem
    plt_path = utils.get_output_path(config)

    # -------------------------------------------------------------------------
    # Plot
    # -------------------------------------------------------------------------
    generate_plots(config, plt_path, n_files)


def auto_control_plots(
    plot_config: str, file_keys: str, prod_path: str, prod_config: str, n_files=None
):
    """Set the configuration file and the output paths when a config file is provided during automathic plot production."""
    # -------------------------------------------------------------------------
    # Read user settings
    # -------------------------------------------------------------------------
    with open(plot_config) as f:
        config = json.load(f)

    # check validity of plot settings
    valid = utils.check_plot_settings(config)
    if not valid:
        return

    # -------------------------------------------------------------------------
    # Add missing information (output, dataset) to the config
    # -------------------------------------------------------------------------
    config = utils.add_config_entries(config, file_keys, prod_path, prod_config)

    # -------------------------------------------------------------------------
    # Define PDF file basename
    # -------------------------------------------------------------------------
    # Format: l200-p02-{run}-{data_type}; One pdf/log/shelve file for each subsystem

    try:
        data_types = (
            [config["dataset"]["type"]]
            if isinstance(config["dataset"]["type"], str)
            else config["dataset"]["type"]
        )
        plt_basename = "{}-{}-".format(
            config["dataset"]["experiment"].lower(),
            config["dataset"]["period"],
        )
    except (KeyError, TypeError):
        # means something about dataset is wrong -> print Subsystem.get_data doc
        utils.logger.error(
            "\033[91mSomething is missing or wrong in your 'dataset' field of the config. You can see the format here under 'dataset=':\033[0m"
        )
        utils.logger.info("\033[91m%s\033[0m", subsystem.Subsystem.get_data.__doc__)
        return

    user_time_range = utils.get_query_timerange(dataset=config["dataset"])
    # will be returned as None if something is wrong, and print an error message
    if not user_time_range:
        return

    # create output folders for plots
    period_dir = utils.make_output_paths(config, user_time_range)
    # get correct time info for subfolder's name
    name_time = config["dataset"]["run"]
    output_paths = period_dir + name_time + "/"
    utils.make_dir(output_paths)
    if not output_paths:
        return

    # we don't care here about the time keyword timestamp/run -> just get the value
    plt_basename += name_time
    plt_path = output_paths + plt_basename
    plt_path += "-{}".format("_".join(data_types))

    # plot
    generate_plots(config, plt_path, n_files)


def generate_plots(config: dict, plt_path: str, n_files=None):
    """Generate plots once the config file is set and once we provide the path and name in which store results. n_files specifies if we want to inspect the entire time window (if n_files is not specified), otherwise we subdivide the time window in smaller datasets, each one being composed by n_files files."""
    # no subdivision of data (useful when the inspected time window is short enough)
    if n_files is None:
        # some output messages, just to warn the user...
        if config["saving"] is None:
            utils.logger.warning(
                "\033[93mData will not be saved, but the pdf will be.\033[0m"
            )
        elif config["saving"] == "append":
            utils.logger.warning(
                "\033[93mYou're going to append new data to already existing data. If not present, you first create the output file as a very first step.\033[0m"
            )
        elif config["saving"] == "overwrite":
            utils.logger.warning(
                "\033[93mYou have accepted to overwrite already generated files, there's no way back until you manually stop the code NOW!\033[0m"
            )
        else:
            utils.logger.error(
                "\033[91mThe selected saving option in the config file is wrong. Try again with 'overwrite', 'append' or nothing!\033[0m"
            )
            sys.exit()
        # do the plots
        make_plots(config, plt_path, config["saving"])

    # for subdivision of data, let's loop over lists of timestamps, each one of length n_files
    else:
        # list of datasets to loop over later on
        bunches = utils.bunch_dataset(config.copy(), n_files)

        # remove unnecessary keys for precaution - we will replace the time selections with individual timestamps/file keys
        config["dataset"].pop("start", None)
        config["dataset"].pop("end", None)
        config["dataset"].pop("runs", None)

        for idx, bunch in enumerate(bunches):
            utils.logger.debug(f"You are inspecting bunch #{idx+1}/{len(bunches)}...")
            # if it is the first dataset, just override previous content
            if idx == 0:
                config["saving"] = "overwrite"
            # if we already inspected the first dataset, append the ones coming after
            if idx > 0:
                config["saving"] = "append"

            # get the dataset
            config["dataset"]["timestamps"] = bunch
            # make the plots / load data for the dataset of interest
            make_plots(config.copy(), plt_path, config["saving"])


def make_plots(config: dict, plt_path: str, saving: str):
    # -------------------------------------------------------------------------
    # flag events - PULSER
    # -------------------------------------------------------------------------
    # put it in a dict, so that later, if pulser is also wanted to be plotted, we don't have to load it twice
    subsystems = {"pulser": subsystem.Subsystem("pulser", dataset=config["dataset"])}
    # get list of all parameters needed for all requested plots, if any
    parameters = utils.get_all_plot_parameters("pulser", config)
    # get data for these parameters and time range given in the dataset
    # (if no parameters given to plot, baseline and wfmax will always be loaded to flag pulser events anyway)
    subsystems["pulser"].get_data(parameters)
    utils.logger.debug(subsystems["pulser"].data)

    # -------------------------------------------------------------------------
    # flag events - FC baseline
    # -------------------------------------------------------------------------
    subsystems["FCbsln"] = subsystem.Subsystem("FCbsln", dataset=config["dataset"])
    parameters = utils.get_all_plot_parameters("FCbsln", config)
    subsystems["FCbsln"].get_data(parameters)
    # the following 3 lines help to tag FC bsln events that are not in coincidence with a pulser
    subsystems["FCbsln"].flag_pulser_events(subsystems["pulser"])
    subsystems["FCbsln"].flag_fcbsln_only_events()
    subsystems["FCbsln"].data.drop(columns={"flag_pulser"})
    utils.logger.debug(subsystems["FCbsln"].data)

    # -------------------------------------------------------------------------
    # flag events - muon
    # -------------------------------------------------------------------------
    subsystems["muon"] = subsystem.Subsystem("muon", dataset=config["dataset"])
    parameters = utils.get_all_plot_parameters("muon", config)
    subsystems["muon"].get_data(parameters)
    utils.logger.debug(subsystems["muon"].data)

    # -------------------------------------------------------------------------
    # What subsystems do we want to plot?
    subsystems_to_plot = list(config["subsystems"].keys())

    for system in subsystems_to_plot:
        # -------------------------------------------------------------------------
        # set up subsystem
        # -------------------------------------------------------------------------

        # set up if wasn't already set up (meaning, not pulser, previously already set up)
        if system not in subsystems:
            # Subsystem: knows its channel map & software status (on/off channels)
            subsystems[system] = subsystem.Subsystem(system, dataset=config["dataset"])
            # get list of parameters needed for all requested plots, if any
            parameters = utils.get_all_plot_parameters(system, config)
            # get data for these parameters and dataset range
            subsystems[system].get_data(parameters)

        # load also aux channel if necessary (FOR ALL SYSTEMS), and add it to the already existing df
        for plot in config["subsystems"][system].keys():
            # !!! add if for sipms...
            subsystems[system].include_aux(
                config["subsystems"][system][plot]["parameters"],
                config["dataset"],
                config["subsystems"][system][plot],
                "pulser01ana",
            )

        utils.logger.debug(subsystems[system].data)

        # -------------------------------------------------------------------------
        # flag events (FOR ALL SYSTEMS)
        # -------------------------------------------------------------------------
        # flag pulser events for future parameter data selection
        subsystems[system].flag_pulser_events(subsystems["pulser"])
        # flag FC baseline events (not in correspondence with any pulser event) for future parameter data selection
        subsystems[system].flag_fcbsln_events(subsystems["FCbsln"])
        # flag muon events for future parameter data selection
        subsystems[system].flag_muon_events(subsystems["muon"])

        # remove timestamps for given detectors (moved here cause otherwise timestamps for flagging don't match)
        subsystems[system].remove_timestamps(utils.REMOVE_KEYS)
        utils.logger.debug(subsystems[system].data)

        # -------------------------------------------------------------------------
        # make subsystem plots
        # -------------------------------------------------------------------------

        # - set up log file for each system
        # file handler
        file_handler = utils.logging.FileHandler(plt_path + "-" + system + ".log")
        file_handler.setLevel(utils.logging.DEBUG)
        # add to logger
        utils.logger.addHandler(file_handler)

        plotting.make_subsystem_plots(
            subsystems[system], config["subsystems"][system], plt_path, saving
        )

        # -------------------------------------------------------------------------
        # beautification of the log file
        # -------------------------------------------------------------------------
        # Read the log file into a string
        with open(plt_path + "-" + system + ".log") as f:
            log_text = f.read()
        # Define a regular expression pattern to match escape sequences for color codes
        pattern = re.compile(r"\033\[[0-9;]+m")
        # Remove the color codes from the log text using the pattern
        clean_text = pattern.sub("", log_text)
        # Write the cleaned text to a new file
        with open(plt_path + "-" + system + ".log", "w") as f:
            f.write(clean_text)
