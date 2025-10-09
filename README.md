# TFDD Events Database 

This project is a continuation of work originally developed in the Geography repository.

Results will be downloaded by running a streamlit app (app.py) in the terminal

The structure of this repository is as follows:
- app.py - this is the main file that will be run in terminal
- utils.py - the full process lives here
- data folder
- * downloads folder - contains downloaded results for each basin code
- geography subfolder
- * search_terms.xlsx - file with the search terms the script will use on Nexis Uni site
- * classes folder - the main script will use the Python classes in this folder for different behavior, including logging in to Nexis Uni (LoginClass.py), the search process (SearchClass.py), downloading (DownloadClass.py), as well as file format conversions needed in the process

## Prerequisites
Setup documentation in Box
requirements.txt contains the packages and libraries needed to run the script

## Installation and Running
How to download https://oregonstate.box.com/s/dzdijzw7glxo63niarajqg0adhw4ur7p

## Contributors
- Selena Wallace - primary development and maintenance
- Peter Nadel - Streamlit app integration, webdriver implementation (utils.py and LoginClass.py), requirements management, and OOP architecture guidance

## Acknowledgments
This project is an automated version of a data collection process developed by the Shared Waters Lab partnership between Oregon State University, Tufts University, and IHE Delft.
This project builds on an initial implementation by David Vasquez. 
The codebase was substantially redesigned and refactored in 2023-2024.