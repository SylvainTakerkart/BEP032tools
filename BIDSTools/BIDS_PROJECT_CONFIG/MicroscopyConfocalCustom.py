"""
This file shows the customization for a MicroscopyConfocal project.
For example: each experiment may have multiple chunks, so we define each chunk and its path.
"""
import os
import shutil
from BIDSTools.ProjectConfig import ProjectConfig
from BIDSTools.Experiment import Experiment

class MicroscopyConfocalCustom:
    def __init__(self, project_config: ProjectConfig, experiment: Experiment, curren_dir: str):
        self.project_config = project_config
        self.experiment = experiment
        self.current_dir = curren_dir
        self.chunk_list = self.project_config.get_segments_list()
        self.data_file_format = self.project_config.get_data_file_format()
        self.microscopy_type =self.project_config.global_config.get('microscopy_type', 'CONF')


        self.custom_pattern = self.project_config.get_custom_config()
    def get_chunk_details(self):
        chunk_dict = {}
        experiment_dict = self.experiment.__dict__

        for chunk_key in self.chunk_list:
            chunk_data = {}

            # Find all fields in the experiment that start with this chunk_key
            # Example: if chunk_key is "image01", we look for "image01_filename", etc.
            chunk_fields = [
                field_name.replace(f"{chunk_key}_", "")
                for field_name in experiment_dict
                if field_name.startswith(f"{chunk_key}_")
            ]
            print(chunk_fields)
            print(self.custom_pattern)
            for field in chunk_fields:
                # Build the full attribute name using the pattern
                print(chunk_key, field)
                target_field = self.custom_pattern.format(chunk_key=chunk_key, field=field)
                value = getattr(self.experiment, target_field, None)
                chunk_data[field] = value

            chunk_data['chunk'] = chunk_key
            raw_data_path_pater = self.project_config.get_raw_data_path()
            chunk_data['raw_data_path'] = getattr(self.experiment, raw_data_path_pater.format(chunk_key=chunk_key), None)

            # Format the output file path using the available fields


            chunk_dict[chunk_key] = chunk_data

        return chunk_dict

    def get_confocal_data_file_name_by_chunck(self, chunk: dict):
        chunk_all_info = self.experiment.to_dict()
        for k, v in chunk.items():
            chunk_all_info[k] = v

        chunk_key = chunk.get("chunk")
        if chunk_key:
            chunk_id_field = f"{chunk_key}_chunk_id"
            chunk_id_value = getattr(self.experiment, chunk_id_field, None)
            if chunk_id_value:
                chunk_all_info["chunk_id"] = chunk_id_value
        chunk_all_info["microscope_type"] = self.microscopy_type
        return chunk_all_info

    def get_chunk_data_path(self, chunk: dict):

        chunk_info = self.get_confocal_data_file_name_by_chunck(chunk)
        chunk_info['final_path'] = self.data_file_format.format(**chunk_info)
        return chunk_info



    def write_chunk_info(self):
        chun_details = self.get_chunk_details()
        for chunk_key, chunk_info in chun_details.items():
            chunk_info = self.get_chunk_data_path(chunk_info)
            # create empty file with final path
            with open(os.path.join(self.current_dir, chunk_info['final_path']), 'w') as f:
                f.write('')
            # copy raw data
            shutil.copyfile(chunk_info['raw_data_path'], os.path.join(self.current_dir, os.path.basename(chunk_info['raw_data_path'])))
            print(chunk_info)



    def build_customization(self, list_experiments_already_processed):
        self.write_chunk_info()

        self.get_chunk_details()
        list_experiments_already_processed.append(self.experiment)






def main():
    from BIDSTools.ProjectConfig import ProjectConfig
    from BIDSTools.Experiment import Experiment

    # Simulate an experiment with attributes dynamically assigned
    experiment = Experiment()
    experiment.participant_id = "001"
    experiment.session_id = "01"
    experiment.modality = "anat"
    experiment.sample_id = "01"
    experiment.image01_datafile_path  = "image01_img.tif"
    experiment.image01_chunk_id = "01"
    experiment.image02_filename = "image02_img02.tif"
    experiment.image02_datafile_path = "image02_img02.tif"
    experiment.image02_meta = "image02_meta02.json"
    experiment.image03_filename = "image03_img03.tif"
    experiment.image03_meta = "image03_meta03.json"
    experiment.image04_data_path = "image04_img04.tif"
    experiment.image03_datafile_path = "image03_datafile_path"

    # Load project configuration
    config_file = "microscopy_confocal.yml"  # Make sure this file exists in PROJECT_CONFIG_DIR
    project_config = ProjectConfig(config_file)

    # Create an instance of the custom handler
    custom_handler = MicroscopyConfocalCustom(project_config, experiment, "./output")

    # Get chunk details
    chunk_details = custom_handler.get_chunk_details()

    # Display results
    print("📦 Chunk Details:")
    from pprint import pprint
    pprint(chunk_details)

    current_dir = "./output/sub-01/ses-01/micr/"
    os.makedirs(current_dir, exist_ok=True)
    custom_handler.write_chunk_info()

if __name__ == "__main__":
    main()
