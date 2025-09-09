# Spectroscopy Changelog

## Version 2.8
- Phasors analysis: add tau_n calculation and display
- Improve phasor centroid information display layout

## Version 2.7.2
- [LASERBLOOD] : Replace '745/90 ET Bandpass' Emission Filter with '775/140 BrightLine HC'

## Version 2.7.1
- [LASERBLOOD] : Update Laser Wavelenght -> Emission Filters (BROAD BANDPASS) map

## Version 2.7
- [LASERBLOOD] : Add Emission Filters (BROAD BANDPASS) to selectable metadata

## Version 2.6.2
- [LASERBLOOD] : Add unique "id" field to Laserblood metadata

## Version 2.6.1
- [LASERBLOOD] : Make PDAC/Healthy metadata field not mandatory

## Version 2.6
- [LASERBLOOD] : add Cuvette holder and Replicate to metadata

## Version 2.5
- [LASERBLOOD] : add id, timestamp, healthy/PDAC and weeks to metadata


## Version 2.4
- Fix phasors harmonics visualization when in free running mode
- Improve settings storage handling across software versions
- Fix parameters inconsistencies between Acquire and Read mode

## Version 2.3
- Make Read Data files controls more flexible

## Version 2.2
- Loading calibration reference: warning system improvements

## Version 2.1
- Fix Time Tagger Functionality
- Fix SBR calculation
- Improve Fitting user experience
- Improve Card Detection user experience

## Version 2.0
- Add automatic channels connections detection
- x-axis negative values ​​cut on exported spectroscopy plots (images/scripts)

## Version 1.9
- Add automatic card connection detection
- Fix Sync In laser frequency detection for low frequencies
- Improvements/simplification on exported data naming system

## Version 1.8
- Time Tagger feature (.bin export/reader script) added
- SBR (Signal-to-Background Ratio) value calculation added

## Version 1.7
- Improvements and fixes on Read Data mode

## Version 1.6
- Fixes on binned counts granularity

## Version 1.5
- Realtime improvements during Spectroscopy/Phasors acquisitions
- Improvements on the Fitting algorithm
- Last ROIs chosen during Fitting analysis are now saved in memory

## Version 1.4
- User can choose "Reader" mode to read external files for each tab (Spectroscopy/Phasors/Fitting)
- Improvements on Fitting functionality
- User can set a CPS threshold to highlight values ​​that exceed the limit
- User can view the acquisition time countdown
- Enhanced user-friendliness of bin file/scripts export

## Version 1.3
- Spectroscopy/Phasors/Fitting mode analysis
- More user friendly and customizable UI
- Download Python/Matlab scripts to reconstruct the acquisition
- User can specify a folder and filename for data export

## Version 1.0

- Added visual errors
- Simplified requirements for pyinstaller
- UI/UX improvements
- GUI parameterization
- Free running and Fixed acquisition mode choice
- Automatically set the correct firmware based on the connection channel selected (USB/SMA)
- Exported bin file size helper added
- Export data functionality added
