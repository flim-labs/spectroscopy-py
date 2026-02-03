<a name="readme-top"></a>

<div align="center">
  <h1>Spectroscopy Laserblood - Export Data </h1>
</div>
<div align="center">
  <a href="https://www.flimlabs.com/">
    <img src="../assets/images/shared/spectroscopy-logo.png" alt="Logo" width="120" height="120">
  </a>
</div>
<br>

<!-- TABLE OF CONTENTS -->
<details>
  <summary>Table of Contents</summary>
  <ol>
    <li>
      <a href="#introduction">Introduction</a>
    </li>
    <li><a href="#spectroscopy-file-format">Spectroscopy File Format</a></li>
     <li><a href="#phasors-file-format">Phasors File Format</a></li>
     <li><a href="#laserblood-metadata-file-format">Laserblood Metadata File Format</a></li>
    <li><a href="#data-visualization">Data Visualization</a>
    </li>
    </ul>
    </li>
    <li><a href="#useful-links">Useful links</a></li>
    <li><a href="#license">License</a></li>
    <li><a href="#contact">Contact</a></li>
  </ol>
</details>

## Introduction

<div align="center">
    <img src="../assets/images/spectroscopy-exported-data.png" alt="Spectroscopy Laserblood GUI" width="100%">
</div>

The [Spectroscopy Laserblood](https://github.com/flim-labs/spectroscopy-py/tree/laserblood) software allows seamless export of **decay curves** and **phasors** data to binary files, along with comprehensive **Laserblood metadata** for biomedical research applications. This guide provides an in-depth exploration of the **binary files structure** and **metadata format**, offering a comprehensive understanding of how exported data is formatted and can be leveraged for advanced analysis and clinical research within the [Laserblood EU project](https://www.laserblood.eu/) framework.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Spectroscopy File Format

Here a detailed explanation of the exported Spectroscopy binary data file structure:

##### Header (4 bytes):

The first 4 bytes of the file must be `SP01`. This serves as a validation check to ensure the correct format of the file. If the check fails, the script prints "Invalid data file" and exits.

##### Metadata Section (Variable length):

Following the header, metadata is stored in the file. This includes:

- `JSON length (4 bytes)`: An unsigned integer representing the length of the JSON metadata.
- `JSON metadata`: This is a variable-length string that contains information about the data, including _enabled channels_, _bin width_, _acquisition time_, _laser period_ and _tau ns_. This information is printed to the console.

##### Data Records (Variable length):

After the metadata, the script enters a loop to read and process data in chunks of variable length, depending on the number of active channels. Each chunk represents a data record containing:

- `Timestamp (8 bytes)`: A double representing the data acquisition time in seconds.
- `Channel Cumulated Curve Values (variable length)`: A variable number of unsigned integers (4 bytes each) representing cumulated decay curve for each active channel at the corresponding timestamp. For each active channel, **256 values are stored as 4-byte unsigned integers**.
The length of each data record is calculated as:

    - **8 bytes** for the timestamp.
    - **1024 bytes** for each active channel (256 values of 4 bytes each).

For example, if there are _3_ active channels, the total length of a data record will be `8 + 1024 * 3 = 3080 bytes`.

<p align="right">(<a href="#readme-top">back to top</a>)</p>



## Phasors File Format

Here a detailed explanation of the exported Phasors binary data file structure:

##### Header (4 bytes):

The first 4 bytes of the file must be `SPF1`. This serves as a validation check to ensure the correct format of the file. If the check fails, the script prints "Invalid phasors_data file" and exits.

##### Metadata Section (Variable length):

Following the header, metadata is stored in the file. This includes:

- `JSON length (4 bytes)`: An unsigned integer representing the length of the JSON metadata.
- `JSON metadata`: This is a variable-length string that contains information about the data, including _enabled channels_, _bin width_, _acquisition time_, _laser period_, _harmonics_ and _tau ns_. This information is printed to the console.

##### Data Records (Variable length):

After the metadata, the script enters a loop to read and process phasor data. Each data record contains:

- `Timestamp (8 bytes)`: An unsigned integer representing the timestamp of the data in nanoseconds.
- `Channel Index (4 bytes)`: A string representing the name of the channel index.
- `g (8 bytes)`:   A float representing the real part of the phasor (X axis).
- `s (8 bytes)`: A float representing the imaginary part of the phasor (Y axis).



<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Laserblood Metadata File Format

For acquisitions performed within the [Laserblood EU project](https://www.laserblood.eu/) framework, the software automatically exports comprehensive metadata files containing detailed experimental parameters essential for biomedical research and PDAC (Pancreatic Ductal Adenocarcinoma) detection studies.

##### Laserblood Metadata JSON Structure:

The metadata is exported as a **JSON file** with a structured format that includes:

##### File Naming Convention:

Laserblood metadata files follow a standardized naming pattern:
```
{timestamp}_{laser_type}_{filter_type}_{user_filename}_laserblood_metadata.json
```

Example: `20240906_143022_405nm_650-100_sample01_laserblood_metadata.json`

##### JSON Structure Overview:

The JSON file contains the following main sections:

- **Acquisition Information**: Timestamp, acquisition mode, bin width, acquisition time, and hardware configuration
- **Laser and Filter Configuration**: Wavelength specifications, laser power, repetition rate
- **Sample Identification**: Sample ID, PDAC/Healthy classification, experimental conditions
- **Nanoparticle Properties**: Type, concentration, volume specifications
- **Protein Corona Analysis**: Protein source details, incubation parameters, dilution factors
- **Measurement Setup**: Cuvette specifications, detector configuration, processing steps
- **Quality Metrics**: Average CPS, SBR values, pile-up thresholds
- **Custom Parameters**: User-defined experimental fields

##### Key Metadata Fields:

The metadata includes critical parameters such as:

- **Sample Classification**: `PDAC/Healthy` for medical research categorization
- **Nanoparticle Details**: Type, concentration (µg/µL), volume (ml)
- **Protein Source**: Human/murine plasma with volume and incubation percentage
- **Incubation Conditions**: Time (min), temperature (°C), type (static/dynamic)
- **Processing Steps**: Centrifuge, pellet, supernatant, washing cycles
- **Hardware Configuration**: FPGA firmware, detector type, laser specifications
- **Measurement Parameters**: Cuvette material, dimensions, laser power percentage

##### Data Validation and Quality Control:

The metadata system includes built-in validation to ensure:

- All required fields are properly completed before acquisition
- Consistent data formatting across experiments
- Traceability for clinical research requirements
- Integration with exported binary data files

This comprehensive metadata system supports the reproducibility requirements of the Laserblood consortium and facilitates advanced data analysis workflows for pancreatic cancer detection research.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Data Visualization

The script files are automatically downloaded along with the acquisition .bin file once the acquisition is complete and a file name has been chosen. Follow one of the guides below if you wish to use the Python or Matlab script:

- **Python script**:

  - Open the terminal and navigate to the directory where the saved files are located (it is advisable to save and group them in a folder):

    ```sh
    cd YOUR_DOWNLOADED_DATA_ROOT_FOLDER
    ```

  - Create a virtual environment using the command:
    ```sh
    python -m venv venv
    ```
  - Activate the virtual environment with the command:
    ```sh
    venv\Scripts\activate
    ```
  - Install the necessary dependencies listed in the automatically downloaded _requirements.txt_ with:
    ```sh
    pip install -r requirements.txt
    ```
  - Run your script with:
    ```sh
    python YOUR_SCRIPT_NAME.py
    ```
    <br>

- **Matlab script**:  
   Simply open your MATLAB command window prompt and, after navigating to the folder containing the script, type the name of the script to launch it.


## Useful Links

For more details about the project follow these links:

- [Spectroscopy Laserblood introduction](../index.md)
- [Spectroscopy Laserblood GUI guide](../v3.0/index.md)
- [Spectroscopy Laserblood Console guide ](./spectroscopy-console.md)

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## License

Distributed under the MIT License.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- CONTACT -->

## Contact

FLIM LABS: info@flimlabs.com

Project Link: [FLIM LABS - Spectroscopy Laserblood](https://github.com/flim-labs/spectroscopy-py/tree/laserblood)

<p align="right">(<a href="#readme-top">back to top</a>)</p>
