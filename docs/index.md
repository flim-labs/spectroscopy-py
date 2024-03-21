<!-- TABLE OF CONTENTS -->
<details>
  <summary>Table of Contents</summary>
  <ol>
    <li>
      <a href="#about-the-project">About The Project</a>
      <ul>
        <li><a href="#built-with">Built With</a></li>
      </ul>
    </li>
    <li>
      <a href="#getting-started">Getting Started</a>
      <ul>
        <li><a href="#prerequisites">Prerequisites</a></li>
        <li><a href="#installation">Installation</a></li>
      </ul>
    </li>
    <li><a href="#usage-guides">Usage Guides</a></li>
    <li><a href="#license">License</a></li>
    <li><a href="#contact">Contact</a></li>
  </ol>
</details>

# About the project

[![Spectroscopy GUI Overview](./docs/assets/images/screenshots/spectroscopy_gui_thumbnail.png)](https://www.youtube.com/watch?v=eHLvt_NrZAE)

Welcome to [FLIM LABS Spectroscopy](https://github.com/flim-labs/spectroscopy-py), a Python application designed to **analyze the fluorescence intensity decay as a function of time** and plotting a decay profile histogram. Facilitated by an underlying data processor developed in Rust, responsible for data retrieval from the hardware component, this application enables real-time data analysis and visualization. Whether your focus is on rigorous data analysis or dynamic visualizations, Spectroscopy serves as a flexible tool for the precise measurement and exploration of fluorescence intensity decay profile.

### Built With

|                                                                      |                                                          |
| -------------------------------------------------------------------- | -------------------------------------------------------- |
| [Python](https://www.python.org/)                                    | [click](https://pypi.org/project/click/)                 |
| [colorama](https://pypi.org/project/colorama/)                       | [contourpy](https://pypi.org/project/contourpy/)         |
| [cycler](https://pypi.org/project/cycler/)                           | [fonttools](https://pypi.org/project/fonttools/)         |
| [importlib-resources](https://pypi.org/project/importlib-resources/) | [Jinja2](https://pypi.org/project/Jinja2/)               |
| [kiwisolver](https://pypi.org/project/kiwisolver/)                   | [MarkupSafe](https://pypi.org/project/MarkupSafe/)       |
| [matplotlib](https://pypi.org/project/matplotlib/)                   | [mpld3](https://pypi.org/project/mpld3/)                 |
| [numpy](https://pypi.org/project/numpy/)                             | [packaging](https://pypi.org/project/packaging/)         |
| [pillow](https://pypi.org/project/pillow/)                           | [pyparsing](https://pypi.org/project/pyparsing/)         |
| [PyQt6](https://pypi.org/project/PyQt6/)                             | [pyqt6-plugins](https://pypi.org/project/pyqt6-plugins/) |
| [PyQt6-Qt6](https://pypi.org/project/PyQt6-Qt6/)                     | [PyQt6-sip](https://pypi.org/project/PyQt6-sip/)         |
| [pyqt6-tools](https://pypi.org/project/pyqt6-tools/)                 | [pyqtgraph](https://pypi.org/project/pyqtgraph/)         |
| [python-dateutil](https://pypi.org/project/python-dateutil/)         | [python-dotenv](https://pypi.org/project/python-dotenv/) |
| [qt6-applications](https://pypi.org/project/qt6-applications/)       | [qt6-tools](https://pypi.org/project/qt6-tools/)         |
| [six](https://pypi.org/project/six/)                                 | [zipp](https://pypi.org/project/zipp/)                   |
| [flim-labs](https://pypi.org/project/flim-labs/)                     |

<!-- GETTING STARTED -->

## Getting Started

To directly test the application, skipping the prerequisites and installation requirements you can download an installer at this [link](https://github.com/flim-labs/spectroscopy-py/releases/tag/v1.0) (_Note: you still need to have the FLIM LABS acquisition card_).

To get a local copy up and running follow these steps.

### Prerequisites

To be able to run this project locally on your machine you need to satisfy these requirements:

- Windows OS (>= Windows 10)
- 4GB RAM
- Multicore CPU
- Possess a [FLIM LABS acquisition card](https://www.flimlabs.com/products/data-acquisition-card/) to be able to acquire your data
- FLIM LABS Data Acquisition Card drivers installed [(download here)](https://flim-labs.github.io/flim-labs-drivers/data-acquisition-card-drivers/)
- Python version <= 3.9

### Installation

1. Clone the repo
   ```sh
   git clone https://github.com/flim-labs/spectroscopy-py
   ```
2. Set the virtual environment in the root folder
   ```sh
   python -m venv venv
   ```
3. Activate the virtual environment:
   ```sh
   venv\Scripts\activate
   ```
4. Install the dependencies
   ```sh
   pip install -r requirements.txt
   ```
5. Run the project with GUI mode
   ```sh
   python spectroscopy.py
   ```

## Usage Guides

Navigate to the following links to view detailed application usage guides:

- [Spectroscopy GUI guide](./v1.0/index.md)
- [Spectroscopy Console guide](./python-flim-labs/spectroscopy-console.md)

## Contact

FLIM LABS: info@flimlabs.com

Project Link: [FLIM LABS - Spectroscopy](https://github.com/flim-labs/spectroscopy-py)

<p align="right">(<a href="#readme-top">back to top</a>)</p>
