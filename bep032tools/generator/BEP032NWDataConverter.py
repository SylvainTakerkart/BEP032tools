from pathlib import Path
from datetime import datetime
import filecmp
import shutil
import argparse
import os
import re
import glob
import numpy as np

#import bep032tools.validator.BEP032Validator
from bep032tools.generator.BEP032Generator import BEP032Data
from bep032tools.generator.utils import *


try:
    import pandas as pd

    HAVE_PANDAS = True
except ImportError:
    HAVE_PANDAS = False

try:
    import neo

    HAVE_NEO = True
except ImportError:
    HAVE_NEO = False

from bep032tools.validator.BEP032Validator import build_rule_regexp
from bep032tools.rulesStructured import RULES_SET
from bep032tools.rulesStructured import DATA_EXTENSIONS

METADATA_LEVELS = {i: r['authorized_metadata_files'] for i, r in enumerate(RULES_SET)}
METADATA_LEVEL_BY_NAME = {build_rule_regexp(v)[0]: k for k, values in METADATA_LEVELS.items() for v in values}

# TODO: These can be extracted from the BEP032Data init definition. Check out the
# function inspection options
ESSENTIAL_CSV_COLUMNS = ['sub_id', 'ses_id']
OPTIONAL_CSV_COLUMNS = ['tasks', 'runs', 'data_file']


class BEP032PatchClampNWData(BEP032Data):
    """
    Representation of a patchclamp dataset recorded by NW at INT, Marseille, France, as a
    BEP032 object, as specified by in the
    [ephys BEP](https://bids.neuroimaging.io/bep032)

    The BEP032Data object can track multiple realizations of `split`, `run`, `task` but only a
    single realization of `session` and `subject`, i.e. to represent multiple `session` folders,
    multiple BEP032Data objects are required. To include multiple realizations of tasks
    or runs, call the `register_data` method for each set of parameters separately.
    The particularity of patchclamp data is that we do not use the concept of `session`, nor the
    corresponding directory in the BIDS hierarchy. Therefore, for now, this implementation is
    a bit of a hack (no change in the core of the class definition), but it might evolve in the
    future and require changes in the core of the class.

    Parameters
    ----------
    sub_id : str
        subject identifier, e.g. '0012' or 'j.s.smith'
    ses-id : str
        session identifier, e.g. '20210101' or '007'; not used for patchclamp data; implementation to be adjusted
        in the future!
    tasks : str
        task identifier of data files
    runs : str
        run identifier of data files


    """

    def __init__(self, sub_id, ses_id):
        super().__init__(sub_id, ses_id, modality='ephys', ephys_type='ice')

    def register_data_files(self, *files, task=None, run=None, autoconvert=None):
        """
        Register data with the BEP032 data structure.

        Parameters
        ----------
        *files : path to files to be added as data files.
            If multiple files are provided they are treated as a single data files split into
            multiple chunks and will be enumerated according to the order they are provided in.

        task: str
            task name used
        run: str
            run name used
        autoconvert: str
            accepted values: 'nix', 'nwb'. Automatically convert to the specified format.
            Warning: Using this feature can require extensive compute resources. Default: None
        """

        files = [Path(f) for f in files]
        for file_idx in range(len(files)):
            if files[file_idx].suffix not in DATA_EXTENSIONS:
                if autoconvert is None:
                    raise ValueError(f'Wrong file format of data {files[file_idx].suffix}. '
                                     f'Valid formats are {DATA_EXTENSIONS}. Use `autoconvert`'
                                     f'parameter for automatic conversion.')
                elif autoconvert not in ['nwb', 'nix']:
                    raise ValueError(f'`autoconvert` only accepts `nix` and `nwb` as values, '
                                     f'received {autoconvert}.')

                print(f'Converting data file to {autoconvert} format.')
                files[file_idx] = convert_data(files[file_idx], autoconvert)

        key = ''
        if task is not None:
            key += f'task-{task}'
        if run is not None:
            if key:
                key += '_'
            key += f'run-{run}'

        if key not in self.data:
            self.data[key] = files
        else:
            self.data[key].extend(files)

    @property
    def basedir(self):
        return self._basedir

    @basedir.setter
    def basedir(self, basedir):
        """
        Parameters
        ----------
        basedir : (str,path)
            path to the projects base folder (project root).
        """
        if not Path(basedir).exists():
            raise ValueError('Base directory does not exist')
        self._basedir = Path(basedir)

    def get_data_folder(self, mode='absolute'):
        """
        Generates the path to the folder of the data files

        Parameters
        ----------
        mode : str
            Returns an absolute or relative path
            Valid values: 'absolute', 'local'

        Returns
        ----------
        pathlib.Path
            Path of the data folder
        """

        if self.ephys_type == 'ece':
            # for extra-cellular ephys, a session-level directory is used in the BIDS hierarchy
            path = Path(f'sub-{self.sub_id}', f'ses-{self.ses_id}', self.modality)
        elif self.ephys_type == 'ice':
            # for intra-cellular ephys, there is no session-level directory in the BIDS hierarchy
            path = Path(f'sub-{self.sub_id}', self.modality)
        else:
            raise ValueError('The ephys_type option should take the value ece or ice to designate extra- or intra-'
                             'cellular electrophysiology')

        if mode == 'absolute':
            if self.basedir is None:
                raise ValueError('No base directory set.')
            path = self.basedir / path

        return path

    def generate_directory_structure(self):
        """
        Generate the required folders for storing the dataset

        Returns
        ----------
        path
            Path of created data folder
        """

        if self.basedir is None:
            raise ValueError('No base directory set.')

        data_folder = Path(self.basedir).joinpath(self.get_data_folder())
        data_folder.mkdir(parents=True, exist_ok=True)

        if self.ephys_type == 'ece':
            self.filename_stem = f'sub-{self.sub_id}_ses-{self.ses_id}'
        elif self.ephys_type == 'ice':
            self.filename_stem = f'sub-{self.sub_id}'
        else:
            raise ValueError('The ephys type should be take the value ece or ice')

        return data_folder

    def organize_data_files(self, mode='link', output_format='nwb'):
        """
        Add datafiles to BEP032 structure

        Parameters
        ----------
        mode: str
            Can be either 'link', 'copy', 'move' or 'convert'.
            This function overrides the one in the parent class BEP032data. It only adds the 'convert' mode to
            deal with data conversion, for now only for the particular case of the NW patchclamp dataset.
        """
        postfix = '_ephys'
        if self.basedir is None:
            raise ValueError('No base directory set.')

        if self.filename_stem is None:
            raise ValueError('No filename stem set.')

        data_folder = self.get_data_folder(mode='absolute')

        for key, files in self.data.items():
            # add '_' prefix for filename concatenation
            if key:
                key = '_' + key
            for i, file in enumerate(files):
                if mode == 'convert':
                    suffix = '.' + output_format
                    new_filename = self.filename_stem + key + suffix
                    destination = data_folder / new_filename
                    print(str(destination))
                    convert_file(str(file), str(destination), output_format)
                else:
                    # preserve the suffix
                    suffix = file.suffix
                    # append split postfix if required
                    split = ''
                    if len(files) > 1:
                        split = f'_split-{i}'
                    new_filename = self.filename_stem + key + split + postfix + suffix
                    destination = data_folder / new_filename
                    create_file(file, destination, mode, exist_ok=True)

    def convert_file(source, destination, output_format):
        """
        Create a file at a destination location with format conversion

        Parameters
        ----------
        source: str
            Path of the file containing the original data.
        destination: str
            Path of the converted data file.
        output_format: str
            Output file format. Valid parameters are 'nwb' and 'nix'.

        Raises
        ----------
        ValueError
            In case of invalid output_format.
        """
        if output_format == 'nwb':
            if False:  # temporary debugging thing... do not really convert the file, just create an empty destination file!
                print(source, type(destination))
                # Read the file
                ior = neo.io.AxonIO(filename=source)
                blk = ior.read_block()
                # blk.annotate(session_start_time=datetime.datetime(2020, 7, 23, 9, 55, 0))
                blk.annotate(session_description='tmp session description')
                blk.annotate(identifier='tmp identifier')
                # Write nwb file
                iow = neo.io.NWBIO(filename=destination, mode="w")
                iow.write_all_blocks([blk])
            else:
                open(destination, 'w').close()
        else:
            raise ValueError(f'Invalid output data format "{output_format}"')

    def generate_metadata_file_participants(self, output):
        age = self.md['participants_md']['age']
        date = self.md['participants_md']['date']
        participant_df = pd.DataFrame([
            ['sub-' + self.sub_id, 'rattus norvegicus', age, 'M', '2001-01-01T00:00:00']],
            columns=['participant_id', 'species', 'age', 'sex', 'birthday'])
        participant_df.set_index('participant_id', inplace=True)
        if not output.with_suffix('.tsv').exists():
            # create participants.tsv file
            participant_df.to_csv(output.with_suffix('.tsv'), mode='w', index=True, header=True, sep='\t')
            #save_tsv(participant_df, output)
        else:
            # append new subject to existing participants.tsv file
            participant_df.to_csv(output.with_suffix('.tsv'), mode='a', index=True, header=False, sep='\t')

    def generate_metadata_file_samples(self, output):
        n_samples = len(self.md['samples_md'])
        samples_df = pd.DataFrame(columns=['sample_id', 'sample_type', 'participant_id'])
        for sample_ind in range(n_samples):
            sample_id = self.md['samples_md'][sample_ind]['sample_id']
            sample_type = self.md['samples_md'][sample_ind]['sample_type']
            participant_id = self.md['samples_md'][sample_ind]['participant_id']
            current_sample_df = pd.DataFrame([[sample_id, sample_type, participant_id]],
                                             columns=['sample_id', 'sample_type', 'participant_id'])
            samples_df = pd.concat([samples_df,current_sample_df])
        samples_df.set_index('sample_id', inplace=True)
        if not output.with_suffix('.tsv').exists():
            # create samples.tsv file
            samples_df.to_csv(output.with_suffix('.tsv'), mode='w', index=True, header=True, sep='\t')
            #save_tsv(participant_df, output)
        else:
            # append data from new subject to existing samples.tsv file
            samples_df.to_csv(output.with_suffix('.tsv'), mode='a', index=True, header=False, sep='\t')


    def generate_metadata_file_tasks(self, output):
        pass

    def generate_metadata_file_dataset_description(self, output):
        task_dict = {
            "Name": "Electrophysiology",
            "BIDSVersion": "1.6.0",
            "License": "CC BY 4.0",
            "Authors": ["NW"],
            "Acknowledgements": "We thank the Rudolf the reindeer, the christmas gnomes and "
                                "Miss Moneypenny.",
            "HowToAcknowledge": "Bond J, Claus S (2000) How to deliver 1 Million parcel in one "
                                "night. https://doi.org/007/007 ",
            "Funding": ["ANR blahblah"],
            "ReferencesAndLinks": "https://doi.org/007/007",
        }
        save_json(task_dict, output)

    def generate_metadata_file_probes(self, output):
        probes_df = pd.DataFrame([
            ['e380a', 'multi-shank', 0, 'iridium-oxide', 0, 0, 0, 'circle', 20],
            ['e380b', 'multi-shank', 1.5, 'iridium-oxide', 0, 100, 0, 'circle', 20],
            ['t420a', 'tetrode', 3.6, 'iridium-oxide', 0, 200, 0, 'circle', 20],
            ['t420b', 'tetrode', 7, 'iridium-oxide', 500, 0, 0, 'circle', 20]],
            columns=['probe_id', 'type', 'coordinate_space', 'material', 'x', 'y', 'z', 'shape',
                     'contact_size'])
        probes_df.set_index('probe_id', inplace=True)
        save_tsv(probes_df, output)

    def generate_metadata_file_channels(self, output):
        pass

    def generate_metadata_file_contacts(self, output):
        pass

    def generate_metadata_file_ephys(self, output):
        pass

    def generate_metadata_file_scans(self, output):
        pass

    def validate(self):
        """
        Validate the generated structure using the BEP032 validator

        Parameters
        ----------
        output_folder: str
            path to the folder to validate

        Returns
        ----------
        bool
            True if validation was successful. False if it failed.
        """
        bep032tools.validator.BEP032Validator.is_valid(self.basedir)


def convert_data(source_file, output_format):
    if not HAVE_NEO:
        raise ValueError('Conversion of data required neo package to be installed. '
                         'Use `pip install neo`')

    io = neo.io.get_io(source_file)
    block = io.read_block()

    output_file = Path(source_file).with_suffix('.' + output_format)

    if output_format == 'nix':
        io_write = neo.NixIO(output_file, mode='rw')
    elif output_format == 'nwb':
        io_write = neo.NWBIO(str(output_file), mode='w')
    else:
        raise ValueError(f'Supported formats are `nwb` and `nix`, not {output_format}')

    # ensure all required annotations are present for nwb file generation
    start_time = datetime.fromtimestamp(int(block.segments[0].t_start.rescale('s')))
    block.annotations.setdefault('session_start_time', start_time)
    block.annotations.setdefault('session_description', block.file_origin)
    block.annotations['session_description'] = str(block.annotations['session_description'])
    block.annotations.setdefault('identifier', block.file_origin)
    block.annotations['identifier'] = str(block.annotations['identifier'])

    io_write.write_all_blocks([block])

    return output_file


def create_file(source, destination, mode, exist_ok=False):
    """
    Create a file at a destination location

    Parameters
    ----------
    source: str
        Source location of the file.
    destination: str
        Destination location of the file.
    mode: str
        File creation mode. Valid parameters are 'copy', 'link' and 'move'.
    exist_ok: bool
        If False, raise an Error if the destination already exist. Default: False

    Raises
    ----------
    ValueError
        In case of invalid creation mode.
    """
    if Path(destination).exists():
        if not exist_ok:
            raise ValueError(f'Destination already exists: {destination}')
        # ensure file content is the same
        elif not filecmp.cmp(source, destination, shallow=True):
            raise ValueError(f'File content of source ({source}) and destination ({destination}) '
                             f'differs.')
        # remove current version to create new version with new mode
        Path(destination).unlink()

    if mode == 'copy':
        shutil.copy(source, destination)
    elif mode == 'link':
        os.link(source, destination)
    elif mode == 'move':
        shutil.move(source, destination)
    else:
        raise ValueError(f'Invalid file creation mode "{mode}"')


def extract_structure_from_csv(csv_file):
    """
    Load csv file that contains folder structure information and return it as pandas.datafram.

    Parameters
    ----------
    csv_file: str
        The file to be loaded.

    Returns
    -------
    pandas.dataframe
        A dataframe containing the essential columns for creating an BEP032 structure
    """
    if not HAVE_PANDAS:
        raise ImportError('Extraction of bep032tools structure from csv requires pandas.')

    df = pd.read_csv(csv_file, dtype=str)

    # ensure all fields contain information
    if df.isnull().values.any():
        raise ValueError(f'Csv file contains empty cells.')

    # standardizing column labels
    # df = df.rename(columns=LABEL_MAPPING)

    # Check is the header contains all required names
    if not set(ESSENTIAL_CSV_COLUMNS).issubset(df.columns):
        raise ValueError(f'Csv file ({csv_file}) does not contain required information '
                         f'({ESSENTIAL_CSV_COLUMNS}). Accepted column names are specified in the BEP.')

    return df


def read_NW_metadata(metadata_file):
    """
    Read the excel metadata file as formatted by NW

    Parameters
    ----------
    metadata_file: str
        Source location of the file.

    Raises
    ----------
    ValueError
        In case of invalid creation mode.

    Returns
    ----------
    metadata
        Pandas dataframe
    """

    md = pd.read_excel(metadata_file)

    metadata = {}

    participants_metadata = {}
    samples_metadata_list = []

    participants_metadata.update({'date': str(md.columns[1])})
    participants_metadata.update({'sex': np.array(md.loc[(md[md.columns[1]]=='Sexe')][md.columns[2]])[0]})
    participants_metadata.update({'strain': np.array(md.loc[(md[md.columns[1]]=='Mice Line')][md.columns[2]])[0]})
    participants_metadata.update({'weight': np.array(md.loc[(md[md.columns[1]]=='Weight')][md.columns[2]])[0]})
    participants_metadata.update({'age': np.array(md.loc[(md[md.columns[1]]=='Age')][md.columns[2]])[0]})
    participants_metadata.update({'participant_id': 'sub-{}'.format(participants_metadata['date'][0:10])})

    samples_inds_list = md.loc[(md[md.columns[1]]=='Slice')].index

    all_filenames_list = []
    for ind, sample_ind in enumerate(samples_inds_list):
        # create sub data frame for the current sample / cell
        start_ind = sample_ind
        if ind < len(samples_inds_list) - 1:
            end_ind = samples_inds_list[ind+1]
        else:
            end_ind = len(md)
        sf = md[start_ind:end_ind]
        slice_nbr = np.array(sf.loc[(sf[sf.columns[1]]=='Slice')][sf.columns[2]])[0]
        cell_nbr = np.array(sf.loc[(sf[sf.columns[1]]=='Cell')][sf.columns[2]])[0]
        sample_id = "slice{:02d}cell{:02d}".format(slice_nbr, cell_nbr)
        current_sample_metadata = {}
        current_sample_metadata.update({'sample_id': 'sample-{}'.format(sample_id)})
        current_sample_metadata.update({'sample_type': 'in vitro differentiated cells'})
        current_sample_metadata.update({'participant_id': participants_metadata['participant_id'] })

        re_value = np.array(sf.loc[(sf[sf.columns[1]] == 'Re')][sf.columns[2]])[0]
        current_sample_metadata.update({'re_value': re_value})
        re_unit = np.array(sf.loc[(sf[sf.columns[1]] == 'Re')][sf.columns[3]])[0]
        current_sample_metadata.update({'re_unit': re_unit})
        # offset_value = np.array(sf.loc[(sf[sf.columns[1]] == 'Offset')][sf.columns[2]])[0]
        # current_sample_metadata.update({})
        # offset_unit = np.array(sf.loc[(sf[sf.columns[1]] == 'Offset')][sf.columns[3]])[0]
        # current_sample_metadata.update({})
        # rseal_value = np.array(sf.loc[(sf[sf.columns[1]] == 'Rseal')][sf.columns[2]])[0]
        # current_sample_metadata.update({})
        # rseal_unit = np.array(sf.loc[(sf[sf.columns[1]] == 'Rseal')][sf.columns[3]])[0]
        # current_sample_metadata.update({})
        # hc_value = np.array(sf.loc[(sf[sf.columns[1]] == 'hc')][sf.columns[2]])[0]
        # current_sample_metadata.update({})
        # hc_unit = np.array(sf.loc[(sf[sf.columns[1]] == 'hc')][sf.columns[3]])[0]
        # current_sample_metadata.update({})
        pipcap_valueunit = np.array(sf.loc[(sf[sf.columns[1]] == 'Pipette Capacitance')][sf.columns[3]])[0]
        current_sample_metadata.update({'pipette_capacitance': pipcap_valueunit})
        # vr_value = np.array(sf.loc[(sf[sf.columns[4]] == 'VR')][sf.columns[5]])[0]
        # current_sample_metadata.update({})
        # vr_unit = np.array(sf.loc[(sf[sf.columns[4]] == 'VR')][sf.columns[6]])[0]
        # current_sample_metadata.update({})
        # rm_value = np.array(sf.loc[(sf[sf.columns[4]] == 'Rm')][sf.columns[5]])[0]
        # current_sample_metadata.update({})
        # rm_unit = np.array(sf.loc[(sf[sf.columns[4]] == 'Rm')][sf.columns[6]])[0]
        # current_sample_metadata.update({})
        # hc70_value = np.array(sf.loc[(sf[sf.columns[4]] == 'hc at -70 mV')][sf.columns[5]])[0]
        # current_sample_metadata.update({})
        # hc70_unit = np.array(sf.loc[(sf[sf.columns[4]] == 'hc at -70 mV')][sf.columns[6]])[0]
        # current_sample_metadata.update({})
        # rs_value = np.array(sf.loc[(sf[sf.columns[4]] == 'Rs')][sf.columns[5]])
        # current_sample_metadata.update({})
        # rs_unit = np.array(sf.loc[(sf[sf.columns[4]] == 'Rs')][sf.columns[6]])
        # current_sample_metadata.update({})
        # cm_value = np.array(sf.loc[(sf[sf.columns[4]] == 'Cm')][sf.columns[5]])[0]
        # current_sample_metadata.update({})
        # cm_unit = np.array(sf.loc[(sf[sf.columns[4]] == 'Cm')][sf.columns[6]])[0]
        # current_sample_metadata.update({})

        c = np.array(sf)[:,3]
        t = c[np.where(c=='File')[0][0]+1:]
        # find strings in there... they correspond to the file names containing the ephys data for this sample/cell
        files_inds = np.where(np.array([type(t[i]) for i in range(len(t))])==str)[0]
        # extract all the filenames (all this to deal with the - indicating that several files
        filenames_list = []
        for f_ind in files_inds:
            file_string = t[f_ind]
            dash_ind = file_string.find('-')
            if dash_ind == -1:
                filenames_list.append(file_string)
            else:
                # compute length of what's after the dash in this string... this will give us the length of what
                # we should extract before the string!
                substring_length = len(file_string) - dash_ind - 1
                start_file_number = int(file_string[dash_ind-substring_length:dash_ind])
                end_file_number = int(file_string[dash_ind+1:dash_ind+1+substring_length])
                for nbr in range(start_file_number,end_file_number+1):
                    if substring_length == 3:
                        this_file_string = file_string[0:dash_ind-substring_length] + '{:03d}'.format(nbr)
                    elif substring_length == 2:
                        this_file_string = file_string[0:dash_ind-substring_length] + '{:02d}'.format(nbr)
                    elif substring_length == 1:
                        this_file_string = file_string[0:dash_ind-substring_length] + '{:1d}'.format(nbr)
                    filenames_list.append(this_file_string)
        current_sample_metadata.update({'data_files': filenames_list})
        all_filenames_list.extend(filenames_list)
        samples_metadata_list.append(current_sample_metadata)


    metadata.update({"participants_md":participants_metadata})
    metadata.update({"samples_md":samples_metadata_list})

    print(metadata)

    return metadata

def convert_patchclamp2bids(raw_data_dir, output_bids_dir):
    """
    Create a BIDS structure from a patchclamp dataset organized with the convention of NW. The raw_data_dir should
    contain a set of directories (one per day, with one animal used per day), each containing a set of data files in
    abf format (Axon binary format), and a subdirectory with an excel file containing all the corresponding metadata.
    Several slices are extracted and prepared per day. Each slice goes into the recording setup one at a time. One cell
    (sometimes two) is recorded for a time between 30s and 30mn; this is called a "recording". Most of the times, there
    are several recordings for each cell (one per "protocol", or "experimental condition"), performed sequentially in
    time. Then the electrode is changed to record another cell. Then, all this is performed on another slice.
    In the excel file, you see slice1cell1, with a description of the protocols/recordings; then slice1cell2, and etc.

    Parameters
    ----------
    raw_data_dir: str
        Path to the directory containing the raw data files
    output_bids_dir: str
        Path to the directory where the BIDS dataset will be created
    """

    recording_days_list = os.listdir(raw_data_dir)

    # select those recording days for which the excel file exists... those will give us the list of subjects, i.e of
    # animals because we have one animal per day
    sub_ids_list = []
    ses_ids_list = []
    metadata_file_list = []
    sub_ind = 0
    for current_day in recording_days_list:
        xls_file = os.path.join(raw_data_dir,current_day,current_day,'*.xls*')
        xls_list = glob.glob(xls_file)
        if len(xls_list) == 1:
            sub_ind += 1
            ses_ids_list.append(current_day)
            sub_ids_list.append(str(current_day))
            metadata_file_list.append(xls_list[0])
            print('The following recording date has been selected: ' + current_day)
        elif len(xls_list) == 0:
            print('No excel file for this recording date: ' + current_day + '. Skipping...')
        else:
            print('Several excel files for this recording date: ' + current_day + '. Skipping...')

    print(ses_ids_list)
    print(sub_ids_list)

    for current_ind in range(len(ses_ids_list)):
        sub_id, ses_id = sub_ids_list[current_ind], ses_ids_list[current_ind]
        session = BEP032PatchClampNWData(sub_id, ses_id)
        session.basedir = output_bids_dir
        # generate the BIDS directory structure
        session.generate_directory_structure()

        # identify the input ephys data files for this session, as the abf files available in the data directory
        data_path_filter = os.path.join(raw_data_dir,current_day,'*.abf')
        data_files = glob.glob(data_path_filter)
        print(len(data_files))

        # read excel metadata file
        metadata_struct = read_NW_metadata(metadata_file_list[current_ind])
        session.md = metadata_struct

        # loop over ephys data files!
        for current_data_file in data_files:
            run_id = os.path.splitext(os.path.split(current_data_file)[1])[0]
            session.register_data_files(current_data_file, run=run_id)
            # ST note: this seems WEIRD: files have been selected to have abf extension above, and the extension is
            # checked again in the call to register_data_files

        # before going further, we might need to handle / identify the date in the names of directory and files
        session.organize_data_files(mode='link')
        session.generate_all_metadata_files()
        #session.generate_all_metadata_files(metadata_file_list[current_ind], current_data_file)



    # df = extract_structure_from_csv(csv_file)
    #
    # df = df[ESSENTIAL_CSV_COLUMNS]
    # test_data_files = [Path('empty_ephy.nix')]
    # for f in test_data_files:
    #     f.touch()
    #
    # for session_kwargs in df.to_dict('index').values():
    #     session = BEP032TemplateData(**session_kwargs)
    #     session.basedir = pathToDir
    #     session.generate_structure()
    #     session.register_data_files(*test_data_files)
    #     session.organize_data_files(mode='copy')
    #     session.generate_all_metadata_files()
    #
    # # cleanup
    # for f in test_data_files:
    #     if f.exists():
    #         f.unlink()




def main():
    """

    Notes
    ----------

    Usage via command line: BEP032NWDataConverter.py [-h] raw_data_dir output_bids_dir
    Example: python ./BEP032NWDataConverter.py ~/amubox/ShareElec/nw_data/sourcedata/2016-03/ ~/tmp/tmp_ando_data/

    positional arguments:
        raw_data_dir:     Path to the directory containing the raw data files
        output_bids_dir:  Path to the directory where the BIDS dataset will be created

    optional arguments:
        -h, --help  show this help message and exit
    """

    parser = argparse.ArgumentParser()
    parser.add_argument('raw_data_dir', help='Path to your csv file')
    parser.add_argument('output_bids_dir', help='Path to your folder')

    # Create two argument groups

    args = parser.parse_args()

    # Check if directory exists
    if not os.path.isdir(args.raw_data_dir):
        print('Input directory does not exist:', args.raw_data_dir)
        exit(1)
    convert_patchclamp2bids(args.raw_data_dir, args.output_bids_dir)



if __name__ == '__main__':
    main()
