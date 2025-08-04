
import sys
import argparse
from BIDSTools.BidsDatasetBuilder import main

def cli():
    parser = argparse.ArgumentParser(
        description="Generate a BIDS dataset using Elab configuration and metadata files.",
        epilog="""
Example:
  build-bids -f elab_config.json -m metadata.CSV -o output/ -t v1 -p project_config.yml
"""
    )
    parser.add_argument("-f", "--config-file", required=True, help="Path to the Elab configuration JSON file.")
    parser.add_argument("-m", "--metadata-file", required=True, help="Path to the metadata file to be processed.")
    parser.add_argument("-o", "--output-dir", required=True, help="Output directory for BIDS dataset.")
    parser.add_argument("-t", "--tag", required=True, help="Tag for the output dataset.")
    parser.add_argument("-p", "--project-config", required=True, help="Project YAML config file.")


    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args()

    main(args.config_file, args.metadata_file, args.output_dir, args.tag, args.project_config)

if __name__ == '__main__':
    cli()
