import os
import yaml
from BIDSTools.helper import load_yaml_file
from BIDSTools.resource_paths import PROJECT_CONFIG_DIR

class ProjectConfig:
    def __init__(self, config_file):
        self.config_file = os.path.join(PROJECT_CONFIG_DIR, config_file)
        self.global_config = load_yaml_file(self.config_file)
        self.config = self.global_config.get('fields', {})

    def get_config(self):
        return self.config

    def get_config_file(self):
        return self.config_file

    def get_project_name(self):
        return self.global_config.get('PROJECT_NAME', 'unknown')

    def get_project_modalities(self):
        modalities = self.global_config.get('modality', [])
        if isinstance(modalities, str):
            return [modalities]
        return modalities

    def get_segments_list(self):
        return self.config.get('segment_list', {}).get('value', [])

    def get_datafile_fields(self):
        return self.config.get('datafilepaths_list', {}).get('value', [])

    def is_session_required(self):
        return self.config.get('session_id', {}).get('required', False)

    def get_data_file_format(self):
        return self.config.get('output_filename_format', {}).get('default', 'Missig format')

    def get_custom_config(self):
        return self.config.get('custom_pattern',{}).get('pattern',"Missing pattern")

    def get_raw_data_path(self):

        return self.config.get('datafilepaths_list', {}).get('raw_data_path_pattern', '{chunk_key}_datafile_path')


    def get_data_type(self):
        data_types = self.global_config.get('data_types', [])
        if not data_types:
            raise ValueError("No data types defined in the project configuration.")
        if isinstance(data_types, str):
            return [data_types]
        return data_types


if __name__ == "__main__":
    pc = ProjectConfig("microscopy_confocal.yml")

    print("Nom du projet :", pc.get_project_name())
    print("Modalities :", pc.get_project_modalities())
    print("Chunks :", pc.get_chunks_list())
    print("Champs de fichiers de données :", pc.get_datafile_fields())
    print("Session requise :", pc.is_session_required())
    print("\n--- Infos par chunk ---")
    for chunk, path_field in zip(pc.get_chunks_list(), pc.get_datafile_fields()):
        print(f"Chunk: {chunk} -> Champ: {path_field}")
