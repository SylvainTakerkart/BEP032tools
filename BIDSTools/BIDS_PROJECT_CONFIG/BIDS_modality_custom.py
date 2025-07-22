"""
bids_common_modality.py

A generic handler for BIDS modalities (eyetracking, microscopy, etc.) using the segment abstraction.
Compatible with unified YAML configs using the 'segment' and 'segment_id' fields.
"""
from BIDSTools.ProjectConfig import ProjectConfig
from BIDSTools.Experiment import Experiment
import os
import shutil
from BIDSTools.convertfileformat import ConvertedfSData
from BIDSTools.log import  log
class BIDSCommonModality:
    def __init__(self, project_config, experiment, current_dir,converter = None):
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
        segment_info = self.experiment.to_dict()
        segment_info.update(segment)

        segment_info['modality'] = self.project_config.global_config.get('modality', 'unknown')

        segment['final_path'] = self.data_file_format.format(**segment_info)

        return segment

    def write_segment_info(self):
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
        super().__init__(project_config, experiment, current_dir)
        self.microscopy_type =self.project_config.global_config.get('microscope_type', 'CONF')
        experiment.microscope_type = self.microscopy_type


class EyetrackingCustom(BIDSCommonModality):
    def __init__(self, project_config, experiment, current_dir):
        super().__init__(project_config, experiment, current_dir)




class ModalityCustomBuilder:
    def __init__(self, project_config, experiment, current_dir):
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