# Marine Data Statistics

A Streamlit app for importing water-level, current, and wave observations from
CSV or XLSX files, summarizing the primary measurement, and plotting its time
series.

## Run locally

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

In the sidebar, upload a file, choose its worksheet (for XLSX), select the data
type, enter a location name, and map each field to its Excel-style column
letter. The first row is treated as column headers by default; turn that option
off for headerless files.

The app reports the maximum, average, and minimum of water level, current speed,
or wave height, displayed to two decimal places. Units are water level and wave
height in metres, current speed in metres per second, wave period in seconds,
and directions in degrees. Maximum and minimum rows include their associated
measurements and original data-row timestep. For currents, Data 2 and Data 3
are east-west (X) and north-south (Y) vector components; the app derives the
towards bearing and omits the components from the result data. Wave directions
are interpreted as coming-from bearings. For waves, the app adds 8-sector
monthly direction and height distributions plus a wave-height/period occurrence
diagram with 0.5 m and 1 s bins. Timesteps start at 1 for the first row after
the header. Rows without a valid date or primary measurement are excluded.
Results can be downloaded as an Excel workbook or CSV, with the location name
included.