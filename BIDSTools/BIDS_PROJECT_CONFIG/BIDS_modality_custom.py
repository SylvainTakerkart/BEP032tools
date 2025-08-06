"""
bids_modality_custom.py
this file contain contain the common modlity custom part of bids project
and the customieation  part of each modlity
it is a factory for  creating custom modality classes which will process the data , with the good  format and
the good path ( here is the place for the conversion part)
the current directory is the directory where the BIDS output will be written
example:

  /sub-1/session-1/beh/  #  as current directory
        sub_1_session_1_beh_task-1-events.tsv   # as data file  writin in the current directory
        sub_1_session_1_beh_task-1-eyetracking.tsv # as data file  writin in the current directory




"""
from BIDSTools.ProjectConfig import ProjectConfig
from BIDSTools.Experiment import Experiment
import os
import shutil
from BIDSTools.convertfileformat import ConvertedfSData
from BIDSTools.log import  log
class BIDSCommonModality:
    def __init__(self, project_config, experiment, current_dir,converter = None):
        """
        Initialize the BIDSCommonModality class with project configuration, experiment details, and directory path.

        Parameters
        ----------
        project_config : ProjectConfig
            An instance of the ProjectConfig class containing project-specific configurations.
        experiment : Experiment
            An instance of the Experiment class containing details of the current experiment.
        current_dir : str
            Path to the current working directory where files will be processed and stored.
        converter : optional
            An optional converter object for handling data format conversions.

        Attributes
        ----------
        segment_type : str
            The type of segment (e.g., 'run', 'chunk') as defined in the project configuration.
        segment_id_attr : str
            The attribute name for segment IDs, formatted based on segment type.
        data_type : str
            The data type as specified in the project configuration.
        segment_list : list
            A list of segments obtained from the project configuration.
        data_file_format : str
            The file format pattern for data files as defined in the project configuration.
        custom_pattern : str
            The custom configuration pattern for segments.
        segment_dict : dict
            A dictionary to store segment details.
        converter : optional
            An optional converter object for handling data format conversions.
        """
        self.project_config = project_config
        self.experiment = experiment
        self.current_dir = current_dir
        self.segment_type = self.project_config.get_segement_value()  # e.g., 'run', 'chunk', etc.
        self.segment_id_attr = self.project_config.config.get('segment_id', f"{self.segment_type}_id").format(segment=self.segment_type)
        self.data_type =self.project_config.get_data_type()
        self.segment_list = self.project_config.get_segments_list()
        self.data_file_format = self.project_config.get_data_file_format()
        self.custom_pattern = self.project_config.get_custom_config()
        self.segment_dict = {}
        self.converter = converter

    def get_segment_details(self):
        segment_dict = {}
        experiment_dict = self.experiment.to_dict()

        for segment_key in self.segment_list:
            segment_data = {}


            # Find all fields in the experiment that start with this segment_key
            segment_fields = [
                field_name.replace(f"{segment_key}_", "")
                for field_name in experiment_dict
                if field_name.startswith(f"{segment_key}_")
            ]
            print(segment_fields)
            for field in segment_fields:

                pattern = self.custom_pattern.format(
                    **{f"{self.segment_type}_key": segment_key, "field": field, "segment_key": segment_key}
                )
                value = getattr(self.experiment, pattern, None)
                segment_data[field] = value

            segment_data[self.segment_type] = segment_key

            raw_data_path_pattern = self.project_config.get_raw_data_path()

            print("format dict:", {f"{self.segment_type}_key": segment_key,
                                   "segment_key": segment_key})
            segment_data['raw_data_path'] = getattr(
                self.experiment,
                raw_data_path_pattern.format(**{f"{self.segment_type}_key": segment_key, "segment_key": segment_key}),
                None
            )
            print(segment_data)
            # Add segment_id if available
            if 'id' in segment_data:
                segment_data[self.segment_id_attr] = segment_data['id']
                segment_data['segment_id'] = segment_data['id']
            else:
                raise ValueError(f"Segment ID not found for {segment_key}")



            segment_dict[segment_key] = segment_data
            self.segment_dict = segment_dict
        return segment_dict

    def get_segment_data_path(self, segment):
        # Add any extra info from experiment or segment


        """
        Formats the data path for a given segment based on the BIDS configuration.

        Parameters
        ----------
        segment : dict
            A dictionary containing information about the segment.

        Returns
        -------
        segment : dict
            The input dictionary with an additional 'final_path' key containing the formatted data path.
        """

        segment_info = self.experiment.to_dict()
        segment_info.update(segment)

        segment_info['modality'] = self.project_config.global_config.get('modality', 'unknown')

        segment['final_path'] = self.data_file_format.format(**segment_info)

        return segment

    def write_segment_info(self):
        """
        Write BIDS segment information files for the experiment.

        Copies raw data for each segment to the correct location if available.
        Creates a converter for each segment if available and calls its convert_bids_data method.
        """
        details = self.get_segment_details()
        for segment_key, segment_info in details.items():
            segment_info = self.get_segment_data_path(segment_info)
            # create empty file with final path
            os.makedirs(self.current_dir, exist_ok=True)
           # with open(os.path.join(self.current_dir, segment_info['final_path']), 'w') as f:
            #    f.write('')
            # copy raw data if available to  destination path with the correct name

            if segment_info.get('raw_data_path'):
                # this will copy the raw data to the current directory
                shutil.copyfile(
                    segment_info['raw_data_path'],
                    os.path.join(self.current_dir, os.path.basename(segment_info['final_path'])),
                )
                final_raw_data_path = os.path.join(self.current_dir, os.path.basename(segment_info['final_path']))
                segment_info['final_raw_data_path'] = final_raw_data_path
                # creat the specific converter with segment info
                self.create_converter(segment_info)
                if self.converter is None:

                    log.info(f"Modality {self.project_config.global_config.get('modality')} has no converter")


                else:



                    # make the conversion if the converter is  available

                    self.converter.convert_bids_data()






    def create_converter(self, segment_info):
        """
        Creates a converter for the given segment_info.

        Parameters
        ----------
        segment_info : dict
            A dictionary containing information about the segment.

        Notes
        -----
        The converter is determined by the file extension of the raw data path in the segment info.
        Currently, only .edf files are supported and use the `ConvertedfSData` converter.
        """
        raw_data_path = segment_info['raw_data_path']
        all_info = self.experiment.to_dict()
        all_info.update(segment_info)
        temps_exp=Experiment(**all_info)
        ext = os.path.splitext(raw_data_path)[1]
        final_raw_data_path = segment_info['final_raw_data_path']





        if ext=='.edf':
           self.converter = ConvertedfSData(final_raw_data_path, None, self.current_dir, temps_exp)


        else:
            log.info(f"Unknown file format: {ext}")










class MicroscopyCustom(BIDSCommonModality):
    def __init__(self, project_config, experiment, current_dir):
        """
        Initialize the MicroscopyCustom class.

        Parameters
        ----------
        project_config : ProjectConfig
            The project configuration object.
        experiment : Experiment
            The experiment object.
        current_dir : str
            The directory where the BIDS output will be written.

        Notes
        -----
        This class is a customization of the BIDSCommonModality class for Microscopy projects.
        It sets the microscope_type attribute of the experiment to the value in the project config.
        """
        super().__init__(project_config, experiment, current_dir)
        self.microscopy_type =self.project_config.global_config.get('microscope_type', 'CONF')
        experiment.microscope_type = self.microscopy_type


class EyetrackingCustom(BIDSCommonModality):
    def __init__(self, project_config, experiment, current_dir):
        """
        Initialize the EyetrackingCustom class.

        Parameters
        ----------
        project_config : ProjectConfig
            The project configuration object.
        experiment : Experiment
            The experiment object.
        current_dir : str
            The directory where the BIDS output will be written.

        Notes
        -----
        This class is a customization of the BIDSCommonModality class for Eyetracking projects.
        """
        super().__init__(project_config, experiment, current_dir)
        super().__init__(project_config, experiment, current_dir)




class ModalityCustomBuilder:
    def __init__(self, project_config, experiment, current_dir):
        """
        Initialize the ModalityCustomBuilder class.

        Parameters
        ----------
        project_config : ProjectConfig
            The project configuration object.
        experiment : Experiment
            The experiment object.
        current_dir : str
            The directory where the BIDS output will be written.

        Notes
        -----
        This class is a factory for creating custom modality classes based on the project configuration.
        It creates an instance of either the MicroscopyCustom or EyetrackingCustom class depending on the project name.
        """
        if project_config.get_project_name() == 'microscopy_confocal':
            self.custom = MicroscopyCustom(project_config, experiment, current_dir)
        elif project_config.get_project_name() == 'eyetracking':
            self.custom = EyetrackingCustom(project_config, experiment, current_dir)
        else:
            raise ValueError(f"Unknown project config: {project_config.get_project_name()} perhaps check your config file?")

    def build_customizations(self):
        self.custom.write_segment_info()
        return self.custom



if __name__ == "__main__":
    from BIDSTools.ProjectConfig import ProjectConfig
    from BIDSTools.Experiment import Experiment

    # Example: Load config and create a mock experiment
    config_file = "/home/INT/idrissou.f/PycharmProjects/BEP032tools/BIDSTools/BIDS_PROJECT_CONFIG/microscopy_confocal.yml"
    config_file2 = "/home/INT/idrissou.f/PycharmProjects/BEP032tools/BIDSTools/BIDS_PROJECT_CONFIG/eyetracking.yml"
    project_config = ProjectConfig(config_file)
    project_config2 = ProjectConfig(config_file2)

    # Mock experiment with fields for 2 segments
    experiment = Experiment(
        participant_id="001",
        session_id="01",
        modality="eyetracking",
        task="test",
        sample_id="01",
        imageo01_datafile_path="/home/INT/idrissou.f/PycharmProjects/BEP032tools/BIDSTools/data/im0.czi",
        image01_id="01",
        image01_datafile_path="/home/INT/idrissou.f/PycharmProjects/BEP032tools/BIDSTools/data/im0.czi",
        image02_id="02"

    )
    experiment2 = Experiment(
        participant_id="01",
        session_id="01",
        task="test",
        modality="eyetracking",
        run01_datafile_path="/home/INT/idrissou.f/PycharmProjects/BEP032tools/BIDSTools/data/im0.czi",
        run01_id="01",
        run02_datafile_path="/home/INT/idrissou.f/PycharmProjects/BEP032tools/BIDSTools/data/im0.czi",
        run02_id="02",
        run03_datafile_path="/home/INT/idrissou.f/PycharmProjects/BEP032tools/BIDSTools/data/im0.czi",
        run03_id="03"
    )
    output_dir = "./output"


    # use  common parent class
    #handler = BIDSCommonModality(project_config, experiment, output_dir)
    #handler = BIDSCommonModality(project_config2, experiment2, output_dir)
    # use custom classes
    handler= MicroscopyCustom(project_config, experiment, output_dir)
    #handler= EyetrackingCustom(project_config2, experiment2, output_dir)

    handler.write_segment_info()