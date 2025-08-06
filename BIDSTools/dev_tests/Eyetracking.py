"""
Custom handler for Eyetracking projects.
Handles segment (run) extraction and file path formatting for BIDS conversion.
"""

import os
from BIDSTools.ProjectConfig import ProjectConfig
from BIDSTools.Experiment import Experiment
import shutil
class EyetrackingCustom:
    def __init__(self, project_config: ProjectConfig, experiment: Experiment, current_dir: str):
        self.project_config = project_config
        self.experiment = experiment
        self.current_dir = current_dir
        self.segment_list = self.project_config.get_segments_list()
        self.data_file_format = self.project_config.get_data_file_format()
        self.eyetracking_type = self.project_config.global_config.get('eyetracking_type', 'DEFAULT')
        self.custom_pattern = self.project_config.get_custom_config()

    def get_segment_details(self):
        segment_dict = {}
        experiment_dict = self.experiment.__dict__

        for segment_key in self.segment_list:
            run_data = {}
            # Find all fields in the experiment that start with this segment_key
            segment_fields = [
                field_name.replace(f"{segment_key}_", "")
                for field_name in experiment_dict
                if field_name.startswith(f"{segment_key}_")
            ]
            for field in segment_fields:
                target_field = self.custom_pattern.format(run_key=segment_key, field=field)
                value = getattr(self.experiment, target_field, None)
                run_data[field] = value




            run_data['run'] = segment_key
            raw_data_path_pattern = self.project_config.get_raw_data_path()
            run_data['raw_data_path'] = getattr(self.experiment, raw_data_path_pattern.format(run_key=segment_key), None)
            segment_dict[segment_key] = run_data
        return segment_dict

    def get_eyetracking_data_file_name_by_segment(self, segment: dict):
        segment_all_info = self.experiment.to_dict()
        for k, v in segment.items():
            segment_all_info[k] = v

        segment_key=segment.get("run")
        if segment_key:
            run_id_field = f"{segment_key}_id"
            run_id_value = getattr(self.experiment, run_id_field, None)
            if run_id_value:
                segment_all_info["run_id"] = run_id_value
        # Example: format the filename using the data_file_format and segment info

        return segment_all_info





    def get_run_data_path(self, segment: dict):

        chunk_info = self.get_eyetracking_data_file_name_by_segment(segment)

        chunk_info['final_path'] = self.data_file_format.format(**chunk_info)


        return chunk_info

    def write_run_info(self):
        run_details = self.get_segment_details()
        for chunk_key, chunk_info in run_details.items():
            chunk_info = self.get_run_data_path(chunk_info)
            # create empty file with final path
            with open(os.path.join(self.current_dir, chunk_info['final_path']), 'w') as f:
                f.write('')
            # copy raw data
            print(chunk_info)
            shutil.copyfile(chunk_info['raw_data_path'], os.path.join(self.current_dir, os.path.basename(chunk_info['raw_data_path'])))


# Example usage
if __name__ == "__main__":
    config_file = "../BIDS_PROJECT_CONFIG/eyetracking.yml"
    experiment = Experiment()
    experiment.participant_id = "001"  # Replace with ax
    experiment.session_id = "01"
    experiment.modality = "func"
    experiment.sample_id = "01"
    experiment.run01_id = "01"
    experiment.run01_datafile_path = "run01_datafile_path"
    experiment.run01_task = "eyetracking"
    project_config = ProjectConfig(config_file)
    custom_handler = EyetrackingCustom(project_config, experiment,
                                       "../BIDS_PROJECT_CONFIG/output")
    print(custom_handler.eyetracking_type)
    segment_details = custom_handler.get_segment_details()
    print(segment_details)
    custom_handler.write_run_info()