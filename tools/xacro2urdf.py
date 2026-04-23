#!/usr/bin/env python3

import os
import sys
import argparse

try:
    import xacro
except ModuleNotFoundError:
    print("Error: 'xacro' Python package not found.", file=sys.stderr)
    print("Please install it using: pip install xacro", file=sys.stderr)
    sys.exit(1)

def convert_xacro_to_urdf(xacro_file, urdf_file):
    """
    Converts a .xacro file to a .urdf file using the xacro Python package.
    """
    print(f"Converting {xacro_file} to {urdf_file}...")
    try:
        # Process the xacro file
        doc = xacro.process_file(xacro_file)
        
        # Get the XML string
        urdf_content = doc.toxml()
        
        # Write to the output file
        with open(urdf_file, 'w') as f:
            f.write(urdf_content)
            
        print(f"Successfully converted {xacro_file} to {urdf_file}")
        return True

    except Exception as e:
        print(f"Error during xacro conversion: {e}", file=sys.stderr)
        return False

def main():
    parser = argparse.ArgumentParser(description="Convert a .xacro file to a .urdf file.")
    parser.add_argument("input", help="Path to the input .xacro file (or a .urdf file containing xacro).")
    parser.add_argument("-o", "--output", help="Path to the output .urdf file. If not provided, it will be the same as the input with a .urdf extension.")

    args = parser.parse_args()

    input_file = args.input
    if not os.path.exists(input_file):
        print(f"Error: Input file not found at {input_file}", file=sys.stderr)
        sys.exit(1)

    output_file = args.output
    if not output_file:
        # If no output file is specified, create it in the same directory as the input.
        base_name = os.path.splitext(input_file)[0]
        output_file = base_name + ".urdf"

    # Ensure the output directory exists.
    output_dir = os.path.dirname(output_file)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    if not convert_xacro_to_urdf(input_file, output_file):
        sys.exit(1)

if __name__ == "__main__":
    main()
